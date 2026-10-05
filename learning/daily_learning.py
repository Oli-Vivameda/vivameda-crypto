"""Read-only crypto evidence review; independent paper journal, no network or trades."""
import argparse, hashlib, json, math, os, sqlite3, time
from pathlib import Path

CHECKS=('wallet_clusters','developer_history','top_holder_ownership','wallet_age','token_controls','liquidity_control','trading_mechanics')
FEATURES=('band','buy_ratio','vol_mc','pc5','pc1','liq_change','vol_accel')

def canonical(v): return json.dumps(v,sort_keys=True,separators=(',',':'),allow_nan=False)
def digest(v): return hashlib.sha256(canonical(v).encode()).hexdigest()
def finite(v): return type(v) in (int,float) and math.isfinite(v)
def readonly(path):
    c=sqlite3.connect('file:'+str(Path(path).resolve())+'?mode=ro',uri=True,timeout=30)
    c.row_factory=sqlite3.Row;c.execute('PRAGMA query_only=ON');c.execute('BEGIN');return c

def atomic(path,value):
    path=Path(path);tmp=path.with_name('.'+path.name+'.'+str(os.getpid()))
    try:
        with tmp.open('x') as f:
            f.write(canonical(value)+'\n');f.flush();os.fsync(f.fileno())
        tmp.chmod(0o644);os.replace(tmp,path)
    finally:
        if tmp.exists():tmp.unlink()

def local_db(path,policy):
    c=sqlite3.connect(path,timeout=30)
    c.execute('PRAGMA journal_mode=WAL');c.execute('PRAGMA synchronous=FULL')
    c.executescript('''CREATE TABLE IF NOT EXISTS activation(id INTEGER PRIMARY KEY CHECK(id=1),body TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS decisions(mint TEXT PRIMARY KEY,created_ts INTEGER NOT NULL,body TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS reviews(day TEXT PRIMARY KEY,body TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS events(seq INTEGER PRIMARY KEY,kind TEXT,body TEXT,previous_hash TEXT,hash TEXT);
    ''')
    for table in ('activation','decisions','reviews','events'):
        for op in ('UPDATE','DELETE'):
            c.execute(f"CREATE TRIGGER IF NOT EXISTS {table}_no_{op} BEFORE {op} ON {table} BEGIN SELECT RAISE(ABORT,'append only'); END")
    c.execute('BEGIN IMMEDIATE');row=c.execute('SELECT body FROM activation').fetchone()
    if row:
        a=json.loads(row[0])
        if a['policy_sha256']!=digest(policy):raise ValueError('Frozen paper policy changed')
    else:
        a={'activated_at':int(time.time()),'policy_sha256':digest(policy),'policy':policy}
        c.execute('INSERT INTO activation VALUES(1,?)',(canonical(a),))
    c.commit();verify_events(c);return c,a

def event(c,kind,body):
    row=c.execute('SELECT seq,hash FROM events ORDER BY seq DESC LIMIT 1').fetchone();seq=1 if not row else row[0]+1;prev='' if not row else row[1]
    h=digest({'seq':seq,'kind':kind,'body':body,'previous_hash':prev})
    c.execute('INSERT INTO events VALUES(?,?,?,?,?)',(seq,kind,canonical(body),prev,h))

def verify_events(c):
    prev='';expected_seq=1
    for seq,kind,raw,previous_hash,h in c.execute('SELECT seq,kind,body,previous_hash,hash FROM events ORDER BY seq'):
        body=json.loads(raw)
        if seq!=expected_seq or previous_hash!=prev or h!=digest({'seq':seq,'kind':kind,'body':body,'previous_hash':prev}):
            raise ValueError('Learning event chain invalid')
        prev=h;expected_seq+=1

def holdout_mints(c):
    # Read identifiers only. Never read pl_results, probabilities or holdout outcomes.
    return {r[0] for r in c.execute('SELECT mint FROM pl_predictions')}

def valid_endpoint(c,p):
    return (finite(c.get('entry_mc')) and c['entry_mc']>0 and c.get('coverage_ok')==1
        and type(c.get('lateness')) is int and 0<=c['lateness']<=180
        and c.get('observed_ts')==c['decision_ts']+p['review_horizon_minutes']*60+c['lateness']
        and finite(c.get('max_gap')) and 0<=c['max_gap']<=180
        and finite(c.get('multiple')) and c['multiple']>0)

def matched_cases(cases,p):
    winners=[c for c in cases if c.get('endpoint_eligible') and c['multiple']>=p['matched_winner_endpoint']]
    failures=[c for c in cases if c.get('endpoint_eligible') and c['multiple']<=p['matched_failure_endpoint']]
    matches=[];used=set()
    for w in sorted(winners,key=lambda c:c['decision_ts']):
        candidates=[]
        for f in failures:
            if f['mint'] in used or w['regime']!=f['regime']:continue
            if abs(w['decision_ts']-f['decision_ts'])>p['matched_call_time_difference_seconds']:continue
            if abs(w['score']-f['score'])>p['matched_score_difference']:continue
            if min(w['entry_mc'],f['entry_mc'],w['entry_liq'],f['entry_liq'])<=0:continue
            cap=abs(math.log10(w['entry_mc']/f['entry_mc']));liq=abs(math.log10(w['entry_liq']/f['entry_liq']))
            if cap>p['matched_log_cap_difference'] or liq>p['matched_log_liquidity_difference']:continue
            if not finite(w.get('age_hours')) or not finite(f.get('age_hours')):continue
            age=abs(w['age_hours']-f['age_hours'])
            if age>p['matched_age_hours_difference']:continue
            candidates.append((cap+liq+age, f['mint'],f))
        if candidates:
            _,_,f=min(candidates);used.add(f['mint']);delta={}
            for k in FEATURES:
                a=w['features'].get(k);b=f['features'].get(k)
                if finite(a) and finite(b):delta[k]=a-b
            matches.append({'winner_mint':w['mint'],'failure_mint':f['mint'],'regime':w['regime'],
                'winner_endpoint':w['multiple'],'failure_endpoint':f['multiple'],'feature_differences':delta,
                'status':'exploratory_reconstructed_not_causal_not_a_trade_rule'})
    return matches

def review(source,target,state,p,now=None):
    now=int(time.time()) if now is None else now;verify_events(target);excluded=holdout_mints(source)
    rows=source.execute('''SELECT d.*,l.symbol,l.name,l.created_ts,s.peak_mc,s.last_mc,s.min_mult,
    o.observed_ts,o.lateness,o.multiple,o.liq AS endpoint_liq,h.coverage_ok,h.max_gap
    FROM v2_cases d JOIN launches l ON l.mint=d.mint LEFT JOIN v2_state s ON s.id=d.id
    LEFT JOIN v2_outcomes o ON o.id=d.id AND o.horizon=?
    LEFT JOIN v2_horizon_metrics h ON h.id=d.id AND h.horizon=o.horizon AND h.observed_ts=o.observed_ts
    WHERE d.source='ALERT' AND d.decision_ts<=? AND NOT EXISTS(SELECT 1 FROM pl_predictions p WHERE p.mint=d.mint)
    ORDER BY d.decision_ts,d.id LIMIT ?''',(p['review_horizon_minutes'],now,p['max_development_cases']+1)).fetchall()
    if len(rows)>p['max_development_cases']:raise ValueError('Development export bound exceeded')
    first={}
    for r in rows:
        c=dict(r)
        if c['mint'] in excluded or c['mint'] in first:continue
        raw=c.get('features')
        try:c['features']=json.loads(raw) if isinstance(raw,str) else raw
        except (ValueError,TypeError):c['features']={}
        if not isinstance(c['features'],dict):c['features']={}
        c['age_hours']=(c['decision_ts']-c['created_ts']/1000)/3600 if finite(c.get('created_ts')) else None
        c['endpoint_eligible']=valid_endpoint(c,p)
        c['provenance']='reconstructed_call_features; local knowledge time not established'
        c['tracked_peak_multiple']=c['peak_mc']/c['entry_mc'] if finite(c.get('peak_mc')) and c['entry_mc']>0 else None
        c['last_multiple']=c['last_mc']/c['entry_mc'] if finite(c.get('last_mc')) and c['entry_mc']>0 else None
        first[c['mint']]=c
    cases=list(first.values());pairs=matched_cases(cases,p);eligible=[c for c in cases if c['endpoint_eligible']]
    selected=sorted(cases,key=lambda c:c['tracked_peak_multiple'] or 0,reverse=True)[:p['max_case_memory']//2]
    losers=sorted([c for c in cases if c not in selected and c['last_multiple'] is not None],key=lambda c:c['last_multiple'])[:p['max_case_memory']-len(selected)]
    cards=[{k:c.get(k) for k in ('mint','symbol','name','decision_ts','entry_mc','entry_liq','regime','tracked_peak_multiple','last_multiple','endpoint_eligible','provenance')} for c in selected+losers]
    summary={'tokens':len(cases),'eligible_60m_endpoints':len(eligible),'missing_or_incomplete':len(cases)-len(eligible),
        'endpoint_ge_2':sum(c['multiple']>=2 for c in eligible),'endpoint_le_055':sum(c['multiple']<=.55 for c in eligible),
        'matched_pairs':len(pairs),'holdout_identifiers_excluded':len(excluded),'recorded_alert_events':len(rows)}
    note={'schema':'crypto-daily-memory-v1','generated_at':now,'policy_sha256':digest(p),'summary':summary,'cases':cards,
        'matched_examples':pairs[:5],'weights_updated':False,'rules_promoted':False,'live_execution':False,
        'limitations':['Tracked peak is not lifetime ATH or realized profit.','Reconstructed case features and unknown historical policy versions are exploratory only.',
        'Frozen model cohort is excluded.','Daily notes do not change entry rules; incomplete evidence remains missing.']}
    day=time.strftime('%Y-%m-%d',time.gmtime(now));target.execute('BEGIN IMMEDIATE')
    if not target.execute('SELECT 1 FROM reviews WHERE day=?',(day,)).fetchone():
        target.execute('INSERT INTO reviews VALUES(?,?)',(day,canonical(note)));event(target,'daily_review',note)
        target.commit();atomic(state/'latest_memory.json',note)
        # Public summary has no private runtime identities or detailed traces.
        atomic(state/'public_summary.json',{'generated_at':now,'summary':summary,'weights_updated':False,'live_execution':False})
        return note
    target.rollback();return json.loads(target.execute('SELECT body FROM reviews WHERE day=?',(day,)).fetchone()[0])

def snapshot_features(rows):
    if len(rows)<4:raise ValueError('insufficient_snapshot_history')
    if any(not all(finite(v) for v in r) for r in rows):raise ValueError('nonfinite_snapshot')
    cur=rows[-1];prices=[r[1] for r in rows if r[1]>0];liq=[r[3] for r in rows if r[3]>0]
    if len(prices)<4 or not liq or cur[2]<=0:raise ValueError('invalid_snapshot')
    return {'band':(max(prices)-min(prices))/min(prices),'vol_accel':cur[4]/max(1,cur[5]/12),
        'liq_change':cur[3]/liq[0]-1,'buy_ratio':cur[8]/max(1,cur[8]+cur[9]),'vol_mc':cur[5]/cur[2],
        'pc5':cur[10],'pc1':cur[11]}

def decision(features,checks,score,p):
    if any(checks.get(k)=='REJECT' for k in CHECKS):return 'SKIP','explicit_screening_reject'
    if any(checks.get(k)!='PASS' for k in CHECKS):return 'WATCH','incomplete_seven_check_evidence'
    if not all(finite(features.get(k)) for k in ('band','vol_accel','liq_change')):return 'WATCH','missing_features'
    if (score>=p['minimum_score'] and features['band']<=p['maximum_band']
        and features['vol_accel']>=p['minimum_volume_acceleration']
        and features['liq_change']>=p['minimum_liquidity_change']):return 'ENTER_REVIEW','frozen_paper_filter_only'
    return 'WATCH','paper_market_filter_not_met'

def journal(source,target,state,p,activation,wallet_dir,now=None):
    now=int(time.time()) if now is None else now
    verify_events(target)
    rows=source.execute('''SELECT d.mint,d.id,d.decision_ts,d.score,l.pinned_pair FROM v2_cases d
    JOIN launches l ON l.mint=d.mint WHERE d.source='ALERT' AND d.decision_ts>=? AND d.decision_ts<=?
    AND NOT EXISTS(SELECT 1 FROM pl_predictions p WHERE p.mint=d.mint)
    ORDER BY d.decision_ts,d.id LIMIT ?''',(max(activation['activated_at'],now-p['journal_max_delay_seconds']),now,p['max_journal_per_pass'])).fetchall()
    count=0
    for row in rows:
        mint=row['mint']
        if target.execute('SELECT 1 FROM decisions WHERE mint=?',(mint,)).fetchone():continue
        ss=source.execute('SELECT ts,price,mc,liq,vol_m5,vol_h1,buys_m5,sells_m5,buys_h1,sells_h1,pc_m5,pc_h1 FROM snapshots WHERE mint=? AND ts BETWEEN ? AND ? ORDER BY ts',(mint,now-2100,now)).fetchall()
        raw=[list(x) for x in ss];checks={};reason=None;features={};evidence=None
        try:
            if not raw or now-raw[-1][0]>p['snapshot_max_age_seconds']:raise ValueError('stale_snapshot')
            features=snapshot_features(raw)
            saved=source.execute('SELECT review FROM prealert_reviews WHERE mint=? AND checked_at BETWEEN ? AND ? ORDER BY checked_at DESC LIMIT 1',(mint,now-p['screening_max_age_seconds'],now)).fetchone()
            if not saved:raise ValueError('stale_or_missing_scanner_review')
            evidence=json.loads(saved[0]);ts=evidence.get('checked_at')
            if not finite(ts) or not 0<=now-ts<=p['screening_max_age_seconds']:raise ValueError('stale_or_missing_screening')
            if evidence.get('mint')!=mint or evidence.get('chain')!='solana':raise ValueError('mint_or_chain_mismatch')
            if evidence.get('pair')!=row['pinned_pair']:raise ValueError('pair_mismatch_or_missing')
            for k,v in evidence.get('checks',{}).items():
                if not isinstance(v,dict):continue
                observed=v.get('observed_at');refs=v.get('evidence_refs')
                fresh=finite(observed) and 0<=now-observed<=p['screening_max_age_seconds']
                checks[k]=v.get('status') if fresh and isinstance(refs,list) and refs and all(isinstance(x,str) and x.strip() for x in refs) else 'UNKNOWN'
        except (ValueError,FileNotFoundError,PermissionError,TypeError,KeyError) as err:reason=str(err)[:120]
        action,why=decision(features,checks,row['score'],p)
        if reason:action='WATCH';why=reason
        body={'mint':mint,'source_case':row['id'],'original_call_ts':row['decision_ts'],'decision_ts':now,
            'decision':action,'reason':why,'features':features,'snapshot_sha256':digest(raw),'source_snapshot':raw,
            'screening':checks,'source_screening_review':evidence,'screening_sha256':digest(evidence),
            'policy_sha256':digest(p),'mode':'PAPER_REVIEW_ONLY','live_execution':False,
            'filled':False,'quote_verified':False,'note':'No order-book quote, fill, exit or PnL is inferred.'}
        target.execute('BEGIN IMMEDIATE')
        try:
            target.execute('INSERT OR IGNORE INTO decisions VALUES(?,?,?)',(mint,now,canonical(body)))
            if target.execute('SELECT changes()').fetchone()[0]:event(target,'paper_decision',body);count+=1
            target.commit()
        except BaseException:target.rollback();raise
    return {'new_paper_decisions':count,'live_execution':False,'weights_updated':False}

def main():
    a=argparse.ArgumentParser();a.add_argument('mode',choices=['review','journal']);a.add_argument('--source',required=True);a.add_argument('--state',required=True);a.add_argument('--wallet-dir',default='/var/lib/vivameda-wallet-intelligence/data');a.add_argument('--policy',default=str(Path(__file__).with_name('policy.json')));args=a.parse_args()
    p=json.loads(Path(args.policy).read_text());state=Path(args.state);state.mkdir(parents=True,exist_ok=True)
    c,activation=local_db(state/'learning.sqlite',p)
    with readonly(args.source) as source:
        result=review(source,c,state,p) if args.mode=='review' else journal(source,c,state,p,activation,args.wallet_dir)
    print(canonical({'summary':result.get('summary')} if args.mode=='review' else result))
if __name__=='__main__':main()
