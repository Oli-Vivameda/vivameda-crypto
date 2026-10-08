"""Owner-run ten-question live gateway acceptance; aggregates only, no permission changes."""
import argparse,collections,hashlib,json,os,pathlib,pwd,subprocess,sys,tempfile,time
HERE=pathlib.Path(__file__).resolve().parent
APP=pathlib.Path('/opt/vivameda-crypto-runtime')
EXPECTED={'crypto_agent.py':'ddd57fea740ce087122482a89ad1ea65d18516f2a077264d0bc6f593b8dd2423','factual_guard.py':'352e9369fd986df447d172b40e3de08f6b4c4fd9bcf9d3d05adbf83cc8d7db74'}
QUESTIONS=(('What is the memory generation date in ISO UTC?','memory.data.generated_at'),('What is the last sampled multiple?','memory.data.cases.0.last_multiple'),('What is the maximum tracked sampled multiple?','memory.data.cases.0.tracked_peak_multiple'),('What is the matched failure endpoint threshold?','thresholds.matched_failure_endpoint'),('What is the matched winner endpoint threshold?','thresholds.matched_winner_endpoint'),('How many eligible 60-minute endpoints are supplied?','memory.data.summary.eligible_60m_endpoints'),('How many missing or incomplete endpoints are supplied?','memory.data.summary.missing_or_incomplete'),('How many WATCH decisions are recorded in the paper summary?','paper_summary.data.groups.WATCH.recorded'),('Does predictive validation require live execution?','validation.live_execution_required'),('What caused the gaps? Is a specific cause established?','missingness.cause'))
CHILD='''import json,sys,time
sys.path.insert(0,'/opt/vivameda-crypto-runtime')
import runtime_gateway as g
q=json.load(sys.stdin)
r=g.call('submit',owner=2,session='crypto-acceptance-directive2',question=q['question'],request_id=q['request_id'])
end=time.monotonic()+360
while r['status'] in ('queued','running'):
 if time.monotonic()>end:raise SystemExit(2)
 time.sleep(.25);r=g.call('get',owner=2,id=r['id'])
if r['status']!='succeeded':raise SystemExit(3)
print(r['answer'])
'''
def main():
 p=argparse.ArgumentParser();p.add_argument('--expected-sha256',required=True);a=p.parse_args()
 if hashlib.sha256(pathlib.Path(__file__).read_bytes()).hexdigest()!=a.expected_sha256:raise SystemExit('Reviewed acceptance helper hash mismatch')
 if os.geteuid()!=0:raise SystemExit('Owner root terminal required; existing authenticated vivameda-agent UID is used')
 receipt=HERE/'LIVE_GATEWAY_ACCEPTANCE.json'
 if receipt.exists():print(receipt.read_text());return
 if any(hashlib.sha256((APP/f).read_bytes()).hexdigest()!=h for f,h in EXPECTED.items()):raise SystemExit('Installed guard hashes differ')
 sys.path.insert(0,str(APP));import crypto_agent as agent;import factual_guard as guard
 modes=collections.Counter();correct=unassessable=failed=unsupported=0;start=time.monotonic()
 for i,(question,field) in enumerate(QUESTIONS):
  # Expected live values stay private. No pilot database, prediction ledger or outcomes are opened.
  packet={'memory':agent.memory(question),'paper_summary':agent.read_evidence('paper_summary.json')}
  known=guard.facts(packet)
  r=subprocess.run(['/usr/sbin/runuser','-u','vivameda-agent','--','/usr/bin/python3','-c',CHILD],input=json.dumps(dict(question='Crypto explain: '+question,request_id='crypto-directive2-live-20261008-'+str(i))),capture_output=True,text=True,timeout=370)
  if r.returncode:failed+=1;continue
  try:
   answer=json.loads(r.stdout)['answer'];table=answer['evidence_table'];modes[answer['mode']]+=1
   unsupported+=sum(row.get('field') not in known or known.get(row.get('field'))!=row.get('value') for row in table)
   if field not in known:unassessable+=1
   else:correct+=any(row.get('field')==field and row.get('value')==known[field] for row in table)
   unsupported+=sum(s not in guard.APPROVED for s in answer.get('supported_statements',[]))
  except (ValueError,KeyError,TypeError):failed+=1
 out=dict(question_count=10,facts_correct=correct,unassessable_questions=unassessable,failed_questions=failed,invented_explanations_or_unsupported_rows=unsupported,answer_modes=dict(modes),passed=correct==10 and not failed and not unsupported and not unassessable,response_time_seconds=round(time.monotonic()-start,3),scope='ten live gateway submissions; live retained daily evidence, not synthetic fixtures',selection_quality_verified=correct==10 and modes.get('validated_evidence_selection',0)==10,free_text_interpretation_verified=False,application_sha256=EXPECTED['crypto_agent.py'],guard_sha256=EXPECTED['factual_guard.py'],permissions_changed=False,pilot_modified=False,provider_requests=0)
 account=pwd.getpwnam('vivameda-engineer');fd,name=tempfile.mkstemp(dir=HERE,prefix='live-acceptance-')
 try:
  os.fchmod(fd,0o600);os.fchown(fd,account.pw_uid,account.pw_gid)
  with os.fdopen(fd,'w') as f:json.dump(out,f,sort_keys=True);f.write('\n');f.flush();os.fsync(f.fileno())
  os.replace(name,receipt)
 finally:
  if os.path.exists(name):os.unlink(name)
 print(json.dumps(out,sort_keys=True))
if __name__=='__main__':main()
