import hashlib
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
import replay_wallet_cache as helper
from freeze_wallet_replay import freeze, PROGRAM

class FreezeTests(unittest.TestCase):
    def test_private_cohort_hash_and_database_preservation(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'cache'
            tx={'transaction':{'message':{'instructions':[{'programId':PROGRAM}]}},'test_private_identifier':'private'}
            with sqlite3.connect(p) as db:
                db.execute('CREATE TABLE tx(body TEXT)')
                db.executemany('INSERT INTO tx VALUES (?)',[(json.dumps(tx),),('bad json',)])
            before=p.read_bytes();r=freeze(helper,p)
            self.assertEqual(before,p.read_bytes());self.assertEqual(r['transaction_count'],1)
            self.assertEqual(r['transactions'],[tx]);self.assertTrue(r['private_do_not_publish'])
            encoded=json.dumps([tx],sort_keys=True,separators=(',',':')).encode()
            self.assertEqual(r['transactions_sha256'],hashlib.sha256(encoded).hexdigest())
            self.assertEqual(r['oversized_or_invalid_rows'],1)
            self.assertFalse(r['production_changed']);self.assertEqual(r['network_calls'],0)
    def test_failed_capture_returns_no_partial_artifact(self):
        class Failing:
            def audit_cache(self,*args):raise RuntimeError('blocked')
        with self.assertRaises(RuntimeError):freeze(Failing(),Path('unused'))

if __name__=='__main__':unittest.main()
