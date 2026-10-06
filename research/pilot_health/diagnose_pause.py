#!/usr/bin/env python3
"""Bounded owner-run diagnosis. No network, writes, outcomes or identity output."""
import argparse
import ast
from collections import Counter
import hashlib
import json
import math
from pathlib import Path
import sqlite3
import time
from types import SimpleNamespace

BASE=Path('/opt/vivameda-crypto-early-scout')
EXPECTED={'early_scout.py':'3e73978a41e2e21e090a7eea92bbdc1a52dc190ce229ac262a3c6a2b0af6a043',
          'scout_learning_v2.py':'a519ad19680ba72f0d593c4627fe5faa2d8dfa93fcd112eaba21abcf5a6da9b6'}
SAFE_REASONS={'mint','pair','created_ts','captured_ts','snapshot_ts','points','history_seconds',
              'score','prior_alert_level','mc','liq','vol1','input hash','unexpected or missing decision fields',
              'future decision or creation','outside current scanner age universe','stale or future snapshot',
              'cycle inputs not contemporaneous','exact emitted signal vector required'}


def read_only(path):
    con=sqlite3.connect('file:'+str(path)+'?mode=ro',uri=True,timeout=.1)
    started=time.monotonic()
    con.set_progress_handler(lambda:int(time.monotonic()-started>10),1000)
    con.execute('PRAGMA query_only=ON');con.execute('BEGIN')
    return con


def namespace(source, now):
    # No production imports, main loop, filesystem/log setup or credentials.
    names={'candidates','history','score_candidate','fc_core_validate','fc_core_integer',
           'fc_core_number','fc_core_digest','fc_core_canonical'}
    nodes=[]
    for n in ast.parse(source).body:
        if isinstance(n,ast.FunctionDef) and n.name in names:nodes.append(n)
        elif isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id in ('FC_CORE_SIGNALS','FC_CORE_FIELDS') for t in n.targets):nodes.append(n)
    g={'time':SimpleNamespace(time=lambda:now),'json':json,'math':math,'hashlib':hashlib}
    exec(compile(ast.Module(body=nodes,type_ignores=[]),'reviewed-pure-diagnostics','exec'),g)
    return g


def readiness(con, source, now):
    g=namespace(source,now); rows=g['candidates'](con)
    if len(rows)>60:raise ValueError('candidate bound')
    counts=Counter()
    for row in rows:
        mint,created,_,_,_,pinned=row
        history=g['history'](con,mint)
        latest=con.execute('SELECT pair,ts FROM snapshots WHERE mint=? ORDER BY ts DESC LIMIT 1',(mint,)).fetchone()
        if latest is None:counts['no_stored_pair_snapshot']+=1
        elif now-latest[1]>120:counts['stored_pair_snapshot_older_than_120_seconds']+=1
        elif pinned and latest[0]!=pinned:counts['stored_pair_differs_from_pinned_pair']+=1
        try:
            score,metrics,failed=g['score_candidate'](history)
            if not metrics:
                reason=failed[0] if len(failed)==1 and failed[0] in ('history','base_gate','price_history') else 'other_score_admission_failure'
                counts[reason]+=1;continue
            counts['score_ready']+=1
            prev=con.execute('SELECT alert_level FROM launches WHERE mint=?',(mint,)).fetchone()[0]
            record={'mint':mint,'pair':latest[0] if latest else 'diagnostic-placeholder',
                    'created_ts':int(created//1000),'captured_ts':now,'snapshot_ts':int(history[-1][0]),
                    'points':len(history),'history_seconds':int(history[-1][0]-history[0][0]),
                    'mc':metrics['mc'],'liq':metrics['liq'],'vol1':metrics['vol1'],
                    'score':score,'signals':{k:k not in failed for k in g['FC_CORE_SIGNALS']},
                    'prior_alert_level':prev,'input_sha256':g['fc_core_digest']([list(r) for r in history])}
            g['fc_core_validate'](record,now)
            counts['current_input_validation_passed']+=1
        except ValueError as e:
            reason=str(e) if str(e) in SAFE_REASONS else 'other_value_error'
            counts['input_rejected:'+reason]+=1
        except Exception:
            counts['other_scoring_error']+=1
    return {'selected_candidates':len(rows),'counts':dict(counts),
            'current_snapshot_probe_only':True,'original_failed_cycle_reconstructed':False,
            'provider_pair_availability_not_verified':True}


def diagnose(base=BASE, now=None):
    now=int(time.time()) if now is None else now
    observed={f:hashlib.sha256((base/f).read_bytes()).hexdigest() for f in EXPECTED}
    if observed!=EXPECTED:raise ValueError('deployed source mismatch')
    report={'checked_at':now,'production_changed':False,'pause_cleared':False,
            'provider_requests':0,'ledger_outcomes_read':False,'source_hashes_match':True}
    directory=base/'data'/'forward_capture'
    marker=json.loads((directory/'PAUSED.json').read_text())
    report['pause_observed_ts']=marker.get('observed_ts')
    report['recorded_exception_class']=marker.get('reason') if marker.get('reason') in ('ValueError','OperationalError','IntegrityError','OSError','PermissionError','TypeError','KeyError') else 'other'
    capture=read_only(directory/'capture.sqlite')
    try:
        # Binding and counts only. Do not read event payloads or endpoint values.
        row=capture.execute("SELECT json_extract(body,'$.activation_ts'),json_extract(body,'$.deadline'),json_extract(body,'$.scanner_sha256'),json_extract(body,'$.tracker_sha256') FROM fc_activation WHERE id=1").fetchone()
        report.update(activation_ts=row[0],deadline=row[1],activation_binding_matches=row[2]==observed['early_scout.py'] and row[3]==observed['scout_learning_v2.py'])
        report['event_counts']=dict(capture.execute('SELECT kind,count(*) FROM fc_events GROUP BY kind'))
    finally:capture.rollback();capture.close()
    production=read_only(base/'data'/'early_scout.sqlite')
    try:report['readiness']=readiness(production,(base/'early_scout.py').read_text(),now)
    finally:production.rollback();production.close()
    return report


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--expected-sha256',required=True);args=parser.parse_args()
    if hashlib.sha256(Path(__file__).read_bytes()).hexdigest()!=args.expected_sha256:raise SystemExit('diagnostic source mismatch')
    try:print(json.dumps(diagnose(),sort_keys=True))
    except Exception:raise SystemExit('Diagnostic unavailable; no private exception details emitted')
