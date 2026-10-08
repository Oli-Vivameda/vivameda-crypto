"""Directive 3 owner-run aggregate research. No network or production writes."""
import argparse, ast, bisect, collections, datetime, hashlib, json, math, os
import pathlib, sqlite3, statistics, subprocess, sys

SIGNALS=('liq25k','vol_mc25','buy52','h1_not_extended','m5_not_extended',
         'band_compact','net_constructive','higher_low','liq_stable','volume_accel','txns100')
FIELDS=('ts','price','mc','liq','vol_m5','vol_h1','buys_m5','sells_m5',
        'buys_h1','sells_h1','pc_m5','pc_h1')
SPLIT=1791417600  # 2026-10-08T00:00:00Z
CUTOFF=1791483000 # 2026-10-08T18:10:00Z
SEED=20261008
GRID=(1.10,1.25,1.50,2.00)
SOURCE_SHA='3e73978a41e2e21e090a7eea92bbdc1a52dc190ce229ac262a3c6a2b0af6a043'
SCANNER=pathlib.Path('/opt/vivameda-crypto-early-scout/data/early_scout.sqlite')
PILOT=SCANNER.parent/'forward_capture/capture.sqlite'
STATE=pathlib.Path('/var/lib/vivameda-crypto-earlier-entry/research')

def canonical(v): return json.dumps(v,sort_keys=True,separators=(',',':'),allow_nan=False)
def digest(v):return hashlib.sha256(canonical(v).encode()).hexdigest()
def require_python():
    if sys.version_info[:2]!=(3,12):raise ValueError('Python 3.12 required')
def finite(v):return type(v) in (int,float) and math.isfinite(v)
def pure_scorer(path,expected=SOURCE_SHA):
    raw=pathlib.Path(path).read_bytes()
    if hashlib.sha256(raw).hexdigest()!=expected:raise ValueError('scanner source hash mismatch')
    tree=ast.parse(raw)
    node=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='score_candidate')
    # Copy one known pure function; never import the production module.
    ns={};exec(compile(ast.Module(body=[node],type_ignores=[]),str(path),'exec'),ns)
    return ns['score_candidate']

def verify_live_functions(live=SCANNER.parents[1]/'early_scout.py'):
    base=pathlib.Path(__file__).with_name('frozen_scorer_source.txt').read_bytes()
    raw=pathlib.Path(live).read_bytes()
    if len(raw)>1024*1024:raise ValueError('Live source bound')
    if hashlib.sha256(base).hexdigest()!=SOURCE_SHA:raise ValueError('Frozen source binding')
    def functions(data):
        text=data.decode();tree=ast.parse(text)
        return {n.name:ast.get_source_segment(text,n) for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in ('candidates','history','score_candidate')}
    if functions(raw)!=functions(base):raise ValueError('Live candidate/history/scorer drift; review required')
    return hashlib.sha256(raw).hexdigest()

def membership_connection(db,pilot):
    """Only a guarded SQL view can read pilot cohort membership, never raw rows."""
    con=sqlite3.connect(pathlib.Path(db).resolve().as_uri()+'?mode=ro',uri=True,timeout=2)
    con.execute('PRAGMA query_only=ON')
    con.execute('ATTACH DATABASE ? AS pilot',(pathlib.Path(pilot).resolve().as_uri()+'?mode=ro',))
    # query_only also applies to TEMP DDL: create views before enabling it below.
    con.execute('PRAGMA query_only=OFF')
    con.execute("""CREATE TEMP VIEW d3_members AS
        SELECT mint FROM main.pl_predictions
        UNION SELECT event_key FROM pilot.fc_events WHERE kind='cohort'
        UNION SELECT json_extract(c.value,'$.mint') FROM pilot.fc_events e,
            json_each(e.body,'$.controls') c WHERE e.kind='cohort'""")
    con.execute('PRAGMA query_only=ON')
    def guard(action,table,column,database,source):
        if action==sqlite3.SQLITE_READ:
            if table=='pl_predictions':return sqlite3.SQLITE_OK if column=='mint' and source=='d3_members' else sqlite3.SQLITE_DENY
            if database=='pilot':return sqlite3.SQLITE_OK if source=='d3_members' and table in ('fc_events','json_each') else sqlite3.SQLITE_DENY
            if table.startswith('pl_') or table.startswith('v2_') or table.startswith('fc_'):return sqlite3.SQLITE_DENY
        if action in (sqlite3.SQLITE_INSERT,sqlite3.SQLITE_UPDATE,sqlite3.SQLITE_DELETE,sqlite3.SQLITE_ATTACH,sqlite3.SQLITE_DETACH):return sqlite3.SQLITE_DENY
        return sqlite3.SQLITE_OK
    con.set_authorizer(guard);con.execute('BEGIN')
    # Force view resolution now: absent membership tables fail closed.
    members={r[0] for r in con.execute('SELECT mint FROM d3_members')}
    if None in members or any(not isinstance(x,str) or not x for x in members):raise ValueError('invalid exclusion membership')
    return con,members

def read_history(con,phase,cutoff=CUTOFF):
    lo,hi=(0,SPLIT) if phase=='development' else (SPLIT,cutoff)
    # Anti-join happens before market inputs are projected to Python.
    cols=','.join('s.'+k for k in FIELDS)
    sql=f'''SELECT s.mint,s.pair,l.created_ts,{cols} FROM snapshots s
      JOIN launches l ON l.mint=s.mint WHERE s.ts>=? AND s.ts<?
      AND NOT EXISTS(SELECT 1 FROM d3_members x WHERE x.mint=s.mint)
      ORDER BY s.mint,s.pair,s.ts'''
    by=collections.defaultdict(list);created={};n=0
    for mint,pair,created_ms,*row in con.execute(sql,(lo,hi)):
        n+=1
        if n>500000:raise ValueError('research snapshot bound exceeded')
        by[(mint,pair)].append(tuple(row));created[mint]=created_ms/1000
    return by,created

def wallet_coverage_line(con,now=None,root=pathlib.Path('/var/lib/vivameda-wallet-intelligence/data')):
    """Coverage telemetry only, no wallet-quality feature or identity publication."""
    import time
    now=int(time.time()) if now is None else now;ms=now*1000
    rows=con.execute('''WITH selected AS (SELECT mint,pinned_pair FROM launches
      WHERE created_ts BETWEEN ? AND ? AND last_trade_ts>=?
      AND current_mc BETWEEN 30000 AND 750000
      AND (ath_mc IS NULL OR ath_mc<=0 OR current_mc>=ath_mc*.35)
      ORDER BY last_trade_ts DESC LIMIT 60)
      SELECT mint,pinned_pair FROM selected s WHERE NOT EXISTS(SELECT 1 FROM d3_members x WHERE x.mint=s.mint)''',
      (ms-21600000,ms-1800000,ms-720000)).fetchall()
    required=complete=known=0
    for mint,pair in rows:
        try:
            # No path traversal or source identity echo.
            if not isinstance(mint,str) or not 32<=len(mint)<=44 or not mint.isalnum():continue
            path=root/(mint+'.json')
            if path.stat().st_size>8*1024*1024:continue
            report=json.loads(path.read_bytes());packet=report.get('screening_packet',{});history=packet.get('history',{})
            if report.get('schema')!='wallet-intelligence-v3' or packet.get('mint')!=mint or packet.get('pair')!=pair:continue
            if not finite(history.get('observed_at')) or not 0<=now-history['observed_at']<=300:continue
            n=history.get('coverage_summary',{}).get('owners_required')
            owners=history.get('wallets',[])
            if type(n) is not int or n<0 or not isinstance(owners,list) or len(owners)>n:continue
            good=sum(w.get('pagination_complete') is True and w.get('pending_transactions')==0 and w.get('null_timestamps')==0
              and w.get('unknown_programs')==[] and finite(w.get('head_at')) and 0<=now-w['head_at']<=300 for w in owners)
            required+=n;complete+=good;known+=1
        except (OSError,ValueError,TypeError):continue
    return {'complete_fresh_owner_token_requirements':complete,'known_required_owner_token_requirements':required,
      'current_candidate_reports_verified':known,'current_nonexcluded_candidates':len(rows),
      'complete_denominator_verified':known==len(rows) and len(rows)>0,'max_freshness_seconds':300}

def covered(rows,t0,horizon=3600):
    """Reject invalid values, missing endpoint and any >180-second observed gap."""
    if not rows or rows[0][0]!=t0:return None,'missing_index'
    end=next((i for i,r in enumerate(rows) if t0+horizon<=r[0]<=t0+horizon+180),None)
    if end is None:return None,'missing_endpoint'
    path=rows[:end+1]
    if any(not finite(r[2]) or r[2]<=0 for r in path):return None,'invalid_mc'
    if any(b[0]-a[0]>180 for a,b in zip(path,path[1:])):return None,'gap'
    before=[r[2] for r in path[1:] if r[0]<=t0+horizon]
    if not before:return None,'missing_within_window'
    maximum=max(before)/path[0][2]
    return {'max_multiple':maximum,'endpoint_multiple':path[-1][2]/path[0][2],
            'label':'run' if maximum>=2 else 'non_run' if maximum<1.35 else 'intermediate'},'covered'

def prehistory_ok(rows,t0):
    return (len(rows)>=4 and rows[0][0]<=t0-1800+180
      and all(all(finite(v) for v in r) and r[1]>0 and r[2]>0 for r in rows)
      and all(b[0]-a[0]<=180 for a,b in zip(rows,rows[1:])))

def feature_vector(rows30,rows35,created,anchor,scorer):
    score,metrics,failed=scorer(rows35)
    if not metrics:return None
    c=rows30[-1];prices=[r[1] for r in rows30];first=rows30[0]
    signals={k:k not in failed for k in SIGNALS}
    return {'score':score,'signals':signals,'age_seconds':c[0]-created,
      'gain_since_first_stored':c[2]/anchor[2]-1,'anchor_multiple':c[2]/anchor[2],
      'pump_ath_ratio':None,'buy_ratio':c[8]/max(1,c[8]+c[9]),
      'buy_ratio_m5':c[6]/max(1,c[6]+c[7]),'volume_mc':c[5]/c[2],
      'volume_acceleration':c[4]/(c[5]/12) if c[5]>0 else None,
      'band30':(max(prices)-min(prices))/min(prices),'net30':c[1]/first[1]-1,
      'txns_h1':c[8]+c[9],'txns_m5':c[6]+c[7],
      'liquidity_change30':c[3]/first[3]-1 if first[3]>0 else None,
      'pc_h1':c[11],'pc_m5':c[10],'mc':c[2],'liq':c[3],
      'first_stored_age_seconds':anchor[0]-created,
      'first_stored_pc_h1':anchor[11],'history30_seconds':c[0]-first[0],
      'history35_seconds':rows35[-1][0]-rows35[0][0]}

def study(by,created,phase,scorer,cutoff=CUTOFF):
    eligible=[];counts=collections.Counter();partial=[]
    lo,hi=(0,SPLIT) if phase=='development' else (SPLIT,cutoff)
    pair_times=collections.defaultdict(dict)
    for (mint,pair),rs in by.items():pair_times[mint][pair]=[r[0] for r in rs]
    for (mint,pair),rows in by.items():
        times=[r[0] for r in rows]
        for i,c in enumerate(rows):
            counts['observed_minutes']+=1;t0=c[0]
            if not pair or not 1800<=t0-created[mint]<=21600:counts['age_or_pair']+=1;continue
            if not all(finite(v) for v in c) or not 30000<=c[2]<=750000 or c[1]<=0 or c[3]<25000 or c[5]<20000:counts['base_or_invalid']+=1;continue
            hist35=rows[bisect.bisect_left(times,t0-2100):i+1]
            if any(not all(finite(v) for v in r) for r in hist35):counts['invalid_history']+=1;continue
            score,metrics,failed=scorer(hist35)
            if not metrics:counts['scorer_history']+=1;continue
            # Exclude label windows touching another split or not completely closed.
            if t0-1800<lo or t0+3780>=hi:counts['split_or_immature']+=1;continue
            future=rows[i:bisect.bisect_right(times,t0+3780)]
            out,why=covered(future,t0)
            counts[why]+=1
            if out is None:continue
            h30=rows[bisect.bisect_left(times,t0-1800):i+1]
            if not prehistory_ok(h30,t0):
                counts['partial_prehistory']+=1;partial.append(out['label']);continue
            # A pair switch anywhere in the prehistory or label interval fails closed.
            if any(other!=pair and bisect.bisect_right(ts,t0+3780)>bisect.bisect_left(ts,t0-2100)
                   for other,ts in pair_times[mint].items()):counts['pair_switch']+=1;continue
            anchor=next((r for r in rows[:i+1] if finite(r[2]) and r[2]>0),None)
            if anchor is None:counts['anchor_missing']+=1;continue
            f=feature_vector(h30,hist35,created[mint],anchor,scorer)
            eligible.append({'mint':mint,'pair':pair,'ts':t0,'day':t0//86400,
                'hour':t0//3600,'features':f,**out})
    return eligible,dict(counts),dict(collections.Counter(partial))

def distribution(values,total=None):
    vals=sorted(v for v in values if finite(v));n=len(vals)
    def q(frac):
        if not n:return None
        pos=(n-1)*frac;a=int(pos);b=min(a+1,n-1);return vals[a]+(vals[b]-vals[a])*(pos-a)
    return {'n':n,'missing':(total if total is not None else len(values))-n,
            'median':q(.5),'p25':q(.25),'p75':q(.75)}
def selects(row,arm,g=None):
    f=row['features']
    if f['score']<8:return False
    if arm=='A0':return True
    if not f['signals']['h1_not_extended']:return False
    return arm=='A1' or (g is not None and finite(f.get('anchor_multiple')) and f['anchor_multiple']<=g)
def arm_summary(rows):
    return {'minutes':len(rows),'run_minutes':sum(r['label']=='run' for r in rows),
      'non_run_minutes':sum(r['label']=='non_run' for r in rows),
      'run_rate':sum(r['label']=='run' for r in rows)/len(rows) if rows else None,
      'endpoint_2x_rate':sum(r['endpoint_multiple']>=2 for r in rows)/len(rows) if rows else None,
      'endpoint_multiple':distribution([r['endpoint_multiple'] for r in rows]),
      'unique_tokens':len({r['mint'] for r in rows}),'utc_days':len({r['day'] for r in rows})}
def aggregate(rows,counts,partial,phase,g=None):
    runs=[r for r in rows if r['label']=='run'];non=collections.defaultdict(list)
    need=collections.Counter(r['hour'] for r in runs)
    for r in rows:
        if r['label']=='non_run':non[r['hour']].append(r)
    sampled=[]
    for hour,n in need.items():
        options=sorted(non[hour],key=lambda r:digest([SEED,r['mint'],r['pair'],r['ts']]))
        sampled.extend(options[:n])
    keys=[k for k in rows[0]['features'] if k not in ('signals',)] if rows else []
    features={k:{'run':distribution([r['features'][k] for r in runs]),
                  'non_run_hour_matched':distribution([r['features'][k] for r in sampled])} for k in keys}
    sig={k:{'run_pass':sum(r['features']['signals'][k] for r in runs),'run_n':len(runs),
            'non_run_pass':sum(r['features']['signals'][k] for r in sampled),'non_run_n':len(sampled)} for k in SIGNALS}
    episodes=[];until={}
    for r in sorted(runs,key=lambda r:(r['ts'],r['mint'])):
        if r['ts']>=until.get(r['mint'],0):episodes.append(r);until[r['mint']]=r['ts']+3600
    arms={a:arm_summary([r for r in rows if selects(r,a,g)]) for a in ('A0','A1','A2')}
    out={'phase':phase,'eligible_covered_candidate_minutes':len(rows),
      'base_rate':len(runs)/len(rows) if rows else None,'label_counts':dict(collections.Counter(r['label'] for r in rows)),
      'utc_day_counts':{datetime.datetime.fromtimestamp(d*86400,datetime.timezone.utc).date().isoformat():sum(r['day']==d for r in rows) for d in sorted({r['day'] for r in rows})},
      'coverage_exclusions':counts,'partial_history_covered_labels':partial,
      'feature_distributions':features,'signal_passes':sig,'sampled_non_run_minutes':len(sampled),
      'run_hours_without_comparison':sum(not non[h] for h in need),
      'run_unique_mints':len({r['mint'] for r in runs}),'nonoverlapping_run_episodes':len(episodes),
      'first_observed_extended_episode_count':sum(r['features']['first_stored_pc_h1']>22 for r in episodes),
      'first_observed_episode_age':distribution([r['features']['first_stored_age_seconds'] for r in episodes]),
      'unseen_pre_candidacy_run_count':None,'arms':arms,'holdout_opened':phase=='holdout',
      'identities_exported':False,'ledger_values_read':False,'pilot_outcomes_read':False,
      'production_changed':False,'provider_requests':0,'pump_ath_historical_feature_available':False,
      'baseline_scope':'retained snapshot-observed candidate-minutes; historical top60/trade/ATH unavailable'}
    if phase=='development':
        grid={str(x):arm_summary([r for r in rows if selects(r,'A2',x)]) for x in GRID}
        valid=[x for x in GRID if grid[str(x)]['run_minutes']>=20 and grid[str(x)]['non_run_minutes']>=20 and grid[str(x)]['utc_days']>=2]
        chosen=min(valid,key=lambda x:(-grid[str(x)]['run_rate'],x)) if valid else None
        out.update(development_grid=grid,proposed_g=chosen,rule_freeze_ready=chosen is not None)
    else:
        out['decision_day_clustered']=cluster_results(rows,g)
    return out

def cluster_results(rows,g):
    days=sorted({r['day'] for r in rows});out={'days':len(days),'seed':SEED,'resamples':2000,'inferentially_readable':len(days)>=10}
    baseline=arm_summary([r for r in rows if selects(r,'A0',g)])
    out['differences_vs_A0']={}
    for arm in ('A1','A2'):
        arm_out=arm_summary([r for r in rows if selects(r,arm,g)])
        out['differences_vs_A0'][arm]={k:arm_out[k]-baseline[k] if arm_out[k] is not None and baseline[k] is not None else None for k in ('run_rate','endpoint_2x_rate')}
    if len(days)<10:return out
    import random
    rng=random.Random(SEED);rep=collections.defaultdict(list)
    grouped={d:[r for r in rows if r['day']==d] for d in days}
    for _ in range(2000):
        sample=[r for d in rng.choices(days,k=len(days)) for r in grouped[d]]
        for arm in ('A0','A1','A2'):
            a=arm_summary([r for r in sample if selects(r,arm,g)])
            for key in ('run_rate','endpoint_2x_rate'):
                if a[key] is not None:rep[(arm,key)].append(a[key])
    out['intervals']={a:{k:{'p025':sorted(rep[(a,k)])[int(len(rep[(a,k)])*.025)],
                          'p975':sorted(rep[(a,k)])[min(len(rep[(a,k)])-1,int(len(rep[(a,k)])*.975))]}
                        for k in ('run_rate','endpoint_2x_rate') if rep[(a,k)]} for a in ('A0','A1','A2')}
    return out

def one_shot(path,rule_hash):
    path.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
    fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    with os.fdopen(fd,'w') as f:f.write(canonical({'rule_sha256':rule_hash,'started_utc':datetime.datetime.now(datetime.timezone.utc).isoformat()}));f.flush();os.fsync(f.fileno())
    dfd=os.open(path.parent,os.O_RDONLY)
    try:os.fsync(dfd)
    finally:os.close(dfd)

def main():
    p=argparse.ArgumentParser();p.add_argument('--expected-sha256',required=True)
    p.add_argument('--phase',choices=('development','holdout'),default='development')
    p.add_argument('--rule-file',type=pathlib.Path);p.add_argument('--rule-commit');p.add_argument('--rule-sha256')
    a=p.parse_args();require_python()
    if hashlib.sha256(pathlib.Path(__file__).read_bytes()).hexdigest()!=a.expected_sha256:raise SystemExit('Reviewed exporter hash mismatch')
    g=None;rh=None
    if a.phase=='holdout':
        if not a.rule_file or not a.rule_commit or not a.rule_sha256:raise SystemExit('Committed frozen rules required; holdout not opened')
        raw=a.rule_file.read_bytes();rh=hashlib.sha256(raw).hexdigest()
        if rh!=a.rule_sha256:raise SystemExit('Rule hash mismatch')
        rule=json.loads(raw)
        if rule.get('development_only') is not True or rule.get('qualification_counts_verified') is not True or rule.get('g') not in GRID:raise SystemExit('Development-qualified frozen rule required')
        result=subprocess.run(['git','show',a.rule_commit+':client_learning/crypto_directive3_20261008/research/frozen_rules.json'],capture_output=True,check=True)
        if result.stdout!=raw:raise SystemExit('Frozen rule not in specified commit')
        g=rule['g']
    try:
        scorer=pure_scorer(pathlib.Path(__file__).with_name('frozen_scorer_source.txt'))
        live_source_sha256=verify_live_functions()
        con,members=membership_connection(SCANNER,PILOT)
        try:
            if a.phase=='holdout':one_shot(STATE/'HOLDOUT_OPENED.json',rh)
            by,created=read_history(con,a.phase)
            rows,counts,partial=study(by,created,a.phase,scorer)
            out=aggregate(rows,counts,partial,a.phase,g)
            out['exclusion_count']=len(members);out['input_sha256']=digest([[k,by[k]] for k in sorted(by)])
            out['source_sha256']=SOURCE_SHA;out['cutoff_utc']='2026-10-08T18:10:00Z'
            out['live_source_sha256']=live_source_sha256;out['live_function_bytes_match']=True
            out['wallet_history_coverage']=wallet_coverage_line(con)
        finally:con.rollback();con.close()
    except (sqlite3.Error,OSError,ValueError):
        out={'available':False,'blocker':'reviewed_source_or_private_access_or_coverage_guard','phase':a.phase,
             'permissions_changed':False,'production_changed':False,'provider_requests':0}
    print(json.dumps(out,sort_keys=True,allow_nan=False))
if __name__=='__main__':main()
