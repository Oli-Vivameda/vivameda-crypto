import importlib.util
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch
import health


class HealthTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.base=Path(self.temp.name)
        self.directory=self.base/'data'/'forward_capture';self.directory.mkdir(parents=True)
        self.db=self.directory/'capture.sqlite'
        self.con=sqlite3.connect(self.db)
        self.con.executescript('CREATE TABLE fc_activation(id INTEGER PRIMARY KEY,body TEXT);CREATE TABLE fc_events(seq INTEGER PRIMARY KEY,kind TEXT,event_key TEXT,body TEXT,previous_hash TEXT,hash TEXT);')
        self.con.execute('INSERT INTO fc_activation VALUES(1,?)',(json.dumps({'activation_ts':1000,'deadline':1000+14*86400}),))
        self.seq=0;self.services={u:True for u in health.UNITS};self.con.commit()

    def tearDown(self):self.con.close();self.temp.cleanup()

    def event(self,kind,value):
        self.seq+=1;self.con.execute('INSERT INTO fc_events VALUES(?,?,?,?,?,?)',(self.seq,kind,str(self.seq),json.dumps(value),'',''));self.con.commit()

    def collect(self,now=1100):return health.collect(self.base,now,self.services)

    def test_collecting_before_first_cycle(self):
        r=self.collect();self.assertEqual(r['status'],'collecting');self.assertEqual(r['cycles'],0)
        self.assertIsNone(r['last_successful_cycle_ts']);self.assertIsNone(r['control_coverage_pct'])

    def test_stall_and_cycle_recovery(self):
        self.assertEqual(self.collect(1601)['status'],'stalled')
        self.event('cycle',{'cycle_ts':1590,'rows':[{'mint':'PRIVATE','mc':999}]})
        r=self.collect(1601);self.assertEqual(r['status'],'collecting');self.assertEqual(r['last_successful_cycle_ts'],1590)
        self.assertNotIn('PRIVATE',json.dumps(r));self.assertNotIn('999',json.dumps(r))

    def test_closed_coverage_same_pair_and_window(self):
        self.event('cohort',{'index_ts':1000,'alert_input':{'mint':'secretA','pair':'pairA','mc':88},'controls':[{'mint':'secretB','pair':'pairB','mc':77},{'mint':'secretC','pair':'pairC','mc':66}]})
        for mint,pair,ts in [('secretA','pairA',4600),('secretA','pairA',4601),('secretB','wrongpair',4600),('secretB','pairB',4781),('secretC','pairC',4780)]:
            self.event('observation',{'mint':mint,'pair':pair,'received_ts':ts,'mc':12345})
        r=self.collect(4781)
        self.assertEqual(r['qualified_covered_windows'],1);self.assertEqual(r['control_covered_windows'],1)
        self.assertEqual(r['control_closed_windows'],2);self.assertEqual(r['control_coverage_pct'],50)
        self.assertEqual(r['matched_events'],1);self.assertEqual(r['timed_observation_rows'],5)
        self.assertNotIn('secret',json.dumps(r));self.assertNotIn('12345',json.dumps(r))
        self.assertEqual(self.collect(4780)['qualified_closed_windows'],0)

    def test_shared_control_entries_count_per_cohort(self):
        for i in range(2):
            self.event('cohort',{'index_ts':1000,'alert_input':{'mint':str(i),'pair':'p'},'controls':[{'mint':'same','pair':'p'}]})
        self.event('observation',{'mint':'same','pair':'p','received_ts':4600,'mc':44})
        r=self.collect(4800);self.assertEqual(r['control_closed_windows'],2);self.assertEqual(r['control_covered_windows'],2)

    def test_empty_controls_missing_is_none(self):
        self.event('cohort',{'index_ts':1000,'alert_input':{'mint':'a','pair':'p'},'controls':[]})
        r=self.collect(4800);self.assertEqual(r['qualified_missing_windows'],1)
        self.assertIsNone(r['control_coverage_pct']);self.assertEqual(r['matched_events'],0)

    def test_pause_no_marker_text_leak(self):
        (self.directory/'PAUSED.json').write_text('{"reason":"PRIVATE-CREDENTIAL"}')
        r=self.collect();self.assertEqual(r['status'],'paused');self.assertNotIn('PRIVATE',json.dumps(r))

    def test_service_failure(self):
        self.services[health.UNITS[0]]=False;self.assertEqual(self.collect()['reason'],'production_service_inactive')

    def test_systemctl_failure_still_reports(self):
        with patch.object(health.subprocess,'run',side_effect=TimeoutError):
            r=health.collect(self.base,1100)
        self.assertEqual(r['reason'],'production_service_inactive')

    def test_installer_wrong_hash_no_changes(self):
        import install_health
        with patch.object(install_health,'command') as command:
            with self.assertRaisesRegex(ValueError,'bundle mismatch'):install_health.install('0'*64,True)
            command.assert_not_called()

    def test_installer_requires_root(self):
        import install_health
        with patch.object(install_health.os,'geteuid',return_value=1000):
            with self.assertRaises(PermissionError):install_health.install(install_health.bundle_hash(),True)

    def test_deadline_stops_stall_alarm(self):
        self.assertEqual(self.collect(1000+14*86400)['status'],'stopped')

    def test_read_only_does_not_modify_database(self):
        before=self.db.read_bytes();self.collect();self.assertEqual(before,self.db.read_bytes())
        self.assertEqual({p.name for p in self.directory.iterdir()},{'capture.sqlite'})

    def test_missing_and_corrupt_database(self):
        self.assertEqual(health.collect(self.base/'missing',1100,self.services)['status'],'not_activated')
        self.con.close();self.db.write_text('private malformed bytes')
        r=self.collect();self.assertEqual(r['status'],'unavailable');self.assertNotIn('malformed',json.dumps(r))

    def test_notification_dedup_and_recovery(self):
        sent=[];r={'checked_at':2000,'status':'paused','reason':'pilot_pause_marker'}
        s,result=health.notify(r,{},sent.append);self.assertEqual(result,'sent')
        s,result=health.notify(dict(r,checked_at=2400),s,sent.append);self.assertEqual(result,'idle')
        s,result=health.notify(dict(r,checked_at=2400,status='collecting',reason=None),s,sent.append)
        self.assertEqual(len(sent),2);self.assertIn('recovered',sent[-1]);self.assertIsNone(s['sent_incident'])

    def test_delivery_failure_retry_rate_limit(self):
        def fail(text):raise ValueError('SECRET-URL')
        r={'checked_at':2000,'status':'stalled','reason':'no_successful_cycle_for_10_minutes'}
        s,result=health.notify(r,{},fail);self.assertEqual(result,'delivery_failed')
        self.assertNotIn('SECRET',json.dumps(s))
        sent=[];s,result=health.notify(dict(r,checked_at=2200,status='paused'),s,sent.append)
        self.assertEqual(result,'retry_wait');self.assertEqual(sent,[])
        s,result=health.notify(dict(r,checked_at=2300),s,sent.append);self.assertEqual(result,'sent')

    def test_notification_normal_stop_not_recovery(self):
        sent=[];s,result=health.notify({'checked_at':3000,'status':'stopped','reason':None},{'sent_incident':'paused'},sent.append)
        self.assertEqual(sent,[])

    def test_atomic_status_permissions(self):
        p=self.base/'status.json';health.atomic_json(p,{'status':'collecting'},0o644)
        self.assertEqual(p.stat().st_mode&0o777,0o644)
        self.assertEqual(json.loads(p.read_text()),{'status':'collecting'})
        self.assertFalse(any(p.name.startswith('.health-') for p in self.base.iterdir()))

    def test_corrupt_notification_state_no_messages(self):
        (self.base/'notification_state.json').write_text('bad')
        with patch.object(health,'STATE',self.base),patch.object(health,'collect',return_value={'checked_at':2000,'status':'paused'}),patch.object(health,'send_telegram') as send:
            health.run();send.assert_not_called()
        self.assertEqual(json.loads((self.base/'status.json').read_text())['notification'],'state_unreadable')

    def test_delivery_failure_keeps_health_report(self):
        with patch.object(health,'STATE',self.base),patch.object(health,'collect',return_value={'checked_at':2000,'status':'paused','reason':'pilot_pause_marker'}),patch.object(health,'notify',return_value=({'pending':'paused'},'delivery_failed')):
            health.run()
        r=json.loads((self.base/'status.json').read_text());self.assertEqual(r['status'],'paused');self.assertEqual(r['notification'],'delivery_failed')
        self.assertEqual((self.base/'notification_state.json').stat().st_mode&0o777,0o600)


if __name__=='__main__':unittest.main()
