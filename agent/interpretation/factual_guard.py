"""Deterministic evidence formatting and fail-closed model fact selection."""
import datetime,hashlib,json,math,pathlib,re,time
MODEL='qwen3:4b-instruct-2507-q4_K_M'
THRESHOLDS={'matched_failure_endpoint':'0.55x','matched_winner_endpoint':'2.00x','minimum_score':'8','maximum_band':'0.25','minimum_volume_acceleration':'1.20','minimum_liquidity_change':'-0.10'}
APPROVED=('Last sampled multiple and maximum tracked sampled multiple are distinct; neither is realized profit.','Held-out forward paper observations can test predictive performance without live execution.','Missing from this bounded packet does not establish that evidence is globally nonexistent.')
def format_value(key,value):
 if value is None:return 'not supplied'
 if type(value) is bool:return 'true' if value else 'false'
 if type(value) in (int,float):
  if not math.isfinite(value):raise ValueError('nonfinite_evidence')
  if key.endswith('_ts') or key in ('generated_at','checked_at','activated_at','deadline','observed_at'):
   return datetime.datetime.fromtimestamp(value,datetime.timezone.utc).isoformat().replace('+00:00','Z')
  if 'multiple' in key or key.endswith('_endpoint'):return format(value,'.8g')+'x'
  return str(value)
 if isinstance(value,str):return value
 raise ValueError('unsupported_scalar')
def facts(packet):
 out={}
 def walk(value,path,key=''):
  if isinstance(value,dict):
   for k,v in sorted(value.items()):
    if k in ('sha256','mint','pair','symbol','name','matched_examples'):continue
    walk(v,path+'.'+k if path else k,k)
  elif isinstance(value,list):
   for i,v in enumerate(value):walk(v,path+'.'+str(i),key)
  else:out[path]=format_value(key,value)
 walk(packet,'')
 for k,v in THRESHOLDS.items():out['thresholds.'+k]=v
 out['definitions.last_multiple']='definition only; observations are fields ending .last_multiple'
 out['definitions.tracked_peak_multiple']='definition only; observations are fields ending .tracked_peak_multiple'
 out['validation.live_execution_required']='false'
 out['missingness.cause']='not established unless explicitly supplied'
 if len(out)>400 or sum(len(k)+len(v) for k,v in out.items())>16000:raise ValueError('evidence_bound')
 return out
def validate(raw,known):
 answer=json.loads(raw)
 if not isinstance(answer,dict) or set(answer)!= {'facts','statements'}:raise ValueError('answer_schema')
 ids=answer['facts'];statements=answer['statements']
 if not isinstance(ids,list) or not 1<=len(ids)<=30 or len(ids)!=len(set(ids)) or any(not isinstance(k,str) or k not in known for k in ids):raise ValueError('unsupported_fact')
 if not isinstance(statements,list) or len(statements)>3 or any(s not in APPROVED for s in statements):raise ValueError('unsupported_explanation')
 # Exact field/value rendering prevents a known number from being attached to a wrong field.
 table=[{'field':k,'value':known[k]} for k in ids]
 rendered='\n'.join(x['field']+': '+x['value'] for x in table)+'\n'+'\n'.join(statements)
 permitted='\n'.join(k+': '+v for k,v in known.items())+'\n'+'\n'.join(APPROVED)
 numeric=r'(?<![A-Za-z])[-+]?\d+(?:\.\d+)?(?:x)?'
 if not set(re.findall(numeric,rendered))<=set(re.findall(numeric,permitted)):raise ValueError('unsupported_number')
 dates=r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?Z'
 if not set(re.findall(dates,rendered))<=set(re.findall(dates,permitted)):raise ValueError('unsupported_date')
 return {'evidence_table':table,'supported_statements':statements}
def accepted(base):
 try:
  p=pathlib.Path(base);d=json.loads((p/'FACTUAL_ACCEPTANCE.json').read_text())
  return d['model']==MODEL and d['facts_correct']==10 and d['question_count']==10 and d['invented_explanations']==0 and d['candidate_agent_sha256']==hashlib.sha256((p/'crypto_agent.py').read_bytes()).hexdigest() and d['guard_sha256']==hashlib.sha256((p/'factual_guard.py').read_bytes()).hexdigest()
 except Exception:return False
def explain(question,packet,model_call,base,force_table=False):
 start=time.monotonic();known=facts(packet)
 fallback={'mode':'evidence_table_only','evidence_table':[{'field':k,'value':v} for k,v in known.items()],'supported_statements':[],'factual_acceptance_passed':False}
 if force_table or not accepted(base):return dict(fallback,response_time_seconds=round(time.monotonic()-start,3))
 try:
  q=question+'\nReturn only JSON with facts (relevant exact field IDs) and statements (exact approved sentences). No new prose, numbers, dates or explanations.'
  raw=model_call(q,{'formatted_facts':known,'approved_statements':APPROVED},())
  result=validate(raw,known);result.update(mode='validated_evidence_selection',factual_acceptance_passed=True,response_time_seconds=round(time.monotonic()-start,3));return result
 except Exception:return dict(fallback,validation='failed_closed',response_time_seconds=round(time.monotonic()-start,3))
