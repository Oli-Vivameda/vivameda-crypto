import hashlib,json,pathlib,sqlite3,tempfile,unittest
from unittest.mock import patch
import archiver as a

class ArchiveTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=pathlib.Path(self.temp.name)
        self.source=self.root/'scanner.sqlite';self.state=self.root/'archive';self.state.mkdir()
        self.writer=a.create_archive(self.source)
        self.writer.execute('CREATE TABLE pl_predictions(mint TEXT,body TEXT)')
        self.writer.execute('CREATE TABLE fc_events(body TEXT)');self.writer.commit()
    def tearDown(self):self.writer.close();self.temp.cleanup()
    def row(self,m='synthetic',ts=100):return (m,ts,'pair',1,40000,30000,1000,30000,100,10,1000,100,1,10)
    def put(self,rows):self.writer.executemany('INSERT INTO snapshots VALUES('+','.join('?' for _ in a.COLS)+')',rows);self.writer.commit()
    def baseline(self):
        a.atomic(self.state/'baseline_start.json',dict(checked_at=0,cycles=0,rejected_cycles=0,seconds_since_last_cycle=0))
        return lambda:dict(checked_at=7200,cycles=30,rejected_cycles=30,seconds_since_last_cycle=60)
    def test_source_reads_wal_without_immutable(self):
        self.writer.execute('PRAGMA journal_mode=WAL');self.put([self.row()])
        con=a.connect_source(self.source)
        try:self.assertEqual(a.read_batch(con,(-1,''),1000),[self.row()]);self.assertFalse(con.in_transaction)
        finally:con.close()
    def test_source_ledger_and_pilot_tables_denied(self):
        con=a.connect_source(self.source)
        try:
            for table in ('pl_predictions','fc_events'):
                with self.assertRaises(sqlite3.DatabaseError):con.execute('SELECT * FROM '+table).fetchall()
            with self.assertRaises(sqlite3.DatabaseError):con.execute('DELETE FROM snapshots')
        finally:con.close()
    def test_ts_ordered_bounded_batches_no_held_transaction(self):
        self.put([self.row('z',i) for i in range(5001)])
        con=a.connect_source(self.source)
        try:
            first=a.read_batch(con,(-1,''),10000);self.assertEqual(len(first),5000);self.assertFalse(con.in_transaction)
            second=a.read_batch(con,(first[-1][1],first[-1][0]),10000);self.assertEqual(len(second),1);self.assertFalse(con.in_transaction)
            self.assertEqual(con.execute('PRAGMA busy_timeout').fetchone()[0],500)
            self.assertEqual(con.execute('PRAGMA query_only').fetchone()[0],1)
        finally:con.close()
    def test_composite_cursor_ties_and_dedupe(self):
        con=a.create_archive(self.state/'a.sqlite')
        try:
            rows=[self.row('a'),self.row('b')]
            self.assertEqual(a.append_batch(con,rows),2);self.assertEqual(a.append_batch(con,rows),0)
            self.assertEqual(con.execute('SELECT ts,mint FROM checkpoints').fetchone(),(100,'b'))
        finally:con.close()
    def test_own_rows_and_checkpoints_append_only(self):
        self.put([self.row()]);a.append_batch(self.writer,[self.row()])
        for table in ('snapshots','checkpoints'):
            for sql in ('DELETE FROM '+table,'UPDATE '+table+' SET ts=200'):
                with self.assertRaises(sqlite3.IntegrityError):self.writer.execute(sql)
                self.writer.rollback()
    def test_schema_changes_source_forbidden(self):
        con=a.connect_source(self.source)
        try:
            with self.assertRaises(sqlite3.DatabaseError):con.execute('CREATE TABLE forbidden(x)')
        finally:con.close()
    def test_rate_material_threshold(self):
        self.assertTrue(a.rate_kill({'total':20,'rejected_rate':.5},{'total':20,'rejected_rate':.55}))
        self.assertFalse(a.rate_kill({'total':20,'rejected_rate':.5},{'total':20,'rejected_rate':.54}))
        self.assertFalse(a.rate_kill({'total':20,'rejected_rate':.5},{'total':19,'rejected_rate':1}))
    def test_counter_reset_refuses(self):
        with self.assertRaises(ValueError):a.count_delta({'cycles':10,'rejected_cycles':10},{'cycles':9,'rejected_cycles':10})
    def test_disk_cap_and_minimum_free(self):
        self.assertFalse(a.disk_ok(self.state,cap=1,min_free=0))
        self.assertFalse(a.disk_ok(self.state,min_free=10**30))
    def test_warmup_opens_no_source_and_logs_no_identity(self):
        h=self.baseline()
        with patch.object(a,'connect_source',side_effect=AssertionError('source opened')):
            out=a.copy(self.state,self.source,lambda:dict(h(),checked_at=3600),lambda _:False,now=3600)
        self.assertEqual(out['state'],'baseline_collecting');self.assertFalse((self.state/'snapshots.sqlite').exists())
        self.assertNotIn('synthetic',(self.state/'runs.jsonl').read_text())
    def test_copy_and_repeat_resume_without_source_mutation(self):
        self.put([self.row()]);before=hashlib.sha256(self.source.read_bytes()).hexdigest();h=self.baseline()
        one=a.copy(self.state,self.source,h,lambda _:False,now=7200)
        two=a.copy(self.state,self.source,h,lambda _:False,now=10800)
        self.assertEqual(one['appended'],1);self.assertEqual(two['appended'],0)
        self.assertEqual(hashlib.sha256(self.source.read_bytes()).hexdigest(),before)
        self.assertNotIn('synthetic',(self.state/'runs.jsonl').read_text())
    def test_health_alarm_stops_without_reading_source(self):
        h=self.baseline()
        with patch.object(a,'connect_source',side_effect=AssertionError('source opened')):
            out=a.copy(self.state,self.source,h,lambda _:True,now=7200)
        self.assertEqual(out['reason'],'health_incident_during_run');self.assertTrue((self.state/'STOP.json').exists())
    def test_wal_growth_stops(self):
        h=self.baseline();a.atomic(self.state/'last_copy_wal.json',{'bytes':0})
        with patch.object(a,'wal_bytes',return_value=1024):out=a.copy(self.state,self.source,h,lambda _:False,now=7200)
        self.assertEqual(out['reason'],'wal_grew_run_over_run')
    def test_busy_is_skipped_once_not_retried(self):
        h=self.baseline();err=sqlite3.OperationalError('synthetic busy');err.sqlite_errorcode=sqlite3.SQLITE_BUSY
        with patch.object(a,'read_batch',side_effect=err) as read:out=a.copy(self.state,self.source,h,lambda _:False,now=7200)
        self.assertEqual(read.call_count,1);self.assertEqual(out['state'],'batch_skipped_busy_or_time_limit');self.assertFalse((self.state/'STOP.json').exists())
    def test_storage_guard_no_source_read(self):
        h=self.baseline()
        with patch.object(a,'disk_ok',return_value=False),patch.object(a,'connect_source',side_effect=AssertionError('opened')):
            out=a.copy(self.state,self.source,h,lambda _:False,now=7200)
        self.assertEqual(out['reason'],'storage_guard')
    def test_two_hour_postflight_is_preserved(self):
        h=self.baseline();a.copy(self.state,self.source,h,lambda _:False,now=7200)
        after=lambda:dict(checked_at=14400,cycles=60,rejected_cycles=60,seconds_since_last_cycle=60)
        a.copy(self.state,self.source,after,lambda _:False,now=14400)
        saved=(self.state/'two_hour_postflight.json').read_bytes()
        self.assertEqual(json.loads(saved)['after_seconds'],7200)
        a.copy(self.state,self.source,lambda:dict(after(),checked_at=18000,cycles=90,rejected_cycles=90),lambda _:False,now=18000)
        self.assertEqual((self.state/'two_hour_postflight.json').read_bytes(),saved)
    def test_root_kill_can_disable_only_its_fixed_timer(self):
        import kill_switch as k
        a.atomic(self.state/'run_started.json',{'time':7200});a.stop(self.state,'arbitrary.service')
        with patch.object(k,'ROOT',self.state),patch.object(k.os,'geteuid',return_value=0),patch.object(a,'health_alarm_since',return_value=False),patch.object(k.subprocess,'run') as called:
            k.run()
        self.assertEqual(called.call_args.args[0],['/usr/bin/systemctl','disable','--now','vivameda-snapshot-archive.timer'])
    def test_receipt_never_opens_snapshot_database(self):
        import read_receipt
        with patch.object(sqlite3,'connect',side_effect=AssertionError('DB read')):
            self.assertEqual(read_receipt.receipt(self.state),{})
    def test_grid_two_parameters_nine_choices(self):
        g=json.loads((pathlib.Path(__file__).parent/'second_leg_grid.json').read_text())
        self.assertEqual(len(g['second_leg']['parameters']),2);self.assertEqual(g['second_leg']['grid_size'],9);self.assertIsNone(g['g'])

if __name__=='__main__':unittest.main()
