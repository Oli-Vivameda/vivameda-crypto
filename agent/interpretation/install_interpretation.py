"""Hash-reviewed crypto-only model repair; no company integration changes."""
import argparse,ast,datetime,hashlib,json,os,pathlib,shutil,subprocess,tempfile,time
BASE=pathlib.Path(__file__).resolve().parent
APP=pathlib.Path('/opt/vivameda-crypto-runtime')
FILES=('crypto_agent.py','model_proxy.py','install_interpretation.py','test_interpretation.py')
OLD={'crypto_agent.py':'9ff8c0bf056d7998a3c546a271e16fe2af1d4d3968ecc15f9f4b35eb14ced313','model_proxy.py':'de0f91bec72c0fc34397a772c76e42338c04a152d1c7bd8d9abe5fa68296484b'}
UNITS=('vivameda-crypto-model.service','vivameda-crypto-runtime.service')
def sha(raw):return hashlib.sha256(raw).hexdigest()
def bundle():return sha(b''.join(n.encode()+b'\0'+(BASE/n).read_bytes()+b'\0' for n in FILES))
def checked(p):
    if any(x.is_symlink() for x in (p,*p.parents)):raise ValueError('Symlink refused')
def command(argv,timeout=30):
    try:return subprocess.run(argv,check=True,capture_output=True,text=True,timeout=timeout)
    except subprocess.CalledProcessError as e:
        raise RuntimeError('Maintenance check failed: '+(e.stderr or str(e))[-2000:]) from e

def wait_proxy(timeout=30):
    # A service marked active may still be importing Python modules. Probe its
    # authenticated socket with an invalid request; no inference is dispatched.
    code="import socket,json; s=socket.socket(socket.AF_UNIX);s.settimeout(2);s.connect('/run/vivameda-crypto-model/model.sock');s.sendall(b'{}\\n');f=s.makefile('rb');d=json.loads(f.readline(1000));assert d.get('proxy_error')=='MODEL_REQUEST_FAILED'"
    deadline=time.monotonic()+timeout
    while True:
        try:
            command(['/usr/sbin/runuser','-u','vivameda-crypto','--','/usr/bin/python3','-c',code],5)
            return
        except (RuntimeError,subprocess.TimeoutExpired):
            if time.monotonic()>=deadline:raise ValueError('Model proxy socket did not become ready')
            time.sleep(.1)

def start_services():
    command(['/usr/bin/systemctl','start',UNITS[0]])
    wait_proxy()
    command(['/usr/bin/systemctl','start',UNITS[1]])
    deadline=time.monotonic()+10
    while not pathlib.Path('/run/vivameda-crypto-runtime/agent.sock').exists():
        if time.monotonic()>deadline:raise ValueError('Runtime socket unavailable')
        time.sleep(.1)
def write(p,raw):
    checked(p);fd,name=tempfile.mkstemp(prefix='.crypto-interpretation-',dir=p.parent)
    try:
        with os.fdopen(fd,'wb') as f:f.write(raw);f.flush();os.fsync(f.fileno())
        os.chmod(name,0o644);os.chown(name,0,0);os.replace(name,p)
    finally:
        if os.path.exists(name):os.unlink(name)
def gateway(code,timeout=30):
    return json.loads(command(['/usr/sbin/runuser','-u','vivameda-agent','--','/usr/bin/python3','-c',"import sys,json,time;sys.path.insert(0,'/opt/vivameda-workspace');import runtime_gateway as g;"+code],timeout).stdout)
def idle():
    jobs=gateway("print(json.dumps(g.jobs(2)))")
    if any(r['status'] in ('running','queued') for r in jobs):raise ValueError('Drain crypto queue first; no job will be stopped')
def postflight():
    return gateway("h=g.call('health',owner=2);assert h['inet_socket_blocked'] and not h['company_paths_visible'];r=g.enqueue(2,dict(session='crypto-model-repair',question='Crypto explain: In at most 150 words, report the aggregate eligible 60-minute endpoint and missing-or-incomplete counts. Distinguish last_multiple from tracked_peak_multiple and realized profit. Can held-out forward paper observations test predictive performance without live trading?',request_id='crypto-model-repair-'+str(time.time_ns())));deadline=time.time()+315\nwhile r['status'] in ('queued','running') and time.time()<deadline:\n time.sleep(.5);r=g.call('get',owner=2,id=r['id'])\nassert r['status']=='succeeded',r.get('error_code');a=json.loads(r['answer']);assert a['domain']=='crypto' and a['action']=='explain' and isinstance(a['answer'],str) and a['answer'].strip();assert not a['live_execution'];print(json.dumps({'health':h,'interpretation_verified':True,'answer_characters':len(a['answer']),'job_id':r['id']}))",335)
def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--install',action='store_true');p.add_argument('--expected-sha256',required=True);a=p.parse_args()
    for n in FILES:checked(BASE/n);ast.parse((BASE/n).read_text())
    digest=bundle()
    if digest!=a.expected_sha256:raise ValueError('Reviewed bundle changed')
    new={n:(BASE/n).read_bytes() for n in OLD}
    for n in OLD:
        checked(APP/n)
        if sha((APP/n).read_bytes())!=OLD[n]:raise ValueError('Installed '+n+' changed; review concurrent work')
    if not a.install:print(json.dumps({'validated':True,'installed':False,'bundle_sha256':digest}));return
    if os.geteuid()!=0:raise ValueError('Existing owner root maintenance terminal required')
    idle();stamp=datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ');backup=pathlib.Path('/opt/vivameda-operations')/('crypto-interpretation-backup-'+stamp);checked(backup);backup.mkdir(mode=0o700)
    originals={n:(APP/n).read_bytes() for n in OLD}
    for n in OLD:shutil.copy2(APP/n,backup/n)
    stopped=False;mutated=False
    try:
        command(['/usr/bin/systemctl','stop',UNITS[1]]);stopped=True
        # Admission is unavailable now. Recheck state on disk before changing source.
        import sqlite3
        with sqlite3.connect('file:/var/lib/vivameda-crypto-runtime/jobs.sqlite3?mode=ro',uri=True) as c:
            if c.execute("SELECT count(*) FROM jobs WHERE status IN ('running','queued')").fetchone()[0]:raise ValueError('Crypto request arrived during preflight; no source changed')
        command(['/usr/bin/systemctl','stop',UNITS[0]])
        for n in OLD:
            if sha((APP/n).read_bytes())!=OLD[n]:raise ValueError('Concurrent source change')
        mutated=True
        for n,raw in new.items():write(APP/n,raw)
        start_services()
        check=postflight()
        for unit in UNITS:command(['/usr/bin/systemctl','is-active','--quiet',unit])
        result={'installed':True,'bundle_sha256':digest,'model':'qwen3:4b-instruct-2507-q4_K_M','activated_at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'backup':str(backup),'source_sha256':{n:sha(raw) for n,raw in new.items()},'postflight':check,'shared_inference_engine':True,'company_default_changed':False,'scanner_changed':False,'weights_trained':False,'live_execution':False}
        write(APP/'INTERPRETATION_ACTIVATION.json',(json.dumps(result,indent=2)+'\n').encode());print(json.dumps(result))
    except BaseException:
        if stopped:
            for unit in reversed(UNITS):subprocess.run(['/usr/bin/systemctl','stop',unit],capture_output=True)
            if mutated:
                for n,raw in originals.items():write(APP/n,raw)
            for unit in UNITS:subprocess.run(['/usr/bin/systemctl','start',unit],capture_output=True)
        raise
if __name__=='__main__':main()
