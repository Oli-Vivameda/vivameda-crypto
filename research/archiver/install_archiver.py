"""Owner-reviewed standalone archive installation; production files never replaced."""
import argparse, hashlib, json, os, pathlib, pwd, grp, shutil, subprocess, sys, tempfile
HERE=pathlib.Path(__file__).resolve().parent
DEST=pathlib.Path('/opt/vivameda-snapshot-archive')
STATE=pathlib.Path('/var/lib/vivameda-snapshot-archive')
FILES=('archiver.py','kill_switch.py','test_archiver.py','install_archiver.py','vivameda-snapshot-archive.service','vivameda-snapshot-archive.timer','second_leg_grid.json','read_receipt.py')
SCANNER_SHA='765aba08982c3f0c562b52755ab9122cdaabfc396b78e7fed878089db87fa54e'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def bundle():return hashlib.sha256(json.dumps({n:sha(HERE/n) for n in FILES},sort_keys=True,separators=(',',':')).encode()).hexdigest()
def command(argv):return subprocess.run(argv,capture_output=True,text=True,check=True,timeout=60)
def install(expected,use_existing_health_user,apply=False):
    if sys.version_info[:2]!=(3,12):raise ValueError('Python 3.12 required')
    if expected!=bundle():raise ValueError('review bundle mismatch')
    if os.geteuid()!=0 or not use_existing_health_user:raise PermissionError('owner terminal and existing-user approval required')
    import archiver
    base=pathlib.Path('/opt/vivameda-crypto-early-scout')
    if sha(base/'early_scout.py')!=SCANNER_SHA:raise ValueError('live scanner source changed; review required')
    if sha(archiver.STATUS)!=archiver.STATUS_SHA:raise ValueError('existing status route changed')
    user=command(['/usr/bin/systemctl','show','vivameda-crypto-pilot-health.service','--property=User','--value']).stdout.strip()
    if not user or user=='root' or user=='vivameda-engineer':raise ValueError('existing dedicated health user required')
    account=pwd.getpwnam(user);group=grp.getgrgid(account.pw_gid).gr_name
    # Access preflight checks OS readability only; never opens live databases.
    paths=[str(archiver.SOURCE),str(archiver.STATUS),str(archiver.AUDIT)]
    command(['/usr/sbin/runuser','-u',user,'--','/usr/bin/python3','-c','import os,sys; assert all(os.access(p,os.R_OK) for p in sys.argv[1:])',*paths])
    raw=command(['/usr/sbin/runuser','-u',user,'--','/usr/bin/python3',str(archiver.STATUS)]).stdout
    observed=json.loads(raw)
    import time
    if observed['status']!='collecting' or not 0<=int(time.time())-observed['checked_at']<=300:raise ValueError('fresh collecting health baseline required')
    baseline={k:observed[k] for k in ('checked_at','cycles','rejected_cycles','seconds_since_last_cycle')}
    frozen=[base/n for n in ('early_scout.py','scout_learning_v2.py')]
    frozen += [pathlib.Path('/etc/systemd/system')/n for n in ('vivameda-early-scout.service','vivameda-scout-learning-v2.service','vivameda-crypto-pilot-health.service','vivameda-crypto-pilot-health.timer')]
    before={str(p):sha(p) for p in frozen}
    units=FILES[4:6]
    if DEST.exists() or STATE.exists() or any((pathlib.Path('/etc/systemd/system')/n).exists() for n in units):raise ValueError('existing archiver; no activation reset allowed')
    for n in FILES:
        if n.endswith('.py'):compile((HERE/n).read_text(),n,'exec')
    command(['/usr/sbin/runuser','-u','vivameda-engineer','--','/usr/bin/python3','-m','unittest','discover','-s',str(HERE),'-p','test_archiver.py'])
    with tempfile.TemporaryDirectory() as d:
        temp=pathlib.Path(d)
        for n in units:(temp/n).write_text((HERE/n).read_text().replace('@USER@',user).replace('@GROUP@',group))
        command(['/usr/bin/systemd-analyze','verify',*[str(temp/n) for n in units]])
        out={'validated':True,'installed':False,'bundle_sha256':expected,'service_user':user,'engineering_permissions_changed':False,'pilot_modified':False,'scanner_changed':False,'provider_requests':0,'telegram_sends':0,'collection_activation_pending':True}
        if not apply:return out
        backup=pathlib.Path(tempfile.mkdtemp(prefix='snapshot-archiver-source-backup-',dir='/opt/vivameda-operations'))
        for n in ('early_scout.py','scout_learning_v2.py'):shutil.copy2(base/n,backup/n)
        (backup/'new_component_absent.json').write_text(json.dumps({'destination_absent':True,'units_absent':True,'frozen_hashes':before},sort_keys=True))
        DEST.mkdir(mode=0o755);STATE.mkdir(mode=0o700);os.chown(STATE,account.pw_uid,account.pw_gid)
        for n in ('archiver.py','kill_switch.py','second_leg_grid.json','read_receipt.py'):shutil.copyfile(HERE/n,DEST/n);(DEST/n).chmod(0o644)
        archiver.atomic(STATE/'baseline_start.json',baseline);os.chown(STATE/'baseline_start.json',account.pw_uid,account.pw_gid)
        for n in units:shutil.copyfile(temp/n,pathlib.Path('/etc/systemd/system')/n)
        try:
            command(['/usr/bin/systemctl','daemon-reload'])
            command(['/usr/bin/systemctl','start','vivameda-snapshot-archive.service'])
            first=json.loads((STATE/'postflight.json').read_text())
            if (STATE/'STOP.json').exists():raise ValueError('first-run kill switch')
            if {str(p):sha(p) for p in frozen}!=before:raise ValueError('frozen source/unit bytes changed')
            if any(sha(DEST/n)!=sha(HERE/n) for n in ('archiver.py','kill_switch.py','second_leg_grid.json','read_receipt.py')):raise ValueError('source postflight mismatch')
            command(['/usr/bin/systemctl','enable','--now','vivameda-snapshot-archive.timer'])
            command(['/usr/bin/systemctl','is-active','vivameda-snapshot-archive.timer'])
            out.update(installed=True,backup=str(backup),first_run_rows=0,first_run_ts_range=None,postflight='baseline collection started; first copy after >=2h; after-window comparison pending',first_run=first)
            return out
        except Exception:
            subprocess.run(['/usr/bin/systemctl','disable','--now','vivameda-snapshot-archive.timer'],capture_output=True,timeout=10)
            archiver.stop(STATE,'install_postflight_failed')
            raise
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--install',action='store_true');p.add_argument('--expected-sha256',required=True);p.add_argument('--use-existing-health-user',action='store_true');a=p.parse_args()
    try:print(json.dumps(install(a.expected_sha256,a.use_existing_health_user,a.install),sort_keys=True))
    except Exception:raise SystemExit('Archiver refused; reviewed source, access, health or existing-install gate failed; timer remains inactive on postflight failure')
