"""Hash-reviewed post-stop owner installer. No automatic restart or activation."""
import argparse, datetime, hashlib, json, os, pathlib, py_compile, shutil, sys, tempfile, time
from earlier_entry import SOURCE_SHA, require_python
from build_launch_patch import build

STOP=1792479039
LIVE=pathlib.Path('/opt/vivameda-crypto-early-scout/early_scout.py')
DEST=pathlib.Path('/var/lib/vivameda-crypto-earlier-entry/launch_path')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def check(bundle,expected,now):
    if now<STOP:raise ValueError('Install refused before 2026-10-20T06:50:39Z')
    if now<STOP+3780:raise ValueError('Wait for passive pilot follow-up through 2026-10-20T07:53:39Z')
    manifest=bundle/'bundle_manifest.json'
    if sha(manifest)!=expected:raise ValueError('Reviewed bundle manifest mismatch')
    m=json.loads(manifest.read_bytes())
    for name,h in m['files'].items():
        if pathlib.PurePosixPath(name).name!=name or sha(bundle/name)!=h:raise ValueError('Bundle source mismatch')
    if sha(LIVE)!=SOURCE_SHA:raise ValueError('Live scanner changed: rebase and review required')
    original=LIVE.read_text();candidate=bundle/'candidate_early_scout.txt'
    if candidate.read_text()!=build(original):raise ValueError('Unexpected candidate behavior')
    if LIVE.with_name('launch_path.py').exists():raise ValueError('Existing path module requires separate reviewed update')
    if not DEST.exists() or not os.access(DEST,os.W_OK):raise ValueError('Owner must prepare dedicated scanner-writable path; no permissions widened by installer')
    return m
def main():
    p=argparse.ArgumentParser();p.add_argument('--install',action='store_true');p.add_argument('--expected-sha256',required=True);a=p.parse_args();require_python();bundle=pathlib.Path(__file__).parent
    try:
        m=check(bundle,a.expected_sha256,int(time.time()))
        if not a.install:print(json.dumps({'preflight':True,'production_changed':False,'service_restart':False}));return
        if os.geteuid()!=0:raise ValueError('Owner root install required')
        with tempfile.TemporaryDirectory() as tmp:
            for name in ('candidate_early_scout.txt','launch_path.py'):
                copy=pathlib.Path(tmp)/(name+'.py');shutil.copy2(bundle/name,copy);py_compile.compile(str(copy),doraise=True)
        backup=pathlib.Path(tempfile.mkdtemp(prefix='crypto-launch-path-',dir='/opt/vivameda-operations'))
        shutil.copy2(LIVE,backup/'early_scout.py');(backup/'receipt.json').write_text(json.dumps({'base_sha256':SOURCE_SHA,'bundle_sha256':a.expected_sha256}))
        try:
            module=LIVE.with_name('launch_path.py');temp_module=module.with_suffix('.py.d3');shutil.copy2(bundle/'launch_path.py',temp_module);os.chmod(temp_module,0o644);os.replace(temp_module,module)
            temp_scanner=LIVE.with_suffix('.py.d3');shutil.copy2(bundle/'candidate_early_scout.txt',temp_scanner);shutil.copystat(LIVE,temp_scanner);os.replace(temp_scanner,LIVE)
            if sha(module)!=m['files']['launch_path.py'] or sha(LIVE)!=m['files']['candidate_early_scout.txt']:raise ValueError('Postflight source hash mismatch')
        except BaseException:
            shutil.copy2(backup/'early_scout.py',LIVE)
            if module.exists():module.rename(backup/'failed-launch_path.py')
            raise
        print(json.dumps({'installed_sources':True,'backup':str(backup),'scanner_sha256':sha(LIVE),'module_sha256':sha(module),
          'service_restarted':False,'runtime_activated':False,'postflight':'source hashes verified; existing process unchanged; post-stop owner restart and first passive row pending',
          'rollback':'stop only after reviewed owner action; restore backup early_scout.py; retain path data/module as inactive; recheck source/service',
          'provider_requests':0,'telegram_sent':False}))
    except (OSError,ValueError,KeyError):raise SystemExit('Install refused; inspect reviewed post-stop/source/storage gates. Production action not claimed.')
if __name__=='__main__':main()
