import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from export_wallet_failure_samples import select_samples

class FailureSampleTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / 'cache'
        tx = {'transaction': {'message': {'instructions': [{'programId': 'D'}]}}}
        with sqlite3.connect(self.path) as db:
            db.execute('CREATE TABLE tx(body TEXT)')
            db.executemany('INSERT INTO tx VALUES (?)', [(json.dumps(tx),)] * 20)
    def reconcile(self, tx):
        return {'history_coverage_complete': False, 'blockers': ['native_underflow', 'route_layout_unknown']}
    def run_sample(self, path=None, limit=1000, reconcile=None):
        return select_samples(path or self.path, reconcile or self.reconcile, lambda tx, i: {'reason': 'unsupported_instruction'}, 'D', limit)
    def test_bounded_sample_and_database_preservation(self):
        before = self.path.read_bytes(); result = self.run_sample()
        self.assertEqual(self.path.read_bytes(), before)
        self.assertEqual(result['category_counts'], {'native_underflow': 3, 'route_layout_unknown': 3})
        self.assertEqual(len(result['samples']), 3)
        self.assertTrue(result['private_do_not_publish'])
    def test_row_limit(self):
        self.assertEqual(len(self.run_sample(limit=1)['samples']), 1)
        with self.assertRaises(ValueError): self.run_sample(limit=True)
    def test_symlink_refused(self):
        link = self.path.parent / 'link'; link.symlink_to(self.path)
        with self.assertRaises(ValueError): self.run_sample(path=link)
    def test_coverage_claim_refused(self):
        with self.assertRaises(RuntimeError): self.run_sample(reconcile=lambda tx: {'history_coverage_complete': True})

if __name__ == '__main__': unittest.main()
