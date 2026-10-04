import ast,hashlib,json,logging,math,pathlib,sqlite3,tempfile,types,unittest
from unittest.mock import Mock

ROOT=pathlib.Path(__file__).parent
def load_functions(filename,ns,prefix=None):
    path=ROOT/filename;tree=ast.parse(path.read_text())
    body=[n for n in tree.body if isinstance(n,ast.FunctionDef) or
        isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id.startswith('LEDGER_') for t in n.targets)]
    exec(compile(ast.Module(body=body,type_ignores=[]),str(path),'exec'),ns)
    return ns

class LiveLedgerTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.clock=Mock(return_value=10000)
        self.ns=dict(json=json,hashlib=hashlib,math=math,sqlite3=sqlite3,logging=logging,
            time=types.SimpleNamespace(time=self.clock,time_ns=lambda:int(self.clock()*10**9)),Path=pathlib.Path)
        load_functions('early_scout.py',self.ns)
        self.v=load_functions('scout_learning_v2.py',dict(self.ns,DB=self.tmp.name+'/db',H=(1,5,15,30,60,120,180,360,720,1440)))
        self.c=self.v['db']();self.c.execute('CREATE TABLE launches(mint TEXT PRIMARY KEY,pinned_pair TEXT)')
        self.c.execute('CREATE TABLE snapshots(mint TEXT)');self.c.execute('INSERT INTO launches VALUES("old",NULL)');self.c.commit()
        self.a=self.ns['ledger_initialize'](self.c)
        self.rows=[(t,1.,100000.,30000.,3000.,30000.,50,40,100,80,2.,3.) for t in (10000,10200,10400,10600)]
        self.clock.return_value=10600
    def tearDown(self):self.c.close();self.tmp.cleanup()
    def record(self,mint='new',rows=None,cap=10600*10**9):
        self.c.execute('INSERT OR IGNORE INTO launches VALUES(?,NULL)',(mint,));self.c.commit()
        return self.ns['ledger_record'](self.c,mint,self.rows if rows is None else rows,cap,8,1,'pair')
    def result(self,seq,late=0,coverage=1):
        cid,ts=self.c.execute('SELECT case_id,decision_ts FROM pl_predictions WHERE seq=?',(seq,)).fetchone()
        self.c.execute('INSERT INTO v2_outcomes VALUES(?,?,?,?,?,?,?,?,?,?)',(cid,60,ts+3600+late,late,200000,30000,2.,2.,1.,0.))
        self.c.execute('INSERT INTO v2_horizon_metrics VALUES(?,?,?,?,?,?,?,?)',(cid,60,ts+3600+late,coverage,60,60,2.,1.));self.c.commit()
    def test_prediction_durable_and_separate_case(self):
        self.record();body=json.loads(self.c.execute('SELECT body FROM pl_predictions').fetchone()[0])
        self.assertEqual(body['features'],{k:self.v['features'](self.rows)[k] for k in self.ns['LEDGER_FEATURES']})
        self.assertEqual(self.c.execute('SELECT source FROM v2_cases').fetchone()[0],'LEDGER_ALERT')
        self.assertEqual(body['source_snapshot_sha256'],self.ns['ledger_hash'](self.rows))
        self.assertTrue(0<body['model_probability']<1)
    def test_restart_does_not_reactivate_or_expand_exclusions(self):
        self.record();a=self.ns['ledger_initialize'](self.c);self.assertEqual(a,self.a)
        self.assertEqual(a['excluded_count'],1)
    def test_old_and_duplicate(self):
        self.assertIsNone(self.record('old'));self.assertEqual(self.record(),1);self.assertIsNone(self.record())
    def test_invalid_capture_consumes_first_attempt(self):
        self.record(cap=1);self.assertIsNone(self.record())
        self.assertEqual(self.c.execute('SELECT valid FROM pl_predictions').fetchone()[0],0)
    def test_future_source_excluded(self):
        rows=[tuple([20000]+list(r[1:])) for r in self.rows];self.record(rows=rows)
        self.assertEqual(self.c.execute('SELECT valid FROM pl_predictions').fetchone()[0],0)
    def test_frozen_input_and_model_metadata(self):
        self.record()
        for table in ('pl_activation','pl_excluded','pl_predictions','pl_events'):
            with self.assertRaises(sqlite3.IntegrityError):self.c.execute('DELETE FROM '+table)
        self.c.rollback()
    def test_timed_outcome_matched_once(self):
        seq=self.record();self.result(seq);self.clock.return_value=14200
        self.ns['ledger_match'](self.c);self.ns['ledger_match'](self.c)
        self.assertEqual(self.c.execute('SELECT eligible FROM pl_results').fetchall(),[(1,)])
    def test_late_incomplete_and_missing_excluded(self):
        a=self.record('a');b=self.record('b');self.record('c')
        self.result(a,late=181);self.result(b,coverage=0);self.clock.return_value=14381
        self.ns['ledger_match'](self.c)
        self.assertEqual(self.c.execute('SELECT sum(eligible),count(*) FROM pl_results').fetchone(),(0,3))
    def test_no_premature_missing_result(self):
        self.record();self.clock.return_value=14380;self.ns['ledger_match'](self.c)
        self.assertEqual(self.c.execute('SELECT count(*) FROM pl_results').fetchone()[0],0)
    def test_deadline_stops_enrollment(self):
        self.clock.return_value=self.a['deadline'];self.assertIsNone(self.record())
        self.assertEqual(self.ns['ledger_health'](self.c)['stop']['reason'],'time_limit')
    def test_200_stop_waits_for_earlier_case(self):
        for i in range(201):self.record('m'+str(i))
        for seq in range(2,202):self.result(seq)
        self.clock.return_value=14200;self.ns['ledger_match'](self.c)
        self.assertEqual(self.ns['ledger_health'](self.c)['status'],'active')
        self.result(1);self.ns['ledger_match'](self.c)
        health=self.ns['ledger_health'](self.c)
        self.assertEqual(health['stop'],{'reason':'sample_limit','cutoff_seq':200})
        self.assertIsNone(self.record('not-enrolled'))
    def test_integrity_error_stops(self):
        self.ns['ledger_fail'](self.c,'fixture');self.assertIsNone(self.record())
    def test_chain_hashes_recompute(self):
        self.record();prev='0'*64
        for seq,kind,key,ts,body,previous,h in self.c.execute('SELECT * FROM pl_events ORDER BY seq'):
            self.assertEqual(prev,previous);self.assertEqual(h,self.ns['ledger_hash']([seq,kind,key,ts,body,previous]));prev=h
    def test_ledger_cases_only_have_60_minute_checkpoint(self):
        self.record();self.v['seed'](self.c);self.clock.return_value=10660
        self.v['prod']=types.SimpleNamespace(choose_pair=lambda *a:{'marketCap':100000,'liquidity':{'usd':30000}})
        self.v['dex']=lambda m:{}
        self.v['track'](self.c)
        self.assertEqual(self.c.execute('SELECT count(*) FROM v2_outcomes').fetchone()[0],0)
    def test_resolved_ledger_no_long_horizon_tracking(self):
        seq=self.record();self.result(seq);self.v['expire'](self.c,14200)
        self.assertEqual(self.c.execute('SELECT status FROM v2_cases').fetchone()[0],'RESOLVED')
    def alert_setup(self):
        self.c.execute('ALTER TABLE launches ADD COLUMN alert_level INTEGER DEFAULT 0')
        self.c.execute('ALTER TABLE launches ADD COLUMN last_alert_ts INTEGER DEFAULT 0')
        self.c.execute('INSERT INTO launches(mint) VALUES("fresh")');self.c.commit()
        self.ns.update(PREALERT_ADMISSION_POLICY='fixture',PREALERT_POLICY='fixture',
            basic_security=Mock(return_value={'mint_authority':'REVOKED','freeze_authority':'REVOKED','creator_pct':0,'top10_raw_pct':1}),
            collect_prealert_review=Mock(return_value={}),evaluate_prealert_review=Mock(return_value=('PASS',[])),
            persist_prealert_review=Mock(),screening_summary=Mock(return_value=''))
        _,metrics,_=self.ns['score_candidate'](self.rows)
        return (self.c,('fresh',0,'creator',None,None,None),{'pairAddress':'pair'},8,metrics,1,self.rows,10600*10**9)
    def test_actual_alert_records_before_delivery(self):
        args=self.alert_setup()
        def send(text):
            self.assertEqual(self.c.execute('SELECT count(*) FROM pl_predictions').fetchone()[0],1)
            self.assertFalse(self.c.in_transaction)
        self.ns['telegram']=send;self.ns['alert'](*args)
        self.assertEqual(json.loads(self.c.execute("SELECT body FROM pl_events WHERE kind='delivery'").fetchone()[0]),{'delivered':True})
    def test_failed_delivery_does_not_replace_decision(self):
        args=self.alert_setup();self.ns['telegram']=Mock(side_effect=RuntimeError('network fixture'))
        with self.assertRaises(RuntimeError):self.ns['alert'](*args)
        self.assertEqual(self.c.execute('SELECT count(*) FROM pl_predictions').fetchone()[0],1)
        self.assertEqual(json.loads(self.c.execute("SELECT body FROM pl_events WHERE kind='delivery'").fetchone()[0]),{'delivered':False})

if __name__=='__main__':unittest.main()
