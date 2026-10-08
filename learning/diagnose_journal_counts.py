"""Owner-run aggregate journal diagnosis. No writes, network, endpoint values or prediction values."""
import argparse,ast,hashlib,json,math,sqlite3,time
from pathlib import Path
APP=Path('/opt/vivameda-crypto-learning')
SOURCE=Path('/opt/vivameda-crypto-early-scout/data/early_scout.sqlite')
TARGET=Path('/var/lib/vivameda-crypto-learning/learning.sqlite')
EXPECTED={'daily_learning.py':'370ca35a27033b7278f45470f8519e2ea2da0e8a5a00707d40e496b9bc00f468','policy.json':'b77dbbcc94562894529b5247dcfe5b1834d6abd5645ea19c61e5ca9465367d36'}
def bundle():
 root=Path(__file__).resolve().parent
 names=('diagnose_journal_counts.py','test_diagnose_journal_counts.py')
 return hashlib.sha256(b''.join(n.encode()+b'\0'+(root/n).read_bytes()+b'\0' for n in names)).hexdigest()
def readonly(path):
 c=sqlite3.connect('file:'+str(Path(path).resolve())+'?mode=ro',uri=True,timeout=.1)
 c.row_factory=sqlite3.Row;c.execute('PRAGMA query_only=ON');c.execute('BEGIN')
 started=time.monotonic();c.set_progress_handler(lambda:int(time.monotonic()-started>10),1000)
 return c
def pure(source):
 names={'finite','snapshot_features','decision'}
 nodes=[n for n in ast.parse(source).body if isinstance(n,ast.FunctionDef) and n.name in names]
 g={'math':math,'CHECKS':('wallet_clusters','developer_history','top_holder_ownership','wallet_age','token_controls','liquidity_control','trading_mechanics')}
 if len(nodes)!=3:raise ValueError('source_shape')
 exec(compile(ast.Module(body=nodes,type_ignores=[]),'verified_pure_journal_functions','exec'),g)
 return g
def collect(s,t,p,activation,functions,now):
 # Opaque exclusion membership only; never project prediction rows, bodies, values or labels.
 member="EXISTS(SELECT 1 FROM pl_predictions x WHERE x.mint=d.mint)"
 daily=[dict(r) for r in s.execute("SELECT date(d.decision_ts,'unixepoch') AS day_utc,d.source AS case_source,count(*) AS retained_cases FROM v2_cases d WHERE d.decision_ts>=? AND d.decision_ts<=? GROUP BY day_utc,d.source ORDER BY day_utc,d.source",(activation,now))]
 gates=[dict(r) for r in s.execute("SELECT date(d.decision_ts,'unixepoch') AS day_utc,count(*) AS retained_alert_cases,sum(l.mint IS NULL) AS missing_launch_join,sum(l.mint IS NOT NULL AND "+member+") AS holdout_membership_excluded,sum(l.mint IS NOT NULL AND NOT "+member+") AS after_join_and_holdout FROM v2_cases d LEFT JOIN launches l ON l.mint=d.mint WHERE d.source='ALERT' AND d.decision_ts>=? AND d.decision_ts<=? GROUP BY day_utc ORDER BY day_utc",(activation,now))]
 cutoff=max(activation,now-p['journal_max_delay_seconds'])
 q="FROM v2_cases d JOIN launches l ON l.mint=d.mint WHERE d.source='ALERT' AND d.decision_ts>=? AND d.decision_ts<=? AND NOT "+member
 n=s.execute("SELECT count(*) "+q,(cutoff,now)).fetchone()[0]
 rows=s.execute("SELECT d.mint,d.id,d.decision_ts,d.score,l.pinned_pair "+q+" ORDER BY d.decision_ts,d.id LIMIT ?",(cutoff,now,p['max_journal_per_pass'])).fetchall()
 counts={'eligible_query_before_limit':n,'excluded_by_pass_limit_now':max(0,n-len(rows)),'selected_by_current_query':len(rows),'already_recorded':0,'new_input_rows':0,'fresh_snapshot':0,'valid_features':0,'fresh_scanner_review':0,'bound_screening_identity':0,'all_seven_pass':0}
 reasons={};actions={'ENTER_REVIEW':0,'WATCH':0,'SKIP':0}
 allowed={'stale_snapshot','insufficient_snapshot_history','nonfinite_snapshot','invalid_snapshot','stale_or_missing_scanner_review','stale_or_missing_screening','mint_or_chain_mismatch','pair_mismatch_or_missing'}
 for row in rows:
  mint=row['mint']
  if t.execute('SELECT 1 FROM decisions WHERE mint=?',(mint,)).fetchone():counts['already_recorded']+=1;continue
  counts['new_input_rows']+=1;features={};checks={};failure=None
  raw=[list(r) for r in s.execute('SELECT ts,price,mc,liq,vol_m5,vol_h1,buys_m5,sells_m5,buys_h1,sells_h1,pc_m5,pc_h1 FROM snapshots WHERE mint=? AND ts BETWEEN ? AND ? ORDER BY ts',(mint,now-2100,now))]
  try:
   if not raw or now-raw[-1][0]>p['snapshot_max_age_seconds']:raise ValueError('stale_snapshot')
   counts['fresh_snapshot']+=1;features=functions['snapshot_features'](raw);counts['valid_features']+=1
   saved=s.execute('SELECT review FROM prealert_reviews WHERE mint=? AND checked_at BETWEEN ? AND ? ORDER BY checked_at DESC LIMIT 1',(mint,now-p['screening_max_age_seconds'],now)).fetchone()
   if not saved:raise ValueError('stale_or_missing_scanner_review')
   evidence=json.loads(saved[0]);stamp=evidence.get('checked_at')
   if not functions['finite'](stamp) or not 0<=now-stamp<=p['screening_max_age_seconds']:raise ValueError('stale_or_missing_screening')
   counts['fresh_scanner_review']+=1
   if evidence.get('mint')!=mint or evidence.get('chain')!='solana':raise ValueError('mint_or_chain_mismatch')
   if evidence.get('pair')!=row['pinned_pair']:raise ValueError('pair_mismatch_or_missing')
   counts['bound_screening_identity']+=1
   for k,v in evidence.get('checks',{}).items():
    if not isinstance(v,dict):continue
    observed=v.get('observed_at');refs=v.get('evidence_refs')
    fresh=functions['finite'](observed) and 0<=now-observed<=p['screening_max_age_seconds']
    checks[k]=v.get('status') if fresh and isinstance(refs,list) and refs and all(isinstance(x,str) and x.strip() for x in refs) else 'UNKNOWN'
   if all(checks.get(k)=='PASS' for k in functions['CHECKS']):counts['all_seven_pass']+=1
  except (ValueError,FileNotFoundError,PermissionError,TypeError,KeyError,AttributeError) as e:
   code=str(e);failure=code if code in allowed else 'schema_or_evidence_shape'
  action,reason=functions['decision'](features,checks,row['score'],p)
  if failure:action='WATCH';reason=failure
  actions[action]+=1;reasons[reason]=reasons.get(reason,0)+1
 recorded={r[0]:r[1] for r in t.execute("SELECT json_extract(body,'$.decision'),count(*) FROM decisions GROUP BY json_extract(body,'$.decision')")}
 return {'checked_at':now,'activation_ts':activation,'source_case_counts_per_day':daily,'source_gate_counts_per_day':gates,'current_query_cutoff_ts':cutoff,'current_pass_gates':counts,'current_pass_would_record_actions':actions,'current_pass_reasons':reasons,'recorded_paper_decisions':{k:recorded.get(k,0) for k in actions},'historic_actual_pass_input_counts':'not_retained; daily counts are retained source cases, not reconstructed polls','historical_timing_drop_counts':'not_identifiable_without_poll_input_audit','production_modified':False,'paper_rows_written':0,'provider_requests':0,'ledger_prediction_values_read':False,'ledger_labels_read':False,'holdout_membership_only':True}
def run():
 observed={n:hashlib.sha256((APP/n).read_bytes()).hexdigest() for n in EXPECTED}
 if observed!=EXPECTED:raise ValueError('installed_source_mismatch')
 p=json.loads((APP/'policy.json').read_text());functions=pure((APP/'daily_learning.py').read_text())
 s=t=None
 try:
  s=readonly(SOURCE);t=readonly(TARGET)
  a=t.execute("SELECT json_extract(body,'$.activated_at') FROM activation WHERE id=1").fetchone()
  if a is None or type(a[0]) is not int:raise ValueError('activation_shape')
  result=collect(s,t,p,a[0],functions,int(time.time()));result['source_hashes_match']=True;return result
 finally:
  for c in (s,t):
   if c is not None:c.rollback();c.close()
if __name__=='__main__':
 a=argparse.ArgumentParser();a.add_argument('--hash',action='store_true');a.add_argument('--expected-sha256');x=a.parse_args()
 if x.hash:print(bundle())
 elif x.expected_sha256!=bundle():raise SystemExit('Reviewed diagnosis bundle mismatch; no database opened.')
 else:
  try:print(json.dumps(run(),sort_keys=True,allow_nan=False))
  except Exception:raise SystemExit('Count diagnosis unavailable; no private details displayed.')

