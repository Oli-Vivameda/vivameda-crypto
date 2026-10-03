"""Frozen exploratory one-hour crypto endpoint baseline. No production integration."""
import json,hashlib,pathlib,datetime,math
import numpy as np
ROOT=pathlib.Path(__file__).resolve().parent
FEATURES=['band','pc5','pc1','buy_ratio','vol_mc','liq_change','vol_accel']
def main():
 raw=(ROOT/'fixed_horizon_training_export.json').read_bytes();data=json.loads(raw)
 cfg={'target':'observed market-cap multiple >=2 at 60 minutes, endpoint lateness <=180 seconds','features':FEATURES,'split':'70% chronological unique eligible mints; train labels must precede first test decision','regularization':1.0,'steps':2000,'learning_rate':0.05,'evaluation':'exploratory, previously inspected audit; not sealed or independent forward validation','production':False}
 out=ROOT/'numerical_training_v1';out.mkdir(exist_ok=False)
 (out/'preregistered_config.json').write_text(json.dumps(cfg,indent=2))
 rows=[];seen=set();excluded={}
 def skip(reason):excluded[reason]=excluded.get(reason,0)+1
 for r in sorted(data['rows'],key=lambda x:(x['decision_ts'],x['id'])):
  if r['mint'] in seen:skip('repeat_mint');continue
  if r.get('horizon')!=60 or r.get('coverage_ok')!=1:skip('coverage');continue
  if not 0<=r['lateness']<=180 or r['observed_ts']!=r['decision_ts']+3600+r['lateness']:skip('timing');continue
  f=json.loads(r['features'])
  if any(k not in f or not isinstance(f[k],(float,int)) or not math.isfinite(f[k]) for k in FEATURES):skip('features');continue
  if not isinstance(r['multiple'],(int,float)) or not math.isfinite(r['multiple']) or r['multiple']<=0:skip('outcome');continue
  seen.add(r['mint']);r['x']=[f[k] for k in FEATURES];r['y']=int(r['multiple']>=2);rows.append(r)
 cut=int(len(rows)*.7);test=rows[cut:];start=test[0]['decision_ts'] if test else 0
 train=[r for r in rows[:cut] if r['observed_ts']<start]
 if len(train)<20 or len(test)<10 or len({r['y'] for r in train})<2:raise ValueError('Insufficient training rows or target classes')
 assert not {r['mint'] for r in train}&{r['mint'] for r in test}
 assert max(r['observed_ts'] for r in train)<min(r['decision_ts'] for r in test)
 x=np.array([r['x'] for r in train]);y=np.array([r['y'] for r in train]);mean=x.mean(0);scale=x.std(0);scale[scale==0]=1
 z=np.c_[np.ones(len(x)),(x-mean)/scale];w=np.zeros(z.shape[1]);w[0]=math.log((y.sum()+.5)/(len(y)-y.sum()+.5))
 for _ in range(2000):
  p=1/(1+np.exp(-np.clip(z@w,-40,40)));g=z.T@(p-y)/len(y);g[1:]+=w[1:]/len(y);w-=.05*g
 tx=np.array([r['x'] for r in test]);ty=np.array([r['y'] for r in test]);p=1/(1+np.exp(-np.clip(np.c_[np.ones(len(tx)),(tx-mean)/scale]@w,-40,40)))
 base=float(y.mean())
 def metrics(v):return {'brier':float(np.mean((v-ty)**2)),'log_loss':float(-np.mean(ty*np.log(np.clip(v,1e-8,1-1e-8))+(1-ty)*np.log(np.clip(1-v,1e-8,1-1e-8))))}
 model={'type':'L2 logistic regression','features':FEATURES,'mean':mean.tolist(),'scale':scale.tolist(),'coefficients':w.tolist(),'source_sha256':hashlib.sha256(raw).hexdigest(),'production':False}
 (out/'model.json').write_text(json.dumps(model,indent=2))
 summary={'trained':True,'model_type':model['type'],'language_model_finetuned':False,'eligible_unique_tokens':len(rows),'train_n':len(train),'test_n':len(test),'embargo_excluded':cut-len(train),'train_positive':int(y.sum()),'test_positive':int(ty.sum()),'excluded':excluded,'model_metrics':metrics(p),'base_rate_metrics':metrics(np.full(len(ty),base)),'production_promoted':False,'knowledge_source':'knowledge_cards.json','limitations':['Small selected ALERT sample','Same short market period','Exploratory evaluation; prior outcomes inspected','Market-cap endpoint is not executable return','No calibration or profitability claim']}
 (out/'evaluation.json').write_text(json.dumps(summary,indent=2))
 (out/'test_predictions.json').write_text(json.dumps([{'id':r['id'],'mint':r['mint'],'decision_ts':r['decision_ts'],'observed_ts':r['observed_ts'],'actual':r['y'],'p':float(v)} for r,v in zip(test,p)],indent=2))
 (out/'split_manifest.json').write_text(json.dumps({'train':[r['id'] for r in train],'test':[r['id'] for r in test]},indent=2))
 print(json.dumps(summary,indent=2))
if __name__=='__main__':main()
