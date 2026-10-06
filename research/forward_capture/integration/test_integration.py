import ast
import hashlib
import json
import logging
import math
import sqlite3
import tempfile
import time
import unittest
import importlib.util
from types import SimpleNamespace
from pathlib import Path
from unittest.mock import patch
import build_integration as build


def functions(source):
    return {n.name: ast.dump(n,include_attributes=False) for n in ast.parse(source).body if isinstance(n,ast.FunctionDef)}


class IntegrationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.base = Path(self.temp.name)
        self.scanner, self.tracker = build.build((build.HERE/'base_early_scout.py').read_text(),(build.HERE/'base_scout_learning_v2.py').read_text())
        scanner_path=self.base/'early_scout.py';scanner_path.write_text(self.scanner)
        (self.base/'scout_learning_v2.py').write_text(self.tracker)
        tree=ast.parse(self.scanner)
        kept=[]
        for n in tree.body:
            if isinstance(n,ast.FunctionDef) and (n.name.startswith('fc_') or n.name=='score_candidate'):
                kept.append(n)
            elif isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and (t.id.startswith('FC_') or t.id.startswith('_fc_')) for t in n.targets):
                kept.append(n)
        self.g=dict(BASE=self.base,Path=Path,hashlib=hashlib,json=json,math=math,sqlite3=sqlite3,time=time,logging=logging,__file__=str(scanner_path))
        exec(compile(ast.Module(body=kept,type_ignores=[]),'isolated-fixture','exec'),self.g)
        self.now=int(time.time())

    def tearDown(self):
        con=self.g['_fc_connection']
        if con is not None:con.close()
        self.temp.cleanup()

    def activate(self,excluded=()):
        d=self.g['FC_DIRECTORY'];d.mkdir(parents=True,mode=0o700)
        con=sqlite3.connect(d/'capture.sqlite')
        self.g['fc_core_initialize'](con,self.now-1,excluded,self.g['FC_PROTOCOL_SHA256'],
             {'scanner_sha256':hashlib.sha256(self.scanner.encode()).hexdigest(),
              'tracker_sha256':hashlib.sha256(self.tracker.encode()).hexdigest()})
        con.close()

    def item(self,mint='alert',low=False):
        prices=[1,1.5,1.7,2] if low else [1,1,1,1]
        rows=[(self.now-600+i*200,p,100000,30000,8000,50000,20,10,100,20,50 if low else 1,170) for i,p in enumerate(prices)]
        score,metrics,failed=self.g['score_candidate'](rows)
        self.assertEqual(score,7 if low else 10)
        row=(mint,(self.now-1800)*1000,'creator',100000,100000,mint+'-pair')
        return (row,{'pairAddress':mint+'-pair'},score,metrics,failed,0,rows,self.now*1000000000)

    def emit(self):
        return self.g['fc_emit_cycle']([self.item(),self.item('control',True)],[],2,'cycle',self.now)

    def test_dormant_no_private_files_without_activation(self):
        self.assertEqual(self.emit(),{})
        self.g['fc_observe_pairs']([],self.now)
        self.assertFalse(self.g['FC_DIRECTORY'].exists())

    def test_exact_private_inputs_cohort_and_count_only_health(self):
        self.activate();self.assertEqual(self.emit(),{'alert':'cycle'})
        con=self.g['fc_connection']()
        self.assertEqual(con.execute("SELECT count(*) FROM fc_events WHERE kind='inputs'").fetchone()[0],2)
        health=json.loads(con.execute("SELECT body FROM fc_events WHERE kind='cycle_health'").fetchone()[0])
        self.assertEqual(health['selected'],2);self.assertNotIn('mint',health)
        cohort=json.loads(con.execute("SELECT body FROM fc_events WHERE kind='cohort'").fetchone()[0])
        self.assertEqual(cohort['controls'][0]['mint'],'control')

    def test_missing_pair_pauses_whole_cycle_and_preserves_no_cohort(self):
        self.activate()
        self.assertEqual(self.g['fc_emit_cycle']([self.item()],['pair_unavailable'],2,'cycle',self.now),{})
        self.assertTrue((self.g['FC_DIRECTORY']/'PAUSED.json').exists())
        con=self.g['_fc_connection']
        self.assertEqual(con.execute("SELECT count(*) FROM fc_events WHERE kind='cohort'").fetchone()[0],0)

    def test_known_admission_failure_disclosed(self):
        self.activate()
        self.g['fc_emit_cycle']([self.item()],['history'],2,'cycle',self.now)
        con=self.g['fc_connection']()
        health=json.loads(con.execute("SELECT body FROM fc_events WHERE kind='cycle_health'").fetchone()[0])
        self.assertEqual(health['admission_failures'],['history'])

    def test_changed_exact_input_or_emitted_metric_pauses(self):
        self.activate();item=list(self.item());item[3]=dict(item[3],mc=100001)
        self.assertEqual(self.g['fc_emit_cycle']([tuple(item)],[],1,'cycle',self.now),{})
        self.assertTrue(self.g['_fc_paused'])

    def test_screening_and_delivery_recorded_independently(self):
        self.activate();self.emit()
        self.g['fc_emit_screening']('alert','cycle','HOLD',False)
        con=self.g['fc_connection']()
        row=json.loads(con.execute("SELECT body FROM fc_events WHERE kind='screening'").fetchone()[0])
        self.assertEqual(row['verdict'],'HOLD');self.assertFalse(row['delivered'])

    def test_passive_receipts_only_relevant_timed_same_pair(self):
        self.activate();self.emit()
        observations=[{'baseToken':{'address':'alert'},'pairAddress':'alert-pair','marketCap':200000},
                      {'baseToken':{'address':'control'},'pairAddress':'control-pair','marketCap':100000},
                      {'baseToken':{'address':'unrelated'},'pairAddress':'another','marketCap':100000}]
        self.g['fc_observe_pairs'](observations,self.now+3599)
        self.g['fc_observe_pairs'](observations,self.now+3600)
        con=self.g['fc_connection']()
        self.assertEqual(con.execute("SELECT count(*) FROM fc_events WHERE kind='observation'").fetchone()[0],2)
        self.g['fc_core_verify'](con)

    def test_low_disk_and_storage_cap_pause(self):
        self.activate()
        with patch('shutil.disk_usage',return_value=type('Usage',(),{'free':1})()):self.emit()
        self.assertTrue(self.g['_fc_paused'])

    def test_binding_change_refused(self):
        self.activate();(self.base/'scout_learning_v2.py').write_text('changed')
        self.assertEqual(self.emit(),{});self.assertTrue(self.g['_fc_paused'])

    def test_lock_contention_bounded_and_isolated(self):
        self.activate()
        locker=sqlite3.connect(self.g['FC_DIRECTORY']/'capture.sqlite');locker.execute('BEGIN IMMEDIATE')
        start=time.monotonic()
        try:self.assertEqual(self.emit(),{})
        finally:locker.rollback();locker.close()
        self.assertLess(time.monotonic()-start,1)
        self.assertTrue(self.g['_fc_paused'])

    def test_cached_prefix_rewrite_detected_on_restart(self):
        self.activate();self.emit()
        con=self.g['_fc_connection'];con.execute('DROP TRIGGER fc_events_no_UPDATE');con.execute("UPDATE fc_events SET body='{}' WHERE seq=1");con.commit()
        con.close();self.g['_fc_connection']=None
        self.assertEqual(self.emit(),{});self.assertTrue(self.g['_fc_paused'])

    def test_every_existing_function_except_three_hooks_unchanged(self):
        old=functions((build.HERE/'base_early_scout.py').read_text());new=functions(self.scanner)
        for name,code in old.items():
            if name not in ('alert','enrich_and_score','dex_pairs'):self.assertEqual(code,new[name],name)
        old=functions((build.HERE/'base_scout_learning_v2.py').read_text());new=functions(self.tracker)
        for name,code in old.items():
            if name!='dex':self.assertEqual(code,new[name],name)

    def test_no_new_network_calls(self):
        def network_calls(source):
            return sorted(ast.unparse(n) for n in ast.walk(ast.parse(source)) if isinstance(n,ast.Call) and
                ((isinstance(n.func,ast.Name) and n.func.id in ('get_json','rpc','dex_pairs','telegram')) or
                 (isinstance(n.func,ast.Attribute) and n.func.attr in ('get','post') and isinstance(n.func.value,ast.Name) and n.func.value.id in ('SESSION','S'))))
        self.assertEqual(network_calls(self.scanner),network_calls((build.HERE/'base_early_scout.py').read_text()))
        self.assertEqual(network_calls(self.tracker),network_calls((build.HERE/'base_scout_learning_v2.py').read_text()))

    def test_capture_before_screening_and_receipt_after_fetch(self):
        tree=ast.parse(self.scanner)
        enrich=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='enrich_and_score')
        calls={n.func.id:n.lineno for n in ast.walk(enrich) if isinstance(n,ast.Call) and isinstance(n.func,ast.Name)}
        self.assertLess(calls['fc_emit_cycle'],calls['alert'])
        for src,name in ((self.scanner,'dex_pairs'),(self.tracker,'dex')):
            fn=next(n for n in ast.parse(src).body if isinstance(n,ast.FunctionDef) and n.name==name)
            receipts=[n.lineno for n in ast.walk(fn) if isinstance(n,ast.Call) and ((isinstance(n.func,ast.Name) and n.func.id=='fc_observe_pairs') or (isinstance(n.func,ast.Attribute) and n.func.attr=='fc_observe_pairs'))]
            fetches=[n.lineno for n in ast.walk(fn) if isinstance(n,ast.Call) and ((isinstance(n.func,ast.Name) and n.func.id=='get_json') or (isinstance(n.func,ast.Attribute) and n.func.attr=='get_json'))]
            self.assertGreater(receipts[0],fetches[0])

    def test_large_exclusion_population_indexed_and_bounded_metadata(self):
        self.activate(['known-'+str(i) for i in range(100000)])
        con=self.g['fc_connection']()
        body=con.execute('SELECT body FROM fc_activation').fetchone()[0]
        self.assertLess(len(body),1000)
        self.assertEqual(con.execute('SELECT count(*) FROM fc_excluded').fetchone()[0],100000)

    def test_500_cycle_resource_fixture(self):
        self.activate()
        start=time.monotonic()
        for i in range(500):
            ts=self.now+i*20
            batch=[]
            for mint, low in [('alert',False),('control',True)]:
                item=list(self.item(mint,low))
                item[0]=(mint,(self.now-3600)*1000,'creator',100000,100000,mint+'-pair')
                prices=[1+(j/35) if low else 1 for j in range(36)]
                rows=[(ts-2100+j*60,p,100000,30000,8000,50000,20,10,100,20,50 if low else 1,170)
                      for j,p in enumerate(prices)]
                item[2],item[3],item[4]=self.g['score_candidate'](rows)
                item[6]=rows;item[7]=ts*1000000000
                batch.append(tuple(item))
            self.g['fc_emit_cycle'](batch,[],2,'resource-'+str(i),ts)
        elapsed=time.monotonic()-start
        con=self.g['fc_connection']()
        self.assertEqual(con.execute("SELECT count(*) FROM fc_events WHERE kind='cycle'").fetchone()[0],500)
        self.assertEqual(con.execute("SELECT count(*) FROM fc_events WHERE kind='cohort'").fetchone()[0],1)
        self.g['fc_core_verify'](con)
        size=sum(p.stat().st_size for p in self.g['FC_DIRECTORY'].glob('capture.sqlite*'))
        self.assertLess(size,32*1024*1024)
        self.assertLess(elapsed,15)
        print(json.dumps({'synthetic_cycles':500,'elapsed_seconds':round(elapsed,3),'database_bytes':size,
                          'network_requests':0,'live_data':False}))

    def test_count_status_contains_no_outcomes_or_identities(self):
        self.assertEqual(self.g['fc_count_status'](),{'status':'not_activated'})
        self.activate();self.emit()
        status=self.g['fc_count_status']()
        self.assertEqual(status['matched_events'],1)
        self.assertEqual(status['control_entries'],1)
        self.assertFalse({'mint','multiple','profit','probability','answer'} & set(status))

    def installer(self):
        spec=importlib.util.spec_from_file_location('activation_fixture',build.HERE/'activate_capture.py')
        mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod);mod.BASE=self.base
        (self.base/'data').mkdir(exist_ok=True)
        con=sqlite3.connect(self.base/'data'/'early_scout.sqlite')
        con.executescript('CREATE TABLE launches(mint TEXT);CREATE TABLE snapshots(mint TEXT);CREATE TABLE v2_cases(mint TEXT);')
        con.execute("INSERT INTO launches VALUES('existing')");con.commit();con.close()
        return mod

    def test_activation_dryrun_has_no_runtime_writes_or_model_table_reads(self):
        mod=self.installer();user=SimpleNamespace(pw_uid=0,pw_gid=0)
        with patch.object(mod,'service_user',return_value=user):
            result=mod.activate(False,mod.bundle_hash())
        self.assertTrue(result['validated']);self.assertFalse(result['installed'])
        self.assertFalse(self.g['FC_DIRECTORY'].exists())
        self.assertEqual(result['excluded_count'],1)

    def test_atomic_activation_private_permissions_and_no_reactivation(self):
        mod=self.installer();user=SimpleNamespace(pw_uid=0,pw_gid=0)
        with patch.object(mod,'service_user',return_value=user),patch.object(mod.os,'geteuid',return_value=0),patch.object(mod.os,'chown'):
            result=mod.activate(True,mod.bundle_hash())
            self.assertTrue(result['installed'])
            with self.assertRaises(ValueError):mod.activate(True,mod.bundle_hash())
        self.assertEqual((self.g['FC_DIRECTORY']/'capture.sqlite').stat().st_mode & 0o777,0o600)
        self.assertEqual(self.g['FC_DIRECTORY'].stat().st_mode & 0o777,0o700)
        self.assertFalse(list(self.g['FC_DIRECTORY'].glob('activation-*')))

    def test_activation_bundle_and_deployed_source_must_match(self):
        mod=self.installer()
        with self.assertRaises(ValueError):mod.activate(False,'0'*64)
        (self.base/'early_scout.py').write_text('changed')
        with self.assertRaises(ValueError):mod.activate(False,mod.bundle_hash())


if __name__=='__main__':unittest.main()
