import hashlib
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch
import replay_wallet_cache as replay

class ReplayTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / 'cache.sqlite'
        with sqlite3.connect(self.path) as db:
            db.execute('CREATE TABLE tx (body TEXT)')
    def insert(self, *bodies):
        with sqlite3.connect(self.path) as db:
            db.executemany('INSERT INTO tx VALUES (?)', [(b,) for b in bodies])
    def body(self, program='DFLOW'):
        return json.dumps({'transaction': {'message': {'instructions': [{'programId': program}]}}, 'private': 'wallet-secret'})
    def reconcile(self, tx):
        return {'status': 'ENDPOINT_AMOUNTS_MATCH', 'history_coverage_complete': False,
                'receipts': [{'kind': 'token_transfer', 'source_account': 'wallet-secret'}],
                'blockers': ['token2022_extensions_unverified', 'wallet-secret']}
    def test_aggregate_and_no_database_changes(self):
        self.insert(self.body(), self.body('OTHER'))
        before = self.path.read_bytes()
        out = replay.audit_cache(self.path, self.reconcile, 'DFLOW')
        self.assertEqual(self.path.read_bytes(), before)
        self.assertEqual(out['endpoint_amounts_match'], 1)
        self.assertEqual(out['receipt_count'], 1)
        self.assertEqual(out['history_complete_claimed'], 0)
        self.assertEqual(out['blocker_transaction_counts']['token2022_extensions_unverified'], 1)
        self.assertNotIn('wallet-secret', json.dumps(out))
    def test_row_limit_selects_latest_inserted(self):
        self.insert(self.body(), self.body('OTHER'))
        out = replay.audit_cache(self.path, self.reconcile, 'DFLOW', 1)
        self.assertEqual(out['rows_examined'], 1)
        self.assertEqual(out['dflow_transactions'], 0)
    def test_invalid_rows_and_size_bound(self):
        self.insert('bad json', '{}', 'x' * 201)
        with patch.object(replay, 'MAX_BODY_BYTES', 200):
            out = replay.audit_cache(self.path, self.reconcile, 'DFLOW')
        self.assertEqual(out['oversized_or_invalid_rows'], 3)
    def test_invalid_limits(self):
        for value in (True, 0, 1001, -1):
            with self.assertRaises(ValueError): replay.audit_cache(self.path, self.reconcile, 'DFLOW', value)
    def test_symlink_refused(self):
        link = self.path.parent / 'link'; link.symlink_to(self.path)
        with self.assertRaises(ValueError): replay.audit_cache(link, self.reconcile, 'DFLOW')
    def test_unexpected_coverage_claim_stops(self):
        self.insert(self.body())
        with self.assertRaisesRegex(RuntimeError, 'unexpected_coverage_claim'):
            replay.audit_cache(self.path, lambda tx: {'history_coverage_complete': True}, 'DFLOW')
    def test_total_bytes_bound(self):
        self.insert(self.body())
        with patch.object(replay, 'MAX_TOTAL_BYTES', 1):
            out = replay.audit_cache(self.path, self.reconcile, 'DFLOW')
        self.assertTrue(out['bounded_stop'])
        self.assertEqual(out['dflow_transactions'], 0)

if __name__ == '__main__': unittest.main()
