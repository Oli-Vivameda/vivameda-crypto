"""Read-only, background developer-event checks. No private keys or trade execution.

History/funding analysis belongs to the hourly research task. This add-on checks
mint authorities for every Solana watch and explicitly verified accounts only.
Missing account coverage never implies a clean developer audit.
"""
import base64
import concurrent.futures
import datetime
import hashlib
import json
import struct
import time
import urllib.request
import urllib.error
from pathlib import Path

STREAM_PROGRAM = 'strmRqUCoQUgGUan5YhzUZa6KqdzwX5L6FpUxfmKg5m'
TOKEN_PROGRAMS = {'TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA',
                  'TokenzQdBNbLqP5VEhdkAS6EPFLC1PHnBqCXEpPxuEb'}
RPC = 'https://api.mainnet-beta.solana.com'


def b58(data):
    chars = '123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz'
    n, out = int.from_bytes(data, 'big'), ''
    while n:
        n, r = divmod(n, 58)
        out = chars[r] + out
    return '1' * (len(data) - len(data.lstrip(b'\0'))) + out


def decode_stream(account, expected):
    if not account or account['owner'] != STREAM_PROGRAM:
        raise ValueError('unverified Streamflow owner')
    raw = base64.b64decode(account['data'][0], validate=True)
    if len(raw) < 625 or int.from_bytes(raw[:8], 'little') != 4 or raw[8] != 4:
        raise ValueError('unsupported Streamflow layout')
    # Official streamflow-finance/js-sdk packages/stream/solana/layout.ts.
    out, offset = {}, 9
    fields = [(x, 8) for x in ['created_at', 'withdrawn_amount', 'canceled_at', 'end_time', 'last_withdrawn_at']]
    fields += [(x, 32) for x in ['sender', 'sender_tokens', 'recipient', 'recipient_tokens', 'mint', 'escrow_tokens', 'treasury', 'treasury_tokens']]
    fields += [('streamflow_fee_total', 8), ('streamflow_fee_withdrawn', 8), ('streamflow_fee_percent', 4), ('partner', 32), ('partner_tokens', 32), ('partner_fee_total', 8), ('partner_fee_withdrawn', 8), ('partner_fee_percent', 4)]
    fields += [(x, 8) for x in ['start_time', 'net_amount_deposited', 'period', 'amount_per_period', 'cliff', 'cliff_amount']]
    fields += [(x, 1) for x in ['cancelable_by_sender', 'cancelable_by_recipient', 'automatic_withdrawal', 'transferable_by_sender', 'transferable_by_recipient', 'can_topup']]
    fields += [('name', 64), ('withdraw_frequency', 8), ('ghost', 4), ('pausable', 1), ('can_update_rate', 1)]
    for key, size in fields:
        value = raw[offset:offset + size]
        offset += size
        if len(value) != size:
            raise ValueError('truncated stream')
        out[key] = (b58(value) if size == 32 else value.rstrip(b'\0').decode(errors='replace') if size == 64
                    else struct.unpack('<f', value)[0] if key.endswith('_percent') else int.from_bytes(value, 'little'))
    for key in ('mint', 'sender', 'recipient', 'escrow_tokens'):
        if out[key] != expected[key]:
            raise ValueError('stream identity mismatch: ' + key)
    return out


def parsed_info(account, kind):
    if not account or account['owner'] not in TOKEN_PROGRAMS:
        raise ValueError('missing or unverified token account')
    parsed = account['data']['parsed']
    if parsed['type'] != kind:
        raise ValueError('unexpected token account type')
    return parsed['info']


def fetch_snapshot(tokens, registry):
    keys = []
    for token in tokens:
        mint = token['contract']
        keys.append(mint)
        for entry in registry.get(mint, {}).get('accounts', []):
            keys.append(entry['address'])
        for entry in registry.get(mint, {}).get('streams', []):
            keys.append(entry['address'])
    keys = list(dict.fromkeys(keys))
    if len(keys) > 100:
        raise ValueError('RPC account batch exceeds 100; split before expanding registry')
    payload = {'jsonrpc': '2.0', 'id': 1, 'method': 'getMultipleAccounts',
               'params': [keys, {'encoding': 'jsonParsed', 'commitment': 'finalized'}]}
    request = urllib.request.Request(RPC, json.dumps(payload).encode(), {'Content-Type': 'application/json'})
    with urllib.request.urlopen(request, timeout=15) as response:
        result = json.load(response)
    if 'error' in result:
        raise ValueError('RPC returned an error')
    result = result['result']
    if len(result['value']) != len(keys):
        raise ValueError('incomplete RPC batch')
    accounts = dict(zip(keys, result['value']))
    observations = {}
    for token in tokens:
        mint = token['contract']
        try:
            info = parsed_info(accounts[mint], 'mint')
            spec = registry.get(mint, {})
            row = {'ts': time.time(), 'slot': result['context']['slot'], 'supply_raw': int(info['supply']),
                   'decimals': int(info['decimals']), 'mint_authority': info.get('mintAuthority'),
                   'freeze_authority': info.get('freezeAuthority'), 'accounts': {}, 'streams': {},
                   'coverage': 'PARTIAL_VERIFIED_ACCOUNTS' if spec.get('accounts') else 'MINT_ONLY_CREATOR_UNVERIFIED'}
            for entry in spec.get('accounts', []):
                value = parsed_info(accounts[entry['address']], 'account')
                if value['mint'] != mint or value['owner'] != entry['owner']:
                    raise ValueError('watched token account identity mismatch')
                row['accounts'][entry['address']] = int(value['tokenAmount']['amount'])
            for entry in spec.get('streams', []):
                row['streams'][entry['address']] = decode_stream(accounts[entry['address']], entry)
            observations[mint] = row
        except (ValueError, TypeError, KeyError):
            observations[mint] = {'error': 'ACCOUNT_IDENTITY_OR_SCHEMA_UNVERIFIED'}
    return observations


def changes(previous, current, now):
    """Return event key and factual text; never infer sales from balance changes."""
    events = []
    if previous and current['slot'] < previous['slot']:
        return events
    for field in ('mint_authority', 'freeze_authority'):
        if current[field] and (not previous or previous[field] != current[field]):
            events.append((field + ':' + current[field], field.replace('_', ' ') + ' is active: ' + current[field]))
    if previous:
        for address, amount in current['accounts'].items():
            before = previous['accounts'].get(address)
            # Material observed decrease: at least 0.1% of current token supply.
            if before is not None and before - amount >= max(1, current['supply_raw'] // 1000):
                events.append(('balance:' + address + ':' + str(before) + ':' + str(amount) + ':' + str(current['slot']),
                               'Verified watched-account balance fell by ' + str((before - amount) / 10 ** current['decimals']) + ' tokens. Transfer purpose/sale status is unverified. Account: ' + address))
    for address, stream in current['streams'].items():
        old = previous.get('streams', {}).get(address) if previous else None
        for field in ('canceled_at', 'cancelable_by_sender', 'cancelable_by_recipient', 'transferable_by_sender', 'transferable_by_recipient', 'pausable', 'can_update_rate'):
            if stream[field] and (not old or old[field] != stream[field]):
                events.append((address + ':' + field + ':' + str(stream[field]), 'Lock condition: ' + field + '=' + str(stream[field])))
        if old and stream['withdrawn_amount'] > old['withdrawn_amount']:
            events.append((address + ':withdrawn:' + str(stream['withdrawn_amount']), 'Verified vesting withdrawal recorded; this is not evidence of a sale.'))
        if old:
            for field in ('start_time', 'end_time', 'cliff', 'cliff_amount', 'net_amount_deposited', 'period', 'amount_per_period'):
                if old[field] != stream[field]:
                    events.append((address + ':' + field + ':' + str(stream[field]), 'Vesting terms changed: ' + field + ' from ' + str(old[field]) + ' to ' + str(stream[field])))
        remaining = stream['net_amount_deposited'] - stream['withdrawn_amount']
        if remaining > 0 and not stream['canceled_at']:
            delta = stream['cliff'] - now
            stage = 'available' if delta <= 0 else 'within24h' if delta <= 86400 else 'within7d' if delta <= 604800 else None
            if stage and stream['cliff_amount'] > stream['withdrawn_amount']:
                when = datetime.datetime.fromtimestamp(stream['cliff'], datetime.timezone.utc).isoformat()
                events.append((address + ':cliff:' + str(stream['cliff']) + ':' + stage, 'Vesting cliff ' + stage + '; cliff time ' + when + '. Unlock eligibility does not mean a sale.'))
    return events


class DeveloperChecks:
    """tick runs on the monitor thread; network work uses a single separate worker."""
    def __init__(self, store, tokens, registry_path):
        self.store = store
        self.tokens = [t for t in tokens if t.get('chain') == 'solana']
        self.registry = json.loads(Path(registry_path).read_text())
        self.executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
        self.future = None
        self.next_attempt = 0
        self.failures = 0

    def tick(self, now=None):
        now = time.time() if now is None else now
        if self.future is not None and self.future.done():
            try:
                observations = self.future.result()
                self.failures = 0
                for token in self.tokens:
                    mint = token['contract']
                    row = observations[mint]
                    key = 'developer:' + mint
                    previous = self.store.get(key)
                    if row.get('error'):
                        self.store.put(key + ':health', {'checked_at': now, 'status': 'UNKNOWN', 'reason': row['error']})
                        continue
                    if previous and row['slot'] < previous['slot']:
                        self.store.put(key + ':health', {'checked_at': now, 'status': 'UNKNOWN', 'reason': 'RPC_SLOT_REGRESSION'})
                        continue
                    for event, message in changes(previous, row, now):
                        if token.get('notifications') == 'marketcap_only':
                            continue
                        digest = hashlib.sha256((mint + event).encode()).hexdigest()
                        if not self.store.get('developer-event:' + digest):
                            self.store.enqueue('developer:' + digest, now, 900,
                                '🚨💎 MEME GEM ALERT — DEVELOPER RISK REVIEW\n' + token['name'] + '\n' + message +
                                '\nMint: ' + mint + '\nhttps://solscan.io/token/' + mint + '\nPartial wallet coverage; observation only.')
                            self.store.put('developer-event:' + digest, now)
                    self.store.put(key, row)
                    self.store.put(key + ':health', {'checked_at': now, 'status': row['coverage']})
                self.store.put('developer_runtime', {'last_success': now, 'tokens_checked': len(self.tokens)})
            except Exception as error:
                self.failures += 1
                wait = min(900, 30 * 2 ** min(5, self.failures - 1))
                if isinstance(error, urllib.error.HTTPError):
                    try:
                        wait = max(wait, int(error.headers.get('Retry-After', '0')))
                    except ValueError:
                        pass
                self.next_attempt = now + wait
                self.store.put('developer_runtime_error', {'at': now, 'status': 'UNKNOWN', 'error_type': type(error).__name__, 'retry_at': self.next_attempt})
            finally:
                self.future = None
                self.store.commit()
        if self.future is None and now >= self.next_attempt:
            self.future = self.executor.submit(fetch_snapshot, self.tokens, self.registry)
            self.next_attempt = now + 20
