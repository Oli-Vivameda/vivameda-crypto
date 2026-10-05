"""Fixed-path owner install. Never edits scanner, model, credentials or source DB."""
import argparse,ast,datetime,hashlib,json,os,pathlib,pwd,subprocess,tempfile
BASE=pathlib.Path(__file__).resolve().parent
APP=pathlib.Path('/opt/vivameda-crypto-learning')
STATE=pathlib.Path('/var/lib/vivameda-crypto-learning')
LIVE=pathlib.Path('/opt/vivameda-conversations-v2/session_agent.py')
FILES=('daily_learning.py','context.py','policy.json','install_daily_learning.py','test_daily_learning.py')
def bundle():return hashlib.sha256(b''.join(n.encode()+b'\0'+(BASE/n).read_bytes()+b'\0' for n in FILES)).hexdigest()
def patch(source):
    if 'def crypto_daily_learning_context_wrapper' in source:return source
    tree=ast.parse(source);nodes=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='automatic_knowledge_context']
    if len(nodes)!=1:raise ValueError('Expected existing automatic crypto context')
    n=nodes[0];lines=source.splitlines(True);lines[n.lineno-1]=lines[n.lineno-1].replace('def automatic_knowledge_context(', 'def base_automatic_knowledge_context(',1)
    wrapper='''\ndef crypto_daily_learning_context_wrapper(q, session):
    base=base_automatic_knowledge_context(q,session)
    if session.get('knowledge_domain')=='crypto':
        from crypto_daily_context import learning_context
        extra=learning_context(q)
        if extra:base+='\\n'+extra
    return base

automatic_knowledge_context=crypto_daily_learning_context_wrapper
'''
    lines.insert(n.end_lineno,wrapper);result=''.join(lines);ast.parse(result);return result

def write(path,data,mode=0o644):
    if any(p.is_symlink() for p in (path,*path.parents)):raise ValueError('Symlink refused')
    fd,tmp=tempfile.mkstemp(prefix='.learning-',dir=path.parent)
    try:
        with os.fdopen(fd,'wb') as f:f.write(data);f.flush();os.fsync(f.fileno())
        os.chmod(tmp,mode);os.chown(tmp,0,0);os.replace(tmp,path)
    finally:
        if os.path.exists(tmp):os.unlink(tmp)

def unit(mode):
    return f'''[Unit]
Description=Vivameda crypto {mode} (no network or execution)
[Service]
Type=oneshot
User=vivameda-scout
Group=vivameda-scout
ExecStart=/usr/bin/python3 {APP}/daily_learning.py {mode} --source /opt/vivameda-crypto-early-scout/data/early_scout.sqlite --state {STATE}
UMask=0077
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ReadWritePaths={STATE}
ReadOnlyPaths=/opt/vivameda-crypto-early-scout/data
RestrictAddressFamilies=AF_UNIX
PrivateNetwork=true
TimeoutStartSec=120
'''
def timer(mode):
    schedule='OnBootSec=90\nOnUnitInactiveSec=60' if mode=='journal' else 'OnCalendar=*-*-* 08:00:00 Asia/Nicosia\nPersistent=true'
    return f'''[Unit]
Description=Vivameda crypto {mode} schedule
[Timer]
{schedule}
Unit=vivameda-crypto-{mode}.service
[Install]
WantedBy=timers.target
'''
def main():
    a=argparse.ArgumentParser();a.add_argument('--install',action='store_true');a.add_argument('--expected-sha256',required=True);x=a.parse_args()
    if bundle()!=x.expected_sha256:raise ValueError('Reviewed bundle changed')
    for n in FILES:
        if (BASE/n).is_symlink():raise ValueError('Symlink source refused')
        if n.endswith('.py'):ast.parse((BASE/n).read_text())
    if not x.install:print(json.dumps({'validated':True,'installed':False,'bundle_sha256':bundle()}));return
    if os.geteuid()!=0:raise SystemExit('Owner maintenance terminal required for fixed service/context installation')
    if any(p.is_symlink() for path in (APP,STATE,LIVE) for p in (path,*path.parents)):raise ValueError('Symlink refused')
    owner=pwd.getpwnam('vivameda-scout');source=LIVE.read_text();new=patch(source)
    # Freeze before any install: an existing policy may not be replaced.
    if (STATE/'learning.sqlite').exists():
        import sqlite3
        with sqlite3.connect('file:'+str(STATE/'learning.sqlite')+'?mode=ro',uri=True) as c:
            row=c.execute('SELECT body FROM activation').fetchone()
        policy=json.loads((BASE/'policy.json').read_text())
        from daily_learning import digest
        if row and json.loads(row[0])['policy_sha256']!=digest(policy):raise ValueError('Existing frozen policy changed')
    stamp=datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    backup=pathlib.Path('/opt/vivameda-operations')/('crypto-learning-backup-'+stamp);backup.mkdir(mode=0o700)
    (backup/'session_agent.py').write_text(source);(backup/'session_agent.py').chmod(0o600)
    for n in FILES:
        if (APP/n).exists():(backup/n).write_bytes((APP/n).read_bytes())
    APP.mkdir(mode=0o755,exist_ok=True);STATE.mkdir(mode=0o755,exist_ok=True);os.chown(STATE,owner.pw_uid,owner.pw_gid)
    for n in FILES:write(APP/n,(BASE/n).read_bytes())
    write(LIVE.with_name('crypto_daily_context.py'),(BASE/'context.py').read_bytes())
    st=LIVE.stat();write(LIVE,new.encode(),st.st_mode&0o777);os.chown(LIVE,st.st_uid,st.st_gid)
    for mode in ('review','journal'):
        for ext,data in (('service',unit(mode)),('timer',timer(mode))):
            dest=pathlib.Path('/etc/systemd/system')/f'vivameda-crypto-{mode}.{ext}'
            if dest.exists():(backup/dest.name).write_bytes(dest.read_bytes())
            write(dest,data.encode())
    subprocess.run(['/usr/bin/systemctl','daemon-reload'],check=True)
    subprocess.run(['/usr/bin/systemctl','start','vivameda-crypto-review.service'],check=True)
    subprocess.run(['/usr/bin/systemctl','enable','--now','vivameda-crypto-review.timer','vivameda-crypto-journal.timer'],check=True)
    print(json.dumps({'installed':True,'bundle_sha256':bundle(),'backup':str(backup),'daily_local_time':'08:00 Asia/Nicosia','journal_interval_seconds':60,'live_execution':False,'weights_updated':False,'scanner_changed':False,'agent_context_patch_requires_new_worker_process':True}))
if __name__=='__main__':main()
