"""Offline DFlow route-layout decoder. Never certifies history or changes gates."""
import hashlib
import json
from pathlib import Path
from protocol_screening import b58decode, b58encode

PROGRAM = 'DF1ow4tspfHX9JwWJsAb9epbkA8hmpSEAtxXy1V27QBH'
SCHEMA_SHA256 = '0b849cec2747c875630bb021acfec2ce7aa6f2a28f78b03ed5cb44a2b135c021'
_raw = Path(__file__).with_name('dflow_schema.json').read_bytes()
if hashlib.sha256(_raw).hexdigest() != SCHEMA_SHA256:
    raise ValueError('dflow_schema_hash_mismatch')
_SCHEMA = json.loads(_raw)
_TYPES = {x['name']: x['type'] for x in _SCHEMA['types']}
_OPS = {bytes(x['discriminator']): x for x in _SCHEMA['instructions']}

class DecodeError(ValueError):
    pass

class Reader:
    def __init__(self, raw):
        self.raw, self.pos, self.nodes = raw, 0, 0
    def take(self, size):
        if size < 0 or self.pos + size > len(self.raw):
            raise DecodeError('truncated_data')
        out = self.raw[self.pos:self.pos + size]
        self.pos += size
        return out
    def fields(self, fields, depth):
        if fields and isinstance(fields[0], dict) and 'name' in fields[0]:
            return {f['name']: self.value(f['type'], depth + 1) for f in fields}
        return [self.value(f, depth + 1) for f in fields]
    def value(self, typ, depth=0):
        self.nodes += 1
        if depth > 24 or self.nodes > 4096:
            raise DecodeError('structure_limit')
        if isinstance(typ, str):
            if typ in ('u8', 'u16', 'u32', 'u64', 'u128'):
                return int.from_bytes(self.take(int(typ[1:]) // 8), 'little')
            if typ == 'bool':
                n = self.take(1)[0]
                if n > 1: raise DecodeError('invalid_bool')
                return bool(n)
            if typ == 'pubkey': return b58encode(self.take(32))
            raise DecodeError('unsupported_primitive')
        if not isinstance(typ, dict): raise DecodeError('invalid_schema')
        if 'defined' in typ:
            name = typ['defined']['name']
            spec = _TYPES[name]
            if spec['kind'] == 'struct':
                return self.fields(spec.get('fields', []), depth)
            if spec['kind'] == 'enum':
                index = self.take(1)[0]
                if index >= len(spec['variants']): raise DecodeError('unknown_variant')
                variant = spec['variants'][index]
                return {'variant': variant['name'], 'fields': self.fields(variant.get('fields', []), depth)}
        if 'vec' in typ:
            count = int.from_bytes(self.take(4), 'little')
            if count > 128: raise DecodeError('vector_limit')
            return [self.value(typ['vec'], depth + 1) for _ in range(count)]
        if 'array' in typ:
            inner, count = typ['array']
            if type(count) is not int or not 0 <= count <= 128: raise DecodeError('array_limit')
            return [self.value(inner, depth + 1) for _ in range(count)]
        if 'option' in typ:
            flag = self.take(1)[0]
            if flag not in (0, 1): raise DecodeError('invalid_option')
            return self.value(typ['option'], depth + 1) if flag else None
        raise DecodeError('unsupported_schema')

def decode_route(tx, index):
    """Decode one successful top-level swap layout; execution semantics stay UNKNOWN.

    Account roles and route parameters are observations, never common-owner edges,
    executed amounts, creator identity or proof of downstream decoder coverage.
    """
    try:
        if not isinstance(tx, dict) or not isinstance(tx.get('meta'), dict) or tx['meta'].get('err', 'missing') is not None:
            raise DecodeError('failed_or_missing_status')
        version = tx.get('version', 'legacy')
        if version != 'legacy' and (type(version) is not int or version not in (0, 1)):
            raise DecodeError('unsupported_transaction_version')
        if type(index) is not int or index < 0: raise DecodeError('invalid_index')
        msg = tx['transaction']['message']; ins = msg['instructions'][index]
        if ins.get('programId') != PROGRAM: raise DecodeError('different_program')
        raw = b58decode(ins.get('data'))
        if len(raw) > 2048: raise DecodeError('data_limit')
        op = _OPS.get(raw[:8])
        if op is None: raise DecodeError('unsupported_instruction')
        accounts = ins.get('accounts')
        if not isinstance(accounts, list) or len(accounts) < len(op['accounts']): raise DecodeError('missing_accounts')
        if any(not isinstance(a, str) or len(b58decode(a)) != 32 for a in accounts): raise DecodeError('invalid_account')
        keys = msg.get('accountKeys', [])
        signers = {k.get('pubkey') for k in keys if isinstance(k, dict) and k.get('signer') is True}
        for actual, role in zip(accounts, op['accounts']):
            if role.get('address') and actual != role['address']: raise DecodeError('fixed_account_mismatch')
            if role.get('signer') and actual not in signers: raise DecodeError('missing_signer')
            if role['name'] == 'program' and actual != PROGRAM: raise DecodeError('program_account_mismatch')
        reader = Reader(raw[8:]); args = reader.fields(op['args'], 0)
        if reader.pos != len(reader.raw): raise DecodeError('trailing_data')
        params = args['params']
        if not params['actions']: raise DecodeError('empty_route')
        if params['slippage_bps'] > 10000 or params['platform_fee_bps'] > 10000 or params.get('positive_slippage_fee_limit_pct', 0) > 100:
            raise DecodeError('invalid_fee_or_slippage')
        return {'status': 'LAYOUT_DECODED', 'instruction': op['name'],
                'actions': [a['variant'] for a in params['actions']], 'parameters': params,
                'history_coverage_complete': False, 'execution_semantics': 'UNKNOWN',
                'scope': 'top-level route layout only; no execution or ownership conclusion'}
    except (DecodeError, ValueError, TypeError, KeyError, IndexError, AttributeError) as exc:
        reason = str(exc) if isinstance(exc, DecodeError) else 'malformed_transaction'
        return {'status': 'UNKNOWN', 'reason': reason, 'history_coverage_complete': False}
