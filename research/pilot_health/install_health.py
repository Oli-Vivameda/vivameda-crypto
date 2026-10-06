#!/usr/bin/env python3
"""Owner-run installation of a read-only monitor. Never reactivates pilot."""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import grp
import pwd
import shutil
import subprocess
import tempfile
import time

HERE=Path(__file__).resolve().parent
FILES=('health.py','read_status.py','vivameda-crypto-pilot-health.service',
       'vivameda-crypto-pilot-health.timer','install_health.py')
EXPECTED={'early_scout.py':'3e73978a41e2e21e090a7eea92bbdc1a52dc190ce229ac262a3c6a2b0af6a043',
          'scout_learning_v2.py':'a519ad19680ba72f0d593c4627fe5faa2d8dfa93fcd112eaba21abcf5a6da9b6'}


def bundle_hash():
    hashes={f:hashlib.sha256((HERE/f).read_bytes()).hexdigest() for f in FILES}
    return hashlib.sha256(json.dumps(hashes,sort_keys=True,separators=(',',':')).encode()).hexdigest()


def command(args):
    return subprocess.run(args,check=True,capture_output=True,text=True,timeout=60)


def install(expected, apply=False):
    if expected!=bundle_hash(): raise ValueError('monitor bundle mismatch')
    if apply and os.geteuid()!=0: raise PermissionError('owner root installation required')
    base=Path('/opt/vivameda-crypto-early-scout')
    for f,h in EXPECTED.items():
        if hashlib.sha256((base/f).read_bytes()).hexdigest()!=h:
            raise ValueError('pilot source binding mismatch')
    user=command(['/usr/bin/systemctl','show','vivameda-early-scout.service','--property=User','--value']).stdout.strip()
    if not user or user=='root': raise ValueError('dedicated existing scanner user required')
    account=pwd.getpwnam(user);group=grp.getgrgid(account.pw_gid).gr_name
    spec=importlib.util.spec_from_file_location('health',HERE/'health.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    preflight=module.collect()
    if preflight['status'] in ('not_activated','unavailable'):
        raise ValueError('existing pilot required; health preflight unavailable')
    # Compile and validate unit syntax before writing installation paths.
    with tempfile.TemporaryDirectory() as d:
        temporary=Path(d)
        for f in FILES:
            if f.endswith('.py'): compile((HERE/f).read_text(),f,'exec')
            elif f.endswith(('.service','.timer')):
                (temporary/f).write_text((HERE/f).read_text().replace('@USER@',user).replace('@GROUP@',group))
        command(['/usr/bin/systemd-analyze','verify',str(temporary/FILES[2]),str(temporary/FILES[3])])
        result={'validated':True,'installed':False,'bundle_sha256':expected,
                'pilot_modified':False,'scanner_changed':False,'live_execution':False,
                'health':preflight}
        if not apply:return result
        destination=Path('/opt/vivameda-crypto-pilot-health')
        state=Path('/var/lib/vivameda-crypto-pilot-health')
        # Existing installation must be exactly the same reviewed package.
        if destination.exists() and any(destination.iterdir()):
            for f in ('health.py','read_status.py'):
                if not (destination/f).exists() or (destination/f).read_bytes()!=(HERE/f).read_bytes():
                    raise ValueError('existing monitor differs; separately reviewed update required')
        backup=Path('/opt/vivameda-operations')/('crypto-health-backup-'+time.strftime('%Y%m%dT%H%M%SZ',time.gmtime()))
        backup.mkdir(mode=0o700)
        for f in FILES[2:4]:
            target=Path('/etc/systemd/system')/f
            if target.exists():shutil.copy2(target,backup/f)
        destination.mkdir(mode=0o755,exist_ok=True)
        for f in ('health.py','read_status.py'):
            shutil.copyfile(HERE/f,destination/f);(destination/f).chmod(0o644)
        state.mkdir(mode=0o755,exist_ok=True);state.chmod(0o755);os.chown(state,account.pw_uid,account.pw_gid)
        for f in FILES[2:4]:
            shutil.copyfile(temporary/f,Path('/etc/systemd/system')/f)
        command(['/usr/bin/systemctl','daemon-reload'])
        command(['/usr/bin/systemctl','enable','--now','vivameda-crypto-pilot-health.timer'])
        command(['/usr/bin/systemctl','start','vivameda-crypto-pilot-health.service'])
        report=json.loads((state/'status.json').read_text())
        if int(time.time())-report['checked_at']>60:raise ValueError('monitor postflight stale')
        # Recheck existing source after install. Never write it or pilot files.
        for f,h in EXPECTED.items():
            if hashlib.sha256((base/f).read_bytes()).hexdigest()!=h:raise ValueError('source changed concurrently')
        result.update(installed=True,backup=str(backup),health=report,
                      timer_active=command(['/usr/bin/systemctl','is-active','vivameda-crypto-pilot-health.timer']).stdout.strip()=='active')
        return result


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--install',action='store_true')
    parser.add_argument('--expected-sha256',required=True);args=parser.parse_args()
    print(json.dumps(install(args.expected_sha256,args.install),sort_keys=True))
