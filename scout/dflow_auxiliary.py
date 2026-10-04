"""Offline candidate for DFlow wrap/unwrap/transfer layouts; does not certify effects.

Layouts transcribed from verified on-chain IDL SHA256
2d48c967de1fcfa93186c21cee90c2df362da5cbc4dc68219a8a2e8c31c29d82.
Existing six-swap decoder and production imports are unchanged.
"""
from dflow_decoder import decode_route, PROGRAM
from protocol_screening import b58decode, SPL

WSOL = 'So11111111111111111111111111111111111111112'
ATA = 'ATokenGPvbdGVxr1b2hvZbsiqW5xWH25efTNsLJA8knL'
SYSTEM = '11111111111111111111111111111111'
WRAP = bytes([47, 62, 155, 172, 131, 205, 37, 201])
UNWRAP = bytes([99, 40, 14, 105, 45, 107, 172, 201])

TRANSFER = bytes([78, 10, 236, 247, 109, 117, 21, 76])

def decode_layout(tx, index):
    """Candidate dispatch; layout recognition never supplies executed amounts."""
    base = decode_route(tx, index)
    if base.get('reason') != 'unsupported_instruction': return base
    try:
        msg = tx['transaction']['message']
        ins = msg['instructions'][index]
        raw = b58decode(ins['data'])
        discriminator = raw[:8]
        if discriminator not in (WRAP, UNWRAP, TRANSFER): return base
        wrap = discriminator == WRAP
        transfer = discriminator == TRANSFER
        if len(raw) != (16 if wrap or transfer else 8): raise ValueError('auxiliary_data_length')
        accounts = ins.get('accounts')
        if not isinstance(accounts, list) or len(accounts) != (6 if wrap else 3):
            raise ValueError('auxiliary_account_count')
        if any(not isinstance(a, str) or len(b58decode(a)) != 32 for a in accounts):
            raise ValueError('auxiliary_invalid_account')
        keys = {k['pubkey'] for k in msg['accountKeys'] if isinstance(k, dict)}
        if any(a not in keys for a in accounts): raise ValueError('auxiliary_account_outside_message')
        if wrap and accounts[2:] != [WSOL, SPL, ATA, SYSTEM]:
            raise ValueError('auxiliary_program_or_mint_mismatch')
        if not wrap and accounts[2] != (SYSTEM if transfer else SPL): raise ValueError('auxiliary_program_or_mint_mismatch')
        return {'status': 'LAYOUT_DECODED', 'instruction': 'wrap_sol' if wrap else ('transfer_sol' if transfer else 'unwrap_sol'),
                'parameters': {'lamports': int.from_bytes(raw[8:], 'little')} if wrap or transfer else {},
                'actions': [], 'history_coverage_complete': False,
                'execution_semantics': 'UNKNOWN', 'account_roles_verified': False,
                'scope': 'auxiliary layout only; no PDA, reserve, ownership or executed-amount proof'}
    except (ValueError, TypeError, KeyError, IndexError, AttributeError):
        return {'status': 'UNKNOWN', 'reason': 'invalid_auxiliary_layout', 'history_coverage_complete': False}
