#!/usr/bin/env python3
"""Owner-run bounded SQLite replay. Aggregate output only; no network/deployment."""
import collections
import hashlib
import json
import os
from pathlib import Path
import pwd
import sqlite3
import stat
import sys
import tempfile
import time

REPO = Path('/var/lib/vivameda-engineering/repo')
SOURCE = REPO / 'server_source/vivameda-crypto-early-scout'
DATABASE = Path('/var/lib/vivameda-wallet-intelligence/data/wallets.sqlite')
DESTINATION = REPO / 'client_learning/public_crypto_release_20261003'
MAX_ROWS = 1000
MAX_BODY_BYTES = 2 * 1024 * 1024
MAX_TOTAL_BYTES = 64 * 1024 * 1024
MAX_SECONDS = 25
PINNED = {'dflow_reconcile.py': 'ddccad4bf40fc775876517b660ca5467d18fcbb2d1e949eb4a78349aa22935d4', 'dflow_decoder.py': '40f43aa7864b3f0afa7f0ce182bab0e9339abf7248b09497c19ec6e545a25150', 'dflow_schema.json': '0b849cec2747c875630bb021acfec2ce7aa6f2a28f78b03ed5cb44a2b135c021', 'protocol_screening.py': 'ca049acdde2198e70d83a82d95552b4bd193116de0b4d28f64c34cd699827636'}

SAFE_REASONS = ['account_outside_message', 'account_reinitialization', 'checked_mint_mismatch', 'close_program_mismatch', 'downstream_program_semantics_unverified', 'duplicate_account_key', 'duplicate_token_balance', 'endpoint_identity_changed', 'failed_or_missing_status', 'fee_exceeds_balance', 'inner_trace_limit', 'invalid_address', 'invalid_balance_index', 'invalid_inner_group', 'invalid_instruction', 'invalid_parsed_info', 'invalid_stack_height', 'invalid_unsigned_amount', 'malformed_transaction', 'missing_close_state', 'missing_endpoint_account_state', 'missing_instruction_trace', 'missing_token_balances', 'missing_transfer_account_state', 'native_balance_length', 'native_balance_residual', 'native_underflow', 'new_wsol_reserve_unverified', 'no_top_level_dflow_route', 'nonempty_close', 'parsed_account_keys_required', 'route_layout_unknown', 'token2022_extensions_unverified', 'token_authority_change_unverified', 'token_balance_residual', 'token_underflow', 'transfer_identity_mismatch', 'unsupported_transaction_version', 'unverified_token_program']

def regular(path):
    if any(p.is_symlink() for p in (path, *path.parents)):
        raise ValueError('symlink_refused')
    if not stat.S_ISREG(path.stat().st_mode): raise ValueError('regular_file_required')


def audit_cache(path, reconcile, program, max_rows=MAX_ROWS):
    """Read latest inserted cached rows; not a random or historical cohort."""
    regular(path)
    if type(max_rows) is not int or not 1 <= max_rows <= MAX_ROWS:
        raise ValueError('invalid_row_limit')
    start = time.monotonic()
    out = {'read_only': True, 'production_changed': False, 'network_calls': 0,
           'selection': 'descending SQLite rowid, at most 1000 cached rows; not chronological or representative',
           'rows_examined': 0, 'dflow_transactions': 0, 'endpoint_amounts_match': 0,
           'unknown': 0, 'history_complete_claimed': 0, 'receipt_count': 0,
           'oversized_or_invalid_rows': 0, 'bounded_stop': False,
           'blocker_transaction_counts': {}, 'receipt_kind_counts': {}}
    blockers = collections.Counter(); kinds = collections.Counter(); used = 0
    db = sqlite3.connect(path.resolve().as_uri() + '?mode=ro', uri=True, timeout=2)
    try:
        db.execute('PRAGMA query_only=ON')
        db.set_progress_handler(lambda: int(time.monotonic() - start > MAX_SECONDS), 1000)
        allowed = {sqlite3.SQLITE_SELECT, sqlite3.SQLITE_READ, sqlite3.SQLITE_FUNCTION}
        db.set_authorizer(lambda action, *args: sqlite3.SQLITE_OK if action in allowed else sqlite3.SQLITE_DENY)
        rows = db.execute('SELECT CASE WHEN length(body)<=? THEN body ELSE NULL END FROM tx ORDER BY rowid DESC LIMIT ?',
                          (MAX_BODY_BYTES, max_rows))
        for row in rows:
            if time.monotonic() - start > MAX_SECONDS:
                out['bounded_stop'] = True; break
            out['rows_examined'] += 1
            body = row[0]
            if not isinstance(body, str) or len(body.encode()) > MAX_BODY_BYTES:
                out['oversized_or_invalid_rows'] += 1; continue
            used += len(body.encode())
            if used > MAX_TOTAL_BYTES:
                out['bounded_stop'] = True; break
            try:
                tx = json.loads(body)
                top = tx['transaction']['message']['instructions']
                if not isinstance(top, list): raise ValueError('invalid_instructions')
                if not any(isinstance(i, dict) and i.get('programId') == program for i in top): continue
                out['dflow_transactions'] += 1
                result = reconcile(tx)
                matched = result.get('status') == 'ENDPOINT_AMOUNTS_MATCH'
                out['endpoint_amounts_match' if matched else 'unknown'] += 1
                # Fail if a changed dependency tries to claim complete coverage.
                if result.get('history_coverage_complete') is not False:
                    raise RuntimeError('unexpected_coverage_claim')
                receipts = result.get('receipts', [])
                out['receipt_count'] += len(receipts)
                for item in receipts:
                    kind = item.get('kind')
                    if kind in {'token_transfer', 'native_transfer', 'account_funding', 'close_refund_or_unwrap'}: kinds[kind] += 1
                for reason in set(result.get('blockers', [])):
                    # Reasons are code-generated; reject arbitrary raw text or identifiers.
                    if isinstance(reason, str) and reason in SAFE_REASONS:
                        blockers[reason] += 1
                    else: blockers['other_unclassified_reason'] += 1
            except (ValueError, TypeError, KeyError, IndexError, AttributeError):
                out['oversized_or_invalid_rows'] += 1
        out['blocker_transaction_counts'] = dict(sorted(blockers.items()))
        out['receipt_kind_counts'] = dict(sorted(kinds.items()))
        out['bytes_examined'] = used
        out['elapsed_seconds'] = round(time.monotonic() - start, 3)
        return out
    except sqlite3.OperationalError as exc:
        raise RuntimeError('cache_replay_database_unavailable_or_time_limit') from exc
    finally:
        db.close()


def main():
    if os.geteuid() != 0: raise SystemExit('Run from the owner maintenance terminal as root.')
    for name, expected in PINNED.items():
        path = SOURCE / name; regular(path)
        if hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            raise SystemExit('Reviewed source hash mismatch: ' + name)
    if len(PINNED) != 4: raise SystemExit('Missing reviewed source pins')
    owner = pwd.getpwnam('vivameda-engineer')
    if owner.pw_uid == 0: raise SystemExit('Invalid engineering owner')
    if any(p.is_symlink() for p in (DESTINATION, *DESTINATION.parents)) or not DESTINATION.is_dir():
        raise SystemExit('Unsafe destination')
    # Isolated invocation (-I) plus pinned module directory, with no bytecode writes.
    sys.dont_write_bytecode = True
    sys.path.insert(0, str(SOURCE))
    from dflow_reconcile import reconcile, PROGRAM
    result = audit_cache(DATABASE, reconcile, PROGRAM)
    result['reviewed_source_hashes'] = PINNED
    result['checked_at'] = int(time.time())
    fd, path = tempfile.mkstemp(prefix='wallet_cache_replay_', suffix='.json', dir=DESTINATION)
    with os.fdopen(fd, 'w') as stream:
        json.dump(result, stream, indent=2)
    os.chmod(path, 0o600); os.chown(path, owner.pw_uid, owner.pw_gid)
    print(json.dumps({'result_file': path, 'rows_examined': result['rows_examined'],
                      'dflow_transactions': result['dflow_transactions'], 'production_changed': False}))

if __name__ == '__main__': main()
