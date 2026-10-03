import ast, pathlib, unittest, sqlite3, tempfile, types, logging
from unittest.mock import Mock

ROOT=pathlib.Path(__file__).resolve().parent

class CryptoStackTests(unittest.TestCase):
    def test_sources_compile_and_expected_contracts_exist(self):
        early=(ROOT/'early_scout.py').read_text()
        learn=(ROOT/'scout_learning_v2.py').read_text()
        compile(early,'early_scout.py','exec')
        compile(learn,'scout_learning_v2.py','exec')
        e={n.name for n in ast.walk(ast.parse(early)) if isinstance(n,ast.FunctionDef)}
        l={n.name for n in ast.walk(ast.parse(learn)) if isinstance(n,ast.FunctionDef)}
        self.assertTrue({'score_candidate','choose_pair','chunks','main'} <= e)
        self.assertTrue({'capture','import_alerts','track','challenge','main'} <= l)
        self.assertIn('v2_cases',learn)
        self.assertIn('v2_outcomes',learn)
        self.assertIn('if late>180:continue',learn)
        self.assertIn("H=(1,5,15,30,60,120,180,360,720,1440)",learn)

    def test_learning_has_no_telegram_credentials(self):
        learn=(ROOT/'scout_learning_v2.py').read_text().lower()
        self.assertNotIn('bot_token',learn)
        self.assertNotIn('credentials.json',learn)


class TimedEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        tree=ast.parse((ROOT/'scout_learning_v2.py').read_text())
        functions=ast.Module(body=[n for n in tree.body if isinstance(n,ast.FunctionDef)],type_ignores=[])
        self.clock=Mock(return_value=10000)
        self.prod=types.SimpleNamespace(choose_pair=lambda mint,pairs,pinned: pairs[0] if pairs else None)
        self.ns=dict(sqlite3=sqlite3,DB=str(pathlib.Path(self.tmp.name)/'test.sqlite'),
                     H=(1,5,15,30,60,120,180,360,720,1440),
                     time=types.SimpleNamespace(time=self.clock),logging=logging,prod=self.prod)
        exec(compile(functions,'learning_functions','exec'),self.ns)
        self.c=self.ns['db']()
        self.c.execute('CREATE TABLE launches(mint TEXT,pinned_pair TEXT)')
    def tearDown(self):
        self.c.close()
        self.tmp.cleanup()
    def case(self,cid='case',ts=1000,source='SHADOW'):
        self.c.execute("""INSERT INTO v2_cases(id,mint,decision_ts,source,regime,entry_mc)
                          VALUES(?,?,?,?,?,?)""",(cid,cid,ts,source,'RECLAIM',100))
        self.c.execute('INSERT INTO launches VALUES(?,NULL)',(cid,))
        self.ns['seed'](self.c)
    def observe(self,cid,ts,mc):
        self.c.execute('INSERT INTO v2_observations VALUES(?,?,?,?)',(cid,ts,mc,10000))
    def outcome(self,cid,h,ts,late=0):
        self.c.execute('INSERT INTO v2_outcomes VALUES(?,?,?,?,?,?,?,?,?,?)',
                       (cid,h,ts,late,100,10000,1,99,0.1,0))
    def test_expiry_without_provider_or_launch(self):
        self.case(ts=1000)
        self.c.execute('DELETE FROM launches')
        self.clock.return_value=1000+86400+181
        self.ns['dex']=Mock(side_effect=AssertionError('must not fetch'))
        self.ns['track'](self.c)
        self.assertEqual(self.c.execute('SELECT status FROM v2_cases').fetchone()[0],'RESOLVED')
        self.assertEqual(self.c.execute('SELECT count(*) FROM v2_outcomes').fetchone()[0],0)
    def test_expiry_boundary_and_idempotence(self):
        self.case(ts=1000)
        self.assertEqual(self.ns['expire'](self.c,87580),0)
        self.assertEqual(self.ns['expire'](self.c,87581),1)
        self.assertEqual(self.ns['expire'](self.c,87582),0)
    def test_strict_horizon_excludes_late_peak(self):
        self.case()
        for ts in range(1000,4601,60):self.observe('case',ts,200)
        self.observe('case',4601,500)
        self.ns['horizon_metric'](self.c,'case',1000,60,100,4601)
        self.assertEqual(self.c.execute('SELECT coverage_ok,max_mult FROM v2_horizon_metrics').fetchone(),(1,2.0))
        self.ns['horizon_metric'](self.c,'case',1000,60,100,4700)
        self.assertEqual(self.c.execute('SELECT observed_ts FROM v2_horizon_metrics').fetchone()[0],4601)
    def test_sparse_and_missing_observations_ineligible(self):
        self.case()
        self.observe('case',4600,500)
        self.ns['horizon_metric'](self.c,'case',1000,60,100,4600)
        self.ns['horizon_metric'](self.c,'case',1000,5,100,1300)
        self.assertEqual(self.c.execute('SELECT sum(coverage_ok) FROM v2_horizon_metrics').fetchone()[0],0)
    def test_slow_fetch_cannot_backdate_checkpoints(self):
        self.case(ts=1000)
        self.clock.side_effect=[1060,1241]
        self.ns['dex']=lambda m:{'case':[{'marketCap':200,'liquidity':{'usd':10000}}]}
        self.ns['track'](self.c)
        self.assertEqual(self.c.execute('SELECT count(*) FROM v2_outcomes').fetchone()[0],0)
        self.assertEqual(self.c.execute('SELECT observed_ts FROM v2_observations').fetchone()[0],1241)
    def test_checkpoint_lateness_boundary(self):
        self.case(ts=1000)
        self.clock.return_value=1240
        self.ns['dex']=lambda m:{'case':[{'marketCap':200,'liquidity':{'usd':10000}}]}
        self.ns['track'](self.c)
        self.assertEqual(self.c.execute('SELECT horizon,lateness FROM v2_outcomes').fetchone(),(1,180))
        self.assertEqual(self.c.execute('SELECT coverage_ok FROM v2_horizon_metrics').fetchone()[0],0)
    def test_horizons_sources_and_missing_denominators(self):
        self.case('shadow')
        self.case('missing')
        self.case('legacy')
        self.case('alert',source='ALERT')
        for ts in range(1000,11801,60):
            self.observe('shadow',ts,200 if ts<=4600 else 500)
            self.observe('alert',ts,100)
        for cid in ('shadow','alert'):
            for h in (60,180):
                self.outcome(cid,h,1000+h*60)
                self.ns['horizon_metric'](self.c,cid,1000,h,100,1000+h*60)
        self.outcome('legacy',60,4600)
        self.clock.return_value=12000
        self.ns['challenge'](self.c)
        a=self.c.execute("""SELECT n_due,n_timed,n,n_missing,n_incomplete,n2,n3,n5,p2
                           FROM v2_challenger_horizon WHERE source='SHADOW' AND horizon=60""").fetchone()
        self.assertEqual(a,(3,2,1,1,1,1,0,0,1.0))
        self.assertEqual(self.c.execute("SELECT n5 FROM v2_challenger_horizon WHERE source='SHADOW' AND horizon=180").fetchone()[0],1)
        self.assertEqual(self.c.execute("SELECT n2 FROM v2_challenger_horizon WHERE source='ALERT' AND horizon=60").fetchone()[0],0)
        self.assertEqual(self.c.execute("SELECT count(*) FROM v2_horizon_metrics WHERE id='legacy'").fetchone()[0],0)
        self.assertEqual(self.c.execute("SELECT count(*) FROM v2_challenger").fetchone()[0],0)
    def test_no_pair_does_not_invent_outcome(self):
        self.case()
        self.clock.return_value=4600
        self.ns['dex']=lambda m:{}
        self.ns['track'](self.c)
        self.assertEqual(self.c.execute('SELECT count(*) FROM v2_outcomes').fetchone()[0],0)

if __name__=='__main__':
    unittest.main()
