import ast, datetime, hashlib, json, pathlib, sqlite3, tempfile, unittest
from unittest import mock
import earlier_entry as c
import shadow_scorer as a
import launch_path as b
import build_launch_patch as patch
import install_launch_path as install
import install_shadow

ROOT=pathlib.Path(__file__).parent
def fixture_row(ts,mc=50000,price=1,pc1=10):return (ts,price,mc,30000,4000,30000,15,5,70,30,3,pc1)
def policy():return {'version':'synthetic-v1','g':1.5,'seed':20261008,'target_per_arm':100,
    'deadline':a.DEADLINE,'source_sha256':c.SOURCE_SHA,'protocol_sha256':'1'*64,
    'rule_sha256':'2'*64,'owner_approved':True,'estimand':'independent_poll_current_scanner_universe'}
class SourceTests(unittest.TestCase):
    def test_python_guard(self):
        c.require_python()
        with mock.patch.object(c.sys,'version_info',(3,13)):
            with self.assertRaisesRegex(ValueError,'3.12'):c.require_python()
    def test_source_bytes(self):self.assertEqual(hashlib.sha256((ROOT/'frozen_scorer_source.txt').read_bytes()).hexdigest(),c.SOURCE_SHA)
    def test_live_function_guard_accepts_unrelated_poststop_hook(self):
        self.assertEqual(c.verify_live_functions(ROOT/'candidate_early_scout.txt'),hashlib.sha256((ROOT/'candidate_early_scout.txt').read_bytes()).hexdigest())
    def test_live_function_guard_rejects_score_drift(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=pathlib.Path(tmp)/'scanner.py';p.write_text((ROOT/'frozen_scorer_source.txt').read_text().replace('buy_ratio >= 0.52','buy_ratio >= 0.53'))
            with self.assertRaises(ValueError):c.verify_live_functions(p)
    def test_isolated_score(self):
        scorer=c.pure_scorer(ROOT/'frozen_scorer_source.txt')
        rows=[fixture_row(1000+i*60) for i in range(12)]
        n,m,failed=scorer(rows);self.assertEqual(n,11);self.assertTrue(m);self.assertEqual(failed,[])
    def test_score_h1_gate(self):
        scorer=c.pure_scorer(ROOT/'frozen_scorer_source.txt');n,m,failed=scorer([fixture_row(1000+i*60,pc1=170) for i in range(12)])
        self.assertEqual(n,10);self.assertIn('h1_not_extended',failed)
    def test_bad_source_refused(self):
        with self.assertRaises(ValueError):c.pure_scorer(ROOT/'earlier_entry.py')
    def test_no_network_imports(self):
        for name in ('earlier_entry.py','shadow_scorer.py','launch_path.py'):
            tree=ast.parse((ROOT/name).read_text())
            imports=[n.names[0].name for n in ast.walk(tree) if isinstance(n,ast.Import)]
            self.assertFalse(set(imports)&{'requests','httpx','urllib','socket'})
    def test_embedded_readonly_access_probe_compiles(self):
        tree=ast.parse((ROOT/'install_shadow.py').read_text())
        code=next(n.value for n in ast.walk(tree) if isinstance(n,ast.Constant) and isinstance(n.value,str) and n.value.startswith('import sqlite3;'))
        compile(code,'access-probe','exec')

class CoverageTests(unittest.TestCase):
    def setUp(self):self.rows=[fixture_row(10000+i*60) for i in range(64)]
    def test_endpoint_and_run_differ(self):
        self.rows[20]=fixture_row(11200,mc=110000);out,why=c.covered(self.rows,10000)
        self.assertEqual(why,'covered');self.assertEqual(out['label'],'run');self.assertEqual(out['endpoint_multiple'],1)
    def test_late_spike_not_run(self):
        self.rows=[r for r in self.rows if r[0]!=13600];self.rows[60]=fixture_row(13660,mc=110000)
        out,why=c.covered(self.rows,10000);self.assertEqual(out['label'],'non_run');self.assertEqual(out['endpoint_multiple'],2.2)
    def test_missing_endpoint(self):self.assertEqual(c.covered(self.rows[:60],10000)[1],'missing_endpoint')
    def test_gap(self):self.assertEqual(c.covered(self.rows[:10]+self.rows[14:],10000)[1],'gap')
    def test_invalid_zero(self):
        self.rows[20]=fixture_row(11200,mc=0);self.assertEqual(c.covered(self.rows,10000)[1],'invalid_mc')
    def test_prehistory_partial(self):self.assertFalse(c.prehistory_ok(self.rows[:10],self.rows[9][0]))
    def test_intermediate(self):
        self.rows[20]=fixture_row(11200,mc=75000);self.assertEqual(c.covered(self.rows,10000)[0]['label'],'intermediate')
    def test_lateness_180(self):
        rs=[r for r in self.rows if r[0]<13600]+[fixture_row(13780)]
        self.assertEqual(c.covered(rs,10000)[1],'gap') # 240-second final observed gap
    def test_split_boundary(self):
        scorer=c.pure_scorer(ROOT/'frozen_scorer_source.txt');ts=c.SPLIT-3600
        rs=[fixture_row(ts+i*60) for i in range(120)]
        result,counts,_=c.study({('synth','pair'):rs},{'synth':ts-1800},'development',scorer)
        self.assertTrue(counts['split_or_immature']);self.assertTrue(all(r['ts']+3780<c.SPLIT for r in result))

class ExclusionTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=pathlib.Path(self.tmp.name);self.db=self.root/'scanner.sqlite';self.pilot=self.root/'pilot.sqlite'
        with sqlite3.connect(self.db) as db:
            db.executescript('CREATE TABLE pl_predictions(mint TEXT,body TEXT);CREATE TABLE pl_results(body TEXT);CREATE TABLE launches(mint TEXT,created_ts INTEGER);')
            db.execute('INSERT INTO pl_predictions VALUES(?,?)',('ledger','DO NOT READ'))
            schema=','.join(k+(' INTEGER' if k=='ts' else ' REAL') for k in c.FIELDS)
            db.execute('CREATE TABLE snapshots(mint TEXT,pair TEXT,'+schema+')')
            for mint in ('ledger','qualified','control','safe'):
                db.execute('INSERT INTO launches VALUES(?,?)',(mint,1000))
                db.execute('INSERT INTO snapshots VALUES('+','.join('?' for _ in range(14))+')',(mint,'pair',*fixture_row(c.SPLIT-30000)))
        with sqlite3.connect(self.pilot) as db:
            db.execute('CREATE TABLE fc_events(kind TEXT,event_key TEXT,body TEXT)')
            db.execute('INSERT INTO fc_events VALUES(?,?,?)',('cohort','qualified',json.dumps({'controls':[{'mint':'control'}]})))
            db.execute('INSERT INTO fc_events VALUES(?,?,?)',('observation','secret',json.dumps({'mc':999})))
    def tearDown(self):self.tmp.cleanup()
    def test_exclusions_before_histories(self):
        con,ids=c.membership_connection(self.db,self.pilot)
        self.assertEqual(ids,{'ledger','qualified','control'})
        by,_=c.read_history(con,'development');self.assertEqual(list(by),[('safe','pair')]);con.close()
    def test_ledger_body_denied(self):
        con,_=c.membership_connection(self.db,self.pilot)
        with self.assertRaises(sqlite3.Error):con.execute('SELECT body FROM pl_predictions').fetchall()
        with self.assertRaises(sqlite3.Error):con.execute('SELECT body FROM pl_results').fetchall()
        con.close()
    def test_raw_pilot_body_denied(self):
        con,_=c.membership_connection(self.db,self.pilot)
        with self.assertRaises(sqlite3.Error):con.execute('SELECT body FROM pilot.fc_events').fetchall()
        con.close()
    def test_source_writes_denied(self):
        con,_=c.membership_connection(self.db,self.pilot)
        with self.assertRaises(sqlite3.Error):con.execute("UPDATE launches SET created_ts=0")
        con.close()
    def test_holdout_date_boundary(self):
        con,_=c.membership_connection(self.db,self.pilot);by,_=c.read_history(con,'holdout');self.assertEqual(dict(by),{});con.close()
    def test_missing_exclusions_fail_closed(self):
        with sqlite3.connect(self.pilot) as db:db.execute('DROP TABLE fc_events')
        with self.assertRaises(sqlite3.Error):c.membership_connection(self.db,self.pilot)
    def test_one_shot_marker(self):
        path=self.root/'sealed/marker.json';c.one_shot(path,'1'*64)
        with self.assertRaises(FileExistsError):c.one_shot(path,'1'*64)

class ShadowTests(unittest.TestCase):
    def setUp(self):self.con=sqlite3.connect(':memory:');a.initialize(self.con,policy(),a.STOP+1)
    def tearDown(self):self.con.close()
    def row(self,mint,score=8,h1=True,multiple=1.1):
        return {'mint':mint,'pair':'synthetic','score':score,'signals':{'h1_not_extended':h1},'anchor_multiple':multiple}
    def test_pre_stop_activation_refused(self):
        with self.assertRaises(ValueError):a.initialize(sqlite3.connect(':memory:'),policy(),a.STOP-1)
    def test_unfrozen_threshold_refused(self):
        p=policy();p['g']=None
        with self.assertRaises(ValueError):a.initialize(sqlite3.connect(':memory:'),p,a.STOP+1)
    def test_no_reset(self):
        with self.assertRaises(ValueError):a.initialize(self.con,policy(),a.STOP+1)
    def test_hard_gate(self):
        with self.con:a.decisions(self.con,[self.row('x',10,False),self.row('y',7)],a.STOP+2,policy())
        self.assertEqual(a.counts(self.con),{'A0':1,'A1':0,'A2':0,'R':1})
    def test_extension_gate(self):
        with self.con:a.decisions(self.con,[self.row('x',10,True,2)],a.STOP+2,policy())
        self.assertEqual(a.counts(self.con),{'A0':1,'A1':1,'A2':0,'R':0})
    def test_draw_logged_once(self):
        with self.con:
            a.decisions(self.con,[self.row('x'),self.row('y',7)],a.STOP+2,policy())
            a.decisions(self.con,[self.row('x'),self.row('y',7)],a.STOP+3,policy())
        rows=self.con.execute("SELECT body FROM events WHERE kind='random_draw'").fetchall();self.assertEqual(len(rows),1)
        r=json.loads(rows[0][0]);self.assertEqual(r['universe_size'],1);self.assertEqual(r['draw_index'],0);self.assertEqual(r['inputs']['mint'],'y')
    def test_events_immutable(self):
        with self.con:a.append(self.con,'cycle','1',{'n':1})
        with self.assertRaises(sqlite3.Error):self.con.execute('DELETE FROM events')
    def test_same_replay_conflict(self):
        a.append(self.con,'cycle','1',{'n':1})
        with self.assertRaises(ValueError):a.append(self.con,'cycle','1',{'n':2})
    def test_followup_missing_not_zero(self):
        index=a.STOP+2;row=self.row('x');row.update(mc=50000,inputs=[list(fixture_row(index))])
        a.append(self.con,'decision','d',{'arm':'A0','inputs':row,'recorded_ts':index})
        src=sqlite3.connect(':memory:');src.execute('CREATE TABLE snapshots(mint TEXT,pair TEXT,'+','.join(k+' REAL' for k in c.FIELDS)+')')
        a.followup(src,self.con,index+4000,set())
        out=json.loads(self.con.execute("SELECT body FROM events WHERE kind='endpoint'").fetchone()[0])
        self.assertEqual(out['status'],'missing_endpoint');self.assertIsNone(out['multiple']);src.close()
    def test_excluded_followup_not_read(self):
        index=a.STOP+2;row=self.row('x');row.update(mc=50000,inputs=[list(fixture_row(index))])
        a.append(self.con,'decision','d',{'arm':'A0','inputs':row,'recorded_ts':index})
        src=sqlite3.connect(':memory:') # no snapshots table: an accidental read would fail
        a.followup(src,self.con,index+4000,{'x'})
        out=json.loads(self.con.execute("SELECT body FROM events WHERE kind='endpoint'").fetchone()[0])
        self.assertEqual(out['status'],'excluded_after_decision');src.close()

class WalletCoverageTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=pathlib.Path(self.tmp.name);self.now=c.SPLIT+3600;self.mint='1'*32
        self.con=sqlite3.connect(':memory:');self.con.executescript('CREATE TABLE d3_members(mint TEXT);CREATE TABLE launches(mint TEXT,pinned_pair TEXT,created_ts INTEGER,last_trade_ts INTEGER,current_mc REAL,ath_mc REAL);')
        self.con.execute('INSERT INTO launches VALUES(?,?,?,?,?,?)',(self.mint,'pair',(self.now-2000)*1000,self.now*1000,50000,60000))
    def tearDown(self):self.con.close();self.tmp.cleanup()
    def report(self,age=0):
        r={'schema':'wallet-intelligence-v3','screening_packet':{'mint':self.mint,'pair':'pair','history':{'observed_at':self.now,'coverage_summary':{'owners_required':2},'wallets':[
          {'pagination_complete':True,'pending_transactions':0,'null_timestamps':0,'unknown_programs':[],'head_at':self.now-age}]}}}
        (self.root/(self.mint+'.json')).write_text(json.dumps(r))
    def test_coverage_reports_missing_required_owner(self):
        self.report();out=c.wallet_coverage_line(self.con,self.now,self.root)
        self.assertEqual(out['complete_fresh_owner_token_requirements'],1);self.assertEqual(out['known_required_owner_token_requirements'],2)
    def test_stale_head_is_not_complete(self):
        self.report(301);self.assertEqual(c.wallet_coverage_line(self.con,self.now,self.root)['complete_fresh_owner_token_requirements'],0)
    def test_missing_report_not_zero_denominator(self):
        out=c.wallet_coverage_line(self.con,self.now,self.root);self.assertFalse(out['complete_denominator_verified']);self.assertEqual(out['current_nonexcluded_candidates'],1)
    def test_excluded_wallet_report_not_opened(self):
        self.con.execute('INSERT INTO d3_members VALUES(?)',(self.mint,));self.report()
        out=c.wallet_coverage_line(self.con,self.now,self.root);self.assertEqual(out['current_nonexcluded_candidates'],0)

class LaunchPathTests(unittest.TestCase):
    def setUp(self):self.tmp=tempfile.TemporaryDirectory();self.root=pathlib.Path(self.tmp.name);self.ts=c.SPLIT*1000
    def tearDown(self):self.tmp.cleanup()
    def row(self,mc=5000):return {'mint':'1'*32,'created_timestamp':self.ts-1000,'market_cap_usd':mc,'ath_market_cap':mc,'complete':False,'last_trade_timestamp':self.ts}
    def test_append_and_deduplicate(self):
        out=b.append_rows([self.row()],self.ts,self.root,min_free=0);self.assertEqual(out['appended'],1)
        out=b.append_rows([self.row()],self.ts,self.root,min_free=0);self.assertEqual(out['appended'],0);self.assertEqual(out['duplicates'],1)
    def test_conflicts_not_replaced(self):
        out=b.append_rows([self.row(),self.row(6000)],self.ts,self.root,min_free=0);self.assertEqual(out['appended'],0);self.assertEqual(out['dropped'],1)
    def test_missing_mc_preserved(self):
        b.append_rows([self.row(None)],self.ts,self.root,min_free=0)
        with sqlite3.connect(next(self.root.glob('launch_path-*.sqlite'))) as db:self.assertIsNone(db.execute('SELECT mc FROM launch_path').fetchone()[0])
    def test_append_only(self):
        b.append_rows([self.row()],self.ts,self.root,min_free=0)
        with sqlite3.connect(next(self.root.glob('launch_path-*.sqlite'))) as db:
            with self.assertRaises(sqlite3.Error):db.execute('DELETE FROM launch_path')
    def test_disk_cap(self):self.assertEqual(b.append_rows([self.row()],self.ts,self.root,cap=1,min_free=0)['reason'],'storage_guard')
    def test_retention_holds_without_delete(self):
        b.append_rows([self.row()],self.ts,self.root,min_free=0)
        out=b.append_rows([self.row()],self.ts+31*86400000,self.root,min_free=0);self.assertEqual(out['reason'],'retention_archive_review_required')
        self.assertEqual(len(list(self.root.glob('launch_path-*.sqlite'))),1)
    def test_source_patch_only_named_hook(self):
        source=(ROOT/'frozen_scorer_source.txt').read_text();candidate=patch.build(source)
        self.assertEqual(candidate,(ROOT/'candidate_early_scout.txt').read_text());self.assertIn('_d3_append_rows(rows, now)',candidate)
    def test_source_drift_refused(self):
        with self.assertRaises(ValueError):patch.build((ROOT/'frozen_scorer_source.txt').read_text()+'\n')
    def test_install_pre_stop_refused(self):
        with self.assertRaisesRegex(ValueError,'before'):install.check(ROOT,'0'*64,a.STOP-1)
    def test_install_waits_for_passive_followup(self):
        with self.assertRaisesRegex(ValueError,'follow-up'):install.check(ROOT,'0'*64,a.STOP+1)

if __name__=='__main__':unittest.main()
