"""Diagnostic audit of retained production calls. Never synthesizes checkpoints."""
import csv,datetime,hashlib,json,math,re
from pathlib import Path
ROOT=Path(__file__).resolve().parent
EVENT=re.compile(r'^(\d{4}-\d\d-\d\d \d\d:\d\d:\d\d),\d+ INFO ALERT (\S+) level=(\d+) score=(\d+)')
CHECK=re.compile(r'v2 checkpoint id=(\S+) horizon_min=(\d+) observed_ts=(\d+) lateness_s=(\d+) multiple=([\d.]+)')
def event(line):
    m=EVENT.search(line)
    if not m:return None
    date,mint,level,score=m.groups()
    ts=int(datetime.datetime.strptime(date,'%Y-%m-%d %H:%M:%S').replace(tzinfo=datetime.timezone.utc).timestamp())
    return {'id':f'{mint}:alert:{ts}','mint':mint,'decision_ts':ts,'decision_utc':date+'Z','level':int(level),'logged_score':int(score)}
def dimensions(c):
    entry=c.get('entry_mc')
    if not isinstance(entry,(float,int)) or not math.isfinite(entry) or entry<=0:
        return {'assessment':'INVALID_ENTRY','horizon_verdict':'UNSCORED'}
    peak=c.get('max_mult');low=c.get('min_mult');last=c.get('last_mc')
    if any(not isinstance(v,(int,float)) or not math.isfinite(v) or v<0 for v in (peak,low,last)):
        return {'assessment':'INVALID_STATE','horizon_verdict':'UNSCORED'}
    last/=entry
    liq=c.get('last_liq')
    liquidity_missing=not isinstance(liq,(int,float)) or not math.isfinite(liq)
    failed=last<=.55 or (not liquidity_missing and liq<=5000)
    hit=peak>=2
    result='PEAK_THEN_FAILURE_OBSERVED' if hit and failed else 'PEAK_2X_OBSERVED' if hit else 'FAILURE_OBSERVED' if failed else 'NO_2X_OBSERVED_YET'
    return {'assessment':result,'peak_multiple':peak,'trough_multiple':low,
     'last_multiple':last,'last_liquidity':liq,'failure_observed':failed,
     'liquidity_missing':liquidity_missing,'tracking_state':c.get('status'),
     'horizon_verdict':'UNSCORED_NO_COMPLETE_PATH_EXPORTED','realized_profit_verified':False}
def checkpoints(lines,cases):
    by={c['id']:c for c in cases};out=[];seen=set()
    for line in lines:
        m=CHECK.search(line)
        if not m:continue
        cid,h,ts,late,mult=m.groups();h,ts,late=int(h),int(ts),int(late)
        c=by.get(cid);key=(cid,h)
        if key in seen:continue
        seen.add(key)
        valid=c is not None and 0<=late<=180 and ts==c['decision_ts']+h*60+late
        out.append({'id':cid,'horizon_min':h,'observed_ts':ts,'lateness_s':late,
         'multiple_rounded_4dp':float(mult),'timing_valid':valid,
         'endpoint_observed':valid,'complete_path_verified':False,
         'training_eligible':False,'reason':'Checkpoint log only; full observations/coverage unavailable'})
    return out
def build():
    raw=(ROOT/'capture_20261002.json').read_bytes();cap=json.loads(raw)
    cs=cap['cases'];by={c['id']:c for c in cs}
    events=[e for s in cap['log_capture']['scout']['lines'] if (e:=event(s))]
    logs=checkpoints(cap['log_capture']['learning_v2']['lines'],cs)
    calls=[]
    for e in events:
        c=by.get(e['id'])
        row=dict(e,case_export_matched=c is not None)
        if c:
            row.update(symbol=c['symbol'],regime=c['regime'],entry_mc=c['entry_mc'],reconstructed_score=c['score'],
             logged_reconstructed_score_equal=e['logged_score']==c['score'],**dimensions(c))
        else:
            row.update(symbol='unavailable',assessment='MISSING_SEPARATE_CALL_HISTORY',horizon_verdict='UNSCORED')
        calls.append(row)
    summary={}
    for source in ('ALERT','SHADOW'):
        rows=[c for c in cs if c['source']==source]
        ds=[dimensions(c) for c in rows]
        summary[source]={'cases':len(rows),'unique_mints':len({c['mint'] for c in rows}),
         'observed_peak_2x':sum(d.get('peak_multiple',0)>=2 for d in ds),
         'observed_peak_3x':sum(d.get('peak_multiple',0)>=3 for d in ds),
         'observed_peak_5x':sum(d.get('peak_multiple',0)>=5 for d in ds),
         'last_observed_at_least_2x':sum(d.get('last_multiple',0)>=2 for d in ds),
         'failure_observed':sum(d.get('failure_observed',False) for d in ds),
         'peak_2x_and_failure':sum(d.get('assessment')=='PEAK_THEN_FAILURE_OBSERVED' for d in ds)}
    score_disagreement=[c['id'] for c in calls if c.get('logged_reconstructed_score_equal') is False]
    matched=sum(c['case_export_matched'] for c in calls)
    result={'scope':'all 76 alert lines in returned retained log; 92 retained V2 cases at frozen capture, not lifetime completeness guarantee',
      'capture_sha256':hashlib.sha256(raw).hexdigest(),'capture_time':cap['captured_at'],
      'production_hashes':cap['production_hashes'],'call_events':len(events),'matched_events':matched,
      'missing_separate_call_histories':len(events)-matched,'score_disagreements':score_disagreement,
      'descriptive_summary':summary,'calls':calls,
      'cases':[dict(c,audit=dimensions(c)) for c in cs],'checkpoint_logs':logs,
      'training_rows_exported':0,'live_rule_deployed':False,'production_thresholds':[8,10]}
    (ROOT/'audit.json').write_text(json.dumps(result,indent=2)+'\n')
    fields=['id','mint','decision_utc','level','logged_score','symbol','regime','entry_mc','assessment','peak_multiple','trough_multiple','last_multiple','last_liquidity','horizon_verdict']
    with (ROOT/'calls.csv').open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=fields,extrasaction='ignore');w.writeheader();w.writerows(calls)
    lines=['# Meme-call audit — 2 October 2026','',
      f"Frozen capture {cap['captured_at']}. SHA-256 {result['capture_sha256']}.",
      f"Retained log: {len(events)} calls, {matched} exact call matches, {len(events)-matched} missing separate call histories. V2: {len(cs)} cases.",
      'These are diagnostic observations, not a backtest win rate, trade P&L or complete 24-hour results. All exported cases are still ACTIVE at capture. Logs and case export were captured sequentially.',
      'Older case states were first tracked after their decision time. No state-only maximum/minimum proves a complete historical path. Missing older paths are not reconstructed.',
      '', '| Source | Cases | Observed peak ≥2× | ≥3× | ≥5× | Last observed ≥2× | Failure observed | Peak ≥2× and failure |',
      '|---|---:|---:|---:|---:|---:|---:|---:|']
    for source,s in summary.items():
        lines.append('| '+source+' | '+' | '.join(str(s[k]) for k in ('cases','observed_peak_2x','observed_peak_3x','observed_peak_5x','last_observed_at_least_2x','failure_observed','peak_2x_and_failure'))+' |')
    lines+=['','Failure diagnostic: latest observed MC/entry ≤0.55 or latest liquidity ≤$5,000. Peak hits and failures overlap. This does not prove a rug pull or an executable fill.',
      f"Logged and reconstructed scores disagree for {len(score_disagreement)} matched calls. Do not train on the reconstructed score as if it were the emitted score.",
      f"Retained V2 log exports {len(logs)} checkpoint records; {sum(r['timing_valid'] for r in logs)} pass timestamp identity. Full DB reports more endpoints; missing log rows are not fabricated. Full-path coverage is unavailable through the current export; zero training labels are exported.",
      '', '## Every retained production call', '',
      '| UTC call time | Mint | Level / emitted score | Symbol | Diagnostic | Peak | Trough | Last |',
      '|---|---|---|---|---|---:|---:|---:|']
    for c in calls:
        num=lambda k:f"{c[k]:.3f}×" if k in c else 'unavailable'
        lines.append(f"| {c['decision_utc']} | {c['mint']} | {c['level']} / {c['logged_score']} | {c['symbol']} | {c['assessment']} | {num('peak_multiple')} | {num('trough_multiple')} | {num('last_multiple')} |")
    lines+=['','## Same-token earlier observation versus later alert','',
      'SHADOW captures are observations, not sent calls or executable recommendations. Selected pairs motivate hypotheses; they are not an unbiased sample or a strategy backtest.',
      '| Token | Shadow-to-alert minutes | Entry MC increase | Shadow observed peak | Alert observed peak |',
      '|---|---:|---:|---:|---:|']
    for c in cs:
        if c['source']!='ALERT':continue
        shadow=by.get(c['mint']+':shadow')
        if not shadow or shadow['decision_ts']>=c['decision_ts']:continue
        if c['symbol'] not in ('AUTONOM','Library','OnionWeb','SAM','wwg'):continue
        lines.append(f"| {c['symbol']} | {(c['decision_ts']-shadow['decision_ts'])/60:.2f} | {(c['entry_mc']/shadow['entry_mc']-1)*100:.1f}% | {shadow['max_mult']:.3f}× | {c['max_mult']:.3f}× |")
    lines+=['','## Findings and limits','',
      'Large observed winners coexist with frequent severe collapses. Higher score is not a calibrated success probability. Entry timing and survival deserve separate challenger tests.',
      'AUTONOM/Library/OnionWeb suggest testing earlier qualification; lowering gates could also admit Vortex-like collapses. Freeze an early candidate using decision-time features and compare forward before changing alerts.',
      'No unique-wallet/bundle/security history is exported. Volume and transaction counts cannot establish genuine independent demand. Unknown security cannot become a pass.',
      'Retained log begins 1 October 2026 at 13:00 UTC with service startup. Log rotation, older deployments, other monitors and earlier chat recommendations are outside this verified scope.',
      'Required next instrumentation: append-only emitted-call ledger including exact score/features/pair/security/data timestamps and source hash; scoped read-only export of call features, v2_observations, outcomes and horizon coverage. Production last_alert_ts is not a complete call ledger.',
      'Rules in AGENT_LEARNING_RULES.md are saved policy and executable audit safeguards; no live production or V2 service code or model weights were changed.']
    (ROOT/'audit.md').write_text('\n'.join(lines)+'\n')
    print(json.dumps({k:result[k] for k in ('call_events','matched_events','missing_separate_call_histories','descriptive_summary','training_rows_exported')},indent=2))
if __name__=='__main__':build()

