import json, pathlib, sqlite3, tempfile, unittest
from unittest.mock import patch
import notifier as n
NOW=1800000000
MINT='A'*32;PAIR='B'*32
def config():return {'activation_ts':NOW-1,'deadline_ts':NOW+1000,'min_mc':100000,'max_mc':500000}
def good():
    checks={k:{'status':'PASS','observed_at':NOW,'evidence_refs':['synthetic:test']} for k in n.REQUIRED}
    review={'mint':MINT,'pair':PAIR,'chain':'solana','policy':'crypto-prealert-v1','checked_at':NOW,'checks':checks}
    return {'mint':MINT,'symbol':'TEST','created_ts':(NOW-3600)*1000,'pinned_pair':PAIR,'last_alert_ts':NOW,'alert_level':1,'ts':NOW,'mc':200000,'liq':30000,'price':.0002,'checked_at':NOW,'verdict':'PASS','review':json.dumps(review)}
class Tests(unittest.TestCase):
    def test_valid(self):self.assertTrue(n.eligible(good(),config(),NOW))
    def test_prefix_and_unknowns(self):
        text=n.message(good(),NOW);self.assertTrue(text.startswith('🔥'))
        self.assertIn('developer history: UNKNOWN',text)
        self.assertIn('$20,000,000',text)
        self.assertIn('No validated 100×',text)
    def test_stale(self):
        r=good();r['ts']=NOW-301;self.assertFalse(n.eligible(r,config(),NOW))
    def test_old_alert(self):
        c=config();c['activation_ts']=NOW+1;self.assertFalse(n.eligible(good(),c,NOW))
    def test_valuation(self):
        for val in (99999,500001,float('nan'),float('inf'),True):
            r=good();r['mc']=val;self.assertFalse(n.eligible(r,config(),NOW))
    def test_identity(self):
        r=good();review=json.loads(r['review']);review['pair']='C'*32;r['review']=json.dumps(review)
        self.assertFalse(n.eligible(r,config(),NOW))
    def test_required_unknown(self):
        for k in n.REQUIRED:
            r=good();review=json.loads(r['review']);review['checks'][k]['status']='UNKNOWN';r['review']=json.dumps(review)
            self.assertFalse(n.eligible(r,config(),NOW))
    def test_background_reject(self):
        r=good();review=json.loads(r['review']);review['checks']['developer_history']={'status':'REJECT'};r['review']=json.dumps(review)
        self.assertFalse(n.eligible(r,config(),NOW))
    def test_evidence_missing(self):
        r=good();review=json.loads(r['review']);review['checks']['token_controls']['evidence_refs']=[];r['review']=json.dumps(review)
        self.assertFalse(n.eligible(r,config(),NOW))
    def test_path_injection(self):
        r=good();r['pinned_pair']='../../credential';self.assertFalse(n.eligible(r,config(),NOW))
    def test_future(self):
        r=good();r['last_alert_ts']=NOW+1;self.assertFalse(n.eligible(r,config(),NOW))
    def state(self,d):
        p=pathlib.Path(d);n.atomic(p/'config.json',config());n.atomic(p/'delivery.json',{});return p
    def test_dedup(self):
        with tempfile.TemporaryDirectory() as d,patch.object(n,'rows',return_value=[good()]):
            p=self.state(d);sent=[]
            self.assertEqual(n.run(p,sender=sent.append,now=NOW)['state'],'sent')
            self.assertEqual(n.run(p,sender=sent.append,now=NOW+1)['state'],'cooldown')
            n.run(p,sender=sent.append,now=NOW+300);self.assertEqual(len(sent),1)
    def test_delivery_ambiguous_not_retried(self):
        with tempfile.TemporaryDirectory() as d,patch.object(n,'rows',return_value=[good()]):
            p=self.state(d);attempt=[]
            def fail(text):attempt.append(text);raise TimeoutError()
            self.assertEqual(n.run(p,sender=fail,now=NOW)['state'],'delivery_unknown')
            n.run(p,sender=fail,now=NOW+300);self.assertEqual(len(attempt),1)
    def test_expiry_no_read_or_send(self):
        with tempfile.TemporaryDirectory() as d,patch.object(n,'rows',side_effect=AssertionError()):
            p=self.state(d);self.assertEqual(n.run(p,now=NOW+1000)['state'],'expired')
    def test_stop_no_read(self):
        with tempfile.TemporaryDirectory() as d,patch.object(n,'rows',side_effect=AssertionError()):
            p=self.state(d);(p/'STOP').touch();self.assertEqual(n.run(p,now=NOW)['state'],'stopped')
    def test_busy_skip(self):
        with tempfile.TemporaryDirectory() as d,patch.object(n,'rows',side_effect=sqlite3.OperationalError()):
            p=self.state(d);self.assertEqual(n.run(p,now=NOW)['state'],'read_skipped')
    def test_state_corrupt_no_send(self):
        with tempfile.TemporaryDirectory() as d:
            p=self.state(d);(p/'delivery.json').write_text('broken')
            with self.assertRaises(ValueError):n.run(p,now=NOW)
    def test_real_sqlite_wal_and_readonly(self):
        with tempfile.TemporaryDirectory() as d:
            p=pathlib.Path(d)/'source.sqlite';c=sqlite3.connect(p)
            c.execute('PRAGMA journal_mode=WAL')
            c.executescript('CREATE TABLE launches(mint TEXT PRIMARY KEY,symbol TEXT,created_ts INTEGER,pinned_pair TEXT,last_alert_ts INTEGER,alert_level INTEGER);CREATE TABLE snapshots(mint TEXT,ts INTEGER,mc REAL,liq REAL,price REAL,PRIMARY KEY(mint,ts));CREATE TABLE prealert_reviews(mint TEXT,level INTEGER,bucket INTEGER,checked_at INTEGER,verdict TEXT,review TEXT,PRIMARY KEY(mint,level,bucket));')
            r=good()
            c.execute('INSERT INTO launches VALUES(?,?,?,?,?,?)',(MINT,'TEST',r['created_ts'],PAIR,NOW,1))
            c.execute('INSERT INTO snapshots VALUES(?,?,?,?,?)',(MINT,NOW,200000,30000,.0002))
            c.execute('INSERT INTO prealert_reviews VALUES(?,?,?,?,?,?)',(MINT,1,NOW//300,NOW,'PASS',r['review']));c.commit()
            c.execute('INSERT INTO snapshots VALUES(?,?,?,?,?)',(MINT,NOW+1,999999,99999,.01));c.commit()
            result=n.rows(p,NOW-1,NOW);self.assertEqual(len(result),1);self.assertEqual(result[0]['mc'],200000)
            self.assertEqual(c.execute('SELECT count(*) FROM snapshots').fetchone()[0],2)
            c.close()
    def test_reads_only_allowlisted_tables(self):
        import inspect
        src=inspect.getsource(n.rows)
        self.assertNotIn('capture.sqlite',src);self.assertNotIn('pl_',src)
        self.assertNotIn('immutable',src);self.assertIn('query_only=ON',src);self.assertIn('mode=ro',src)
    def test_one_message_per_run(self):
        with tempfile.TemporaryDirectory() as d,patch.object(n,'rows',return_value=[good(),good()]):
            p=self.state(d);sent=[];n.run(p,sender=sent.append,now=NOW);self.assertEqual(len(sent),1)
if __name__=='__main__':unittest.main()
