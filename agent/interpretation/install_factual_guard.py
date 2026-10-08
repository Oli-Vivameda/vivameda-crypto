"""Owner installation of factual guard; preserves policy, ledger, pilot and queues."""
import argparse,hashlib,importlib.util,json,os,pathlib,shutil,subprocess,tempfile,time,pwd
HERE=pathlib.Path(__file__).resolve().parent
APP=pathlib.Path('/opt/vivameda-crypto-runtime')
OLD='75b58cf48ae1ec4d3bdf7cbfa800a8979331fadad2b450672a0a5648e9853a3a'
FILES=('crypto_agent.py','factual_guard.py','acceptance_facts.py','test_factual_guard.py','test_interpretation.py','install_interpretation.py','install_factual_guard.py','FACTUAL_ACCEPTANCE.json','test_install_factual_guard.py')
UNIT='vivameda-crypto-runtime.service'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def bundle():return hashlib.sha256(b''.join(n.encode()+b'\0'+(HERE/n).read_bytes()+b'\0' for n in FILES)).hexdigest()
def save_receipt(result):
 user=pwd.getpwnam('vivameda-engineer')
 fd,name=tempfile.mkstemp(prefix='.guard-receipt-',dir=HERE)
 try:
  with os.fdopen(fd,'w') as f:
   os.fchmod(f.fileno(),0o600);os.fchown(f.fileno(),user.pw_uid,user.pw_gid)
   json.dump(result,f,sort_keys=True);f.write('\n');f.flush();os.fsync(f.fileno())
  os.replace(name,HERE/'FACTUAL_GUARD_INSTALL_RECEIPT.json')
 finally:
  if os.path.exists(name):os.unlink(name)
def wait_runtime(h,timeout=15,clock=time.monotonic,pause=time.sleep):
 deadline=clock()+timeout
 while True:
  try:
   h.gateway("d=g.call('health',owner=2);print(json.dumps({'ready':True}))",5)
   return
  except Exception:
   if clock()>=deadline:raise ValueError('runtime_not_ready')
   pause(.1)
def main():
 a=argparse.ArgumentParser();a.add_argument('--hash',action='store_true');a.add_argument('--install',action='store_true');a.add_argument('--expected-sha256');x=a.parse_args()
 if x.hash:print(bundle());return
 if x.expected_sha256!=bundle():raise ValueError('reviewed_bundle_mismatch')
 for n in FILES:
  if (HERE/n).is_symlink():raise ValueError('symlink')
  if n.endswith('.py'):compile((HERE/n).read_text(),n,'exec')
 acceptance=json.loads((HERE/'FACTUAL_ACCEPTANCE.json').read_text())
 if acceptance['candidate_agent_sha256']!=sha(HERE/'crypto_agent.py') or acceptance['guard_sha256']!=sha(HERE/'factual_guard.py'):raise ValueError('acceptance_binding')
 tests=subprocess.run(['/usr/bin/python3','-m','unittest','test_factual_guard','test_interpretation','test_install_factual_guard'],cwd=HERE,capture_output=True,text=True,timeout=30)
 if tests.returncode:raise ValueError('tests_failed')
 if sha(APP/'crypto_agent.py')!=OLD:raise ValueError('installed_source_changed')
 result={'validated':True,'installed':False,'bundle_sha256':bundle(),'tests_passed':20,'factual_acceptance':{'facts_correct':acceptance['facts_correct'],'question_count':10,'invented_explanations':acceptance['invented_explanations'],'response_time_seconds':acceptance['response_time_seconds'],'passed':acceptance['passed']},'free_text_interpretation_verified':False,'scanner_changed':False,'policy_changed':False,'pilot_modified':False,'live_execution':False}
 if not x.install:print(json.dumps(result,sort_keys=True));return
 if os.geteuid()!=0:raise ValueError('owner_root_required')
 spec=importlib.util.spec_from_file_location('reviewed_installer_helper',HERE/'install_interpretation.py');h=importlib.util.module_from_spec(spec);spec.loader.exec_module(h)
 h.idle();backup=pathlib.Path(tempfile.mkdtemp(prefix='crypto-factual-guard-',dir='/opt/vivameda-operations'))
 names=('crypto_agent.py','factual_guard.py','FACTUAL_ACCEPTANCE.json');originals={}
 for n in names:
  h.checked(APP/n);originals[n]=(APP/n).read_bytes() if (APP/n).exists() else None
  if originals[n] is not None:shutil.copy2(APP/n,backup/n)
 stopped=False;stage='stop_runtime'
 try:
  h.command(['/usr/bin/systemctl','stop',UNIT]);stopped=True
  stage='queue_check'
  import sqlite3
  with sqlite3.connect('file:/var/lib/vivameda-crypto-runtime/jobs.sqlite3?mode=ro',uri=True) as c:
   c.execute('PRAGMA query_only=ON')
   if c.execute("SELECT count(*) FROM jobs WHERE status IN ('running','queued')").fetchone()[0]:raise ValueError('queue_not_idle')
  if sha(APP/'crypto_agent.py')!=OLD:raise ValueError('concurrent_source')
  stage='write_candidate'
  for n in names:h.write(APP/n,(HERE/n).read_bytes())
  stage='start_runtime'
  h.command(['/usr/bin/systemctl','start',UNIT])
  stage='wait_runtime'
  wait_runtime(h)
  stage='gateway_postflight'
  check=h.gateway("r=g.enqueue(2,dict(session='crypto-factual-postflight',question='Crypto explain: report supplied counts and dates.',request_id='crypto-factual-'+str(time.time_ns())));deadline=time.time()+315\nwhile r['status'] in ('queued','running') and time.time()<deadline:\n time.sleep(.5);r=g.call('get',owner=2,id=r['id'])\nassert r['status']=='succeeded';a=json.loads(r['answer']);v=a['answer'];assert isinstance(v,dict) and v['mode'] in ('evidence_table_only','validated_evidence_selection') and not a['live_execution'];assert isinstance(v['evidence_table'],list);print(json.dumps({'answer_mode':v['mode'],'response_time_seconds':v['response_time_seconds'],'evidence_rows':len(v['evidence_table']),'live_execution':False}))",335)
  h.command(['/usr/bin/systemctl','is-active','--quiet',UNIT])
  result.update(installed=True,backup=str(backup),postflight=check,application_sha256=sha(APP/'crypto_agent.py'),guard_sha256=sha(APP/'factual_guard.py'),activation_utc=__import__('datetime').datetime.now(__import__('datetime').timezone.utc).isoformat())
  save_receipt(result)
  print(json.dumps(result,sort_keys=True))
 except Exception:
  if stopped:
   h.command(['/usr/bin/systemctl','stop',UNIT])
   for n,raw in originals.items():
    if raw is None:(APP/n).unlink(missing_ok=True)
    else:h.write(APP/n,raw)
   h.command(['/usr/bin/systemctl','start',UNIT])
  save_receipt({'installed':False,'failure_stage':stage,'prior_code_restored':stopped,'bundle_sha256':bundle(),'scanner_changed':False,'pilot_modified':False,'live_execution':False})
  raise ValueError('guard_postflight_failed_prior_code_restored') from None
if __name__=='__main__':
 try:main()
 except Exception:raise SystemExit('Factual guard refused or rolled back; no private error details displayed.')
