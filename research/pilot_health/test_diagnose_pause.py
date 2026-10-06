import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch
import diagnose_pause as d

SOURCE=Path(__file__).resolve().parents[1]/'crypto_forward_capture'/'integration'/'early_scout.py'


class DiagnosticTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Server fixture location differs from the local test tree.
        p=SOURCE if SOURCE.exists() else Path(__file__).resolve().parents[1]/'crypto_forward_capture_20261005'/'integration'/'early_scout.py'
        if not p.exists():p=Path(__file__).resolve().parents[1]/'forward_capture'/'integration'/'early_scout.py'
        cls.source=p.read_text()

    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.p=Path(self.temp.name)/'probe.sqlite'
        self.con=sqlite3.connect(self.p)
        self.con.executescript('CREATE TABLE launches(mint TEXT,created_ts INTEGER,creator TEXT,current_mc REAL,ath_mc REAL,pinned_pair TEXT,last_trade_ts INTEGER,alert_level INTEGER);CREATE TABLE snapshots(mint TEXT,ts INTEGER,pair TEXT,price REAL,mc REAL,liq REAL,vol_m5 REAL,vol_h1 REAL,buys_m5 INTEGER,sells_m5 INTEGER,buys_h1 INTEGER,sells_h1 INTEGER,pc_m5 REAL,pc_h1 REAL);')
        self.now=10000

    def tearDown(self):self.con.close();self.temp.cleanup()

    def seed(self,last=10000):
        self.con.execute('INSERT INTO launches VALUES(?,?,?,?,?,?,?,?)',('PRIVATE-MINT',(self.now-1800)*1000,'PRIVATE-CREATOR',100000,100000,'PRIVATE-PAIR',self.now*1000,0))
        for ts in (last-600,last-400,last-200,last):
            self.con.execute('INSERT INTO snapshots VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)',('PRIVATE-MINT',ts,'PRIVATE-PAIR',1,100000,30000,8000,50000,20,10,100,20,1,170))
        self.con.commit()

    def test_valid_current_inputs_count_only(self):
        self.seed();r=d.readiness(self.con,self.source,self.now)
        self.assertEqual(r['counts']['current_input_validation_passed'],1)
        self.assertFalse(r['original_failed_cycle_reconstructed'])
        self.assertNotIn('PRIVATE',json.dumps(r));self.assertNotIn('100000',json.dumps(r))

    def test_stale_input_reason(self):
        self.seed(last=self.now-200);r=d.readiness(self.con,self.source,self.now)
        self.assertEqual(r['counts']['input_rejected:stale or future snapshot'],1)

    def test_missing_snapshot_and_no_outcome_tables(self):
        self.seed();self.con.execute('DELETE FROM snapshots');self.con.commit()
        r=d.readiness(self.con,self.source,self.now)
        self.assertEqual(r['counts']['no_stored_pair_snapshot'],1);self.assertEqual(r['counts']['history'],1)

    def test_no_private_exception_details(self):
        self.seed();g=d.namespace(self.source,self.now)
        def fail(rows):raise ValueError('PRIVATE-CREDENTIAL')
        g['score_candidate']=fail
        with patch.object(d,'namespace',return_value=g):r=d.readiness(self.con,self.source,self.now)
        self.assertEqual(r['counts']['input_rejected:other_value_error'],1);self.assertNotIn('PRIVATE',json.dumps(r))

    def test_read_only_and_no_database_changes(self):
        self.seed();before=self.p.read_bytes();con=d.read_only(self.p)
        try:
            d.readiness(con,self.source,self.now)
            with self.assertRaises(sqlite3.OperationalError):con.execute('DELETE FROM snapshots')
        finally:con.rollback();con.close()
        self.assertEqual(before,self.p.read_bytes())

    def test_namespace_has_no_network_or_pilot_writer(self):
        g=d.namespace(self.source,self.now)
        for name in ('SESSION','requests','telegram','fc_connection','fc_pause','fc_emit_cycle','db'):
            self.assertNotIn(name,g)


if __name__=='__main__':unittest.main()
