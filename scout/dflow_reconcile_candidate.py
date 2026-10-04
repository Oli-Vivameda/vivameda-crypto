# Offline candidate only. Original pinned reconciler remains unchanged.
# Pump primary semantics: https://t.me/s/pump_tech_updates/11
# Never treat endpoint accounting as complete execution or wallet coverage.
"""Offline transfer accounting for parsed transactions; never certifies a history."""
from collections import Counter
from dflow_auxiliary import decode_layout as decode_route, PROGRAM
from protocol_screening import SPL, TOKEN22, b58decode

ATA = 'ATokenGPvbdGVxr1b2hvZbsiqW5xWH25efTNsLJA8knL'

PUMP_AMM = 'pAMMBay6oceH9fJKBRHGP5D4bD4sWpmSwMn52FMfXEA'
PUMP_CLOSE = bytes.fromhex('f945a4da9667548a')

SYSTEM = '11111111111111111111111111111111'
WSOL = 'So11111111111111111111111111111111111111112'
TOKEN_PROGRAMS = {SPL, TOKEN22}

class EvidenceError(ValueError):
    pass

def uint(value):
    if type(value) is int and value >= 0: return value
    if isinstance(value, str) and value and value.isascii() and value.isdecimal(): return int(value)
    raise EvidenceError('invalid_unsigned_amount')

def address(value):
    if not isinstance(value, str) or len(b58decode(value)) != 32:
        raise EvidenceError('invalid_address')
    return value

def instructions(tx):
    """Preserve each instruction's parent path; never merge sibling invocations."""
    top = tx['transaction']['message']['instructions']
    groups = tx['meta'].get('innerInstructions')
    if not isinstance(top, list) or not isinstance(groups, list) or len(top) > 1024 or len(groups) > 1024:
        raise EvidenceError('missing_instruction_trace')
    by_index = {}
    for group in groups:
        i = group['index']
        if type(i) is not int or not 0 <= i < len(top) or i in by_index:
            raise EvidenceError('invalid_inner_group')
        children = group['instructions']
        if not isinstance(children, list) or len(children) > 4096: raise EvidenceError('inner_trace_limit')
        by_index[i] = children
    output = []
    for i, ins in enumerate(top):
        if not isinstance(ins, dict): raise EvidenceError('invalid_instruction')
        output.append({'path': str(i), 'parent': None, 'root': i, 'instruction': ins})
        stack = [str(i)]
        for j, child in enumerate(by_index.get(i, [])):
            height = child.get('stackHeight')
            if type(height) is not int or height < 2 or height > len(stack) + 1:
                raise EvidenceError('invalid_stack_height')
            stack = stack[:height - 1]
            path = str(i) + '.' + str(j)
            output.append({'path': path, 'parent': stack[-1], 'root': i, 'instruction': child})
            stack.append(path)
    return output

def reconcile(tx):
    """Compare explicit instruction effects to transaction-wide endpoint balances.

    Exact endpoint accounting is necessary, not sufficient, for full semantic
    coverage. Program state, token extensions, intra-transaction ownership changes
    and route intent need independent validation. No common-control edges emitted.
    """
    result = {'status': 'UNKNOWN', 'history_coverage_complete': False,
              'common_control_edges': [], 'receipts': [], 'blockers': []}
    try:
        if not isinstance(tx, dict) or not isinstance(tx.get('meta'), dict) or tx['meta'].get('err', 'missing') is not None:
            raise EvidenceError('failed_or_missing_status')
        version = tx.get('version', 'legacy')
        if version != 'legacy' and (type(version) is not int or version not in (0, 1)):
            raise EvidenceError('unsupported_transaction_version')
        meta = tx['meta']; keys = tx['transaction']['message']['accountKeys']
        if not isinstance(keys, list) or not keys or not all(isinstance(k, dict) for k in keys):
            raise EvidenceError('parsed_account_keys_required')
        names = [address(k['pubkey']) for k in keys]
        if len(set(names)) != len(names): raise EvidenceError('duplicate_account_key')
        known = set(names)
        def acc(v):
            if address(v) not in known: raise EvidenceError('account_outside_message')
            return v
        if len(meta['preBalances']) != len(names) or len(meta['postBalances']) != len(names):
            raise EvidenceError('native_balance_length')
        native = dict(zip(names, map(uint, meta['preBalances'])))
        post_native = dict(zip(names, map(uint, meta['postBalances'])))
        native[names[0]] -= uint(meta['fee'])
        if native[names[0]] < 0: raise EvidenceError('fee_exceeds_balance')
        def balances(rows):
            if not isinstance(rows, list): raise EvidenceError('missing_token_balances')
            out = {}
            for row in rows:
                idx = row['accountIndex']
                if type(idx) is not int or not 0 <= idx < len(names): raise EvidenceError('invalid_balance_index')
                name = names[idx]
                if name in out: raise EvidenceError('duplicate_token_balance')
                out[name] = {'mint': address(row['mint']), 'owner': address(row['owner']),
                             'amount': uint(row['uiTokenAmount']['amount']), 'program': row.get('programId')}
                if out[name]['program'] not in TOKEN_PROGRAMS: raise EvidenceError('unverified_token_program')
            return out
        pre = balances(meta.get('preTokenBalances')); post = balances(meta.get('postTokenBalances'))
        tokens = {a: dict(row) for a, row in pre.items()}
        trace = instructions(tx)
        trace_by_path = {r['path']: r for r in trace}
        routes = {r['root']: decode_route(tx, r['root']) for r in trace if r['parent'] is None and r['instruction'].get('programId') == PROGRAM}
        result['route_layouts'] = [{'root': i, 'status': r['status'], 'instruction': r.get('instruction'),
                                  'actions': r.get('actions', [])} for i, r in routes.items()]
        if not routes: result['blockers'].append('no_top_level_dflow_route')
        if any(r['status'] != 'LAYOUT_DECODED' for r in routes.values()): result['blockers'].append('route_layout_unknown')
        closed = set(); token22 = set(); raw_programs = Counter(); created_native = {}; pump_closed = set(); ata_funding = {}; native_reserves = {}
        def move_native(src, dst, amount):
            src, dst = acc(src), acc(dst)
            if native[src] < amount: raise EvidenceError('native_underflow')
            native[src] -= amount; native[dst] += amount
        def receipt(row, kind, src, dst, amount, mint=None, **extra):
            result['receipts'].append({'path': row['path'], 'parent': row['parent'], 'root': row['root'],
                'under_dflow': row['root'] in routes, 'kind': kind, 'source_account': src,
                'destination_account': dst, 'raw_amount': str(amount), 'mint': mint,
                'purpose': 'unverified', 'common_control_evidence': False, **extra})
        for row in trace:
            ins = row['instruction']; program = ins.get('programId'); parsed = ins.get('parsed')
            if not isinstance(parsed, dict) and program == PUMP_AMM and b58decode(ins.get('data', ''))[:8] == PUMP_CLOSE:
                # Narrow candidate: same-transaction creation with known owner and zero endpoints.
                if b58decode(ins['data']) != PUMP_CLOSE: raise EvidenceError('pump_close_data_length')
                accounts = ins.get('accounts')
                if not isinstance(accounts, list) or len(accounts) != 4: raise EvidenceError('pump_close_accounts')
                user, vault, event, executable = map(acc, accounts)
                if executable != PUMP_AMM or user == vault: raise EvidenceError('pump_close_roles')
                keymap = {k['pubkey']: k for k in keys}
                if keymap[user].get('signer') is not True or any(keymap[a].get('writable') is not True for a in (user, vault)):
                    raise EvidenceError('pump_close_permissions')
                if vault in pump_closed or created_native.get(vault) != PUMP_AMM:
                    raise EvidenceError('pump_close_creation_unverified')
                if meta['preBalances'][names.index(vault)] != 0 or post_native[vault] != 0:
                    raise EvidenceError('pump_close_endpoints')
                amount = native[vault]
                move_native(vault, user, amount)
                receipt(row, 'program_account_close_refund', vault, user, amount,
                        evidence='documented instruction plus same-transaction creation; PDA and deployed version unverified')
                pump_closed.add(vault)
                result['blockers'].append('pump_close_pda_and_deployed_version_unverified')
                continue
            if not isinstance(parsed, dict):
                raw_programs[str(program)] += 1
                continue
            kind = parsed.get('type'); info = parsed.get('info')
            if not isinstance(info, dict): raise EvidenceError('invalid_parsed_info')
            if program == SYSTEM and kind in ('transfer', 'transferWithSeed', 'createAccount', 'createAccountWithSeed'):
                src = acc(info['source']); dst = acc(info['newAccount'] if kind.startswith('create') else info['destination'])
                if kind == 'createAccount' and dst in closed:
                    if native[dst] != 0 or info.get('owner') != tokens[dst]['program']:
                        raise EvidenceError('recreated_token_account_unverified')
                    result.setdefault('lifecycle_events', []).append({'path': row['path'], 'account': dst,
                        'kind': 'recreate_after_observed_close', 'previous_mint': tokens[dst]['mint'],
                        'previous_owner': tokens[dst]['owner']})
                    closed.remove(dst); tokens.pop(dst); created_native.pop(dst, None)
                    native_reserves.pop(dst, None); ata_funding.pop(dst, None)
                amount = uint(info['lamports']); before_funding = native[dst]; move_native(src, dst, amount)
                parent = trace_by_path.get(row['parent'], {}).get('instruction', {})
                parent_parsed = parent.get('parsed', {})
                parent_info = parent_parsed.get('info', {})
                if (kind == 'createAccount' and parent.get('programId') == ATA
                    and parent_parsed.get('type') in ('create', 'createIdempotent')
                    and parent_info.get('account') == dst and parent_info.get('source') == src
                    and parent_info.get('mint') == WSOL and parent_info.get('tokenProgram') == SPL
                    and parent_info.get('systemProgram') == SYSTEM
                    and info.get('owner') == SPL and type(info.get('space')) is int and info['space'] == 165
                    and before_funding == 0 and meta['preBalances'][names.index(dst)] == 0 and amount > 1):
                    ata_funding[dst] = {'reserve': amount, 'parent': row['parent'], 'owner': parent_info.get('wallet')}

                if kind.startswith('create'):
                    if dst in created_native or dst in pump_closed: raise EvidenceError('native_account_reinitialization')
                    created_native[dst] = address(info['owner'])
                receipt(row, 'account_funding' if kind.startswith('create') else 'native_transfer', src, dst, amount)
            elif program in TOKEN_PROGRAMS:
                if program == TOKEN22: token22.add(program)
                if kind in ('initializeAccount', 'initializeAccount2', 'initializeAccount3'):
                    a = acc(info['account'])
                    if a in tokens or a in closed: raise EvidenceError('account_reinitialization')
                    tokens[a] = {'mint': address(info['mint']), 'owner': address(info['owner']), 'amount': 0, 'program': program}
                    # Initial WSOL token amount depends on rent reserve, not just lamports.
                    if tokens[a]['mint'] == WSOL:
                        result['blockers'].append('new_wsol_reserve_unverified')
                        funding = ata_funding.get(a)
                        if (program == SPL and funding and row['parent'] == funding['parent']
                            and info['owner'] == funding['owner'] and native[a] == funding['reserve']):
                            native_reserves[a] = funding['reserve']
                            result['blockers'].append('ata_rent_and_historical_program_semantics_unverified')
                elif kind == 'syncNative':
                    a = acc(info['account'])
                    if (program != SPL or a not in tokens or a in closed
                        or tokens[a]['program'] != SPL or tokens[a]['mint'] != WSOL):
                        raise EvidenceError('sync_native_identity_unverified')
                    if a not in native_reserves: raise EvidenceError('sync_native_historical_reserve_missing')
                    amount = native[a] - native_reserves[a]
                    if amount < tokens[a]['amount']: raise EvidenceError('sync_native_decrease_unsupported')
                    previous = tokens[a]['amount']; tokens[a]['amount'] = amount
                    result.setdefault('state_updates', []).append({'path': row['path'], 'account': a,
                        'kind': 'sync_native', 'previous_raw_amount': str(previous), 'raw_amount': str(amount),
                        'reserve_lamports': str(native_reserves[a]),
                        'evidence': 'conditional same-transaction ATA creation funding; not archived account state'})
                elif kind in ('transfer', 'transferChecked'):
                    src, dst = acc(info['source']), acc(info['destination'])
                    if src not in tokens or dst not in tokens or src in closed or dst in closed:
                        raise EvidenceError('missing_transfer_account_state')
                    a, b = tokens[src], tokens[dst]
                    if a['mint'] != b['mint'] or a['program'] != program or b['program'] != program:
                        raise EvidenceError('transfer_identity_mismatch')
                    if kind == 'transferChecked' and info.get('mint') != a['mint']:
                        raise EvidenceError('checked_mint_mismatch')
                    amount = uint(info['amount'] if kind == 'transfer' else info['tokenAmount']['amount'])
                    if a['amount'] < amount: raise EvidenceError('token_underflow')
                    a['amount'] -= amount; b['amount'] += amount
                    if a['mint'] == WSOL: move_native(src, dst, amount)
                    receipt(row, 'token_transfer', src, dst, amount, a['mint'], source_owner=a['owner'],
                            destination_owner=b['owner'], authority=info.get('authority'), token_program=program)
                elif kind in ('mintTo', 'burn'):
                    a = acc(info['account'])
                    if a not in tokens or a in closed: raise EvidenceError('mint_burn_account_missing')
                    state = tokens[a]
                    if state['program'] != program or state['mint'] != acc(info['mint']) or state['mint'] == WSOL:
                        raise EvidenceError('mint_burn_identity_mismatch')
                    amount = uint(info['amount']); previous = state['amount']
                    updated = previous + amount if kind == 'mintTo' else previous - amount
                    if not 0 <= updated <= 2**64 - 1: raise EvidenceError('mint_burn_amount_bounds')
                    state['amount'] = updated
                    result.setdefault('state_updates', []).append({'path': row['path'], 'account': a,
                        'kind': kind, 'raw_amount': str(amount), 'previous_raw_balance': str(previous),
                        'raw_balance': str(updated), 'mint': state['mint'], 'authority_verified': False})
                    result['blockers'].append('mint_burn_authority_and_supply_unverified')
                elif kind == 'closeAccount':
                    a, dst = acc(info['account']), acc(info['destination'])
                    if a not in tokens or a in closed: raise EvidenceError('missing_close_state')
                    state = tokens[a]
                    if state['program'] != program: raise EvidenceError('close_program_mismatch')
                    if state['mint'] != WSOL and state['amount'] != 0: raise EvidenceError('nonempty_close')
                    amount = native[a]; move_native(a, dst, amount)
                    receipt(row, 'close_refund_or_unwrap', a, dst, amount, authority=info.get('owner'))
                    state['amount'] = 0; closed.add(a)
                elif kind == 'setAuthority':
                    # Close authority is not token ownership. Other changes need timeline decoding.
                    if info.get('authorityType') != 'closeAccount':
                        raise EvidenceError('token_authority_change_unverified')
                elif kind not in ('getAccountDataSize', 'initializeImmutableOwner'):
                    result['blockers'].append('unsupported_token_effect:' + str(kind))
            elif program == SYSTEM:
                result['blockers'].append('unsupported_system_effect:' + str(kind))
        token_residuals = []
        for a in sorted(set(tokens) | set(post)):
            before, after = tokens.get(a), post.get(a)
            if before is None or (after is None and a not in closed):
                result['blockers'].append('missing_endpoint_account_state'); continue
            if after is None: continue
            if a in closed or any(before[k] != after[k] for k in ('mint', 'owner', 'program')):
                result['blockers'].append('endpoint_identity_changed'); continue
            delta = after['amount'] - before['amount']
            if delta: token_residuals.append({'account': a, 'raw_residual': str(delta)})
        native_residuals = [{'account': a, 'lamport_residual': str(post_native[a] - native[a])}
                            for a in names if post_native[a] != native[a]]
        result.update(token_residuals=token_residuals, native_residuals=native_residuals,
                      raw_program_counts=dict(raw_programs), token_accounts_checked=len(tokens),
                      raw_program_semantics_verified=False)
        if token_residuals: result['blockers'].append('token_balance_residual')
        if native_residuals: result['blockers'].append('native_balance_residual')
        if token22: result['blockers'].append('token2022_extensions_unverified')
        result['blockers'].append('downstream_program_semantics_unverified')
        result['blockers'] = sorted(set(result['blockers']))
        # Accounting status never clears the semantic/coverage blockers.
        accounting_blockers = set(result['blockers']) - {'downstream_program_semantics_unverified', 'token2022_extensions_unverified', 'new_wsol_reserve_unverified', 'pump_close_pda_and_deployed_version_unverified', 'ata_rent_and_historical_program_semantics_unverified', 'mint_burn_authority_and_supply_unverified'}
        result['status'] = 'ENDPOINT_AMOUNTS_MATCH' if not accounting_blockers else 'UNKNOWN'
        result['endpoint_match_scope'] = 'explicit parsed effects and endpoint amounts; not full execution semantics'
    except (EvidenceError, ValueError, TypeError, KeyError, IndexError, AttributeError) as exc:
        result['blockers'].append(str(exc) if isinstance(exc, EvidenceError) else 'malformed_transaction')
    return result
