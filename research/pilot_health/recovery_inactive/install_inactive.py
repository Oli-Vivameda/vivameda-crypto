"""Owner-installed notification preference only; no timer, pilot or DB changes."""
import argparse, hashlib, json, os, pathlib, shutil, subprocess, sys, tempfile
HERE=pathlib.Path(__file__).resolve().parent
TARGET=pathlib.Path('/opt/vivameda-crypto-pilot-health/health.py')
OLD='f5684d83e4912bc02325ec653c0c5271c742b112823f64f72fa78568c0683f86'
FILES=('health.py','test_inactive.py','install_inactive.py')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def bundle():return hashlib.sha256(json.dumps({n:sha(HERE/n) for n in FILES},sort_keys=True,separators=(',',':')).encode()).hexdigest()
def command(argv):return subprocess.run(argv,capture_output=True,text=True,check=True,timeout=60)
def replace(source):
    fd,name=tempfile.mkstemp(dir=TARGET.parent,prefix='.recovery-inactive-')
    try:
        st=TARGET.stat();os.fchmod(fd,st.st_mode&0o777);os.fchown(fd,st.st_uid,st.st_gid)
        with os.fdopen(fd,'wb') as out:out.write(source.read_bytes());out.flush();os.fsync(out.fileno())
        os.replace(name,TARGET)
    finally:
        if os.path.exists(name):os.unlink(name)
def run(expected,apply=False):
    if sys.version_info[:2]!=(3,12):raise ValueError('Python 3.12 required')
    if expected!=bundle():raise ValueError('review bundle mismatch')
    for n in FILES:compile((HERE/n).read_text(),n,'exec')
    if os.geteuid()!=0:raise PermissionError('owner terminal required')
    if sha(TARGET)!=OLD:raise ValueError('live source changed; review required')
    frozen=[pathlib.Path('/opt/vivameda-crypto-early-scout')/n for n in ('early_scout.py','scout_learning_v2.py')]
    frozen += [pathlib.Path('/etc/systemd/system')/n for n in ('vivameda-crypto-pilot-health.service','vivameda-crypto-pilot-health.timer')]
    before={str(p):sha(p) for p in frozen}
    out=dict(validated=True,installed=False,bundle_sha256=expected,recovery_notifications_active=False,incident_notifications_active=True,pilot_modified=False,units_changed=False,permissions_changed=False,alarm_sent_by_installer=False)
    if not apply:return out
    if subprocess.run(['/usr/bin/systemctl','is-active','vivameda-crypto-pilot-health.service'],capture_output=True,text=True).stdout.strip()=='active':raise ValueError('oneshot busy; wait for completion')
    command(['/usr/sbin/runuser','-u','vivameda-engineer','--','/usr/bin/python3','-m','unittest','discover','-s',str(HERE),'-p','test_inactive.py'])
    command(['/usr/bin/systemctl','is-active','vivameda-crypto-pilot-health.timer'])
    backup=pathlib.Path(tempfile.mkdtemp(prefix='crypto-health-recovery-inactive-',dir='/opt/vivameda-operations'))
    shutil.copy2(TARGET,backup/'health.py')
    try:
        if sha(TARGET)!=OLD:raise ValueError('concurrent source change')
        replace(HERE/'health.py')
        if sha(TARGET)!=sha(HERE/'health.py'):raise ValueError('postflight source mismatch')
        if {str(p):sha(p) for p in frozen}!=before:raise ValueError('frozen bytes changed')
        command(['/usr/bin/systemctl','is-active','vivameda-crypto-pilot-health.timer'])
    except Exception:
        replace(backup/'health.py');raise
    out.update(installed=True,backup=str(backup),source_sha256=sha(TARGET),tests_passed=5,service_restarted=False,postflight='source and unchanged timer verified; next normal-cycle recovery_suppressed receipt pending')
    return out
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--expected-sha256',required=True);p.add_argument('--install',action='store_true');a=p.parse_args()
    try:print(json.dumps(run(a.expected_sha256,a.install),sort_keys=True))
    except Exception:raise SystemExit('Notification update refused; inspect reviewed source/hash or wait for idle oneshot')
