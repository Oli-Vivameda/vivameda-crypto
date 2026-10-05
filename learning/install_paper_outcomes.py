"""Owner install for paper endpoints; preserves frozen base code and policy."""
import argparse,ast,datetime,hashlib,importlib.util,json,os,pathlib,subprocess
BASE=pathlib.Path(__file__).resolve().parent
APP=pathlib.Path('/opt/vivameda-crypto-learning')
FILES=('paper_outcomes.py','test_paper_outcomes.py','install_paper_outcomes.py')
BASE_FILES=('daily_learning.py','context.py','policy.json','install_daily_learning.py','test_daily_learning.py')
BASE_HASH='d63bc98534fa81af7357a6c9b802e1d4ae7ea20578b61538c62b0601a0207a9e'
def bundle(root=BASE,names=FILES):return hashlib.sha256(b''.join(n.encode()+b'\0'+(root/n).read_bytes()+b'\0' for n in names)).hexdigest()
def main():
 a=argparse.ArgumentParser();a.add_argument('--install',action='store_true');a.add_argument('--expected-sha256',required=True);x=a.parse_args()
 if bundle()!=x.expected_sha256:raise ValueError('Reviewed endpoint bundle changed')
 for n in FILES:
  if (BASE/n).is_symlink():raise ValueError('Symlink source refused')
  ast.parse((BASE/n).read_text())
 if not x.install:print(json.dumps({'validated':True,'installed':False,'endpoint_bundle_sha256':bundle()}));return
 if os.geteuid()!=0:raise SystemExit('Existing owner maintenance terminal required')
 if bundle(APP,BASE_FILES)!=BASE_HASH:raise ValueError('Frozen installed base bundle differs')
 spec=importlib.util.spec_from_file_location('verified_base_installer',APP/'install_daily_learning.py');helper=importlib.util.module_from_spec(spec);spec.loader.exec_module(helper);write=helper.write
 dest=pathlib.Path('/etc/systemd/system/vivameda-crypto-journal.service.d/20-paper-endpoints.conf')
 for path in (APP,dest):
  if any(p.is_symlink() for p in (path,*path.parents)):raise ValueError('Symlink destination refused')
 stamp=datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ');backup=pathlib.Path('/opt/vivameda-operations')/('crypto-endpoints-backup-'+stamp);backup.mkdir(mode=0o700)
 for n in FILES:
  if (APP/n).exists():(backup/n).write_bytes((APP/n).read_bytes())
 if dest.exists():(backup/dest.name).write_bytes(dest.read_bytes())
 subprocess.run(['/usr/bin/systemctl','stop','vivameda-crypto-journal.service'],check=True)
 for n in FILES:write(APP/n,(BASE/n).read_bytes())
 dest.parent.mkdir(mode=0o755,exist_ok=True)
 write(dest,b'[Service]\nExecStart=\nExecStart=/usr/bin/python3 /opt/vivameda-crypto-learning/paper_outcomes.py --journal-first --source /opt/vivameda-crypto-early-scout/data/early_scout.sqlite --state /var/lib/vivameda-crypto-learning\n')
 subprocess.run(['/usr/bin/systemctl','daemon-reload'],check=True)
 subprocess.run(['/usr/bin/systemctl','start','vivameda-crypto-journal.service'],check=True)
 print(json.dumps({'installed':True,'endpoint_bundle_sha256':bundle(),'backup':str(backup),'base_bundle_unchanged':True,'policy_changed':False,'weights_updated':False,'live_execution':False}))
if __name__=='__main__':main()
