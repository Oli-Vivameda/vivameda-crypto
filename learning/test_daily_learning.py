import json,sqlite3,tempfile,time,unittest
from pathlib import Path
from daily_learning import *
from context import learning_context
from install_daily_learning import patch
P=json.loads(Path(__file__).with_name('policy.json').read_text())
class LearningTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
 def tearDown(self):self.tmp.cleanup()
 def test_endpoint_requires_exact_time_and_coverage(self):
  c={'entry_mc':100,'coverage_ok':1,'lateness':1,'observed_ts':4601,'decision_ts':1000,'max_gap':180,'multiple':2}
  self.assertTrue(valid_endpoint(c,P))
  for key,value in [('coverage_ok',0),('lateness',181),('observed_ts',4600),('max_gap',181),('multiple',float('nan'))]:
   self.assertFalse(valid_endpoint(dict(c,**{key:value}),P))
 def case(self,mint,multiple,**kw):
  c={'mint':mint,'decision_ts':10000,'score':8,'entry_mc':100000,'entry_liq':30000,'age_hours':1,'regime':'COMPRESSION','features':{'band':.1},'endpoint_eligible':True,'multiple':multiple};c.update(kw);return c
 def test_matching_rejects_different_regimes_and_uses_controls_once(self):
  a=[self.case('w1',2),self.case('w2',3),self.case('f',.3),self.case('wrong',.2,regime='OTHER')]
  x=matched_cases(a,P);self.assertEqual(len(x),1);self.assertEqual(x[0]['failure_mint'],'f')
  self.assertEqual(matched_cases([a[0],self.case('big',.3,entry_mc=900000)],P),[])
 def test_policy_freezes_and_journal_is_append_only(self):
  c,a=local_db(self.root/'s.sqlite',P);c.execute('INSERT INTO decisions VALUES(?,?,?)',('mint',1,'{}'));c.commit()
  with self.assertRaises(sqlite3.IntegrityError):c.execute("UPDATE decisions SET body='x'")
  c.rollback();c.close()
  with self.assertRaises(ValueError):local_db(self.root/'s.sqlite',dict(P,minimum_score=9))
 def test_unknown_never_enters_and_reject_skips(self):
  f={'band':.1,'vol_accel':2,'liq_change':0};checks={k:'PASS' for k in CHECKS}
  self.assertEqual(decision(f,checks,8,P)[0],'ENTER_REVIEW')
  checks['wallet_age']='UNKNOWN';self.assertEqual(decision(f,checks,8,P)[0],'WATCH')
  checks['wallet_clusters']='REJECT';self.assertEqual(decision(f,checks,8,P)[0],'SKIP')
 def test_read_only_source_cannot_be_mutated(self):
  p=self.root/'prod.sqlite';c=sqlite3.connect(p);c.execute('CREATE TABLE pl_predictions(mint TEXT)');c.execute("INSERT INTO pl_predictions VALUES('sealed-mint')");c.commit();c.close()
  with readonly(p) as c:
   self.assertEqual(holdout_mints(c),{'sealed-mint'})
   with self.assertRaises(sqlite3.OperationalError):c.execute("DELETE FROM pl_predictions")
 def test_context_staleness_and_relevance(self):
  p=self.root/'memory.json';d={'schema':'crypto-daily-memory-v1','generated_at':1000,'live_execution':False,'cases':[{'name':'Agent Cat','symbol':'AGENTCAT','mint':'a'},{'name':'Failure','symbol':'BAD','mint':'b'}]};p.write_text(json.dumps(d))
  self.assertIn('AGENTCAT',learning_context('AGENTCAT',p,1001));self.assertNotIn('BAD',learning_context('AGENTCAT',p,1001));self.assertEqual(learning_context('',p,200000),'')
 def test_agent_patch_calls_dynamic_context_only_for_crypto(self):
  source="def automatic_knowledge_context(q, session):\n    session['knowledge_domain']='crypto' if q=='crypto' else 'general'\n    return 'base'\n\ndef other(): return 1\n"
  patched=patch(source);self.assertEqual(patch(patched),patched)
  import sys,types
  module=types.ModuleType('crypto_daily_context');module.learning_context=lambda q:'fresh evidence';sys.modules['crypto_daily_context']=module
  ns={};exec(patched,ns);self.assertIn('fresh evidence',ns['automatic_knowledge_context']('crypto',{}));self.assertEqual(ns['automatic_knowledge_context']('other',{}),'base')
 def test_nonfinite_snapshot_blocked(self):
  rows=[[1,1,100,30000,100,1200,1,1,60,40,0,0]]*4
  self.assertEqual(snapshot_features(rows)['buy_ratio'],.6)
  rows[-1]=list(rows[-1]);rows[-1][2]=float('nan')
  with self.assertRaises(ValueError):snapshot_features(rows)
 def test_review_excludes_holdout_and_is_idempotent(self):
  db=self.root/'source.sqlite';s=sqlite3.connect(db)
  s.executescript("""CREATE TABLE pl_predictions(mint TEXT);CREATE TABLE launches(mint TEXT,symbol TEXT,name TEXT,created_ts INTEGER,pinned_pair TEXT);
  CREATE TABLE v2_cases(id TEXT,mint TEXT,decision_ts INTEGER,source TEXT,score INTEGER,regime TEXT,features TEXT,entry_mc REAL,entry_liq REAL);
  CREATE TABLE v2_state(id TEXT,peak_mc REAL,last_mc REAL,min_mult REAL);
  CREATE TABLE v2_outcomes(id TEXT,horizon INTEGER,observed_ts INTEGER,lateness INTEGER,multiple REAL,liq REAL);
  CREATE TABLE v2_horizon_metrics(id TEXT,horizon INTEGER,observed_ts INTEGER,coverage_ok INTEGER,max_gap INTEGER);""")
  for mint,multiple in [('dev',2),('holdout',99)]:
   s.execute('INSERT INTO launches VALUES(?,?,?,?,?)',(mint,mint,mint,100000,'pair'))
   s.execute('INSERT INTO v2_cases VALUES(?,?,?,?,?,?,?,?,?)',(mint,mint,1000,'ALERT',8,'COMPRESSION','{}',100,30000))
   s.execute('INSERT INTO v2_state VALUES(?,?,?,?)',(mint,300,200,1))
   s.execute('INSERT INTO v2_outcomes VALUES(?,?,?,?,?,?)',(mint,60,4600,0,multiple,30000))
   s.execute('INSERT INTO v2_horizon_metrics VALUES(?,?,?,?,?)',(mint,60,4600,1,100))
  s.execute("INSERT INTO pl_predictions VALUES('holdout')");s.commit();s.close()
  t,act=local_db(self.root/'local.sqlite',P)
  with readonly(db) as source:
   x=review(source,t,self.root,P,5000);y=review(source,t,self.root,P,5100)
  self.assertEqual(x,y);self.assertEqual(x['summary']['tokens'],1);self.assertEqual(x['summary']['eligible_60m_endpoints'],1)
  self.assertNotIn('holdout',str(x['cases']));self.assertEqual(t.execute('SELECT count(*) FROM events').fetchone()[0],1)
  verify_events(t)
 def test_journal_no_retroactive_enrollment(self):
  s=sqlite3.connect(':memory:');s.row_factory=sqlite3.Row
  s.executescript("CREATE TABLE pl_predictions(mint TEXT);CREATE TABLE launches(mint TEXT,pinned_pair TEXT);CREATE TABLE v2_cases(mint TEXT,id TEXT,decision_ts INTEGER,score INTEGER,source TEXT);")
  s.execute("INSERT INTO launches VALUES('old','p')");s.execute("INSERT INTO v2_cases VALUES('old','old',1,8,'ALERT')")
  t,a=local_db(self.root/'j.sqlite',P)
  x=journal(s,t,self.root,P,{'activated_at':1000},self.root,5000)
  self.assertEqual(x['new_paper_decisions'],0)
 def test_event_chain_detects_changed_hash(self):
  c,a=local_db(self.root/'chain.sqlite',P);event(c,'x',{'a':1});c.commit();c.execute('DROP TRIGGER events_no_UPDATE');c.execute("UPDATE events SET hash='wrong'");c.commit()
  with self.assertRaises(ValueError):verify_events(c)
 def test_recent_journal_snapshots_and_screening_are_saved_once(self):
  s=sqlite3.connect(':memory:');s.row_factory=sqlite3.Row
  s.executescript("CREATE TABLE pl_predictions(mint TEXT);CREATE TABLE launches(mint TEXT,pinned_pair TEXT);CREATE TABLE v2_cases(mint TEXT,id TEXT,decision_ts INTEGER,score INTEGER,source TEXT);CREATE TABLE snapshots(mint TEXT,ts INTEGER,price REAL,mc REAL,liq REAL,vol_m5 REAL,vol_h1 REAL,buys_m5 REAL,sells_m5 REAL,buys_h1 REAL,sells_h1 REAL,pc_m5 REAL,pc_h1 REAL);CREATE TABLE prealert_reviews(mint TEXT,checked_at INTEGER,review TEXT);")
  s.execute("INSERT INTO launches VALUES('new','pair')");s.execute("INSERT INTO v2_cases VALUES('new','case',4990,8,'ALERT')")
  for ts in (4800,4860,4920,4980):s.execute('INSERT INTO snapshots VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)',('new',ts,1,100000,30000,200,1200,12,8,60,40,0,0))
  evidence={'mint':'new','chain':'solana','pair':'pair','checked_at':4980,'checks':{k:{'status':'PASS','observed_at':4980,'evidence_refs':['saved-reference']} for k in CHECKS}}
  s.execute('INSERT INTO prealert_reviews VALUES(?,?,?)',('new',4980,canonical(evidence)))
  t,a=local_db(self.root/'recent.sqlite',P)
  self.assertEqual(journal(s,t,self.root,P,{'activated_at':4900},self.root,5000)['new_paper_decisions'],1)
  self.assertEqual(journal(s,t,self.root,P,{'activated_at':4900},self.root,5001)['new_paper_decisions'],0)
  saved=json.loads(t.execute('SELECT body FROM decisions').fetchone()[0]);self.assertEqual(saved['decision'],'ENTER_REVIEW');self.assertFalse(saved['filled']);self.assertEqual(saved['decision_ts'],5000);self.assertEqual(saved['source_snapshot'][-1][0],4980);verify_events(t)
if __name__=='__main__':unittest.main()
