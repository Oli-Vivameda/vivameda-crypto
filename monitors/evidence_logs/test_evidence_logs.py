import importlib.util,json,pathlib,tempfile,unittest
from unittest.mock import patch
import health,monitor
import install_evidence_logs as install

class AuditTests(unittest.TestCase):
 def test_installer_hash_refusal_before_commands(self):
  with patch.object(install,'command') as command:
   with self.assertRaisesRegex(ValueError,'bundle mismatch'):install.run('health','0'*64,True)
   command.assert_not_called()
 def test_installer_requires_owner_without_reading_private_source(self):
  with patch.object(install.os,'geteuid',return_value=1000),patch.object(install,'sha',wraps=install.sha) as sha:
   with self.assertRaises(PermissionError):install.run('health',install.bundle(),True)
   # sha is used only for candidate bundle checks, never installed source.
   self.assertTrue(all(str(c.args[0]).startswith(str(install.HERE)) for c in sha.call_args_list))
 def test_health_append_only_and_sanitized(self):
  with tempfile.TemporaryDirectory() as d,patch.object(health,'STATE',pathlib.Path(d)):
   r={'checked_at':100,'status':'paused','reason':'private-token','private':'secret'}
   health.append_audit(r,'sent');p=pathlib.Path(d)/'incident_send_log.jsonl';first=p.read_bytes()
   health.append_audit(dict(r,checked_at=200),'idle');self.assertTrue(p.read_bytes().startswith(first))
   self.assertNotIn('private',p.read_text());self.assertNotIn('secret',p.read_text());self.assertEqual(p.stat().st_mode&0o777,0o600)
 def test_notification_dedup_unchanged(self):
  sent=[];r={'checked_at':1000,'status':'paused','reason':'pilot_pause_marker'}
  state,result=health.notify(r,{},sent.append);self.assertEqual(result,'sent')
  _,result=health.notify(dict(r,checked_at=2000),state,sent.append);self.assertEqual(result,'idle');self.assertEqual(len(sent),1)
 def test_alarm_pending_then_ack_and_delay(self):
  with tempfile.TemporaryDirectory() as d:
   p=pathlib.Path(d)/'alarm.jsonl';a='a'*32
   monitor.alarm_log(p,a,100,'pending');first=p.read_bytes();monitor.alarm_log(p,a,100,'sent',102.75)
   rows=[json.loads(r) for r in p.read_text().splitlines()];self.assertTrue(p.read_bytes().startswith(first));self.assertEqual(rows[1]['delay_seconds'],2.75);self.assertIsNone(rows[0]['delay_seconds']);self.assertEqual(p.stat().st_mode&0o777,0o600)
 def test_missing_ack_never_invented(self):
  with tempfile.TemporaryDirectory() as d:
   p=pathlib.Path(d)/'alarm.jsonl';monitor.alarm_log(p,'a'*32,100,'sent',None);self.assertIsNone(json.loads(p.read_text())['telegram_api_acknowledgement_time'])
 def test_write_failure_does_not_disable_alarms(self):
  with patch.object(monitor.os,'open',side_effect=OSError):self.assertFalse(monitor.alarm_log(pathlib.Path('/missing'),'a'*32,100,'pending'))
 def test_health_log_failure_visible_without_changing_state(self):
  r={'checked_at':100,'status':'paused','reason':'pilot_pause_marker'}
  with patch.object(health.os,'open',side_effect=OSError):health.append_audit(r,'sent')
  self.assertEqual(r['audit_log'],'unavailable');self.assertEqual(r['status'],'paused')

class ExistingDiagnosticsTests(unittest.TestCase):
 def test_rejected_cycle_diagnostics_survive_logging_update(self):
  import sqlite3
  with tempfile.TemporaryDirectory() as d:
   base=pathlib.Path(d); directory=base/'data'/'forward_capture';directory.mkdir(parents=True)
   con=sqlite3.connect(directory/'capture.sqlite')
   con.execute('CREATE TABLE fc_activation (id INTEGER, body TEXT)')
   con.execute('CREATE TABLE fc_events (kind TEXT, body TEXT)')
   con.execute('INSERT INTO fc_activation VALUES (1,?)',(json.dumps(dict(activation_ts=100,deadline=10000)),))
   for kind,stamp in [('cycle',3990),('rejected_cycle',1000),('rejected_cycle',3900),('rejected_cycle',3995)]:
    con.execute('INSERT INTO fc_events VALUES (?,?)',(kind,json.dumps(dict(cycle_ts=stamp))))
   con.commit();con.close()
   report=health.collect(base=base,now=4000,services={u:True for u in health.UNITS})
   self.assertEqual(report['rejected_cycles'],3)
   self.assertEqual(report['last_rejected_cycle_ts'],3995)
   self.assertEqual(report['rejected_cycles_last_30m'],2)
   self.assertEqual(report['availability_diagnosis'],'provider_pair_rejections_observed')
   self.assertEqual(report['status'],'collecting')
   self.assertFalse((directory/'PAUSED.json').exists())

if __name__=='__main__':unittest.main()
