import json,sqlite3,tempfile,time,unittest
from pathlib import Path
from unittest.mock import patch
from wallet_candidates import export
from wallet_analysis import analyse
from wallet_worker import cycle
from wallet_intelligence import Store
A="5F1Se9J2L16YcK1fpk18NhSvnPjtyjQSaczKGLDoV1Uy"
B="BSDuf5ka7xz5rCaNQJBx1ThNWgKa4mS1hFhAZoihzw9J"
class PipelineTests(unittest.TestCase):
 def test_export_readonly_and_narrow(self):
  with tempfile.TemporaryDirectory() as d:
   db=Path(d)/"scanner";c=sqlite3.connect(db)
   c.execute("CREATE TABLE launches(mint,creator,pinned_pair,alert_level,last_alert_ts,created_ts,last_trade_ts,current_mc)")
   c.execute("INSERT INTO launches VALUES(?,?,?,?,?,?,?,?)",(A,B,A,1,1,6400000,9999000,50000));c.commit();c.close()
   before=db.read_bytes();out=Path(d)/"feed.json"
   self.assertEqual(len(export(db,out,10000)),1);self.assertEqual(db.read_bytes(),before)
   self.assertNotIn("current_mc",out.read_text())
 def test_stale_feed_holds_without_network(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/"feed";p.write_text(json.dumps({"exported_at":1,"candidates":[{"mint":A,"pair":A,"creator":B}]}))
   with patch("wallet_worker.collect_full") as scan:
    self.assertEqual(cycle(p,Path(d)/"data",1000)["status"],"stale_candidate_feed");scan.assert_not_called()
 def test_queue_and_provider_cooldown(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/"feed";p.write_text(json.dumps({"exported_at":1000,"candidates":[{"mint":A,"pair":A,"creator":B}]}))
   result={"issues":["provider_http_429"],"events":[],"wallet_histories":[]}
   with patch("wallet_worker.collect_full",return_value=result):
    self.assertEqual(cycle(p,Path(d)/"data",1000)["status"],"PARTIAL_PROVIDER_ERROR")
   with patch("wallet_worker.collect_full") as scan:
    self.assertEqual(cycle(p,Path(d)/"data",1001)["status"],"idle");scan.assert_not_called()
 def test_infrastructure_excluded_not_unknown(self):
  with tempfile.TemporaryDirectory() as d:
   s=Store(Path(d)/"db")
   r={"holders":[{"owner":A,"reported_pct":70,"provider_label":{"type":"AMM"}},
                  {"owner":B,"reported_pct":5,"provider_label":None}],
      "developer":B,"wallet_histories":[],"events":[],"generated_at":1000}
   out=analyse(r,s.db);self.assertEqual(out["concentration"]["unclassified_top10_reported_pct"],5)
   self.assertFalse(out["developer_history"]["complete"]);self.assertEqual(out["admission"]["status"],"HOLD");s.db.close()
 def test_developer_association_keeps_evidence(self):
  with tempfile.TemporaryDirectory() as d:
   s=Store(Path(d)/"db")
   e={"relation":"mint_authority_at_initialization","source":B,"target":A,"signature":"sig","block_time":9,"transaction_signers":[B]}
   s.db.execute("INSERT INTO signatures VALUES(?,?,?,?)",(B,"sig",9,0))
   s.db.execute("INSERT INTO events VALUES(?,?,?)",("sig","0",json.dumps(e)));s.db.commit()
   r={"holders":[],"developer":B,"wallet_histories":[],"events":[],"generated_at":1000}
   out=analyse(r,s.db);self.assertEqual(out["developer_history"]["associated_mint_initializations"][0]["mint"],A);s.db.close()
 def test_research_gap_does_not_pause_provider(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/"feed";p.write_text(json.dumps({"exported_at":1000,"candidates":[{"mint":A,"pair":A,"creator":B}]}))
   result={"issues":["transaction_unavailable"],"events":[],"wallet_histories":[],"screening":{"verdict":"HOLD","checks":{}}}
   with patch("wallet_worker.collect_full",return_value=result):
    self.assertEqual(cycle(p,Path(d)/"data",1000)["status"],"SCREENED_HOLD")
   c=sqlite3.connect(Path(d)/"data"/"queue.sqlite")
   self.assertIsNone(c.execute("SELECT value FROM control WHERE key='cooldown'").fetchone());c.close()

class ProviderClassificationTests(unittest.TestCase):
 def test_history_provider_errors_back_off(self):
  for code in (-32005,-32011,-32019):
   with self.subTest(code=code),tempfile.TemporaryDirectory() as d:
    p=Path(d)/"feed";p.write_text(json.dumps({"exported_at":1000,"candidates":[{"mint":A,"pair":A,"creator":B}]}))
    result={"issues":["RuntimeError:rpc_error_code_"+str(code)+"_method_getSignaturesForAddress"],"events":[],"wallet_histories":[],"screening":{"verdict":"HOLD","checks":{}}}
    with patch("wallet_worker.collect_full",return_value=result):
     out=cycle(p,Path(d)/"data",1000)
    self.assertEqual(out["status"],"PARTIAL_PROVIDER_ERROR")
    self.assertEqual(out["verdict"],"HOLD")
    c=sqlite3.connect(Path(d)/"data"/"queue.sqlite")
    self.assertIsNone(c.execute("SELECT value FROM control WHERE key='cooldown'").fetchone());c.close()

class QueueIsolationTests(unittest.TestCase):
 def test_departed_candidate_does_not_block_current_feed(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/"feed";root=Path(d)/"data"
   p.write_text(json.dumps({"exported_at":1000,"candidates":[{"mint":A,"pair":A,"creator":B}]}))
   result={"issues":[],"events":[],"wallet_histories":[],"screening":{"verdict":"HOLD","checks":{}}}
   with patch("wallet_worker.collect_full",return_value=result),patch("wallet_worker.time.time",return_value=1000):
    cycle(p,root,1000)
   c=sqlite3.connect(root/"queue.sqlite");c.execute("UPDATE queue SET next_due=0,priority=99 WHERE mint=?",(A,));c.commit();c.close()
   p.write_text(json.dumps({"exported_at":1001,"candidates":[{"mint":B,"pair":A,"creator":B}]}))
   with patch("wallet_worker.collect_full",return_value=result) as scan:
    out=cycle(p,root,1001)
   self.assertEqual(out["mint"],B);self.assertEqual(scan.call_args.args[0],B)
 def test_local_exception_does_not_set_provider_cooldown(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/"feed";root=Path(d)/"data"
   p.write_text(json.dumps({"exported_at":1000,"candidates":[{"mint":A,"pair":A,"creator":B}]}))
   with patch("wallet_worker.collect_full",side_effect=ValueError("local malformed evidence")):
    self.assertEqual(cycle(p,root,1000)["status"],"ERROR")
   c=sqlite3.connect(root/"queue.sqlite")
   self.assertIsNone(c.execute("SELECT value FROM control WHERE key='cooldown'").fetchone());c.close()


class CandidateBackoffTests(unittest.TestCase):
 def test_failure_leaves_other_candidate_runnable(self):
  issues=["provider_http_429","provider_network_error","RuntimeError:rpc_error_code_-32019_method_getSignaturesForAddress"]
  for issue in issues:
   with self.subTest(issue=issue),tempfile.TemporaryDirectory() as d:
    p=Path(d)/"feed";root=Path(d)/"data"
    p.write_text(json.dumps({"exported_at":1000,"candidates":[{"mint":A,"pair":A,"creator":B,"screening_priority":2},{"mint":B,"pair":A,"creator":B}]}))
    failed={"issues":[issue],"events":[],"wallet_histories":[],"screening":{"verdict":"HOLD","checks":{}}}
    good=dict(failed,issues=[])
    with patch("wallet_worker.time.time",return_value=1000),patch("wallet_worker.collect_full",return_value=failed):
     out=cycle(p,root,1000)
    self.assertEqual(out["mint"],A);self.assertEqual(out["retry_scope"],"candidate")
    with patch("wallet_worker.time.time",return_value=1001),patch("wallet_worker.collect_full",return_value=good) as collect:
     out=cycle(p,root,1001)
    self.assertEqual(out["mint"],B);self.assertEqual(collect.call_count,1)
 def test_legacy_global_and_six_hour_candidate_backoff_migrate(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/"feed";root=Path(d)/"data";root.mkdir()
   p.write_text(json.dumps({"exported_at":1000,"candidates":[{"mint":A,"pair":A,"creator":B}]}))
   c=sqlite3.connect(root/"queue.sqlite")
   c.executescript("CREATE TABLE queue(mint TEXT PRIMARY KEY,seen INTEGER,next_due INTEGER,attempts INTEGER,last_status TEXT,priority INTEGER);CREATE TABLE control(key TEXT PRIMARY KEY,value INTEGER);")
   c.execute("INSERT INTO queue VALUES(?,?,?,?,?,?)",(A,1000,22000,5,"ERROR",2))
   c.execute("INSERT INTO control VALUES('cooldown',22000)");c.commit();c.close()
   with patch("wallet_worker.collect_full") as collect:cycle(p,root,1000);collect.assert_not_called()
   c=sqlite3.connect(root/"queue.sqlite")
   self.assertIsNone(c.execute("SELECT value FROM control WHERE key='cooldown'").fetchone())
   self.assertEqual(c.execute("SELECT next_due FROM queue").fetchone()[0],1120);c.close()
 def test_old_due_low_priority_not_starved(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/"feed";root=Path(d)/"data"
   p.write_text(json.dumps({"exported_at":1000,"candidates":[{"mint":A,"pair":A,"creator":B,"screening_priority":2},{"mint":B,"pair":A,"creator":B}]}))
   good={"issues":[],"events":[],"wallet_histories":[],"screening":{"verdict":"HOLD","checks":{}}}
   with patch("wallet_worker.time.time",return_value=1000),patch("wallet_worker.collect_full",return_value=good):
    self.assertEqual(cycle(p,root,1000)["mint"],A)
   with patch("wallet_worker.time.time",return_value=1121),patch("wallet_worker.collect_full",return_value=good):
    self.assertEqual(cycle(p,root,1121)["mint"],B)
 def test_generic_timeout_is_candidate_scoped(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/"feed";root=Path(d)/"data"
   p.write_text(json.dumps({"exported_at":1000,"candidates":[{"mint":A,"pair":A,"creator":B,"screening_priority":2},{"mint":B,"pair":A,"creator":B}]}))
   with patch("wallet_worker.time.time",return_value=1000),patch("wallet_worker.collect_full",side_effect=TimeoutError()):
    out=cycle(p,root,1000)
   self.assertEqual(out["retry_after_seconds"],120)
   good={"issues":[],"events":[],"wallet_histories":[],"screening":{"verdict":"HOLD","checks":{}}}
   with patch("wallet_worker.time.time",return_value=1001),patch("wallet_worker.collect_full",return_value=good):
    self.assertEqual(cycle(p,root,1001)["mint"],B)


class LaneScheduleTests(unittest.TestCase):
 def test_research_and_fast_each_batch_with_same_total_rpc_budget(self):
  from wallet_worker import run_batch
  with tempfile.TemporaryDirectory() as d:
   good={"status":"SCREENED_HOLD","mint":A}
   with patch("wallet_worker.cycle",return_value=good) as one:
    for _ in range(4):run_batch("feed",d)
   self.assertEqual([c.kwargs["research"] for c in one.call_args_list],[True,False]*4)
   self.assertEqual([c.kwargs["rpc_budget"] for c in one.call_args_list],[60,20]*4)
 def test_unsupported_candidate_backoff_does_not_block_other(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/"feed";root=Path(d)/"data"
   p.write_text(json.dumps({"exported_at":1000,"candidates":[{"mint":A,"pair":A,"creator":B,"screening_priority":2},{"mint":B,"pair":A,"creator":B}]}))
   bad={"issues":["ValueError:unsupported_pool_mints"],"events":[],"wallet_histories":[],"screening":{"verdict":"HOLD","checks":{}}}
   with patch("wallet_worker.time.time",return_value=1000),patch("wallet_worker.collect_full",return_value=bad):
    self.assertEqual(cycle(p,root,1000)["retry_after_seconds"],1800)
   with patch("wallet_worker.collect_full",return_value=bad):
    self.assertEqual(cycle(p,root,1001)["mint"],B)
 def test_fast_refresh_does_not_postpone_research_priority(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/"feed";root=Path(d)/"data"
   p.write_text(json.dumps({"exported_at":1000,"candidates":[{"mint":A,"pair":A,"creator":B,"screening_priority":2},{"mint":B,"pair":A,"creator":B}]}))
   good={"issues":[],"events":[],"wallet_histories":[],"screening":{"verdict":"HOLD","checks":{}}}
   with patch("wallet_worker.time.time",return_value=1000),patch("wallet_worker.collect_full",return_value=good):
    cycle(p,root,1000,research=False)
   c=sqlite3.connect(root/"queue.sqlite")
   self.assertEqual(c.execute("SELECT research_due FROM queue WHERE mint=?",(A,)).fetchone()[0],0);c.close()

if __name__=="__main__":unittest.main()

class IdentityQueueTests(unittest.TestCase):
 def test_missing_identity_cannot_consume_valid_candidate_slot(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/"feed";root=Path(d)/"data"
   p.write_text(json.dumps({"exported_at":1000,"candidates":[{"mint":A,"screening_priority":99},{"mint":B,"pair":A,"creator":B}]}))
   good={"issues":[],"events":[],"wallet_histories":[],"screening":{"verdict":"HOLD","checks":{}}}
   with patch("wallet_worker.collect_full",return_value=good) as call:cycle(p,root,1000)
   self.assertEqual(call.call_args.args[0],B)
   self.assertEqual(json.loads((root/"identity_pending.json").read_text())["count"],1)
 def test_identity_reappears_without_waiting_for_backoff(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/"feed";root=Path(d)/"data"
   p.write_text(json.dumps({"exported_at":1000,"candidates":[{"mint":A}]}))
   with patch("wallet_worker.collect_full") as call:
    self.assertEqual(cycle(p,root,1000)["status"],"idle");call.assert_not_called()
   p.write_text(json.dumps({"exported_at":1001,"candidates":[{"mint":A,"creator":B,"pair":A}]}))
   good={"issues":[],"events":[],"wallet_histories":[],"screening":{"verdict":"HOLD","checks":{}}}
   with patch("wallet_worker.collect_full",return_value=good) as call:
    self.assertEqual(cycle(p,root,1001)["mint"],A);call.assert_called_once()
 def test_export_keeps_deferred_identities_separate(self):
  with tempfile.TemporaryDirectory() as d:
   db=Path(d)/"scanner";c=sqlite3.connect(db)
   c.execute("CREATE TABLE launches(mint,creator,pinned_pair,alert_level,last_alert_ts,created_ts,last_trade_ts,current_mc)")
   c.executemany("INSERT INTO launches VALUES(?,?,?,?,?,?,?,?)",[(A,None,None,2,1,6400000,9999000,50000),(B,A,B,1,1,6400000,9999000,50000)])
   c.commit();c.close();before=db.read_bytes();out=Path(d)/"feed.json"
   self.assertEqual([i["mint"] for i in export(db,out,10000)],[B])
   self.assertEqual(json.loads(out.read_text())["deferred_identities"][0]["mint"],A)
   self.assertEqual(before,db.read_bytes())
 def test_discovery_fills_missing_creator_but_never_replaces_existing(self):
  import ast,re
  source=Path(__file__).with_name("early_scout.py").read_text()
  node=next(n for n in ast.parse(source).body if isinstance(n,ast.FunctionDef) and n.name=="upsert_pump")
  ns={"time":time,"re":re};exec(compile(ast.Module(body=[node],type_ignores=[]),"<test>","exec"),ns)
  c=sqlite3.connect(":memory:")
  c.execute("CREATE TABLE launches(mint PRIMARY KEY,created_ts,creator,name,symbol,protocol,token_program,pump_pool,first_seen,last_pump_seen,last_trade_ts,current_mc,ath_mc,complete)")
  row={"mint":A,"created_timestamp":1000}
  ns["upsert_pump"](c,[row]);self.assertIsNone(c.execute("SELECT creator FROM launches").fetchone()[0])
  ns["upsert_pump"](c,[dict(row,creator=B)]);self.assertEqual(c.execute("SELECT creator FROM launches").fetchone()[0],B)
  ns["upsert_pump"](c,[dict(row,creator=A)]);self.assertEqual(c.execute("SELECT creator FROM launches").fetchone()[0],B)
  c.close()
