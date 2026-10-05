"""Prospective paper endpoints. No training, execution, retrospective backfill or network."""
import argparse,json,math,sqlite3,time
from pathlib import Path
from daily_learning import canonical,digest,finite,readonly,local_db,verify_events,event,atomic,journal
HORIZON=3600
LATENESS=180
SCHEMA='crypto-paper-endpoints-v1'
def setup(c):
 c.execute('CREATE TABLE IF NOT EXISTS paper_endpoints(mint TEXT PRIMARY KEY,body TEXT NOT NULL)')
 for op in ('UPDATE','DELETE'):
  c.execute(f"CREATE TRIGGER IF NOT EXISTS paper_endpoints_no_{op} BEFORE {op} ON paper_endpoints BEGIN SELECT RAISE(ABORT,'append only'); END")
 c.commit()
def classify(body,rows,now):
 target=body['decision_ts']+HORIZON
 if now<target:return None
 result={'schema':SCHEMA,'mint':body['mint'],'paper_decision':body['decision'],'decision_ts':body['decision_ts'],'target_ts':target,'recorded_ts':now,'decision_sha256':digest(body),'live_execution':False,'filled':False,'status':'MISSING','reason':'deadline_missed_no_backfill'}
 if now>target+LATENESS:return result
 entry=body.get('source_snapshot',[])
 if not entry or len(entry[-1])<4:return dict(result,reason='missing_saved_baseline')
 baseline=entry[-1];start=baseline[0];mc=baseline[2]
 if not finite(start) or not 0<=body['decision_ts']-start<=120 or not finite(mc) or mc<=0:return dict(result,reason='invalid_saved_baseline')
 if not rows or rows[-1][0]<target:return None
 # Use the earliest retained observation at/after target, discovered before deadline.
 end=next((r for r in rows if target<=r[0]<=now),None)
 if end is None:return None
 ordered=[baseline]+[r for r in rows if start<r[0]<=end[0]]
 if any(len(r)<4 or not all(finite(v) and v>0 for v in r[1:4]) for r in ordered):return dict(result,reason='invalid_market_observation')
 times=[r[0] for r in ordered]
 if any(not finite(t) for t in times) or times!=sorted(set(times)):return dict(result,reason='invalid_observation_order')
 gap=max(b-a for a,b in zip(times,times[1:])) if len(times)>1 else HORIZON
 result.update(observed_ts=end[0],lateness=end[0]-target,max_gap_seconds=gap,baseline_snapshot_ts=start,samples=len(ordered),observations_sha256=digest(ordered))
 if end[0]-target>LATENESS or gap>180:return dict(result,reason='incomplete_coverage')
 return dict(result,status='ELIGIBLE',reason='timely_observed_market_endpoint',market_cap_multiple=end[2]/mc,price_multiple=end[1]/baseline[1],endpoint_liquidity=end[3],note='Observed market path only: no quote, fill, exit, fee or realized PnL inferred.')
def wilson(k,n):
 if not n:return None
 z=1.959963984540054;p=k/n;den=1+z*z/n;center=(p+z*z/(2*n))/den;half=z*math.sqrt(p*(1-p)/n+z*z/(4*n*n))/den
 return {'rate':p,'ci95':[max(0,center-half),min(1,center+half)],'events':k,'n':n,'method':'Wilson; descriptive, no independence or causal claim'}
def report(c,now):
 groups={}
 for action in ('ENTER_REVIEW','WATCH','SKIP'):
  decisions=[json.loads(r[0]) for r in c.execute('SELECT body FROM decisions') if json.loads(r[0])['decision']==action]
  outcomes=[json.loads(r[0]) for r in c.execute('SELECT body FROM paper_endpoints') if json.loads(r[0])['paper_decision']==action]
  valid=[o for o in outcomes if o['status']=='ELIGIBLE'];pending=sum(b['decision_ts']+HORIZON+LATENESS>=now and not any(o['mint']==b['mint'] for o in outcomes) for b in decisions)
  groups[action]={'recorded':len(decisions),'eligible':len(valid),'pending':pending,'missing':sum(o['status']=='MISSING' for o in outcomes),'excluded_holdout':sum(o['status']=='EXCLUDED_HOLDOUT' for o in outcomes),'endpoint_ge_2':wilson(sum(o['market_cap_multiple']>=2 for o in valid),len(valid)),'endpoint_le_055':wilson(sum(o['market_cap_multiple']<=.55 for o in valid),len(valid))}
 return {'schema':SCHEMA,'generated_at':now,'groups':groups,'weights_updated':False,'policy_changed':False,'live_execution':False,'comparison':'Observational groups selected by fixed policy, not randomized or matched treatment effects. No profitable edge claim.','training_status':'Collect prospective labels; no fit or model promotion. Historical matched reviews are not these labels.'}
def evaluate(source,c,state,now=None):
 now=int(time.time()) if now is None else now;setup(c);verify_events(c)
 for raw, in c.execute('SELECT body FROM decisions ORDER BY created_ts').fetchall():
  body=json.loads(raw);mint=body['mint']
  if c.execute('SELECT 1 FROM paper_endpoints WHERE mint=?',(mint,)).fetchone():continue
  if now<body['decision_ts']+HORIZON:continue
  # Exclusion checked before any market outcomes are read.
  if source.execute('SELECT 1 FROM pl_predictions WHERE mint=? LIMIT 1',(mint,)).fetchone():
   value={'schema':SCHEMA,'mint':mint,'paper_decision':body['decision'],'decision_ts':body['decision_ts'],'recorded_ts':now,'decision_sha256':digest(body),'status':'EXCLUDED_HOLDOUT','live_execution':False}
  else:
   rows=[]
   if now<=body['decision_ts']+HORIZON+LATENESS:
    start=body.get('source_snapshot',[[body['decision_ts']]])[-1][0]
    rows=[list(r) for r in source.execute('SELECT ts,price,mc,liq FROM snapshots WHERE mint=? AND ts>? AND ts<=? ORDER BY ts',(mint,start,now))]
   value=classify(body,rows,now)
  if value is None:continue
  c.execute('BEGIN IMMEDIATE')
  try:
   c.execute('INSERT OR IGNORE INTO paper_endpoints VALUES(?,?)',(mint,canonical(value)))
   if c.execute('SELECT changes()').fetchone()[0]:event(c,'paper_endpoint',value)
   c.commit()
  except BaseException:c.rollback();raise
 summary=report(c,now);atomic(Path(state)/'paper_summary.json',summary);return summary

def main():
 a=argparse.ArgumentParser();a.add_argument('--source',required=True);a.add_argument('--state',required=True);a.add_argument('--journal-first',action='store_true');x=a.parse_args();p=json.loads(Path(__file__).with_name('policy.json').read_text());state=Path(x.state);c,activation=local_db(state/'learning.sqlite',p)
 with readonly(x.source) as s:
  if x.journal_first:journal(s,c,state,p,activation,None)
  r=evaluate(s,c,state)
 print(canonical(r))
if __name__=='__main__':main()
