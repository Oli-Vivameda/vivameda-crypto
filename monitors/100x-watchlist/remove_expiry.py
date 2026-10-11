"""Owner-authorized removal of relay expiry; preserve activation and delivery history."""
import argparse, fcntl, hashlib, json, os, pathlib, shutil, subprocess, sys, tempfile
HERE=pathlib.Path(__file__).resolve().parent
SOURCE=pathlib.Path('/opt/vivameda-100x-watchlist/notifier.py')
STATE=pathlib.Path('/var/lib/vivameda-100x-watchlist')
OLD='1a5b133179cb29d7bb1b00dfdaedaad555a0fb40f963ba60168e36725bc090bd'
NEW='576081eef5c6c02c6941dbc63b224d6eb647fbf121d71c2dc4667cb9c8030848'
TESTS='de4db749019dcc1a1977c896fb198aeefb78778c6a1567c2394515c14a6cf16d'
TIMER='vivameda-100x-watchlist.timer'
SERVICE='vivameda-100x-watchlist.service'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def command(argv):return subprocess.run(argv,check=True,capture_output=True,text=True,timeout=60)
def replace(path,raw,metadata):
    fd,name=tempfile.mkstemp(dir=path.parent)
    try:
        os.fchmod(fd,metadata.st_mode & 0o777);os.fchown(fd,metadata.st_uid,metadata.st_gid)
        with os.fdopen(fd,'wb') as out:out.write(raw);out.flush();os.fsync(out.fileno())
        os.replace(name,path)
    finally:
        if os.path.exists(name):os.unlink(name)
def main(expected):
    if sys.version_info[:2]!=(3,12) or os.geteuid()!=0:raise ValueError('owner root Python 3.12 required')
    if sha(pathlib.Path(__file__))!=expected:raise ValueError('reviewed updater mismatch')
    if sha(HERE/'notifier.py')!=NEW or sha(HERE/'test_notifier.py')!=TESTS:raise ValueError('candidate mismatch')
    compile((HERE/'notifier.py').read_text(),'notifier.py','exec')
    command(['/usr/sbin/runuser','-u','vivameda-engineer','--','/usr/bin/python3','-m','unittest','discover','-s',str(HERE),'-p','test_notifier.py'])
    initial=sha(SOURCE)
    if initial not in (OLD,NEW):raise ValueError('installed source changed')
    conf=STATE/'config.json'
    before=conf.read_bytes();config=json.loads(before)
    if initial==NEW and config.get('deadline_ts') is None:
        print(json.dumps({'updated':True,'already_continuous':True,'deadline_ts':None}));return
    if 'activation_ts' not in config or 'deadline_ts' not in config:raise ValueError('invalid existing config')
    if command(['/usr/bin/systemctl','is-active',TIMER]).stdout.strip()!='active':raise ValueError('relay timer not active')
    frozen=[pathlib.Path('/opt/vivameda-crypto-early-scout')/n for n in ('early_scout.py','scout_learning_v2.py')]
    frozen.extend(pathlib.Path('/etc/systemd/system')/n for n in (TIMER,SERVICE))
    hashes={str(p):sha(p) for p in frozen}
    backup=pathlib.Path(tempfile.mkdtemp(prefix='100x-watchlist-no-expiry-',dir='/opt/vivameda-operations'))
    shutil.copyfile(SOURCE,backup/'notifier.py');shutil.copyfile(conf,backup/'config.json')
    (backup/'config.json').chmod(0o600)
    source_meta=SOURCE.stat();config_meta=conf.stat()
    command(['/usr/bin/systemctl','stop',TIMER])
    try:
        command(['/usr/bin/systemctl','stop',SERVICE])
        with (STATE/'run.lock').open('a') as lock:
            fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
            if conf.read_bytes()!=before or sha(SOURCE)!=initial:raise ValueError('relay changed during update')
            delivery_before=sha(STATE/'delivery.json')
            config['deadline_ts']=None
            replace(SOURCE,(HERE/'notifier.py').read_bytes(),source_meta)
            replace(conf,json.dumps(config,sort_keys=True,allow_nan=False).encode(),config_meta)
            if sha(STATE/'delivery.json')!=delivery_before:raise ValueError('delivery history changed')
            if {str(p):sha(p) for p in frozen}!=hashes:raise ValueError('frozen bytes changed')
        command(['/usr/bin/systemctl','start',SERVICE])
        report=json.loads((STATE/'status.json').read_text())
        if report.get('state') not in ('waiting','sent','cooldown','read_skipped','stopped','state_cap','delivery_unknown'):raise ValueError('postflight failed')
        command(['/usr/bin/systemctl','start',TIMER])
        command(['/usr/bin/systemctl','is-active',TIMER])
        print(json.dumps({'updated':True,'deadline_ts':None,'activation_ts':config['activation_ts'],'source_sha256':sha(SOURCE),'backup':str(backup),'delivery_history_preserved':True,'scanner_changed':False,'pilot_modified':False,'first_run':report},sort_keys=True))
    except Exception:
        command(['/usr/bin/systemctl','stop',SERVICE])
        replace(SOURCE,(backup/'notifier.py').read_bytes(),source_meta)
        replace(conf,before,config_meta)
        command(['/usr/bin/systemctl','start',TIMER])
        raise
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--expected-sha256',required=True);a=p.parse_args()
    try:main(a.expected_sha256)
    except Exception:raise SystemExit('Expiry update refused or restored; inspect reviewed updater and relay health.')
