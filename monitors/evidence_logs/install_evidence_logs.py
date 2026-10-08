"""Hash-bound owner update of evidence logging only; no pilot/units/config changes."""
import argparse,hashlib,json,os,pathlib,shutil,subprocess,tempfile,time
HERE=pathlib.Path(__file__).resolve().parent
TARGETS={'health':(('health.py','/opt/vivameda-crypto-pilot-health/health.py','408fdcdbc731f5c35faa034300c9711a87beb00a80da8bf19b889e8d1896c47b'),),
 'movement':(('monitor.py','/opt/vivameda-market-moves/monitor.py','273d7afb31c0162c70e64aaf6f1fb0ba431bc04a5948a61180f27f0a26c447d4'),('exchange.py','/opt/vivameda-tradingview/exchange.py','88de1f4ecedf32bdeffe241d6b34506fa4359958c598512037c5d5fac319830d'))}
FILES=('health.py','monitor.py','exchange.py','test_evidence_logs.py','install_evidence_logs.py')
def sha(p):return hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()
def bundle():return hashlib.sha256(json.dumps({f:sha(HERE/f) for f in FILES},sort_keys=True,separators=(',',':')).encode()).hexdigest()
def command(args):return subprocess.run(args,capture_output=True,text=True,check=True,timeout=60)
def replace(source,target):
 fd,name=tempfile.mkstemp(dir=target.parent,prefix='.evidence-log-')
 try:
  os.fchmod(fd,target.stat().st_mode&0o777);os.fchown(fd,target.stat().st_uid,target.stat().st_gid)
  with os.fdopen(fd,'wb') as out:out.write(source.read_bytes());out.flush();os.fsync(out.fileno())
  os.replace(name,target)
 finally:
  if os.path.exists(name):os.unlink(name)
def run(component,expected,apply=False):
 if expected!=bundle():raise ValueError('reviewed logging bundle mismatch')
 for f in FILES:compile((HERE/f).read_text(),f,'exec')
 if os.geteuid()!=0:raise PermissionError('owner root terminal required; no permissions are widened')
 targets=TARGETS[component]
 for _,path,old in targets:
  if sha(path)!=old:raise ValueError('installed source changed; owner review required')
 # Freeze scanner, tracker, unit and monitoring configuration bytes across install.
 frozen=[pathlib.Path('/opt/vivameda-crypto-early-scout')/f for f in ('early_scout.py','scout_learning_v2.py')]
 frozen += [pathlib.Path('/opt/vivameda-market-moves/config.json')]
 frozen += [pathlib.Path('/etc/systemd/system')/u for u in ('vivameda-crypto-pilot-health.service','vivameda-crypto-pilot-health.timer','vivameda-market-moves.service','vivameda-market-moves.timer','vivameda-tradingview.service')]
 before={str(p):sha(p) for p in frozen}
 out=dict(validated=True,installed=False,component=component,bundle_sha256=expected,pilot_modified=False,policy_changed=False,units_changed=False,cadence_changed=False,permissions_changed=False)
 if not apply:return out
 unit='vivameda-crypto-pilot-health.service' if component=='health' else 'vivameda-market-moves.service'
 if subprocess.run(['/usr/bin/systemctl','is-active',unit],capture_output=True,text=True).stdout.strip()=='active':raise ValueError('oneshot busy; retry after current run without changing timer')
 tests=command(['/usr/sbin/runuser','-u','vivameda-engineer','--','/usr/bin/python3','-m','unittest','discover','-s',str(HERE),'-p','test_evidence_logs.py'])
 backup=pathlib.Path(tempfile.mkdtemp(prefix='crypto-evidence-logs-'+component+'-',dir='/opt/vivameda-operations'))
 for f,path,_ in targets:shutil.copy2(path,backup/f)
 restart=component=='movement'
 if restart:command(['/usr/bin/systemctl','stop','vivameda-tradingview.service'])
 try:
  for f,path,old in targets:
   if sha(path)!=old:raise ValueError('concurrent source change')
   replace(HERE/f,pathlib.Path(path))
  if restart:command(['/usr/bin/systemctl','start','vivameda-tradingview.service'])
  if {str(p):sha(p) for p in frozen}!=before:raise ValueError('frozen configuration or pilot source changed')
  if restart:command(['/usr/bin/systemctl','is-active','vivameda-tradingview.service'])
  else:command(['/usr/bin/systemctl','is-active','vivameda-crypto-pilot-health.timer'])
  # No synthetic or real alarm is emitted by this installer.
  out.update(installed=True,backup=str(backup),source_hashes={f:sha(path) for f,path,_ in targets},tests_passed=9,postflight='source hashes and existing service/timer verified; next timer audit and first real alarm acknowledgement pending',alarm_sent_by_installer=False)
 except Exception:
  for f,path,_ in targets:replace(backup/f,pathlib.Path(path))
  if restart:subprocess.run(['/usr/bin/systemctl','start','vivameda-tradingview.service'],capture_output=True,timeout=60)
  raise
 return out
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--component',choices=TARGETS,required=True);p.add_argument('--expected-sha256',required=True);p.add_argument('--install',action='store_true');a=p.parse_args()
 try:print(json.dumps(run(a.component,a.expected_sha256,a.install),sort_keys=True))
 except Exception:raise SystemExit('Logging update refused or failed; private error details withheld; inspect reviewed checks')
