"""Passive snapshot custody only. No analysis, providers, ledger or capture access."""
import argparse, fcntl, hashlib, json, os, pathlib, shutil, sqlite3, subprocess, sys, time
ROOT=pathlib.Path('/var/lib/vivameda-snapshot-archive')
SOURCE=pathlib.Path('/opt/vivameda-crypto-early-scout/data/early_scout.sqlite')
STATUS=pathlib.Path('/opt/vivameda-crypto-pilot-health/read_status.py')
STATUS_SHA='a60a835469585ffcc0f2263f7ba327df83beb3272cea5bff265200e91623d632'
AUDIT=pathlib.Path('/var/lib/vivameda-crypto-pilot-health/incident_send_log.jsonl')
CAP=512*1024**2
FREE=3*1024**3
RESERVE=1024**2
BATCH=5000
COLS=('mint','ts','pair','price','mc','liq','vol_m5','vol_h1','buys_m5','sells_m5','buys_h1','sells_h1','pc_m5','pc_h1')
INCIDENTS={'paused','stalled','unhealthy','unavailable'}
def atomic(path,value):
    tmp=path.with_name('.'+path.name+'.tmp')
    with tmp.open('w') as out:json.dump(value,out,sort_keys=True,allow_nan=False);out.write('\n');out.flush();os.fsync(out.fileno())
    os.replace(tmp,path)
def log(root,record):
    fd=os.open(root/'runs.jsonl',os.O_WRONLY|os.O_APPEND|os.O_CREAT|os.O_NOFOLLOW,0o600)
    with os.fdopen(fd,'a') as out:out.write(json.dumps(record,sort_keys=True,allow_nan=False)+'\n');out.flush();os.fsync(out.fileno())
def stop(root,reason):
    atomic(root/'STOP.json',{'reason':reason,'time':int(time.time())})
def status():
    if hashlib.sha256(STATUS.read_bytes()).hexdigest()!=STATUS_SHA:raise ValueError('status_route_changed')
    data=json.loads(subprocess.run(['/usr/bin/python3',str(STATUS)],capture_output=True,text=True,check=True,timeout=3).stdout)
    now=int(time.time())
    if not 0<=now-data['checked_at']<=300 or data['status']!='collecting':raise ValueError('fresh_collecting_health_required')
    keys=('checked_at','cycles','rejected_cycles','seconds_since_last_cycle')
    result={k:data[k] for k in keys}
    if not all(type(x) is int and x>=0 for x in result.values()):raise ValueError('invalid_count_status')
    return result
def wal_bytes(source):
    p=pathlib.Path(str(source)+'-wal')
    try:return p.stat().st_size
    except FileNotFoundError:return 0
def health_alarm_since(start):
    # Existing sanitized audit only; no capture DB or endpoint reads.
    with AUDIT.open('rb') as stream:
        stream.seek(0,2);size=stream.tell();stream.seek(max(0,size-65536))
        if size>65536:stream.readline()
        for line in stream:
            row=json.loads(line)
            if row['time']>=start and row['state'] in INCIDENTS:return True
    return False
def count_delta(a,b):
    accepted=b['cycles']-a['cycles'];rejected=b['rejected_cycles']-a['rejected_cycles']
    if min(accepted,rejected)<0:raise ValueError('counts_reversed')
    total=accepted+rejected
    return {'accepted':accepted,'rejected':rejected,'total':total,'rejected_rate':rejected/total if total else None}
def rate_kill(baseline,observed):
    return (baseline['total']>=20 and observed['total']>=20 and
            observed['rejected_rate']-baseline['rejected_rate']>=.05-1e-12)
def connect_source(source):
    con=sqlite3.connect(source.resolve().as_uri()+'?mode=ro',uri=True,timeout=.5)
    con.execute('PRAGMA busy_timeout=500');con.execute('PRAGMA query_only=ON')
    def authorize(op,table,column,db,view):
        if op==sqlite3.SQLITE_READ and (table!='snapshots' or column not in COLS):return sqlite3.SQLITE_DENY
        if op in (sqlite3.SQLITE_INSERT,sqlite3.SQLITE_UPDATE,sqlite3.SQLITE_DELETE,sqlite3.SQLITE_ATTACH,sqlite3.SQLITE_DETACH):return sqlite3.SQLITE_DENY
        return sqlite3.SQLITE_OK
    con.set_authorizer(authorize)
    return con
def read_batch(con,cursor,ceiling):
    started=time.monotonic()
    con.set_progress_handler(lambda:int(time.monotonic()-started>1),1000)
    try:
        con.execute('BEGIN')
        return con.execute('SELECT '+','.join(COLS)+' FROM snapshots WHERE (ts,mint)>(?,?) AND ts<=? ORDER BY ts,mint LIMIT 5000',(cursor[0],cursor[1],ceiling)).fetchall()
    finally:
        con.rollback();con.set_progress_handler(None,0)
def create_archive(path):
    con=sqlite3.connect(path,timeout=.5)
    con.execute('PRAGMA journal_mode=DELETE');con.execute('PRAGMA synchronous=FULL')
    con.executescript('''CREATE TABLE IF NOT EXISTS snapshots(mint TEXT NOT NULL,ts INTEGER NOT NULL,pair TEXT,
        price REAL,mc REAL,liq REAL,vol_m5 REAL,vol_h1 REAL,buys_m5 INTEGER,sells_m5 INTEGER,
        buys_h1 INTEGER,sells_h1 INTEGER,pc_m5 REAL,pc_h1 REAL,PRIMARY KEY(mint,ts));
        CREATE INDEX IF NOT EXISTS archive_ts_mint ON snapshots(ts,mint);
        CREATE TRIGGER IF NOT EXISTS snapshots_no_update BEFORE UPDATE ON snapshots BEGIN SELECT RAISE(ABORT,'append only'); END;
        CREATE TRIGGER IF NOT EXISTS snapshots_no_delete BEFORE DELETE ON snapshots BEGIN SELECT RAISE(ABORT,'append only'); END;
        CREATE TABLE IF NOT EXISTS checkpoints(ts INTEGER,mint TEXT,PRIMARY KEY(ts,mint));
        CREATE TRIGGER IF NOT EXISTS checkpoints_no_update BEFORE UPDATE ON checkpoints BEGIN SELECT RAISE(ABORT,'append only'); END;
        CREATE TRIGGER IF NOT EXISTS checkpoints_no_delete BEFORE DELETE ON checkpoints BEGIN SELECT RAISE(ABORT,'append only'); END;''')
    return con
def disk_ok(root,rows=0,cap=CAP,min_free=FREE):
    used=sum(p.stat().st_size for p in root.iterdir() if p.is_file())
    return used*2+rows*4096+RESERVE<cap and shutil.disk_usage(root).free>=min_free
def append_batch(con,rows):
    # Source transaction has ended before any archive write starts.
    if len(rows)>BATCH:raise ValueError('batch too large')
    appended=0
    with con:
        for row in rows:
            if len(row)!=len(COLS) or not isinstance(row[0],str) or type(row[1]) is not int:raise ValueError('invalid snapshot key')
            before=con.total_changes
            con.execute('INSERT OR IGNORE INTO snapshots VALUES('+','.join('?' for _ in COLS)+')',row)
            appended+=con.total_changes-before
        if rows:con.execute('INSERT OR IGNORE INTO checkpoints VALUES(?,?)',(rows[-1][1],rows[-1][0]))
    return appended
def copy(root=ROOT,source=SOURCE,health_reader=status,alarm_reader=health_alarm_since,now=None):
    started=time.monotonic();now=int(time.time()) if now is None else now
    report={'time':now,'appended':0,'copied_ts_min':None,'copied_ts_max':None,'batches':0,'batch_runtime_seconds':[]}
    root=pathlib.Path(root)
    with (root/'writer.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        if (root/'STOP.json').exists():report['state']='stopped';return report
        try:
            atomic(root/'run_started.json',{'time':now})
            before=health_reader();initial= json.loads((root/'baseline_start.json').read_text())
            if before['checked_at']-initial['checked_at']<7200:
                report['state']='baseline_collecting';atomic(root/'postflight.json',{'baseline_start':initial,'latest':before,'wal_bytes':wal_bytes(source),'first_copy_pending':True});return report
            bp=root/'baseline.json'
            if not bp.exists():atomic(bp,{'start':initial,'end':before,'delta':count_delta(initial,before)})
            baseline=json.loads(bp.read_text())
            baseline_counts=baseline['delta']
            active=root/'activation.json'
            if not active.exists():
                if baseline_counts['total']<20:raise ValueError('baseline_sample_insufficient')
                # Recorded before any snapshot access; never reset on later failure.
                fd=os.open(active,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
                with os.fdopen(fd,'w') as out:json.dump({'activation_ts':now,'development_end':now+21*86400,'holdout_end':now+28*86400,'first_copy_status':before},out,sort_keys=True);out.flush();os.fsync(out.fileno())
            activation=json.loads(active.read_text())
            if now>=activation['holdout_end']:raise ValueError('collection_window_closed')
            if alarm_reader(now):raise ValueError('health_incident_during_run')
            previous=json.loads((root/'last_copy_wal.json').read_text()) if (root/'last_copy_wal.json').exists() else None
            pre_wal=wal_bytes(source)
            if previous and pre_wal>previous['bytes']:raise ValueError('wal_grew_run_over_run')
            if not disk_ok(root):raise ValueError('storage_guard')
            dest=create_archive(root/'snapshots.sqlite')
            src=None
            try:
                src=connect_source(source)
                key=dest.execute('SELECT ts,mint FROM checkpoints ORDER BY ts DESC,mint DESC LIMIT 1').fetchone() or (-1,'')
                ceiling=now-120 # Do not archive the mutable current minute.
                while time.monotonic()-started<20 and report['batches']<20:
                    tick=time.monotonic()
                    try:rows=read_batch(src,key,ceiling)
                    except sqlite3.OperationalError as exc:
                        code=getattr(exc,'sqlite_errorcode',0)&255
                        if code in (sqlite3.SQLITE_BUSY,sqlite3.SQLITE_LOCKED,sqlite3.SQLITE_INTERRUPT):report['state']='batch_skipped_busy_or_time_limit';break
                        raise
                    if not rows:report['state']='caught_up';break
                    if alarm_reader(now):raise ValueError('health_incident_during_run')
                    if not disk_ok(root,len(rows)):raise ValueError('storage_guard')
                    dest.execute('PRAGMA max_page_count='+str(max(1,(CAP-RESERVE)//(2*4096))))
                    added=append_batch(dest,rows);key=(rows[-1][1],rows[-1][0])
                    report['appended']+=added;report['batches']+=1
                    report['copied_ts_min']=rows[0][1] if report['copied_ts_min'] is None else report['copied_ts_min']
                    report['copied_ts_max']=rows[-1][1]
                    report['batch_runtime_seconds'].append(round(time.monotonic()-tick,6))
                    if alarm_reader(now):raise ValueError('health_incident_during_run')
                else:report['state']='bounded_run_complete'
            finally:
                if src is not None:src.close()
                dest.close()
            after=health_reader();post_wal=wal_bytes(source)
            observed=count_delta(activation['first_copy_status'],after)
            if rate_kill(baseline_counts,observed):raise ValueError('rejected_cycle_rate_increased')
            if alarm_reader(now):raise ValueError('health_incident_during_run')
            if previous and post_wal>previous['bytes']:raise ValueError('wal_grew_run_over_run')
            atomic(root/'last_copy_wal.json',{'bytes':post_wal,'time':int(time.time())})
            postflight={'baseline':baseline,'latest':after,'since_first_copy':observed,'after_start':activation['first_copy_status'],'after_seconds':after['checked_at']-activation['first_copy_status']['checked_at'],'wal_before':pre_wal,'wal_after':post_wal,'two_hour_after_available':after['checked_at']-activation['first_copy_status']['checked_at']>=7200,'first_copy_pending':False}
            atomic(root/'postflight.json',postflight)
            if postflight['two_hour_after_available'] and not (root/'two_hour_postflight.json').exists():atomic(root/'two_hour_postflight.json',postflight)
        except Exception as exc:
            reasons={'fresh_collecting_health_required','status_route_changed','invalid_count_status','counts_reversed','baseline_sample_insufficient','collection_window_closed','health_incident_during_run','wal_grew_run_over_run','storage_guard','rejected_cycle_rate_increased'}
            reason=str(exc) if str(exc) in reasons else 'archiver_guard_or_io_failed'
            stop(root,reason);report.update(state='stop_requested',reason=reason)
        finally:
            report['runtime_seconds']=round(time.monotonic()-started,6);log(root,report)
    return report
if __name__=='__main__':
    if sys.version_info[:2]!=(3,12):raise SystemExit('Python 3.12 required')
    print(json.dumps(copy(),sort_keys=True))
