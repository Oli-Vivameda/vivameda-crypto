import hashlib
import importlib.util
import json
from pathlib import Path
import sqlite3
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import build_recovery as build
import install_recovery as install

OLD=build.HERE.parent/'crypto_forward_capture'/'integration'
if not OLD.exists():OLD=build.HERE.parent/'crypto_forward_capture_20261005'/'integration'
if not OLD.exists():OLD=build.HERE.parent/'forward_capture'/'integration'
sys.path.insert(0,str(OLD))
spec=importlib.util.spec_from_file_location('original_fixtures',OLD/'test_integration.py')
fixtures=importlib.util.module_from_spec(spec);spec.loader.exec_module(fixtures)
AMENDMENT=hashlib.sha256((build.HERE/'AMENDMENT_20261006.md').read_bytes()).hexdigest()

class RecoveryTests(unittest.TestCase):
    def setUp(self):
        self.f=fixtures.IntegrationTests()
        original=fixtures.build.build
        def amended(*args):
            scanner,tracker=original(*args)
            return build.build(scanner,AMENDMENT),tracker
        with patch.object(fixtures.build,'build',side_effect=amended):self.f.setUp()
        self.g=self.f.g
    def tearDown(self):self.f.tearDown()

    def test_candidate_bytes_match_deterministic_reviewed_builder(self):
        self.assertEqual((build.HERE/'early_scout.py').read_text(),self.f.scanner)

    def test_unavailable_pair_rejects_whole_cycle_then_next_cycle_works(self):
        self.f.activate()
        self.g['fc_emit_cycle']([self.f.item()],['pair_unavailable'],2,'bad',self.f.now)
        self.assertFalse((self.g['FC_DIRECTORY']/'PAUSED.json').exists())
        con=self.g['fc_connection']()
        c=dict(con.execute('SELECT kind,count(*) FROM fc_events GROUP BY kind'))
        self.assertEqual(c,{'rejected_cycle':1})
        self.assertEqual(self.f.emit(),{'alert':'cycle'})
        self.g['fc_core_verify'](con)
    def test_unknown_failure_still_pauses(self):
        self.f.activate();self.g['fc_emit_cycle']([],['invalid_score_inputs'],1,'bad',self.f.now)
        self.assertTrue(self.g['_fc_paused'])
    def test_accounting_error_still_pauses(self):
        self.f.activate();self.g['fc_emit_cycle']([],['pair_unavailable'],2,'bad',self.f.now)
        self.assertTrue(self.g['_fc_paused'])
    def test_input_mismatch_still_pauses(self):self.f.test_changed_exact_input_or_emitted_metric_pauses()
    def test_integrity_failure_still_pauses(self):self.f.test_cached_prefix_rewrite_detected_on_restart()
    def test_no_new_network_calls(self):self.f.test_no_new_network_calls()
    def test_original_alert_and_scorer_unchanged(self):self.f.test_every_existing_function_except_three_hooks_unchanged()
    def test_pause_reason_redacts_unknown_exception(self):
        self.assertEqual(self.g['fc_safe_reason'](ValueError('private-mint/path')),'other_capture_error')
        self.assertEqual(self.g['fc_safe_reason'](ValueError('capture runtime binding')),'capture runtime binding')
    def bind_original(self,tamper=False):
        d=self.g['FC_DIRECTORY'];d.mkdir(parents=True)
        con=sqlite3.connect(d/'capture.sqlite')
        self.g['fc_core_initialize'](con,install.ACTIVATION,[],install.PROTOCOL,
             {'scanner_sha256':build.OLD_SCANNER,'tracker_sha256':build.OLD_TRACKER})
        # Fixture tracker has exactly the reviewed original bytes.
        a=install.audit_empty(con)
        install.append_repair(con,a,hashlib.sha256(self.f.scanner.encode()).hexdigest(),
                              '0'*64 if tamper else AMENDMENT,
                              {'observed_ts':1791269470},install.ACTIVATION+100)
        con.commit();con.close()
    def test_repair_accepts_new_source_preserving_original_activation(self):
        self.bind_original();con=self.g['fc_connection']()
        self.assertIsNotNone(con)
        a=json.loads(con.execute('SELECT body FROM fc_activation').fetchone()[0])
        self.assertEqual(a['scanner_sha256'],build.OLD_SCANNER)
        self.assertEqual(a['deadline'],install.DEADLINE)
        with self.assertRaises(sqlite3.IntegrityError):con.execute("UPDATE fc_activation SET body='{}'")
    def test_wrong_amendment_binding_refused(self):
        self.bind_original(tamper=True)
        with self.assertRaisesRegex(ValueError,'capture repair binding'):self.g['fc_connection']()
    def test_nonempty_pilot_refused_without_reset(self):
        self.bind_original();con=sqlite3.connect(self.g['FC_DIRECTORY']/'capture.sqlite')
        try:
            before=con.execute('SELECT count(*) FROM fc_events').fetchone()[0]
            with self.assertRaisesRegex(ValueError,'original empty pilot'):install.audit_empty(con)
            self.assertEqual(con.execute('SELECT count(*) FROM fc_events').fetchone()[0],before)
        finally:con.close()

    def original_empty(self):
        d=self.g['FC_DIRECTORY'];d.mkdir(parents=True)
        (self.f.base/'early_scout.py').write_bytes((OLD/'early_scout.py').read_bytes())
        con=sqlite3.connect(d/'capture.sqlite')
        self.g['fc_core_initialize'](con,install.ACTIVATION,[],install.PROTOCOL,
             {'scanner_sha256':build.OLD_SCANNER,'tracker_sha256':build.OLD_TRACKER})
        con.close()
        (d/'PAUSED.json').write_text(json.dumps({'paused':True,'reason':'ValueError','observed_ts':1791269470}))
        return d
    def test_installer_dryrun_preserves_files_and_database(self):
        d=self.original_empty();before={p.name:p.read_bytes() for p in d.iterdir()}
        with patch.object(install,'BASE',self.f.base):result=install.install(install.bundle_hash())
        self.assertFalse(result['installed'])
        self.assertEqual(before,{p.name:p.read_bytes() for p in d.iterdir()})
    def test_installer_backup_immutable_activation_and_verified_restart(self):
        d=self.original_empty();backup=self.f.base/'backup';backup.mkdir()
        original_activation=sqlite3.connect(d/'capture.sqlite').execute('SELECT body FROM fc_activation').fetchone()[0]
        with patch.object(install,'BASE',self.f.base),patch.object(install.os,'geteuid',return_value=0), \
             patch.object(install.tempfile,'mkdtemp',return_value=str(backup)), \
             patch.object(install.shutil,'disk_usage',return_value=SimpleNamespace(free=4*1024**3)), \
             patch.object(install,'systemctl') as ctl,patch.object(install,'counts',return_value={'runtime_repair':1,'cycle':1}), \
             patch.object(install.subprocess,'run',return_value=SimpleNamespace(stdout='active\n')):
            result=install.install(install.bundle_hash(),True)
        self.assertTrue(result['installed']);self.assertTrue(result['usable_cycle_verified'])
        self.assertFalse((d/'PAUSED.json').exists());self.assertTrue((d/'PAUSED.original-20261006.json').exists())
        self.assertEqual((backup/'capture.sqlite').stat().st_mode&0o777,0o600)
        con=sqlite3.connect(d/'capture.sqlite')
        try:
            self.assertEqual(con.execute('SELECT body FROM fc_activation').fetchone()[0],original_activation)
            self.g['fc_core_verify'](con)
        finally:con.close()
        self.assertEqual(ctl.call_args_list[0].args,('stop',))
        self.assertEqual(ctl.call_args_list[1].args,('start',))
    def test_install_failure_restores_source_and_pause(self):
        d=self.original_empty();backup=self.f.base/'backup';backup.mkdir()
        source=(self.f.base/'early_scout.py').read_bytes()
        with patch.object(install,'BASE',self.f.base),patch.object(install.os,'geteuid',return_value=0), \
             patch.object(install.tempfile,'mkdtemp',return_value=str(backup)), \
             patch.object(install.shutil,'disk_usage',return_value=SimpleNamespace(free=4*1024**3)), \
             patch.object(install,'systemctl',side_effect=[None,RuntimeError('start failed'),None]):
            with self.assertRaises(RuntimeError):install.install(install.bundle_hash(),True)
        self.assertEqual((self.f.base/'early_scout.py').read_bytes(),source)
        self.assertTrue((d/'PAUSED.json').exists())

if __name__=='__main__':unittest.main()
