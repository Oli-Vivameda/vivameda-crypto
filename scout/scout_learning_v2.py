#!/usr/bin/env python3
import json,logging,sqlite3,time
from pathlib import Path
import requests
import early_scout as prod
BASE=Path('/opt/vivameda-crypto-early-scout'); DB=BASE/'data'/'early_scout.sqlite'
LOG=BASE/'logs'/'learning_v2.log'; H=(1,5,15,30,60,120,180,360,720,1440)
S=requests.Session(); S.headers.update({'User-Agent':'Vivameda-Learning-V2'})
def configure_logging():
 # early_scout configures root logging on import; this process needs its own file.
 logging.basicConfig(filename=LOG,level=logging.INFO,format='%(asctime)s %(levelname)s %(message)s',force=True)
def f(v):
 try:return float(v)
 except:return 0.0
def db():
 c=sqlite3.connect(DB,timeout=30); c.execute('PRAGMA journal_mode=WAL')
 c.execute('''CREATE TABLE IF NOT EXISTS v2_cases(id TEXT PRIMARY KEY,mint TEXT,decision_ts INTEGER,
 source TEXT,score INTEGER,level INTEGER,regime TEXT,features TEXT,entry_price REAL,entry_mc REAL,
 entry_liq REAL,status TEXT DEFAULT 'ACTIVE')''')
 c.execute('''CREATE TABLE IF NOT EXISTS v2_state(id TEXT PRIMARY KEY,peak_mc REAL,peak_ts INTEGER,
 trough_mc REAL,trough_ts INTEGER,last_mc REAL,last_liq REAL,last_ts INTEGER,max_mult REAL DEFAULT 1,
 min_mult REAL DEFAULT 1,label TEXT DEFAULT 'OPEN')''')
 c.execute('''CREATE TABLE IF NOT EXISTS v2_outcomes(id TEXT,horizon INTEGER,observed_ts INTEGER,
 lateness INTEGER,mc REAL,liq REAL,multiple REAL,max_mult REAL,min_mult REAL,drawdown REAL,
 PRIMARY KEY(id,horizon))''')
 c.execute('''CREATE TABLE IF NOT EXISTS v2_evals(mint TEXT,ts INTEGER,score INTEGER,regime TEXT,
 features TEXT,failed TEXT,alert_level INTEGER,PRIMARY KEY(mint,ts))''')
 c.execute('''CREATE TABLE IF NOT EXISTS v2_challenger(ts INTEGER,regime TEXT,n INTEGER,n2 INTEGER,
 n3 INTEGER,n5 INTEGER,nfail INTEGER,p2 REAL,p3 REAL,p5 REAL,pfail REAL,PRIMARY KEY(ts,regime))''')
 # Legacy outcome/state peaks remain diagnostic only; never backfill timed evidence.
 c.execute('''CREATE TABLE IF NOT EXISTS v2_observations(
 id TEXT, observed_ts INTEGER, mc REAL, liq REAL, PRIMARY KEY(id,observed_ts))''')
 c.execute('''CREATE TABLE IF NOT EXISTS v2_horizon_metrics(
 id TEXT,horizon INTEGER,observed_ts INTEGER,coverage_ok INTEGER,samples INTEGER,
 max_gap INTEGER,max_mult REAL,min_mult REAL,PRIMARY KEY(id,horizon))''')
 c.execute('''CREATE TABLE IF NOT EXISTS v2_challenger_horizon(
 ts INTEGER,source TEXT,regime TEXT,horizon INTEGER,n_due INTEGER,n_timed INTEGER,
 n INTEGER,n_missing INTEGER,n_incomplete INTEGER,n2 INTEGER,n3 INTEGER,n5 INTEGER,
 nfail INTEGER,p2 REAL,p3 REAL,p5 REAL,pfail REAL,
 PRIMARY KEY(ts,source,regime,horizon))''')
 c.commit();return c
def features(rows):
 if not rows:return {}
 cur=rows[-1]; ps=[f(r[1]) for r in rows if f(r[1])>0]; ls=[f(r[3]) for r in rows if f(r[3])>0]
 if not ps:return {}
 b,s=int(cur[8] or 0),int(cur[9] or 0); mc=f(cur[2]); v1=f(cur[5]); v5=f(cur[4])
 low=min(ps); high=max(ps); li=ps.index(low)
 return {'points':len(rows),'history_min':(rows[-1][0]-rows[0][0])/60,'price':f(cur[1]),
 'mc':mc,'liq':f(cur[3]),'vol5':v5,'vol1':v1,'buys1':b,'sells1':s,
 'buy_ratio':b/max(1,b+s),'vol_mc':v1/max(1,mc),'pc5':f(cur[10]),'pc1':f(cur[11]),
 'band':(high-low)/low,'net':ps[-1]/ps[0]-1,'liq_change':ls[-1]/ls[0]-1 if len(ls)>1 else 0,
 'vol_accel':v5/max(1,v1/12),'reclaim':ps[-1]/low-1,'low_pos':li/max(1,len(ps)-1)}
def regime(x):
 if x.get('points',0)<4:return 'INSUFFICIENT'
 if x['pc1']>=35 and x['vol_mc']>=.75 and x['buy_ratio']>=.50 and x['liq']>=25000:return 'CONTINUATION'
 if x['band']<=.35 and -.12<=x['net']<=.25 and x['liq']>=25000:return 'COMPRESSION'
 if x['band']>=.30 and x['reclaim']>=.15 and x['buy_ratio']>=.51 and x['low_pos']>0:return 'RECLAIM'
 return 'OTHER'
def label(maxm,lastm,liq):
 if maxm>=10:return '10X_PLUS'
 if maxm>=5:return '5X'
 if maxm>=3:return '3X'
 if maxm>=2:return '2X'
 if maxm>=1.35:return 'WEAK'
 if lastm<=.55 or liq<=5000:return 'FAILED'
 return 'FLAT'
def capture(c):
 now=int(time.time()); bucket=now//300*300
 ms=c.execute('''SELECT DISTINCT s.mint FROM snapshots s JOIN launches l ON l.mint=s.mint
 WHERE s.ts>=? AND l.created_ts BETWEEN ? AND ?''',(now-120,(now-6*3600)*1000,(now-30*60)*1000)).fetchall()
 for (mint,) in ms:
  rows=c.execute('''SELECT ts,price,mc,liq,vol_m5,vol_h1,buys_m5,sells_m5,buys_h1,sells_h1,
  pc_m5,pc_h1 FROM snapshots WHERE mint=? AND ts>=? AND ts<=? ORDER BY ts''',(mint,now-2100,now)).fetchall()
  if not rows:continue
  score,m,failed=prod.score_candidate(rows); x=features(rows); x.update(m or {}); rg=regime(x)
  al=c.execute('SELECT alert_level,last_alert_ts FROM launches WHERE mint=?',(mint,)).fetchone() or (0,0)
  c.execute('INSERT OR IGNORE INTO v2_evals VALUES(?,?,?,?,?,?,?)',
   (mint,bucket,score,rg,json.dumps(x,sort_keys=True),json.dumps(failed),al[0]))
  cur=rows[-1]; sid=mint+':shadow'
  c.execute('''INSERT OR IGNORE INTO v2_cases(id,mint,decision_ts,source,score,level,regime,features,
  entry_price,entry_mc,entry_liq) VALUES(?,?,?,?,?,?,?,?,?,?,?)''',
   (sid,mint,now,'SHADOW',score,al[0],rg,json.dumps(x,sort_keys=True),f(cur[1]),f(cur[2]),f(cur[3])))
  ats=int(al[1] or 0)
  if ats:
   snap=c.execute('SELECT ts,price,mc,liq FROM snapshots WHERE mint=? AND ts<=? ORDER BY ts DESC LIMIT 1',(mint,ats)).fetchone()
   pre=c.execute('''SELECT ts,price,mc,liq,vol_m5,vol_h1,buys_m5,sells_m5,buys_h1,sells_h1,
   pc_m5,pc_h1 FROM snapshots WHERE mint=? AND ts>=? AND ts<=? ORDER BY ts''',(mint,ats-2100,ats)).fetchall()
   if snap and pre:
    ax=features(pre); asc,am,af=prod.score_candidate(pre); ax.update(am or {}); arg=regime(ax); aid=f'{mint}:alert:{ats}'
    c.execute('''INSERT OR IGNORE INTO v2_cases(id,mint,decision_ts,source,score,level,regime,features,
    entry_price,entry_mc,entry_liq) VALUES(?,?,?,?,?,?,?,?,?,?,?)''',
     (aid,mint,ats,'ALERT',asc,al[0],arg,json.dumps(ax,sort_keys=True),f(snap[1]),f(snap[2]),f(snap[3])))
 c.commit()
def import_alerts(c):
 now=int(time.time())
 for mint,level,ats in c.execute('SELECT mint,alert_level,last_alert_ts FROM launches WHERE alert_level>0 AND last_alert_ts>=?',(now-86400,)).fetchall():
  aid=f'{mint}:alert:{ats}'
  if c.execute('SELECT 1 FROM v2_cases WHERE id=?',(aid,)).fetchone():continue
  snap=c.execute('SELECT ts,price,mc,liq FROM snapshots WHERE mint=? AND ts<=? ORDER BY ts DESC LIMIT 1',(mint,ats)).fetchone()
  pre=c.execute('''SELECT ts,price,mc,liq,vol_m5,vol_h1,buys_m5,sells_m5,buys_h1,sells_h1,
   pc_m5,pc_h1 FROM snapshots WHERE mint=? AND ts>=? AND ts<=? ORDER BY ts''',(mint,ats-2100,ats)).fetchall()
  if not snap or not pre:continue
  x=features(pre); score,m,failed=prod.score_candidate(pre);x.update(m or {});rg=regime(x)
  c.execute('''INSERT OR IGNORE INTO v2_cases(id,mint,decision_ts,source,score,level,regime,features,
   entry_price,entry_mc,entry_liq) VALUES(?,?,?,?,?,?,?,?,?,?,?)''',
   (aid,mint,ats,'ALERT',score,level,rg,json.dumps(x,sort_keys=True),f(snap[1]),f(snap[2]),f(snap[3])))
 c.commit()
def seed(c):
 for cid,mc,ts in c.execute('''SELECT d.id,d.entry_mc,d.decision_ts FROM v2_cases d
 LEFT JOIN v2_state s ON s.id=d.id WHERE s.id IS NULL''').fetchall():
  c.execute('INSERT INTO v2_state(id,peak_mc,peak_ts,trough_mc,trough_ts,last_mc,last_ts) VALUES(?,?,?,?,?,?,?)',
   (cid,mc,ts,mc,ts,mc,ts))
 c.commit()
def dex(mints):
 out=[]
 for batch in prod.chunks(mints,30):
  try:
   d=prod.get_json(prod.DEX_BATCH+','.join(batch),timeout=12)
   if isinstance(d,list):out.extend(d)
  except Exception as e:logging.warning('dex %s',e)
  time.sleep(.2)
 by={}
 for p in out:by.setdefault((p.get('baseToken') or {}).get('address'),[]).append(p)
 return by
def expire(c,now):
 # Independent of launch joins, provider availability and polling selection.
 count=c.execute("UPDATE v2_cases SET status='RESOLVED' WHERE status='ACTIVE' AND decision_ts<?",
                 (now-max(H)*60-180,)).rowcount
 c.commit()
 if count:logging.info('v2 expired cases=%s',count)
 return count
def horizon_metric(c,cid,dts,h,em,observed_ts):
 # Strict within-horizon peaks exclude even timely-but-late endpoint prices.
 due=dts+h*60
 rows=c.execute('''SELECT observed_ts,mc FROM v2_observations
 WHERE id=? AND observed_ts>=? AND observed_ts<=? ORDER BY observed_ts''',
 (cid,dts,due)).fetchall()
 times=[dts]+[r[0] for r in rows]+[due]
 gap=max(b-a for a,b in zip(times,times[1:]))
 valid=bool(rows) and gap<=180 and em>0
 multiples=[1.0]+[r[1]/em for r in rows] if em>0 else []
 c.execute('INSERT OR IGNORE INTO v2_horizon_metrics VALUES(?,?,?,?,?,?,?,?)',
 (cid,h,observed_ts,int(valid),len(rows),gap,
 max(multiples) if multiples else None,min(multiples) if multiples else None))
def track(c):
 now=int(time.time());expire(c,now)
 cs=c.execute('''SELECT d.id,d.mint,d.decision_ts,d.entry_mc,l.pinned_pair FROM v2_cases d
 JOIN launches l ON l.mint=d.mint WHERE d.status='ACTIVE' AND d.decision_ts>=?''',(now-max(H)*60-180,)).fetchall()
 by=dex(sorted(set(r[1] for r in cs))) if cs else {}
 # Timestamp after fetching: slow HTTP responses must not masquerade as on-time.
 now=int(time.time());expire(c,now)
 for cid,mint,dts,em,pinned in cs:
  if now-dts>max(H)*60+180:continue
  pair=prod.choose_pair(mint,by.get(mint,[]),pinned)
  if not pair:continue
  mc=f(pair.get('marketCap')); liq=f((pair.get('liquidity') or {}).get('usd'))
  if mc<=0 or em<=0:continue
  c.execute('INSERT OR IGNORE INTO v2_observations VALUES(?,?,?,?)',(cid,now,mc,liq))
  st=c.execute('SELECT peak_mc,peak_ts,trough_mc,trough_ts,max_mult,min_mult FROM v2_state WHERE id=?',(cid,)).fetchone()
  if not st:continue
  pm,pts,tm,tts,maxm,minm=st; mult=mc/max(1,em)
  if mc>pm:pm,pts=mc,now
  if mc<tm:tm,tts=mc,now
  maxm=max(maxm,mult);minm=min(minm,mult); lab=label(maxm,mult,liq)
  c.execute('''UPDATE v2_state SET peak_mc=?,peak_ts=?,trough_mc=?,trough_ts=?,last_mc=?,last_liq=?,
  last_ts=?,max_mult=?,min_mult=?,label=? WHERE id=?''',(pm,pts,tm,tts,mc,liq,now,maxm,minm,lab,cid))
  age=(now-dts)/60
  for h in H:
   if age<h or c.execute('SELECT 1 FROM v2_outcomes WHERE id=? AND horizon=?',(cid,h)).fetchone():continue
   late=max(0,now-(dts+h*60))
   if late>180:continue
   dd=mc/max(1,pm)-1
   c.execute('INSERT INTO v2_outcomes VALUES(?,?,?,?,?,?,?,?,?,?)',(cid,h,now,late,mc,liq,mult,maxm,minm,dd))
   horizon_metric(c,cid,dts,h,em,now)
   logging.info('v2 checkpoint id=%s horizon_min=%s observed_ts=%s lateness_s=%s multiple=%.4f',cid,h,now,late,mult)
 c.commit()
def challenge(c):
 now=int(time.time());stamp=now//900*900
 # Retire lifetime-peak challenger calculation. Existing rows are legacy only.
 for h in H:
  rows=c.execute('''SELECT d.source,d.regime,d.decision_ts,o.observed_ts,o.lateness,
   o.multiple,o.liq,m.coverage_ok,m.max_mult
   FROM v2_cases d
   LEFT JOIN v2_outcomes o ON o.id=d.id AND o.horizon=?
   LEFT JOIN v2_horizon_metrics m ON m.id=d.id AND m.horizon=?
    AND m.observed_ts=o.observed_ts
   WHERE d.decision_ts+?*60+180<=?''',(h,h,h,now)).fetchall()
  groups={}
  for source,rg,dts,ots,late,multiple,liq,ok,peak in rows:
   g=groups.setdefault((source,rg),[0,0,0,0,0,0,0])
   g[0]+=1
   if ots is None or late is None or not 0<=late<=180 or ots!=dts+h*60+late:continue
   g[1]+=1
   if not ok or peak is None:continue
   g[2]+=1
   g[3]+=int(peak>=2);g[4]+=int(peak>=3);g[5]+=int(peak>=5)
   g[6]+=int(multiple<=.55 or liq<=5000)
  for (source,rg),(due,timed,n,n2,n3,n5,nf) in groups.items():
   # Raw observed rates; missing/incomplete cases never count as failures.
   rates=[v/n if n else None for v in (n2,n3,n5,nf)]
   c.execute('INSERT OR REPLACE INTO v2_challenger_horizon VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',
    (stamp,source,rg,h,due,timed,n,due-timed,timed-n,n2,n3,n5,nf,*rates))
 c.commit()
 timing=c.execute('''SELECT count(*),min(o.observed_ts),max(o.observed_ts),
 min(o.lateness),max(o.lateness),
 sum(CASE WHEN o.lateness<0 OR o.lateness>180
 OR o.observed_ts!=d.decision_ts+o.horizon*60+o.lateness THEN 1 ELSE 0 END)
 FROM v2_outcomes o JOIN v2_cases d ON d.id=o.id''').fetchone()
 logging.info('v2 evidence timing_count_first_last_minlate_maxlate_invalid=%s horizon_metrics=%s eligible=%s expired_active=%s',
  timing,c.execute('SELECT count(*) FROM v2_horizon_metrics').fetchone()[0],
  c.execute('SELECT count(*) FROM v2_horizon_metrics WHERE coverage_ok=1').fetchone()[0],
  c.execute("SELECT count(*) FROM v2_cases WHERE status='ACTIVE' AND decision_ts<?",
   (now-max(H)*60-180,)).fetchone()[0])
def main():
 configure_logging()
 c=db();logging.info('v2 started');last=0
 while True:
  try:
   expire(c,int(time.time()))
   capture(c);import_alerts(c);seed(c);track(c)
   if time.time()-last>900:challenge(c);last=time.time()
  except Exception as e:logging.exception('loop %s',e)
  time.sleep(60)
if __name__=='__main__':main()
