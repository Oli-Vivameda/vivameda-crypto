"""Hash-bound owner update of the separate relay; scanner and state remain intact."""
import argparse, fcntl, hashlib, json, os, pathlib, shutil, subprocess, sys, tempfile
HERE=pathlib.Path(__file__).resolve().parent
DEST=pathlib.Path('/opt/vivameda-100x-watchlist')
STATE=pathlib.Path('/var/lib/vivameda-100x-watchlist')
OLD='fc537da049433ce0d900fa58805e7d22663052ab4b79f01c50d5bc4f9cf17ff9'
REVIEWED={'notifier.py': 'e0f7e8905b6e1a97bcd0a43d63247b814786666bfb2cc296bed2dc371d5d1556', 'research.py': '7f1dbd8731d6d06e7aceb7a6f0eae6bb2dfe1c06812884943474e5225954dbcf', 'test_notifier.py': '5e9dd4341627a1ba3fe36be653a1db058eb9c48fca37da6c0b2d9e4bba66fcef', 'test_research.py': '8107916de28b4eab8faea500447a477ee32ebc35753d9807106ba7d288e9807e'}
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
    if not REVIEWED or any(sha(HERE/n)!=h for n,h in REVIEWED.items()):raise ValueError('candidate mismatch')
    for n in REVIEWED:compile((HERE/n).read_text(),n,'exec')
    command(['/usr/sbin/runuser','-u','vivameda-engineer','--','/usr/bin/python3','-m','unittest','discover','-s',str(HERE),'-p','test_*.py'])
    conf=STATE/'config.json';before=conf.read_bytes();config=json.loads(before)
    if config.get('deadline_ts','missing') is not None or 'activation_ts' not in config:raise ValueError('existing indefinite relay required')
    if command(['/usr/bin/systemctl','is-active',TIMER]).stdout.strip()!='active':raise ValueError('relay timer not active')
    initial=sha(DEST/'notifier.py');module=DEST/'research.py'
    if initial==REVIEWED['notifier.py'] and module.exists() and sha(module)==REVIEWED['research.py']:
        print(json.dumps({'updated':True,'already_researched':True,'deadline_ts':None,'source_sha256':initial}));return
    if initial!=OLD or module.exists():raise ValueError('installed source changed')
    frozen=[pathlib.Path('/opt/vivameda-crypto-early-scout')/n for n in ('early_scout.py','scout_learning_v2.py')]
    frozen.extend(pathlib.Path('/etc/systemd/system')/n for n in (TIMER,SERVICE))
    hashes={str(p):sha(p) for p in frozen}
    backup=pathlib.Path(tempfile.mkdtemp(prefix='100x-watchlist-research-',dir='/opt/vivameda-operations'))
    shutil.copyfile(DEST/'notifier.py',backup/'notifier.py');shutil.copyfile(conf,backup/'config.json');(backup/'config.json').chmod(0o600)
    metadata=(DEST/'notifier.py').stat()
    command(['/usr/bin/systemctl','stop',TIMER])
    changed=False
    try:
        command(['/usr/bin/systemctl','stop',SERVICE])
        with (STATE/'run.lock').open('a') as lock:
            fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
            if conf.read_bytes()!=before or sha(DEST/'notifier.py')!=initial or module.exists():raise ValueError('relay changed during update')
            delivery_before=sha(STATE/'delivery.json')
            changed=True
            replace(module,(HERE/'research.py').read_bytes(),metadata)
            replace(DEST/'notifier.py',(HERE/'notifier.py').read_bytes(),metadata)
            if conf.read_bytes()!=before or sha(STATE/'delivery.json')!=delivery_before:raise ValueError('existing state changed')
            if {str(p):sha(p) for p in frozen}!=hashes:raise ValueError('frozen bytes changed')
        command(['/usr/bin/systemctl','start',SERVICE])
        report=json.loads((STATE/'status.json').read_text())
        if report.get('state') not in ('waiting','sent','cooldown','read_skipped','stopped','state_cap','delivery_unknown','screening_changed','research_identity_mismatch'):raise ValueError('postflight failed')
        if {str(p):sha(p) for p in frozen}!=hashes or conf.read_bytes()!=before:raise ValueError('postflight frozen bytes changed')
        command(['/usr/bin/systemctl','start',TIMER])
        if command(['/usr/bin/systemctl','is-active',TIMER]).stdout.strip()!='active':raise ValueError('timer inactive')
        print(json.dumps({'updated':True,'public_research_enabled':True,'independent_developer_research':False,'deadline_ts':None,'activation_ts':config['activation_ts'],'source_sha256':sha(DEST/'notifier.py'),'research_sha256':sha(module),'backup':str(backup),'delivery_history_preserved':True,'scanner_changed':False,'pilot_modified':False,'first_run':report},sort_keys=True))
    except Exception:
        command(['/usr/bin/systemctl','stop',SERVICE])
        if changed:
            replace(DEST/'notifier.py',(backup/'notifier.py').read_bytes(),metadata)
            if module.exists():module.unlink()
        command(['/usr/bin/systemctl','start',TIMER])
        raise
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--expected-sha256',required=True);a=p.parse_args()
    try:main(a.expected_sha256)
    except Exception:raise SystemExit('Research update refused or restored; inspect reviewed updater and relay health.')
