"""Build a narrowly amended scanner without changing frozen source artifacts."""
import hashlib
from pathlib import Path

HERE=Path(__file__).resolve().parent
OLD_SCANNER='3e73978a41e2e21e090a7eea92bbdc1a52dc190ce229ac262a3c6a2b0af6a043'
OLD_TRACKER='a519ad19680ba72f0d593c4627fe5faa2d8dfa93fcd112eaba21abcf5a6da9b6'

def once(source,before,after):
    if source.count(before)!=1:raise ValueError('reviewed source anchor mismatch')
    return source.replace(before,after,1)

def build(source,amendment_hash):
    if hashlib.sha256(source.encode()).hexdigest()!=OLD_SCANNER:
        raise ValueError('original scanner mismatch')
    source=once(source,"FC_MAX_BYTES =",f"FC_AMENDMENT_SHA256 = '{amendment_hash}'\nFC_ORIGINAL_SCANNER_SHA256 = '{OLD_SCANNER}'\nFC_MAX_BYTES =")
    source=once(source,"'observed_ts': int(time.time())}))","'observed_ts': int(time.time()),\n                                      'code': fc_safe_reason(error)}))")
    source=once(source,'def fc_pause(error):', '''def fc_safe_reason(error):
    # Static allowlist only: exception text may contain identities or paths.
    allowed = {'incomplete candidate accounting', 'provider or capture failure invalidates cycle',
               'capture runtime binding', 'capture tracker binding', 'capture repair binding',
               'capture immutability triggers missing', 'capture exclusion binding',
               'capture integrity failed', 'capture anchor changed', 'capture append chain changed',
               'capture storage cap', 'capture minimum free disk', 'exact score replay mismatch',
               'future decision or creation', 'outside current scanner age universe',
               'stale or future snapshot', 'cycle inputs not contemporaneous',
               'exact emitted signal vector required'}
    return str(error) if type(error) is ValueError and str(error) in allowed else 'other_capture_error'


def fc_pause(error):''')
    source=once(source,"            if a['protocol_sha256'] != FC_PROTOCOL_SHA256 or a['scanner_sha256'] != hashlib.sha256(Path(__file__).read_bytes()).hexdigest():",'''            # Verify before trusting a hash-bound recovery event.
            fc_core_verify(con)
            repair = con.execute("SELECT body FROM fc_events WHERE kind='runtime_repair' ORDER BY seq DESC LIMIT 1").fetchone()
            binding = a['scanner_sha256']
            if repair:
                r = json.loads(repair[0])
                if (r.get('original_scanner_sha256') != FC_ORIGINAL_SCANNER_SHA256 or
                    r.get('amendment_sha256') != FC_AMENDMENT_SHA256 or
                    r.get('tracker_sha256') != a['tracker_sha256'] or
                    r.get('activation_ts') != a['activation_ts'] or r.get('deadline') != a['deadline']):
                    raise ValueError('capture repair binding')
                binding = r['scanner_sha256']
            if a['protocol_sha256'] != FC_PROTOCOL_SHA256 or binding != hashlib.sha256(Path(__file__).read_bytes()).hexdigest():''')
    source=once(source,"        if any(reason not in ('history', 'base_gate', 'price_history') for reason in failures):\n            raise ValueError('provider or capture failure invalidates cycle')",'''        if any(reason not in ('history', 'base_gate', 'price_history', 'pair_unavailable') for reason in failures):
            raise ValueError('provider or capture failure invalidates cycle')
        if 'pair_unavailable' in failures:
            # Reject the WHOLE cycle, with no input/cohort/endpoint substitution.
            con.execute('BEGIN IMMEDIATE')
            try:
                fc_guard(con)
                fc_core_append(con, 'rejected_cycle', cycle_id,
                               {'cycle_ts': cycle_ts, 'selected': selected_count,
                                'pair_unavailable': failures.count('pair_unavailable'),
                                'scored_discarded': len(batch),
                                'amendment_sha256': FC_AMENDMENT_SHA256})
                con.commit()
            except BaseException:
                con.rollback()
                raise
            return {}''')
    # The immutable activation retains the original hash. Valid cycles disclose actual runtime.
    source=once(source,"                                         a['scanner_sha256'], verifier=fc_guard)","                                         hashlib.sha256(Path(__file__).read_bytes()).hexdigest(), verifier=fc_guard)")
    return source

if __name__=='__main__':
    old=HERE.parent/'crypto_forward_capture'/'integration'
    if not old.exists():old=HERE.parent/'crypto_forward_capture_20261005'/'integration'
    if not old.exists():old=HERE.parent/'forward_capture'/'integration'
    amendment=hashlib.sha256((HERE/'AMENDMENT_20261006.md').read_bytes()).hexdigest()
    (HERE/'early_scout.py').write_text(build((old/'early_scout.py').read_text(),amendment))
