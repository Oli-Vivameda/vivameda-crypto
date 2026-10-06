#!/usr/bin/env python3
"""Owner-run, hash-bound recovery of the first empty paused pilot only."""
import argparse
import ast
import hashlib
import json
import os
from pathlib import Path
import shutil
import sqlite3
import subprocess
import tempfile
import time

HERE=Path(__file__).resolve().parent
BASE=Path('/opt/vivameda-crypto-early-scout')
ORIGINAL='3e73978a41e2e21e090a7eea92bbdc1a52dc190ce229ac262a3c6a2b0af6a043'
TRACKER='a519ad19680ba72f0d593c4627fe5faa2d8dfa93fcd112eaba21abcf5a6da9b6'
PROTOCOL='3baef84dc6f3dfddff9ea38c1139c4979b86af0d4dbb66e641ea00b44b7359ad'
ACTIVATION=1791269439
DEADLINE=1792479039
UNITS=('vivameda-early-scout.service','vivameda-scout-learning-v2.service')
FILES=('early_scout.py','AMENDMENT_20261006.md','install_recovery.py')

def digest(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()

def file_hash(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def bundle_hash():return digest({f:file_hash(HERE/f) for f in FILES})

def audit_empty(con):
    a=json.loads(con.execute('SELECT body FROM fc_activation WHERE id=1').fetchone()[0])
    if (a.get('activation_ts')!=ACTIVATION or a.get('deadline')!=DEADLINE or
        a.get('protocol_sha256')!=PROTOCOL or a.get('scanner_sha256')!=ORIGINAL or
        a.get('tracker_sha256')!=TRACKER):raise ValueError('original activation mismatch')
    if con.execute('SELECT count(*) FROM fc_events').fetchone()[0]!=0:
        raise ValueError('recovery restricted to original empty pilot')
    required={f'{t}_no_{op}' for t in ('fc_activation','fc_events','fc_excluded') for op in ('UPDATE','DELETE')}|{'fc_excluded_frozen'}
    names={r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='trigger'")}
    if not required<=names:raise ValueError('immutability triggers missing')
    excluded=[r[0] for r in con.execute('SELECT mint FROM fc_excluded ORDER BY mint')]
    if len(excluded)!=a['excluded_count'] or digest(excluded)!=a['excluded_sha256']:
        raise ValueError('exclusion binding mismatch')
    return a

def append_repair(con,a,scanner_hash,amendment_hash,pause,now):
    body={'original_scanner_sha256':ORIGINAL,'scanner_sha256':scanner_hash,
          'tracker_sha256':TRACKER,'amendment_sha256':amendment_hash,
          'activation_ts':a['activation_ts'],'deadline':a['deadline'],
          'repair_ts':now,'original_pause_ts':pause['observed_ts'],
          'original_cause':'unknown_discarded_exception_message',
          'collection_gap_seconds':now-pause['observed_ts'],
          'outcomes_inspected':False,'deadline_extended':False}
    encoded=json.dumps(body,sort_keys=True,separators=(',',':'),allow_nan=False)
    h=digest([1,'runtime_repair','20261006',encoded,'0'*64])
    con.execute('INSERT INTO fc_events VALUES(?,?,?,?,?,?)',(1,'runtime_repair','20261006',encoded,'0'*64,h))
    return h

def systemctl(action,units=UNITS):
    subprocess.run(['/usr/bin/systemctl',action,*units],check=True,capture_output=True,text=True,timeout=45)

def replace_source(target,data,stat):
    fd,name=tempfile.mkstemp(prefix='.recovery-',dir=target.parent)
    try:
        os.fchmod(fd,stat.st_mode&0o777);os.fchown(fd,stat.st_uid,stat.st_gid)
        with os.fdopen(fd,'wb') as out:out.write(data);out.flush();os.fsync(out.fileno())
        os.replace(name,target)
    finally:
        if os.path.exists(name):os.unlink(name)

def counts(database):
    con=sqlite3.connect('file:'+str(database)+'?mode=ro',uri=True,timeout=.1)
    try:return dict(con.execute('SELECT kind,count(*) FROM fc_events GROUP BY kind'))
    finally:con.close()

def install(expected,apply=False):
    if bundle_hash()!=expected:raise ValueError('reviewed recovery bundle mismatch')
    if file_hash(BASE/'early_scout.py')!=ORIGINAL or file_hash(BASE/'scout_learning_v2.py')!=TRACKER:
        raise ValueError('original deployed source mismatch')
    ast.parse((HERE/'early_scout.py').read_text())
    directory=BASE/'data'/'forward_capture';database=directory/'capture.sqlite';marker=directory/'PAUSED.json'
    pause=json.loads(marker.read_text())
    if pause.get('paused') is not True or pause.get('reason')!='ValueError' or pause.get('observed_ts')!=1791269470:
        raise ValueError('original pause mismatch')
    now=int(time.time())
    if not ACTIVATION<=now<DEADLINE:raise ValueError('original collection deadline expired')
    con=sqlite3.connect('file:'+str(database)+'?mode=ro',uri=True,timeout=.1)
    try:con.execute('PRAGMA query_only=ON');a=audit_empty(con)
    finally:con.close()
    report={'validated':True,'installed':False,'bundle_sha256':expected,
            'activation_ts':ACTIVATION,'deadline':DEADLINE,'deadline_extended':False,
            'model_ledger_changed':False,'provider_requests_added':0,'live_execution':False,
            'original_failure_cause_known':False,'private_data_published':False}
    if not apply:return report
    if os.geteuid()!=0:raise PermissionError('owner root required')
    if shutil.disk_usage(directory).free<2*1024**3:raise ValueError('insufficient recovery disk')
    if (directory/'PAUSED.original-20261006.json').exists():raise ValueError('prior recovery preserved')
    original_bytes=(BASE/'early_scout.py').read_bytes();stat=(BASE/'early_scout.py').stat()
    backup=Path(tempfile.mkdtemp(prefix='crypto-capture-recovery-',dir='/opt/vivameda-operations'))
    backup.chmod(0o700)
    stopped=False
    try:
        systemctl('stop');stopped=True
        # Recheck after stopping both writers; no outcome/event payloads are opened.
        con=sqlite3.connect('file:'+str(database)+'?mode=rw',uri=True,timeout=.1)
        try:
            a=audit_empty(con)
            target=sqlite3.connect(backup/'capture.sqlite')
            try:con.backup(target)
            finally:target.close()
            (backup/'capture.sqlite').chmod(0o600)
            shutil.copy2(BASE/'early_scout.py',backup/'early_scout.py')
            shutil.copy2(marker,backup/'PAUSED.json')
            con.execute('PRAGMA synchronous=FULL');con.execute('BEGIN IMMEDIATE')
            head=append_repair(con,a,file_hash(HERE/'early_scout.py'),file_hash(HERE/'AMENDMENT_20261006.md'),pause,int(time.time()))
            con.commit()
        finally:con.close()
        replace_source(BASE/'early_scout.py',(HERE/'early_scout.py').read_bytes(),stat)
        os.rename(marker,directory/'PAUSED.original-20261006.json')
        systemctl('start');stopped=False
        report.update(installed=True,backup=str(backup),repair_head_sha256=head,
                      scanner_sha256=file_hash(BASE/'early_scout.py'),pause_archived=True)
    except Exception:
        replace_source(BASE/'early_scout.py',original_bytes,stat)
        if not marker.exists() and (backup/'PAUSED.json').exists():shutil.copy2(backup/'PAUSED.json',marker)
        if stopped:systemctl('start')
        raise
    # Count-only verification. A rejected cycle is activity, not usable coverage.
    finish=time.monotonic()+180
    while time.monotonic()<finish:
        c=counts(database)
        if marker.exists() or c.get('cycle',0)>0 or c.get('rejected_cycle',0)>0:break
        time.sleep(2)
    report['event_counts']=c
    report['status']='paused' if marker.exists() else ('collecting' if c.get('cycle',0) or c.get('rejected_cycle',0) else 'first_cycle_pending')
    report['usable_cycle_verified']=c.get('cycle',0)>0
    if marker.exists():
        m=json.loads(marker.read_text());report['pause_code']=m.get('code','other_capture_error')
    report['services_active']=all(subprocess.run(['/usr/bin/systemctl','is-active',u],capture_output=True,text=True,timeout=5).stdout.strip()=='active' for u in UNITS)
    systemctl('start',('vivameda-crypto-pilot-health.service',))
    return report

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--install',action='store_true');p.add_argument('--expected-sha256',required=True);args=p.parse_args()
    try:print(json.dumps(install(args.expected_sha256,args.install),sort_keys=True))
    except Exception as e:
        safe={'reviewed recovery bundle mismatch','original deployed source mismatch','original activation mismatch',
              'recovery restricted to original empty pilot','immutability triggers missing','exclusion binding mismatch',
              'original pause mismatch','original collection deadline expired','owner root required',
              'insufficient recovery disk','prior recovery preserved'}
        raise SystemExit(str(e) if str(e) in safe else 'Recovery failed; private details suppressed, check service status')
