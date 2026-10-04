import json,sqlite3,tempfile,time,unittest
from pathlib import Path
from prediction_ledger import Ledger,FEATURES

class LedgerTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.path=self.tmp.name+'/ledger.sqlite'
        self.l=Ledger(self.path)
        self.model=Path(__file__).with_name('published_baseline').joinpath('model.json').read_bytes()
        self.a=self.l.activate(self.model,b'frozen-plan',b'preprocessor',['old'])
        self.x=dict.fromkeys(FEATURES,1.0)
    def tearDown(self):self.l.close();self.tmp.cleanup()
    def record(self,mint='new',**kw):
        args=dict(mint=mint,case_id=mint+':alert',features=self.x,source_snapshot=[[123,1.0]],
            feature_capture_ns=time.time_ns(),preprocessing_sha256=self.a['preprocessing_sha256'])
        args.update(kw);return self.l.record(**args)
    def test_durable_prediction_and_chain(self):
        r=self.record();self.assertEqual(r['kind'],'prediction')
        self.assertLessEqual(r['feature_capture_ns'],r['decision_ts_ns'])
        self.assertTrue(0<r['model_probability']<1)
        self.l.close();self.l=Ledger(self.path)
        self.assertEqual(self.l.verify()['entries'],1)
    def test_duplicate_and_old_mint(self):
        self.record()
        for mint in ('new','old'):
            with self.assertRaises(ValueError):self.record(mint)
        self.assertEqual(self.l.verify()['entries'],1)
    def test_invalid_first_attempt_cannot_be_replaced(self):
        self.x['band']=True
        self.assertEqual(self.record()['exclusion_reason'],'invalid_features')
        self.x['band']=1.0
        with self.assertRaises(ValueError):self.record()
    def test_future_and_pre_activation_capture(self):
        self.assertEqual(self.record('future',feature_capture_ns=time.time_ns()+10**12)['kind'],'excluded')
        self.assertEqual(self.record('past',feature_capture_ns=1)['kind'],'excluded')
    def test_wrong_preprocessor(self):
        self.assertEqual(self.record(preprocessing_sha256='wrong')['kind'],'excluded')
    def test_edits_and_exclusion_changes_blocked(self):
        self.record()
        for sql in ('DELETE FROM entries','UPDATE entries SET body="x"',
                    'DELETE FROM activation','INSERT INTO excluded VALUES("later")'):
            with self.assertRaises(sqlite3.IntegrityError):self.l.con.execute(sql)
    def test_second_activation_blocked(self):
        with self.assertRaises(ValueError):self.l.activate(self.model,b'other',b'other',[])
    def test_concurrent_connection_duplicate(self):
        other=Ledger(self.path)
        try:
            self.record()
            with self.assertRaises(ValueError):other.record('new','id',self.x,[],time.time_ns(),self.a['preprocessing_sha256'])
        finally:other.close()
    def test_hash_detects_modified_entry(self):
        self.record();self.l.con.execute('DROP TRIGGER no_UPDATE_entries')
        self.l.con.execute('UPDATE entries SET body="{}"')
        with self.assertRaises(ValueError):self.l.verify()

if __name__=='__main__':unittest.main()
