"""Owner-installed separate relay; no scanner, wallet, pilot or existing-unit edits."""
import argparse, grp, hashlib, json, os, pathlib, pwd, shutil, subprocess, sys, tempfile, time
HERE=pathlib.Path(__file__).resolve().parent
DEST=pathlib.Path('/opt/vivameda-100x-watchlist')
STATE=pathlib.Path('/var/lib/vivameda-100x-watchlist')
FILES=('notifier.py','test_notifier.py','install.py','vivameda-100x-watchlist.service','vivameda-100x-watchlist.timer','research.py','test_research.py')
SCANNER_SHA='765aba08982c3f0c562b52755ab9122cdaabfc396b78e7fed878089db87fa54e'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def bundle():return hashlib.sha256(json.dumps({n:sha(HERE/n) for n in FILES},sort_keys=True,separators=(',',':')).encode()).hexdigest()
def command(argv):return subprocess.run(argv,capture_output=True,text=True,check=True,timeout=60)
def install(expected,apply=False):
    if sys.version_info[:2]!=(3,12):raise ValueError('Python 3.12 required')
    if expected!=bundle():raise ValueError('reviewed bundle mismatch')
    if os.geteuid()!=0:raise PermissionError('owner root terminal required')
    base=pathlib.Path('/opt/vivameda-crypto-early-scout')
    if sha(base/'early_scout.py')!=SCANNER_SHA:raise ValueError('live source changed')
    user=command(['/usr/bin/systemctl','show','vivameda-crypto-pilot-health.service','--property=User','--value']).stdout.strip()
    if not user or user in ('root','vivameda-engineer'):raise ValueError('dedicated existing bot service user required')
    account=pwd.getpwnam(user);group=grp.getgrgid(account.pw_gid).gr_name
    paths=[base/'credentials.json',base/'data'/'early_scout.sqlite']
    command(['/usr/sbin/runuser','-u',user,'--','/usr/bin/python3','-c','import os,sys; assert all(os.access(p,os.R_OK) for p in sys.argv[1:])',*[str(p) for p in paths]])
    frozen=[base/'early_scout.py',base/'scout_learning_v2.py']
    for name in ('vivameda-early-scout.service','vivameda-scout-learning-v2.service','vivameda-crypto-pilot-health.service','vivameda-crypto-pilot-health.timer','vivameda-snapshot-archive.service','vivameda-snapshot-archive.timer'):
        p=pathlib.Path('/etc/systemd/system')/name
        if p.exists():frozen.append(p)
    before={str(p):sha(p) for p in frozen}
    units=FILES[3:5]
    if DEST.exists() or STATE.exists() or any((pathlib.Path('/etc/systemd/system')/n).exists() for n in units):raise ValueError('existing relay; activation reset forbidden')
    if shutil.disk_usage('/var/lib').free<1024**3:raise ValueError('minimum 1 GiB free space')
    for n in FILES:
        if n.endswith('.py'):compile((HERE/n).read_text(),n,'exec')
    command(['/usr/sbin/runuser','-u','vivameda-engineer','--','/usr/bin/python3','-m','unittest','discover','-s',str(HERE),'-p','test_*.py'])
    with tempfile.TemporaryDirectory() as d:
        temp=pathlib.Path(d)
        for n in units:(temp/n).write_text((HERE/n).read_text().replace('@USER@',user).replace('@GROUP@',group))
        command(['/usr/bin/systemd-analyze','verify',*[str(temp/n) for n in units]])
        out={'validated':True,'installed':False,'bundle_sha256':expected,'service_user':user,'scanner_changed':False,'pilot_modified':False,'engineering_permissions_changed':False,'same_existing_bot_and_chat':True,'live_trading':False}
        if not apply:return out
        backup=pathlib.Path(tempfile.mkdtemp(prefix='100x-watchlist-',dir='/opt/vivameda-operations'))
        (backup/'install.json').write_text(json.dumps({'new_component_absent':True,'frozen_hashes':before},sort_keys=True))
        DEST.mkdir(mode=0o755);STATE.mkdir(mode=0o700);os.chown(STATE,account.pw_uid,account.pw_gid)
        shutil.copyfile(HERE/'notifier.py',DEST/'notifier.py');(DEST/'notifier.py').chmod(0o644)
        shutil.copyfile(HERE/'research.py',DEST/'research.py');(DEST/'research.py').chmod(0o644)
        import notifier
        activation=int(time.time())
        config={'activation_ts':activation,'deadline_ts':None,'min_mc':100000,'max_mc':500000,'policy':'existing-alert-watchlist-v1'}
        for name,value in (('config.json',config),('delivery.json',{})):
            notifier.atomic(STATE/name,value);os.chown(STATE/name,account.pw_uid,account.pw_gid)
        for n in units:shutil.copyfile(temp/n,pathlib.Path('/etc/systemd/system')/n)
        try:
            command(['/usr/bin/systemctl','daemon-reload'])
            command(['/usr/bin/systemctl','start','vivameda-100x-watchlist.service'])
            report=json.loads((STATE/'status.json').read_text())
            if report['state'] not in ('waiting','sent','cooldown','read_skipped','screening_changed','research_identity_mismatch','delivery_unknown'):raise ValueError('relay first-run failed')
            if {str(p):sha(p) for p in frozen}!=before:raise ValueError('frozen bytes changed')
            if sha(DEST/'notifier.py')!=sha(HERE/'notifier.py'):raise ValueError('relay bytes mismatch')
            command(['/usr/bin/systemctl','enable','--now','vivameda-100x-watchlist.timer'])
            command(['/usr/bin/systemctl','is-active','vivameda-100x-watchlist.timer'])
            out.update(installed=True,backup=str(backup),activation_ts=activation,deadline_ts=config['deadline_ts'],first_run=report,notification_prefix='🔥',first_real_candidate_delivery_verified=report['candidate_messages_sent']>0)
            return out
        except Exception:
            subprocess.run(['/usr/bin/systemctl','disable','--now','vivameda-100x-watchlist.timer'],capture_output=True,timeout=10)
            (STATE/'STOP').touch()
            raise
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--expected-sha256');p.add_argument('--install',action='store_true');p.add_argument('--bundle',action='store_true');a=p.parse_args()
    if a.bundle:print(json.dumps({'bundle_sha256':bundle(),'files':{n:sha(HERE/n) for n in FILES}},sort_keys=True))
    else:
        try:print(json.dumps(install(a.expected_sha256,a.install),sort_keys=True))
        except Exception:raise SystemExit('Relay refused; inspect reviewed source, access, existing-install or first-run gate. No credentials printed.')

