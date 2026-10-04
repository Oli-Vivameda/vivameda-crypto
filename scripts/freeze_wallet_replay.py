#!/usr/bin/env python3
"""Freeze a private DFlow cohort for paired offline replay; no deployment."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import pwd
import sys
import tempfile
import time

REVIEW = Path('/var/lib/vivameda-engineering/repo/client_learning/public_crypto_release_20261003')
HELPER_SHA256 = '77a1183d3d243b3bd96986d71c7603dd58e65f84a20688e90f40455e7e4a9de8'
PROGRAM = 'DF1ow4tspfHX9JwWJsAb9epbkA8hmpSEAtxXy1V27QBH'


def freeze(helper, database):
    transactions = []
    def collect(tx):
        transactions.append(tx)
        return {'status': 'UNKNOWN', 'history_coverage_complete': False}
    summary = helper.audit_cache(database, collect, PROGRAM)
    # This is capture only: UNKNOWN above is not a decoder result.
    encoded = json.dumps(transactions, sort_keys=True, separators=(',', ':')).encode()
    return {'private_do_not_publish': True, 'purpose': 'frozen paired replay input; no scoring at capture',
            'checked_at': int(time.time()), 'rows_examined': summary['rows_examined'],
            'selection': summary['selection'], 'bounded_stop': summary['bounded_stop'],
            'oversized_or_invalid_rows': summary['oversized_or_invalid_rows'],
            'transaction_count': len(transactions),
            'transactions_sha256': hashlib.sha256(encoded).hexdigest(),
            'transactions': transactions, 'production_changed': False, 'network_calls': 0}


def main():
    if os.geteuid() != 0: raise SystemExit('Run from the owner root maintenance terminal.')
    path = REVIEW / 'replay_wallet_cache.py'
    if any(p.is_symlink() for p in (path, *path.parents)) or not path.is_file():
        raise SystemExit('Unsafe helper path')
    if hashlib.sha256(path.read_bytes()).hexdigest() != HELPER_SHA256:
        raise SystemExit('Reviewed helper mismatch')
    sys.dont_write_bytecode = True
    spec = importlib.util.spec_from_file_location('reviewed_capture_helper', path)
    helper = importlib.util.module_from_spec(spec); spec.loader.exec_module(helper)
    owner = pwd.getpwnam('vivameda-engineer')
    if owner.pw_uid == 0: raise SystemExit('Invalid engineering owner')
    result = freeze(helper, helper.DATABASE)
    fd, output = tempfile.mkstemp(prefix='wallet_frozen_replay_private_', suffix='.json', dir=REVIEW)
    with os.fdopen(fd, 'w') as stream: json.dump(result, stream, separators=(',', ':'))
    os.chmod(output, 0o600); os.chown(output, owner.pw_uid, owner.pw_gid)
    print(json.dumps({k: result[k] for k in ('rows_examined','transaction_count','transactions_sha256','bounded_stop','production_changed')} | {'private_result_file': output, 'public_upload_performed': False}))

if __name__ == '__main__': main()
