"""Owner-only, reviewed-hash installation; company sources remain private."""
import argparse,ast,datetime,fcntl,hashlib,json,os,pathlib,pwd,shutil,sqlite3,subprocess,tempfile,time
from integration_patch import patch_helper,patch_main,patch_workspace

BASE=pathlib.Path(__file__).resolve().parent
APP=pathlib.Path('/opt/vivameda-crypto-runtime')
STATE=pathlib.Path('/var/lib/vivameda-crypto-runtime')
FILES=('crypto_agent.py','crypto_boundary.py','crypto_runtime.py','runtime_gateway.py','model_proxy.py','integration_patch.py','install_runtime.py','test_crypto_runtime.py','vivameda-crypto-runtime.service','vivameda-crypto-model.service','RUNTIME_SEPARATION.md')
TARGETS={'main':pathlib.Path('/opt/vivameda-conversations-v2/session_agent.py'),'workspace':pathlib.Path('/opt/vivameda-workspace/server.py'),'helper':pathlib.Path('/opt/vivameda-connect/helper.py')}
UNITS=('vivameda-crypto-model.service','vivameda-crypto-runtime.service')
SHARED=('vivameda-workspace.service','vivameda-engineering-helper.service')

def sha(raw):return hashlib.sha256(raw).hexdigest()
def bundle():return sha(b''.join(n.encode()+b'\0'+(BASE/n).read_bytes()+b'\0' for n in FILES))
def checked(p):
    if any(x.is_symlink() for x in [p,*p.parents]):raise ValueError('Symlink refused')
def command(argv):return subprocess.run(argv,check=True,capture_output=True,text=True,timeout=30)
def write(p,raw,uid=0,gid=0,mode=0o644):
    checked(p);fd,name=tempfile.mkstemp(prefix='.crypto-runtime-',dir=p.parent)
    try:
        with os.fdopen(fd,'wb') as f:f.write(raw);f.flush();os.fsync(f.fileno())
        os.chmod(name,mode);os.chown(name,uid,gid);os.replace(name,p)
    finally:
        if os.path.exists(name):os.unlink(name)
def user(name,group):
    try:return pwd.getpwnam(name)
    except KeyError:
        command(['/usr/sbin/useradd','--system','--no-create-home','--home-dir','/nonexistent','--shell','/usr/sbin/nologin','--gid',group,name]);return pwd.getpwnam(name)
def postflight():
    code="import runtime_gateway as g,json,time; h=g.call('health',owner=2); assert h['inet_socket_blocked'] and not h['company_paths_visible']; r=g.enqueue(2,dict(session='crypto-runtime-install',question='Crypto status',request_id='crypto-runtime-install-'+str(time.time_ns()))); deadline=time.time()+10\nwhile r['status'] in ('queued','running') and time.time()<deadline:\n time.sleep(.1);r=g.call('get',owner=2,id=r['id'])\na=json.loads(r['answer']);assert a['domain']=='crypto' and not a['answer']['company_tools']; assert a['answer']['memory']=='AVAILABLE';print(json.dumps({'health':h,'status_verified':True}))"
    result=command(['/usr/sbin/runuser','-u','vivameda-agent','--','/usr/bin/python3','-c',"import sys;sys.path.insert(0,'/opt/vivameda-workspace');"+code])
    return json.loads(result.stdout)
def idle():
    with sqlite3.connect('file:/var/lib/vivameda-agent/workspace/workspace.sqlite3?mode=ro',uri=True) as c:
        if c.execute("SELECT count(*) FROM jobs WHERE status='running'").fetchone()[0]:raise ValueError('Workspace job running; retry after it finishes')
        for session,question in c.execute("SELECT session,question FROM jobs WHERE status='queued'"):
            from runtime_gateway import selected
            if selected(session,question) is not None:raise ValueError('Drain existing crypto requests before switching queues')

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--install',action='store_true');p.add_argument('--expected-sha256',required=True)
    for key in TARGETS:p.add_argument('--expected-'+key+'-sha256',required=True)
    args=p.parse_args()
    for name in FILES:checked(BASE/name)
    contents={n:(BASE/n).read_bytes() for n in FILES}
    digest=sha(b''.join(n.encode()+b'\0'+contents[n]+b'\0' for n in FILES))
    if digest!=args.expected_sha256:raise ValueError('Reviewed runtime bundle changed')
    for name in FILES:
        checked(BASE/name)
        if name.endswith('.py'):ast.parse(contents[name].decode())
    patched={};original={}
    for key,path in TARGETS.items():
        checked(path);raw=path.read_bytes()
        if sha(raw)!=getattr(args,'expected_'+key+'_sha256'):raise ValueError('Live '+key+' changed; review concurrent work')
        original[path]=raw;patched[path]={'main':patch_main,'workspace':patch_workspace,'helper':patch_helper}[key](raw.decode()).encode()
    result={'validated':True,'installed':False,'bundle_sha256':digest,'patched_source_sha256':{k:sha(patched[v]) for k,v in TARGETS.items()}}
    command(['/usr/bin/systemd-analyze','verify',str(BASE/UNITS[0]),str(BASE/UNITS[1])])
    if not args.install:print(json.dumps(result));return
    if os.geteuid()!=0:raise ValueError('Owner root maintenance terminal required')
    for path in (APP,STATE):checked(path)
    if APP.exists() or STATE.exists():raise ValueError('Runtime paths already exist; review receipt before reinstall')
    idle();stamp=datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ');backup=pathlib.Path('/opt/vivameda-operations')/('crypto-runtime-backup-'+stamp);backup.mkdir(mode=0o700)
    gateway_targets=[v.parent/'runtime_gateway.py' for v in TARGETS.values()]
    units=[pathlib.Path('/etc/systemd/system')/n for n in UNITS]
    for path in [*gateway_targets,*units]:
        checked(path)
        if path.exists():raise ValueError('New integration target already exists')
        original[path]=None
    metadata={}
    for i,(path,raw) in enumerate(original.items()):
        metadata[path]=path.stat() if path.exists() else None
        if raw is not None:(backup/str(i)).write_bytes(raw);shutil.copystat(path,backup/str(i))
    import grp
    try:grp.getgrnam('vivameda-crypto')
    except KeyError:command(['/usr/sbin/groupadd','--system','vivameda-crypto'])
    crypto=user('vivameda-crypto','vivameda-crypto');proxy=user('vivameda-crypto-model','vivameda-crypto')
    APP.mkdir(mode=0o755);STATE.mkdir(mode=0o700);os.chown(STATE,crypto.pw_uid,crypto.pw_gid)
    stopped=[];mutated=set()
    try:
        for name in FILES:write(APP/name,contents[name])
        for path in units:write(path,contents[path.name]);mutated.add(path)
        command(['/usr/bin/systemctl','daemon-reload'])
        for unit in UNITS:command(['/usr/bin/systemctl','start',unit])
        # Wait only for sockets, then check isolation and deterministic operation.
        deadline=time.time()+10
        while not pathlib.Path('/run/vivameda-crypto-runtime/agent.sock').exists():
            if time.time()>deadline:raise ValueError('Runtime socket unavailable')
            time.sleep(.1)
        for path in gateway_targets:write(path,contents['runtime_gateway.py']);mutated.add(path)
        health=postflight()
        # Stop admission and require no shared-worker job in flight before publishing routing.
        command(['/usr/bin/systemctl','stop',SHARED[1]]);stopped.append(SHARED[1])
        with sqlite3.connect('/var/lib/vivameda-agent/workspace/workspace.sqlite3',timeout=5) as c:
            c.execute('BEGIN IMMEDIATE')
            if c.execute("SELECT count(*) FROM jobs WHERE status='running'").fetchone()[0]:raise ValueError('Company worker became busy; no running job stopped')
            from runtime_gateway import selected
            if any(selected(s,q) is not None for s,q in c.execute("SELECT session,question FROM jobs WHERE status='queued'")):raise ValueError('Crypto request queued during preflight; drain before retry')
            command(['/usr/bin/systemctl','stop',SHARED[0]]);stopped.append(SHARED[0])
        for key,path in TARGETS.items():
            if sha(path.read_bytes())!=getattr(args,'expected_'+key+'_sha256'):raise ValueError('Concurrent source change')
            st=metadata[path];write(path,patched[path],st.st_uid,st.st_gid,st.st_mode&0o777);mutated.add(path)
        for unit in SHARED:command(['/usr/bin/systemctl','start',unit])
        for unit in (*UNITS,*SHARED):command(['/usr/bin/systemctl','is-active','--quiet',unit])
        health=postflight()
        for unit in UNITS:command(['/usr/bin/systemctl','enable',unit])
        result.update(installed=True,activated_at_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),backup=str(backup),postflight=health,shared_inference_engine=True,dedicated_weights=False,live_execution=False,scanner_changed=False,old_crypto_history_migrated=False)
        write(APP/'ACTIVATION.json',(json.dumps(result,indent=2)+'\n').encode());print(json.dumps(result))
    except BaseException:
        for unit in UNITS:subprocess.run(['/usr/bin/systemctl','stop',unit],capture_output=True)
        for path,raw in original.items():
            if path not in mutated:continue
            if raw is None:path.unlink(missing_ok=True)
            else:
                st=metadata[path];write(path,raw,st.st_uid,st.st_gid,st.st_mode&0o777)
        subprocess.run(['/usr/bin/systemctl','daemon-reload'],capture_output=True)
        for unit in stopped:subprocess.run(['/usr/bin/systemctl','restart',unit],capture_output=True)
        # Keep the runtime state and backup for diagnosis; do not delete user data.
        raise

if __name__=='__main__':main()
