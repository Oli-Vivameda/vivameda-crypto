import json,sqlite3,tempfile,unittest
from pathlib import Path
from daily_learning import local_db,canonical,verify_events
from paper_outcomes import classify,wilson,evaluate
P=json.loads(Path(__file__).with_name('policy.json').read_text())
class EndpointTests(unittest.TestCase):
 def body(self,mint='a'):
  return {'mint':mint,'decision_ts':1000,'decision':'WATCH','source_snapshot':[[1000,1,100,1000]]}
 def rows(self):return [[t,2,200,1000] for t in range(1060,4661,60)]
 def test_own_timestamp_and_first_endpoint(self):
  x=classify(self.body(),self.rows(),4660);self.assertEqual(x['observed_ts'],4600);self.assertEqual(x['market_cap_multiple'],2);self.assertEqual(x['status'],'ELIGIBLE')
 def test_no_late_backfill(self):self.assertEqual(classify(self.body(),self.rows(),4781)['status'],'MISSING')
 def test_wait_and_gaps(self):
  self.assertIsNone(classify(self.body(),self.rows()[:-2],4600));self.assertEqual(classify(self.body(),self.rows()[10:],4660)['reason'],'incomplete_coverage')
 def test_nonfinite_and_invalid_baseline(self):
  b=self.body();b['source_snapshot'][0][2]=float('nan')
  with self.assertRaises(ValueError):classify(b,self.rows(),4660)
  b=self.body();b['source_snapshot'][0][2]=0;self.assertEqual(classify(b,self.rows(),4660)['reason'],'invalid_saved_baseline')
 def test_interval_zero_and_uncertainty(self):
  self.assertIsNone(wilson(0,0));self.assertLess(wilson(1,2)['ci95'][0],.5);self.assertGreater(wilson(1,2)['ci95'][1],.5)
 def test_holdout_excluded_idempotent_and_append_only(self):
  with tempfile.TemporaryDirectory() as tmp:
   state=Path(tmp);c,a=local_db(state/'learning.sqlite',P)
   for mint in ('a','holdout'):c.execute('INSERT INTO decisions VALUES(?,?,?)',(mint,1000,canonical(self.body(mint))))
   c.commit();s=sqlite3.connect(':memory:');s.execute('CREATE TABLE pl_predictions(mint TEXT)');s.execute("INSERT INTO pl_predictions VALUES('holdout')");s.execute('CREATE TABLE snapshots(mint TEXT,ts INTEGER,price REAL,mc REAL,liq REAL)');s.executemany('INSERT INTO snapshots VALUES(?,?,?,?,?)',[['a']+r for r in self.rows()]);s.commit()
   r=evaluate(s,c,state,4660);evaluate(s,c,state,4661);self.assertEqual(r['groups']['WATCH']['eligible'],1);self.assertEqual(r['groups']['WATCH']['excluded_holdout'],1);self.assertEqual(c.execute('SELECT count(*) FROM events').fetchone()[0],2);verify_events(c)
   with self.assertRaises(sqlite3.IntegrityError):c.execute('DELETE FROM paper_endpoints')
if __name__=='__main__':unittest.main()
