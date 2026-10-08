import json,sqlite3,tempfile,unittest
from pathlib import Path
import diagnose_journal_counts as d
import daily_learning as base
P=json.loads(Path(__file__).with_name('policy.json').read_text())
class CountTests(unittest.TestCase):
 def fixture(self):
  s=sqlite3.connect(':memory:');t=sqlite3.connect(':memory:');s.row_factory=sqlite3.Row;t.row_factory=sqlite3.Row
  s.executescript("CREATE TABLE v2_cases(mint TEXT,id TEXT,decision_ts INTEGER,source TEXT,score INTEGER);CREATE TABLE launches(mint TEXT,pinned_pair TEXT);CREATE TABLE pl_predictions(mint TEXT,body TEXT);CREATE TABLE snapshots(mint TEXT,ts INTEGER,price REAL,mc REAL,liq REAL,vol_m5 REAL,vol_h1 REAL,buys_m5 REAL,sells_m5 REAL,buys_h1 REAL,sells_h1 REAL,pc_m5 REAL,pc_h1 REAL);CREATE TABLE prealert_reviews(mint TEXT,checked_at INTEGER,review TEXT);")
  t.executescript("CREATE TABLE decisions(mint TEXT,body TEXT);")
  g=d.pure(Path(base.__file__).read_text())
  return s,t,g
 def row(self,s,mint='private-token',source='ALERT',ts=9900):
  s.execute('INSERT INTO v2_cases VALUES(?,?,?,?,?)',(mint,mint+':case',ts,source,8));s.execute('INSERT INTO launches VALUES(?,?)',(mint,'private-pair'))
 def test_watch_records_without_seven_pass_and_no_private_output(self):
  s,t,g=self.fixture();self.row(s);r=d.collect(s,t,P,9000,g,10000)
  self.assertEqual(r['current_pass_would_record_actions']['WATCH'],1)
  self.assertEqual(r['current_pass_reasons'],{'stale_snapshot':1})
  self.assertNotIn('private-token',json.dumps(r));self.assertNotIn('private-pair',json.dumps(r))
  self.assertEqual(t.execute('SELECT count(*) FROM decisions').fetchone()[0],0)
 def test_exclusion_is_only_opaque_membership_never_prediction_body(self):
  s,t,g=self.fixture();self.row(s);s.execute('INSERT INTO pl_predictions VALUES(?,?)',('private-token','secret prediction payload'));trace=[];s.set_trace_callback(trace.append);r=d.collect(s,t,P,9000,g,10000)
  self.assertEqual(r['source_gate_counts_per_day'][0]['holdout_membership_excluded'],1)
  self.assertEqual(r['current_pass_gates']['selected_by_current_query'],0)
  self.assertFalse(any('body' in q and 'pl_predictions' in q for q in trace));self.assertNotIn('secret',json.dumps(r))
 def test_alert_only_and_timing_are_reported_without_fake_poll_counts(self):
  s,t,g=self.fixture();self.row(s,'shadow','SHADOW');self.row(s,'older','ALERT',9100);r=d.collect(s,t,P,9000,g,10000)
  self.assertEqual(sum(x['retained_cases'] for x in r['source_case_counts_per_day']),2)
  self.assertEqual(r['current_pass_gates']['selected_by_current_query'],0)
  self.assertIn('not_retained',r['historic_actual_pass_input_counts'])
 def test_missing_launch_join_is_counted(self):
  s,t,g=self.fixture();s.execute("INSERT INTO v2_cases VALUES('private','c',9900,'ALERT',8)");r=d.collect(s,t,P,9000,g,10000)
  self.assertEqual(r['source_gate_counts_per_day'][0]['missing_launch_join'],1)
 def test_explicit_reject_classifies_skip_enter_requires_pass(self):
  s,t,g=self.fixture();self.row(s)
  for ts in (9700,9760,9820,9880,9940):
   s.execute('INSERT INTO snapshots VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)',('private-token',ts,1,100000,30000,5000,20000,50,50,600,200,1,2))
  checks={k:{'status':'PASS','observed_at':9990,'evidence_refs':['synthetic']} for k in g['CHECKS']};checks['wallet_age']['status']='REJECT'
  evidence={'mint':'private-token','chain':'solana','pair':'private-pair','checked_at':9990,'checks':checks}
  s.execute('INSERT INTO prealert_reviews VALUES(?,?,?)',('private-token',9990,json.dumps(evidence)))
  r=d.collect(s,t,P,9000,g,10000);self.assertEqual(r['current_pass_would_record_actions']['SKIP'],1)
  checks['wallet_age']['status']='PASS';s.execute('UPDATE prealert_reviews SET review=?',(json.dumps(evidence),));r=d.collect(s,t,P,9000,g,10000)
  self.assertEqual(r['current_pass_would_record_actions']['ENTER_REVIEW'],1)
 def test_readonly_refuses_mutation_and_missing_database(self):
  with tempfile.TemporaryDirectory() as directory:
   p=Path(directory)/'fixture.sqlite';sqlite3.connect(p).close();c=d.readonly(p)
   with self.assertRaises(sqlite3.OperationalError):c.execute('CREATE TABLE x(id)')
   c.close()
   with self.assertRaises(sqlite3.OperationalError):d.readonly(Path(directory)/'absent.sqlite')
if __name__=='__main__':unittest.main()
