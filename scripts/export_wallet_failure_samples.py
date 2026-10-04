#!/usr/bin/env python3
"""Owner-run private diagnostic sample; never publish the generated JSON."""
from contextlib import closing
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import pwd
import sqlite3
import sys
import tempfile
import time

REPO = Path('/var/lib/vivameda-engineering/repo')
REVIEW = REPO / 'client_learning/public_crypto_release_20261003'
HELPER_SHA256 = '77a1183d3d243b3bd96986d71c7603dd58e65f84a20688e90f40455e7e4a9de8'


def select_samples(path, reconcile, decode_route, program, limit=1000):
    if type(limit) is not int or not 1 <= limit <= 1000:
        raise ValueError('invalid_limit')
    if any(p.is_symlink() for p in (path, *path.parents)) or not path.is_file():
        raise ValueError('unsafe_database')
    started = time.monotonic()
    out = {'production_changed': False, 'network_calls': 0, 'private_do_not_publish': True,
           'selection': 'latest inserted rows; new sample, not the earlier frozen replay cohort',
           'rows_examined': 0, 'bounded_stop': False, 'samples': []}
    counts = {'native_underflow': 0, 'route_layout_unknown': 0}
    used = 0
    with closing(sqlite3.connect(path.resolve().as_uri() + '?mode=ro', uri=True, timeout=2)) as db:
        db.execute('PRAGMA query_only=ON')
        db.set_progress_handler(lambda: int(time.monotonic() - started > 25), 1000)
        try:
            for (body,) in db.execute('SELECT CASE WHEN length(body)<=2097152 THEN body END FROM tx ORDER BY rowid DESC LIMIT ?', (limit,)):
                if time.monotonic() - started > 25:
                    out['bounded_stop'] = True; break
                out['rows_examined'] += 1
                if not isinstance(body, str): continue
                size = len(body.encode())
                if size > 2097152: continue
                used += size
                if used > 67108864:
                    out['bounded_stop'] = True; break
                try:
                    tx = json.loads(body)
                    top = tx['transaction']['message']['instructions']
                    roots = [i for i, ins in enumerate(top) if isinstance(ins, dict) and ins.get('programId') == program]
                    if not roots: continue
                    result = reconcile(tx)
                    if result.get('history_coverage_complete') is not False:
                        raise RuntimeError('unexpected_coverage_claim')
                    categories = [k for k in counts if k in result.get('blockers', []) and counts[k] < 3]
                    if not categories: continue
                    for k in categories: counts[k] += 1
                    out['samples'].append({'categories': categories,
                        'body_sha256': hashlib.sha256(body.encode()).hexdigest(),
                        'route_diagnostics': [decode_route(tx, i) for i in roots],
                        'transaction': tx})
                    if all(n == 3 for n in counts.values()): break
                except (ValueError, TypeError, KeyError, IndexError, AttributeError):
                    continue
        finally:
            db.set_progress_handler(None, 0)
    out['category_counts'] = counts
    out['checked_at'] = int(time.time())
    return out


def main():
    if os.geteuid() != 0: raise SystemExit('Run in the owner root maintenance terminal.')
    helper = REVIEW / 'replay_wallet_cache.py'
    if any(p.is_symlink() for p in (helper, *helper.parents)) or hashlib.sha256(helper.read_bytes()).hexdigest() != HELPER_SHA256:
        raise SystemExit('Reviewed helper mismatch')
    sys.dont_write_bytecode = True
    spec = importlib.util.spec_from_file_location('reviewed_cache_helper', helper)
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    for name, expected in module.PINNED.items():
        source = module.SOURCE / name; module.regular(source)
        if hashlib.sha256(source.read_bytes()).hexdigest() != expected:
            raise SystemExit('Reviewed source mismatch: ' + name)
    sys.path.insert(0, str(module.SOURCE))
    from dflow_reconcile import reconcile, PROGRAM
    from dflow_decoder import decode_route
    owner = pwd.getpwnam('vivameda-engineer')
    if owner.pw_uid == 0: raise SystemExit('Invalid engineering owner')
    result = select_samples(module.DATABASE, reconcile, decode_route, PROGRAM)
    result['reviewed_source_hashes'] = module.PINNED
    fd, path = tempfile.mkstemp(prefix='wallet_failure_samples_private_', suffix='.json', dir=REVIEW)
    with os.fdopen(fd, 'w') as stream: json.dump(result, stream)
    os.chmod(path, 0o600); os.chown(path, owner.pw_uid, owner.pw_gid)
    print(json.dumps({'private_result_file': path, 'category_counts': result['category_counts'],
                      'sample_count': len(result['samples']), 'production_changed': False,
                      'public_upload_performed': False}))

if __name__ == '__main__': main()
