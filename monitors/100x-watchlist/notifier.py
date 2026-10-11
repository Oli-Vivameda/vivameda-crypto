"""Separate research watchlist. No scanner scoring edits or pilot/outcome reads."""
import datetime, fcntl, json, math, os, pathlib, re, sqlite3, tempfile, time
import urllib.parse, urllib.request
import research
BASE=pathlib.Path('/opt/vivameda-crypto-early-scout')
STATE=pathlib.Path('/var/lib/vivameda-100x-watchlist')
REQUIRED=('token_controls','liquidity_control','trading_mechanics')
BACKGROUND=('wallet_clusters','developer_history','top_holder_ownership','wallet_age')
MINT=re.compile(r'[1-9A-HJ-NP-Za-km-z]{32,44}')
FRESH=300
STATE_CAP=1024*1024
def atomic(path,value):
    raw=json.dumps(value,sort_keys=True,allow_nan=False).encode()
    if len(raw)>STATE_CAP:raise ValueError('state cap')
    fd,name=tempfile.mkstemp(dir=path.parent)
    try:
        os.fchmod(fd,0o600)
        with os.fdopen(fd,'wb') as out:out.write(raw);out.flush();os.fsync(out.fileno())
        os.replace(name,path)
    finally:
        if os.path.exists(name):os.unlink(name)
def number(x):return type(x) in (float,int) and math.isfinite(x)
def fresh(x,now):return number(x) and 0<=now-x<=FRESH
def rows(database,activation,now):
    con=sqlite3.connect(database.resolve().as_uri()+'?mode=ro',uri=True,timeout=.2)
    con.row_factory=sqlite3.Row
    started=time.monotonic()
    con.set_progress_handler(lambda:int(time.monotonic()-started>2),1000)
    try:
        con.execute('PRAGMA query_only=ON');con.execute('PRAGMA busy_timeout=200')
        con.execute('BEGIN')
        result=con.execute("""
        SELECT l.mint,l.symbol,l.created_ts,l.pinned_pair,l.last_alert_ts,l.alert_level,
               s.ts,s.mc,s.liq,s.price,r.checked_at,r.verdict,r.review
        FROM launches l
        JOIN snapshots s ON s.mint=l.mint AND s.ts=(
          SELECT max(ts) FROM snapshots WHERE mint=l.mint AND ts<=l.last_alert_ts)
        JOIN prealert_reviews r ON r.rowid=(
          SELECT rowid FROM prealert_reviews WHERE mint=l.mint
          ORDER BY checked_at DESC,rowid DESC LIMIT 1)
        WHERE l.last_alert_ts>=? AND l.last_alert_ts BETWEEN ? AND ?
          AND l.alert_level>0 AND length(r.review)<=131072
        ORDER BY l.last_alert_ts,l.mint LIMIT 100
        """,(activation,now-FRESH,now)).fetchall()
        return [dict(r) for r in result]
    finally:
        con.rollback();con.close()
def valid_evidence(item,now):
    if not isinstance(item,dict):return False
    refs=item.get('evidence_refs')
    return fresh(item.get('observed_at'),now) and isinstance(refs,list) and bool(refs) and all(isinstance(r,str) and r.strip() for r in refs)
def eligible(row,config,now):
    if not MINT.fullmatch(str(row.get('mint',''))) or not MINT.fullmatch(str(row.get('pinned_pair',''))):return False
    if not fresh(row.get('last_alert_ts'),now) or not fresh(row.get('ts'),now):return False
    if row['last_alert_ts']<config['activation_ts'] or row['ts']>row['last_alert_ts']:return False
    mc,liq,price=(row.get(k) for k in ('mc','liq','price'))
    if not all(number(x) and x>0 for x in (mc,liq,price)):return False
    if not config['min_mc']<=mc<=config['max_mc']:return False
    if row.get('verdict')!='PASS' or not fresh(row.get('checked_at'),now):return False
    try:r=json.loads(row['review'])
    except (ValueError,TypeError):return False
    if not isinstance(r,dict):return False
    if r.get('mint')!=row['mint'] or r.get('pair')!=row['pinned_pair'] or r.get('chain')!='solana' or r.get('policy')!='crypto-prealert-v1':return False
    if not fresh(r.get('checked_at'),now):return False
    checks=r.get('checks',{})
    if not isinstance(checks,dict):return False
    if any(isinstance(i,dict) and i.get('status')=='REJECT' for i in checks.values()):return False
    return all(valid_evidence(checks.get(k),now) and checks[k].get('status')=='PASS' for k in REQUIRED)
def clean(s):return ''.join(c for c in str(s) if c.isprintable())[:30]
def classification(row,now):
    checks=json.loads(row['review'])['checks']
    complete=all(valid_evidence(checks.get(k),now) and checks[k].get('status')=='PASS' for k in BACKGROUND)
    return 'SCREENING COMPLETE' if complete else 'EARLY WATCH — INCOMPLETE SCREENING'
def message(row,now,assessment=None):
    checks=json.loads(row['review'])['checks'];bg=[]
    for name in BACKGROUND:
        item=checks.get(name,{})
        status=item.get('status','UNKNOWN') if valid_evidence(item,now) else 'UNKNOWN'
        if status!='PASS':status='UNKNOWN'
        bg.append(name.replace('_',' ')+': '+status)
    stamp=datetime.datetime.fromtimestamp(row['ts'],datetime.timezone.utc).isoformat()
    age='unverified'
    if number(row.get('created_ts')) and 0<row['created_ts']/1000<=row['ts']:
        age=f"{(row['ts']-row['created_ts']/1000)/3600:.1f}h"
    return (
        '🔥 '+classification(row,now)+' — SOLANA\n\n'
        +clean(row.get('symbol','?'))+' | age at snapshot '+age+'\n'
        +f"Alert snapshot MC ${row['mc']:,.0f} | liquidity ${row['liq']:,.0f}\n"
        +f"Snapshot price ${row['price']:.10g}\n"
        +'Snapshot UTC: '+stamp+'\n'
        +'Why surfaced: existing scanner alert; snapshot MC within $100k–$500k; required checks PASS.\n'
        +research.describe(assessment or research.empty(row,now))+'\n'
        +'100×: search objective and valuation scenario, not a forecast.\n'
        +f"100× price scenario implies MC ${row['mc']*100:,.0f}, assuming unchanged supply.\n\n"
        +'Required scanner checks PASS: token controls, liquidity control, recent sell receipts.\n'
        +'\n'.join(bg)+'\n\n'
        +'Research watchlist only. No validated 100× probability or entry recommendation.\n'
        +'No independent catalyst, growth or executable exit quote verified by this relay.\n'
        +'Mint: '+row['mint']+'\nPool: '+row['pinned_pair']+'\n'
        +'https://dexscreener.com/solana/'+row['pinned_pair'])
def send(text,credentials=BASE/'credentials.json'):
    c=json.loads(credentials.read_text())
    body=urllib.parse.urlencode({'chat_id':str(c['chat_id']),'text':text,'disable_web_page_preview':'true'}).encode()
    request=urllib.request.Request('https://api.telegram.org/bot'+c['bot_token']+'/sendMessage',data=body,method='POST')
    with urllib.request.urlopen(request,timeout=12) as response:result=json.load(response)
    if result.get('ok') is not True:raise ValueError('delivery failed')
def run(state=STATE,database=BASE/'data'/'early_scout.sqlite',sender=send,now=None,assessor=None):
    live_clock=now is None
    now=int(time.time()) if now is None else now
    config=json.loads((state/'config.json').read_text())
    report={'checked_at':now,'candidate_messages_sent':0,'market_provider_requests':0,'pilot_read':False,'scanner_changed':False}
    deadline=config['deadline_ts']
    if deadline is not None and (not number(deadline) or deadline<config['activation_ts']):raise ValueError('invalid deadline')
    if deadline is not None and now>=deadline:
        report['state']='expired';atomic(state/'status.json',report);return report
    if now<config['activation_ts']:raise ValueError('clock before activation')
    if (state/'STOP').exists():
        report['state']='stopped';atomic(state/'status.json',report);return report
    ledger_path=state/'delivery.json'
    if ledger_path.stat().st_size>STATE_CAP:raise ValueError('state cap')
    ledger=json.loads(ledger_path.read_text())
    if not isinstance(ledger,dict):raise ValueError('invalid delivery state')
    if len(ledger)>=2000:
        report['state']='state_cap';atomic(state/'status.json',report);return report
    if now-max(ledger.get('_last_attempt',0),ledger.get('_last_research',0))<300:
        report['state']='cooldown';atomic(state/'status.json',report);return report
    try:candidates=rows(database,config['activation_ts'],now)
    except sqlite3.OperationalError:
        report['state']='read_skipped';atomic(state/'status.json',report);return report
    report['state']='waiting'
    for row in candidates:
        if row['mint'] in ledger or not eligible(row,config,now):continue
        audit=state/'research';audit.mkdir(mode=0o700,exist_ok=True)
        if len(list(audit.iterdir()))>=2000 and not (audit/(row['mint']+'.json')).exists():
            report['state']='state_cap';break
        ledger['_last_research']=now;atomic(ledger_path,ledger)
        assessment=(assessor or research.assess)(row,database,now)
        if assessment.get('mint')!=row['mint'] or assessment.get('pair')!=row['pinned_pair'] or assessment.get('policy')!=research.POLICY:raise ValueError('research identity')
        report['market_provider_requests']+=assessment['provider_requests']
        atomic(audit/(row['mint']+'.json'),assessment)
        if assessment['identity']=='MISMATCH':
            report['state']='research_identity_mismatch';break
        # Network research can take seconds; any newer HOLD/REJECT or stale screen blocks delivery.
        current=int(time.time()) if live_clock else now
        latest=next((r for r in rows(database,config['activation_ts'],current) if r['mint']==row['mint']),None)
        if latest is None or latest['pinned_pair']!=row['pinned_pair'] or not eligible(latest,config,current):
            report['state']='screening_changed';break
        if (state/'STOP').exists():
            report['state']='stopped';break
        row=latest;now=current
        text=message(row,now,assessment)
        ledger[row['mint']]={'attempted_at':now,'result':'delivery_unknown'}
        ledger['_last_attempt']=now
        atomic(ledger_path,ledger)
        try:
            sender(text);ledger[row['mint']]['result']='sent'
            report['candidate_messages_sent']=1;report['state']='sent'
        except Exception:report['state']='delivery_unknown'
        atomic(ledger_path,ledger);break
    atomic(state/'status.json',report);return report
def main():
    with (STATE/'run.lock').open('a') as lock:
        try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:return
        try:report=run()
        except Exception:
            report={'checked_at':int(time.time()),'state':'failed_closed','candidate_messages_sent':0}
            try:atomic(STATE/'status.json',report)
            except Exception:pass
        print(json.dumps(report,sort_keys=True))
if __name__=='__main__':main()

