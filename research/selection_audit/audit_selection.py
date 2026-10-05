"""Exploratory historical ALERT selection audit; never changes production or ledger."""
import argparse, collections, hashlib, json, math, pathlib, statistics

def finite(x): return type(x) in (int,float) and math.isfinite(x)

def eligible(r):
    f=r['features']
    return (all(finite(f.get(k)) for k in ('points','history_min','mc','liq','vol1'))
        and f['points']>=4 and f['history_min']>=10 and 30000<=f['mc']<=750000
        and f['liq']>=25000 and f['vol1']>=20000)

def endpoint(r,h):
    o=r.get('outcomes',{}).get(str(h))
    if not o:return None,'missing_endpoint'
    ts=r['decision_ts']; late=o.get('lateness'); observed=o.get('observed_ts')
    if not finite(late) or not 0<=late<=180 or observed!=ts+h*60+late:
        return None,'invalid_timing'
    if (o.get('metric_ts')!=observed or o.get('coverage_ok')!=1
        or not finite(o.get('max_gap')) or not 0<=o['max_gap']<=180):
        return None,'incomplete_coverage'
    if not finite(o.get('multiple')) or o['multiple']<=0:
        return None,'invalid_outcome'
    return o['multiple'],'eligible'

def first_alerts(rows):
    by={}
    for r in sorted(rows,key=lambda r:(r['decision_ts'],r['id'])):
        if r['source']=='ALERT':by.setdefault(r['mint'],r)
    return list(by.values())

def match(rows):
    alerts=first_alerts(rows); first={r['mint']:r['decision_ts'] for r in alerts}
    shadows=[r for r in rows if r['source']=='SHADOW' and eligible(r)]
    pairs=[]; unmatched=[]
    # Outcome fields are never consulted during matching.
    for a in alerts:
        if not eligible(a):unmatched.append((a,'alert_ineligible'));continue
        choices=[]
        for s in shadows:
            if s['mint']==a['mint'] or not 0<=a['decision_ts']-s['decision_ts']<=300:
                continue
            # Control must be unalerted at index time; a later alert is permitted.
            if first.get(s['mint'],float('inf'))<=a['decision_ts']:continue
            if s['regime']!=a['regime']:continue
            mc=abs(math.log(s['features']['mc']/a['features']['mc']))
            liq=abs(math.log(s['features']['liq']/a['features']['liq']))
            if mc>math.log(2) or liq>math.log(2):continue
            choices.append((mc+liq+(a['decision_ts']-s['decision_ts'])/300,s['id'],s))
        if choices:pairs.append((a,min(choices,key=lambda x:(x[0],x[1]))[2]))
        else:unmatched.append((a,'no_comparable_stored_shadow'))
    return pairs,unmatched

def summary(values):
    return {'n':len(values),'median':statistics.median(values) if values else None,
        'mean':statistics.mean(values) if values else None}

def audit(data):
    if data.get('schema')!='crypto-selection-history-v1' or data.get('live_ledger_results_read') is not False:
        raise ValueError('Reviewed historical export required')
    rows=data['cases']; cutoff=data['cutoff_ts']
    if any(r['source'] not in ('ALERT','SHADOW') or r['decision_ts']+21780>=cutoff for r in rows):
        raise ValueError('Active-cohort or immature row refused')
    alerts=first_alerts(rows); pairs,unmatched=match(rows)
    groups={}
    for source,rs in [('ALERT',alerts),('SHADOW',[r for r in rows if r['source']=='SHADOW'])]:
        groups[source]={'cases':len(rs),'score_gate_eligible':sum(eligible(r) for r in rs),'horizons':{}}
        for h in (60,180,360):
            counts=collections.Counter(); vals=[]
            for r in rs:
                value,why=endpoint(r,h);counts[why]+=1
                if value is not None:vals.append(value)
            groups[source]['horizons'][str(h)]={'coverage':dict(counts),'endpoint_multiple':summary(vals),
                'observed_endpoint_2x':sum(v>=2 for v in vals)}
    paired={}
    for h in (60,180,360):
        complete=[]; missing=collections.Counter()
        for a,s in pairs:
            av,ar=endpoint(a,h);sv,sr=endpoint(s,h)
            if av is None or sv is None:missing[ar+' / '+sr]+=1
            else:complete.append((av,sv))
        paired[str(h)]={'complete_pairs':len(complete),'excluded_pairs':dict(missing),
            'alert_endpoint_multiple':summary([a for a,s in complete]),
            'control_endpoint_multiple':summary([s for a,s in complete]),
            'paired_multiple_difference':summary([a-s for a,s in complete]),
            'alert_2x':sum(a>=2 for a,s in complete),'control_2x':sum(s>=2 for a,s in complete)}
    features={k:summary([r['features'][k] for r in alerts if finite(r['features'].get(k))]) for k in ('pc1','pc5','band','net')}
    checks={'h1_not_extended':('pc1',-8,22),'m5_not_extended':('pc5',-5,10),
        'band_compact':('band',0,.25),'net_constructive':('net',-.10,.20)}
    signals={}
    for name,(key,lo,hi) in checks.items():
        vals=[r['features'][key] for r in alerts if finite(r['features'].get(key))]
        signals[name]={'known':len(vals),'pass':sum(lo<=v<=hi for v in vals),'unknown':len(alerts)-len(vals)}
    use=collections.Counter(s['mint'] for a,s in pairs)
    return {'schema':'crypto-selection-audit-v1','cutoff_utc':data['cutoff_utc'],
        'exploratory':True,'prospective_validation':False,'production_changed':False,
        'live_ledger_results_read':False,'historical_groups':groups,
        'alert_feature_distributions':features,'reconstructed_signal_passes':signals,
        'matching':{'alert_tokens':len(alerts),'matched':len(pairs),
            'unmatched_reasons':dict(collections.Counter(why for a,why in unmatched)),
            'unique_controls':len(use),'max_control_reuse':max(use.values(),default=0),
            'distinct_alert_days':len({a['decision_ts']//86400 for a,s in pairs}),
            'age_matching_available':False,'confirmatory_comparison_ready':False},
        'matched_horizons':paired,
        'limitations':['Stored SHADOW capture is not a complete contemporaneous candidate universe',
            'Controls within preceding five minutes, same regime, MC/liquidity within factor two',
            'Age matching unavailable; control reuse and market dependence preclude independent-pair inference',
            'Matches chosen without outcomes; missingness can still bias complete-pair summaries',
            'Features and scores reconstructed; not exact emitted inputs',
            '60-minute endpoint is primary diagnostic; other horizons secondary; no executable P&L',
            'Do not use these historical diagnostics to alter the active frozen ledger']}

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('export');a=p.parse_args()
    raw=pathlib.Path(a.export).read_bytes()
    if len(raw)>32*1024*1024:raise ValueError('Export bound exceeded')
    out=audit(json.loads(raw));out['export_sha256']=hashlib.sha256(raw).hexdigest()
    print(json.dumps(out,indent=2,allow_nan=False))

if __name__=='__main__':main()
