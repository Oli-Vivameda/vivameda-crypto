"""Fixed synthetic acceptance; existing local model only, no runtime evidence."""
import argparse,hashlib,json,pathlib,time
import crypto_agent as agent
import factual_guard as guard
PACKET={'memory':{'data':{'generated_at':1791269439,'summary':{'eligible_60m_endpoints':12,'missing_or_incomplete':3},'cases':[{'last_multiple':0.55,'tracked_peak_multiple':2.5}]}},'paper_summary':{'data':{'groups':{'WATCH':{'recorded':0}},'live_execution':False}}}
QUESTIONS=(
 ('date','What is the memory generation date in ISO UTC?','memory.data.generated_at','2026-10-06T06:50:39Z'),
 ('last','What is the last sampled multiple?','memory.data.cases.0.last_multiple','0.55x'),
 ('peak','What is the maximum tracked sampled multiple?','memory.data.cases.0.tracked_peak_multiple','2.5x'),
 ('failure','What is the matched failure endpoint threshold?','thresholds.matched_failure_endpoint','0.55x'),
 ('winner','What is the matched winner endpoint threshold?','thresholds.matched_winner_endpoint','2.00x'),
 ('eligible','How many eligible 60-minute endpoints are supplied?','memory.data.summary.eligible_60m_endpoints','12'),
 ('missing','How many missing or incomplete endpoints are supplied?','memory.data.summary.missing_or_incomplete','3'),
 ('watch','How many WATCH decisions are recorded in the paper summary?','paper_summary.data.groups.WATCH.recorded','0'),
 ('validation','Does predictive validation require live execution?','validation.live_execution_required','false'),
 ('cause','What caused the gaps? Is a specific cause established?','missingness.cause','not established unless explicitly supplied'))
def run(model_call=agent.ask_model):
 known=guard.facts(PACKET);start=time.monotonic();records=[];failure=None
 q='Answer these ten questions by selecting ONE exact formatted_facts field ID for each. Return only JSON {"answers":{"question_id":"field_id",...}}. Do not explain or copy values. A definition describes a metric; when asked for an observed multiple, select its memory.data.cases numeric observation field, not a definitions field or threshold. Questions: '+json.dumps({i:q for i,q,_,_ in QUESTIONS})
 try:
  raw=model_call(q,{'formatted_facts':known,'approved_statements':guard.APPROVED},())
  answers=json.loads(raw)
  if set(answers)!= {'answers'} or not isinstance(answers['answers'],dict) or set(answers['answers'])!={x[0] for x in QUESTIONS}:raise ValueError('acceptance_shape')
  for i,q,field,value in QUESTIONS:
   selected=answers['answers'][i];validated=guard.validate(json.dumps({'facts':[selected],'statements':[]}),known)
   ok=selected==field and validated['evidence_table'][0]['value']==value
   records.append({'question_id':i,'question':q,'expected_field':field,'expected_value':value,'correct':ok})
 except Exception:failure='model_or_validation_failed_closed'
 elapsed=round(time.monotonic()-start,3);correct=sum(r['correct'] for r in records)
 p=pathlib.Path(__file__).resolve().parent
 return {'model':agent.MODEL,'question_count':10,'facts_correct':correct,'invented_explanations':0,'response_time_seconds':elapsed,'response_time_scope':'one batch of ten fixed synthetic questions','passed':correct==10 and failure is None,'failure':failure,'results':records,'fixture_only':True,'free_text_interpretation_verified':False,'mode':'constrained_evidence_selection','candidate_agent_sha256':hashlib.sha256((p/'crypto_agent.py').read_bytes()).hexdigest(),'guard_sha256':hashlib.sha256((p/'factual_guard.py').read_bytes()).hexdigest(),'provider_requests':0,'local_model_requests':1,'production_changed':False}
if __name__=='__main__':
 a=argparse.ArgumentParser();a.add_argument('--local-model',action='store_true');x=a.parse_args()
 if not x.local_model:raise SystemExit('Explicit local-model test required')
 result=run();p=pathlib.Path(__file__).with_name('FACTUAL_ACCEPTANCE.json');p.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,sort_keys=True))
