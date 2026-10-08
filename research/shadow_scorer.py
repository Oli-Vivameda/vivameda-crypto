"""Separate post-stop shadow service candidate. No network, notifications or orders."""
import argparse, collections, datetime, hashlib, json, os, pathlib, random, shutil, sqlite3, sys, time
from earlier_entry import FIELDS, SIGNALS, SOURCE_SHA, canonical, covered, digest, finite, membership_connection, pure_scorer, require_python, verify_live_functions

STATE=pathlib.Path('/var/lib/vivameda-crypto-earlier-entry/shadow')
SCANNER=pathlib.Path('/opt/vivameda-crypto-early-scout/data/early_scout.sqlite')
PILOT=SCANNER.parent/'forward_capture/capture.sqlite'
STOP=1792479039 # 2026-10-20T06:50:39Z
DEADLINE=1794898239 # proposed 2026-11-17T06:50:39Z
MAX_BYTES=512*1024*1024
MIN_FREE=3*1024**3

def initialize(con,policy,now):
    required={'version','g','seed','target_per_arm','deadline','source_sha256','protocol_sha256','rule_sha256','owner_approved','estimand'}
    if set(policy)!=required or policy['owner_approved'] is not True:raise ValueError('Reviewed owner-approved policy required')
    if now<STOP:raise ValueError('Activation deferred until fixed pilot stop')
    if policy['g'] not in (1.1,1.25,1.5,2.0):raise ValueError('A2 development threshold missing')
    if policy['seed']!=20261008 or policy['target_per_arm']!=100 or policy['deadline']!=DEADLINE:raise ValueError('Unreviewed stop or seed')
    if policy['estimand']!='independent_poll_current_scanner_universe':raise ValueError('Independent-poll parity limitation must be accepted')
    if policy['source_sha256']!=SOURCE_SHA or now>=policy['deadline']:raise ValueError('Source binding or activation window')
    for name in ('protocol_sha256','rule_sha256'):
        if len(policy[name])!=64 or any(c not in '0123456789abcdef' for c in policy[name]):raise ValueError('Policy digest')
    con.executescript('''CREATE TABLE IF NOT EXISTS activation(id INTEGER PRIMARY KEY CHECK(id=1),body TEXT NOT NULL);
      CREATE TABLE IF NOT EXISTS events(seq INTEGER PRIMARY KEY,kind TEXT NOT NULL,event_key TEXT NOT NULL,
        body TEXT NOT NULL,previous_hash TEXT NOT NULL,hash TEXT NOT NULL,UNIQUE(kind,event_key));''')
    for table in ('activation','events'):
        for op in ('UPDATE','DELETE'):
            con.execute(f"CREATE TRIGGER IF NOT EXISTS {table}_no_{op} BEFORE {op} ON {table} BEGIN SELECT RAISE(ABORT,'shadow append only'); END")
    body=canonical({'activated_ts':now,'policy':policy})
    if con.execute('SELECT 1 FROM activation').fetchone():raise ValueError('No reactivation or reset')
    con.execute('INSERT INTO activation VALUES(1,?)',(body,));con.commit()

def append(con,kind,key,body):
    value=canonical(body);old=con.execute('SELECT body FROM events WHERE kind=? AND event_key=?',(kind,key)).fetchone()
    if old:
        if old[0]!=value:raise ValueError('Conflicting replay')
        return False
    row=con.execute('SELECT seq,hash FROM events ORDER BY seq DESC LIMIT 1').fetchone()
    seq,prev=(row[0]+1,row[1]) if row else (1,'0'*64)
    h=digest([seq,kind,key,value,prev]);con.execute('INSERT INTO events VALUES(?,?,?,?,?,?)',(seq,kind,key,value,prev,h));return True

def current_candidates(con,now):
    # Apply the scanner LIMIT before exclusions; do not refill to a different universe.
    query='''WITH selected AS (SELECT mint,created_ts,creator,current_mc,ath_mc,pinned_pair,alert_level,last_trade_ts
      FROM launches WHERE created_ts BETWEEN ? AND ? AND last_trade_ts>=?
      AND current_mc BETWEEN 30000 AND 750000
      AND (ath_mc IS NULL OR ath_mc<=0 OR current_mc>=ath_mc*.35)
      ORDER BY last_trade_ts DESC LIMIT 60)
      SELECT * FROM selected s WHERE NOT EXISTS(SELECT 1 FROM d3_members x WHERE x.mint=s.mint)'''
    ms=now*1000
    return con.execute(query,(ms-21600000,ms-1800000,ms-720000)).fetchall()

def prepare_candidates(src,own,now,scorer):
    out=[];reasons=collections.Counter()
    for mint,created,creator,mc,ath,pair,level,trade in current_candidates(src,now):
        rows=src.execute('SELECT '+','.join(FIELDS)+',pair FROM snapshots WHERE mint=? AND ts>=? AND ts<=? ORDER BY ts',(mint,now-2100,now)).fetchall()
        if not rows or now-rows[-1][0]>120:reasons['stale_or_missing']+=1;continue
        if not pair or any(r[-1]!=pair for r in rows):reasons['pair_history']+=1;continue
        exact=[tuple(r[:-1]) for r in rows]
        if any(not all(finite(v) for v in r) for r in exact):reasons['invalid']+=1;continue
        score,metrics,failed=scorer(exact)
        if not metrics:reasons['scorer_gate']+=1;continue
        if any(b[0]-a[0]>180 for a,b in zip(exact,exact[1:])):reasons['history_gap']+=1;continue
        anchor_key=canonical([mint,pair]);stored=own.execute("SELECT body FROM events WHERE kind='anchor' AND event_key=?",(anchor_key,)).fetchone()
        if stored:anchor=json.loads(stored[0])
        else:
            # First observed by this service, not inferred true launch MC.
            anchor={'mint':mint,'pair':pair,'ts':exact[-1][0],'observed_ts':now,'mc':exact[-1][2],'provenance':'first_shadow_observation'}
            append(own,'anchor',anchor_key,anchor)
        signals={k:k not in failed for k in SIGNALS}
        out.append({'mint':mint,'pair':pair,'created_ts':created//1000,'decision_ts':now,
          'snapshot_ts':exact[-1][0],'inputs':[list(r) for r in exact],
          'score':score,'signals':signals,'mc':metrics['mc'],'liq':metrics['liq'],
          'stored_alert_level':level,'would_alert_level':2 if score>=10 else 1 if score>=8 else 0,
          'anchor_mc':anchor['mc'],'anchor_ts':anchor['ts'],'anchor_provenance':anchor['provenance'],
          'anchor_multiple':metrics['mc']/anchor['mc'],'input_sha256':digest(exact)})
    return sorted(out,key=lambda r:r['mint']),dict(reasons)

def decisions(con,rows,now,policy):
    """Commit every decision before follow-up. Random controls use all eligible rows."""
    pending=[];draws=0
    for row in rows:
        if row['score']<8:continue
        arms=['A0']
        if row['signals']['h1_not_extended']:
            arms+=['A1']
            if row['anchor_multiple']<=policy['g']:arms+=['A2']
        added_a0=False
        for arm in arms:
            key=canonical([arm,row['mint']])
            if con.execute("SELECT 1 FROM events WHERE kind='decision' AND event_key=?",(key,)).fetchone():continue
            body={'arm':arm,'inputs':row,'policy_version':policy['version'],'policy_sha256':digest(policy),'recorded_ts':now}
            pending.append(('decision',key,body));added_a0|=arm=='A0'
        if added_a0:
            candidates=[r for r in rows if r['mint']!=row['mint']]
            universe=[r['mint'] for r in candidates];key=canonical(['R',row['mint']])
            seed_material=digest([policy['seed'],row['mint'],now]);rng=random.Random(int(seed_material,16))
            index=rng.randrange(len(candidates)) if candidates else None
            body={'arm':'R','index_mint':row['mint'],'index_ts':now,'seed':policy['seed'],
                'seed_material':seed_material,'universe_sha256':digest(universe),'universe_size':len(universe),
                'draw_index':index,'inputs':candidates[index] if index is not None else None,
                'recorded_ts':now,'policy_version':policy['version'],'policy_sha256':digest(policy)}
            pending.append(('random_draw',key,body));draws+=index is not None
    for kind,key,body in pending:append(con,kind,key,body)
    return len([1 for k,_,_ in pending if k=='decision']),draws

def counts(con):
    out={a:0 for a in ('A0','A1','A2','R')}
    for (body,) in con.execute("SELECT body FROM events WHERE kind='decision'"):out[json.loads(body)['arm']]+=1
    out['R']=sum(json.loads(r[0])['inputs'] is not None for r in con.execute("SELECT body FROM events WHERE kind='random_draw'"))
    return out

def followup(src,own,now,excluded):
    activation=json.loads(own.execute('SELECT body FROM activation').fetchone()[0])
    stop=own.execute("SELECT body FROM events WHERE kind='stop'").fetchone()
    boundary=(json.loads(stop[0])['ts'] if stop else activation['policy']['deadline'])+3780
    if now>boundary:now=boundary
    for kind,key,body in own.execute("SELECT kind,event_key,body FROM events WHERE kind IN ('decision','random_draw')").fetchall():
        entry=json.loads(body);r=entry['inputs']
        if r is None or own.execute("SELECT 1 FROM events WHERE kind='endpoint' AND event_key=?",(key,)).fetchone():continue
        index=entry.get('index_ts',entry['recorded_ts'])
        if now<=index+3780:continue
        if r['mint'] in excluded:
            append(own,'endpoint',key,{'status':'excluded_after_decision','multiple':None,'resolved_ts':now});continue
        # All outcomes come from existing scanner snapshots, not the pilot/tracker.
        paths=src.execute('SELECT '+','.join(FIELDS)+',pair FROM snapshots WHERE mint=? AND ts>=? AND ts<=? ORDER BY ts',(r['mint'],index,index+3780)).fetchall()
        if any(p[-1]!=r['pair'] for p in paths):out=None;why='pair_switch'
        else:
            # Entry MC and time were prospectively committed, not replaced by a later row.
            row0=list(r['inputs'][-1]);row0[0]=index;row0[2]=r['mc']
            exact=[tuple(row0)]+[tuple(p[:-1]) for p in paths if p[0]>index]
            out,why=covered(exact,index)
        append(own,'endpoint',key,{'status':why,'multiple':out['endpoint_multiple'] if out else None,
            'endpoint_2x':out['endpoint_multiple']>=2 if out else None,
            'within_window_2x':out['max_multiple']>=2 if out else None,'resolved_ts':now})

def run_once(own,source=SCANNER,pilot=PILOT,now=None):
    now=int(time.time()) if now is None else now
    a=json.loads(own.execute('SELECT body FROM activation').fetchone()[0]);policy=a['policy']
    if now<a['activated_ts']:raise ValueError('Clock before activation')
    scorer=pure_scorer(pathlib.Path(__file__).with_name('frozen_scorer_source.txt'))
    live_sha256=verify_live_functions()
    src,excluded=membership_connection(source,pilot)
    try:
        halted=own.execute("SELECT 1 FROM events WHERE kind='stop'").fetchone()
        if not halted and (now>=policy['deadline'] or all(n>=policy['target_per_arm'] for n in counts(own).values())):
            with own:append(own,'stop','1',{'ts':min(now,policy['deadline']),'reason':'fixed_date' if now>=policy['deadline'] else 'all_arms_target'})
            halted=True
        if not halted:
            with own:
                rows,reasons=prepare_candidates(src,own,now,scorer)
                n,draws=decisions(own,rows,now,policy)
                append(own,'cycle',str(now),{'ts':now,'candidate_count':len(rows),'universe_sha256':digest([r['mint'] for r in rows]),'reasons':reasons,'decisions_added':n,'random_draws':draws,'source_sha256':SOURCE_SHA,'live_source_sha256':live_sha256})
            # This commit completes before any endpoint computation.
            if all(n>=policy['target_per_arm'] for n in counts(own).values()):
                with own:append(own,'stop','1',{'ts':now,'reason':'all_arms_target'})
        with own:followup(src,own,now,excluded)
        return {'counts':counts(own),'provider_requests':0,'production_changed':False,'telegram_sent':False}
    finally:src.rollback();src.close()

def main():
    p=argparse.ArgumentParser();p.add_argument('--activate',type=pathlib.Path);p.add_argument('--once',action='store_true');a=p.parse_args();require_python()
    STATE.mkdir(parents=True,exist_ok=True,mode=0o700);db=STATE/'shadow.sqlite'
    if not db.exists() and not a.activate:raise SystemExit('Not activated; owner-reviewed frozen policy required')
    if a.activate:
        if db.exists():raise SystemExit('Activation already exists; no reset')
        with sqlite3.connect(db) as con:initialize(con,json.loads(a.activate.read_bytes()),int(time.time()))
        os.chmod(db,0o600);return
    if sum(f.stat().st_size for f in STATE.glob('shadow.sqlite*'))>=MAX_BYTES or shutil.disk_usage(STATE).free<MIN_FREE:raise SystemExit('Shadow storage guard; no production action')
    con=sqlite3.connect(db);con.execute('PRAGMA synchronous=FULL')
    try:print(json.dumps(run_once(con),sort_keys=True))
    finally:con.close()
if __name__=='__main__':main()
