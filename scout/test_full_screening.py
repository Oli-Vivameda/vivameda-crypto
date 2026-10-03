import ast,copy,json,pathlib,tempfile,time,unittest
from unittest.mock import Mock,patch,MagicMock
from screening_policy import POLICY,LIMITS,screen_packet
from full_screening import sale_receipts,index_window,history_packet
from protocol_screening import PUMP,SPL,TOKEN22,b58encode
from wallet_intelligence import Store
import test_prealert_risk as prealert
NOW=4000000
MINT="5F1Se9J2L16YcK1fpk18NhSvnPjtyjQSaczKGLDoV1Uy"
PAIR="BSDuf5ka7xz5rCaNQJBx1ThNWgKa4mS1hFhAZoihzw9J"
DEV="creator"
def fixture():
    ref={"observed_at":NOW,"evidence_refs":["fixture:verified"]}
    owners=[{"owner":PAIR,"pct":75},{"owner":DEV,"pct":1}]+[{"owner":"w"+str(i),"pct":2} for i in range(9)]
    hist=[{"wallet":r["owner"],"window_start":NOW-2592000,"head_at":NOW,"pagination_complete":True,
           "pending_transactions":0,"indexed_transactions":1,"null_timestamps":0,"unknown_programs":[],
           "activity_age_lower_bound":800000} for r in owners if r["owner"]!=PAIR]
    return {"policy":POLICY,"mint":MINT,"pair":PAIR,"creator":DEV,
      "pool":dict(ref,authenticated=True,sell_enabled=True,state={"base_mint":MINT,"coin_creator":DEV,
          "advanced_controls_verified":True,"is_mayhem_mode":False,"can_edit_creator_fee":False,"creator_fee_bps":0},
          token_controls={"status":"PASS"},liquidity={"status":"OBSERVED","outstanding_lp_supply":0}),
      "ownership":dict(ref,authenticated=True,mint=MINT,owners=owners,unseen_pct=6,creator_total_pct=1),
      "history":dict(ref,wallets=hist,events=[]),
      "developer":{"current_provider_flag":False,"attribution_verified":True,"associated_mints":[MINT],"prior_reports":[]},
      "trades":dict(ref,sales=[{"pool":PAIR,"mint":MINT,"seller":"seller"+str(i),"time":NOW,
           "base_sent":10,"quote_received":5,"signature":"sig"+str(i)} for i in range(3)])}
class PolicyTests(unittest.TestCase):
 def setUp(self):self.p=fixture()
 def checks(self):return screen_packet(self.p,MINT,PAIR,DEV,NOW)
 def test_real_positive_policy_path(self):self.assertTrue(all(v["status"]=="PASS" for v in self.checks().values()))
 def test_missing_identity_fails_closed(self):
  self.p["pair"]="wrong";self.assertTrue(all(v["status"]=="UNKNOWN" for v in self.checks().values()))
 def test_missing_each_evidence_section(self):
  for key in ("pool","ownership","history","developer","trades"):
   self.p=fixture();del self.p[key];self.assertFalse(all(v["status"]=="PASS" for v in self.checks().values()),key)
 def test_stale_or_future_sections(self):
  for section in ("pool","ownership","history","trades"):
   for ts in (NOW-301,NOW+1):
    self.p=fixture();self.p[section]["observed_at"]=ts
    self.assertFalse(all(v["status"]=="PASS" for v in self.checks().values()))
 def test_sample_uncertainty(self):
  self.p["ownership"]["unseen_pct"]=10.01;self.assertEqual(self.checks()["top_holder_ownership"]["status"],"UNKNOWN")
 def test_whale_and_developer_exposure(self):
  self.p["ownership"]["owners"][2]["pct"]=5.01;self.assertEqual(self.checks()["top_holder_ownership"]["status"],"REJECT")
  self.p=fixture();self.p["ownership"]["creator_total_pct"]=2.01;self.assertEqual(self.checks()["top_holder_ownership"]["status"],"REJECT")
 def test_missing_wallet_and_unknown_program(self):
  self.p["history"]["wallets"].pop();self.assertNotEqual(self.checks()["wallet_clusters"]["status"],"PASS")
  self.p=fixture();self.p["history"]["wallets"][1]["unknown_programs"]=["unknown"];self.assertEqual(self.checks()["wallet_clusters"]["status"],"UNKNOWN")
 def test_pending_or_incomplete_pagination(self):
  for field,value in (("pending_transactions",1),("pagination_complete",False),("null_timestamps",1),("head_at",NOW-301)):
   self.p=fixture();self.p["history"]["wallets"][0][field]=value;self.assertEqual(self.checks()["developer_history"]["status"],"UNKNOWN")
 def test_shared_sender_is_risk_not_ownership_claim(self):
  self.p["history"]["events"]=[{"relation":"native_transfer","source":"shared","target":"w"+str(i),"block_time":NOW,"signature":str(i)} for i in range(6)]
  c=self.checks()["wallet_clusters"];self.assertEqual(c["status"],"REJECT");self.assertIn("unproven",c["details"]["scope"])
 def test_dev_withdrawal_rejects_without_rug_claim(self):
  self.p["history"]["events"]=[{"relation":"pump_amm_withdraw","source":DEV,"target":"oldpool","block_time":NOW,"signature":"withdraw"}]
  self.assertEqual(self.checks()["developer_history"]["status"],"REJECT")
 def test_prior_report_missing_or_flagged(self):
  self.p["developer"]["associated_mints"].append("oldmint");self.assertEqual(self.checks()["developer_history"]["status"],"UNKNOWN")
  self.p["developer"]["prior_reports"]=[{"mint":"oldmint","retrieved":True,"observed_at":NOW,"rugged":True}]
  self.assertEqual(self.checks()["developer_history"]["status"],"UNKNOWN")
 def test_young_developer(self):
  self.p["history"]["wallets"][0]["activity_age_lower_bound"]=100;self.assertEqual(self.checks()["wallet_age"]["status"],"REJECT")
 def test_no_sales_or_paused_sales(self):
  self.p["trades"]["sales"][0]["quote_received"]=0;self.assertEqual(self.checks()["trading_mechanics"]["status"],"UNKNOWN")
  self.p=fixture();self.p["pool"]["sell_enabled"]=False;self.assertEqual(self.checks()["trading_mechanics"]["status"],"UNKNOWN")
 def test_creator_conflict_is_explicit_and_not_promoted(self):
  self.p["pool"]["state"]["coin_creator"]="different"
  self.p["developer"]["attribution_verified"]=False
  checks=self.checks()
  self.assertEqual(checks["liquidity_control"]["status"],"UNKNOWN")
  self.assertEqual(checks["liquidity_control"]["reason"],"creator_identity_conflict")
  self.assertEqual(checks["developer_history"]["reason"],"creator_identity_conflict")
  self.assertFalse(checks["liquidity_control"]["details"]["identity_changed"])
  self.assertEqual(self.p["creator"],DEV)
  ns=prealert.PrealertTests();ns.setUp()
  self.assertEqual(ns.ns["screen_packet"](self.p,MINT,PAIR,DEV,NOW),checks)
 def test_lp_supply_or_editable_fee_holds(self):
  self.p["pool"]["liquidity"]["outstanding_lp_supply"]=1;self.assertEqual(self.checks()["liquidity_control"]["status"],"UNKNOWN")
  self.p=fixture();self.p["pool"]["state"]["can_edit_creator_fee"]=True;self.assertEqual(self.checks()["liquidity_control"]["status"],"UNKNOWN")
 def test_nan_balance_cannot_pass(self):
  self.p["ownership"]["owners"][1]["pct"]=float("nan");self.assertNotEqual(self.checks()["top_holder_ownership"]["status"],"PASS")
 def test_embedded_policy_exact_match(self):
  ns=prealert.PrealertTests();ns.setUp()
  self.assertEqual(ns.ns["screen_packet"](self.p,MINT,PAIR,DEV,NOW),self.checks())
 def test_actual_collector_to_gate_path(self):
  ns=prealert.PrealertTests();ns.setUp()
  mint_account={"owner":SPL,"data":{"parsed":{"type":"mint","info":{"isInitialized":True,"mintAuthority":None,"freezeAuthority":None,"supply":"100"}}}}
  sec=dict(ns.sec,_mint_account=mint_account,_observed_at=NOW)
  raw=json.dumps({"schema":"wallet-intelligence-v3","mint":MINT,"generated_at":NOW,"screening_packet":self.p}).encode()
  path=MagicMock();path.stat.return_value.st_size=len(raw);path.read_bytes.return_value=raw
  root=MagicMock();root.__truediv__.return_value=path;ns.ns["Path"]=Mock(return_value=root)
  with patch("time.time",return_value=NOW):
   review=ns.ns["collect_prealert_review"](MINT,DEV,{"pairAddress":PAIR},sec)
  self.assertEqual(ns.ns["evaluate_prealert_review"](review,MINT,PAIR,sec,NOW)[0],"PASS")
 def test_runtime_token_control_regression(self):
  ns=prealert.PrealertTests();ns.setUp()
  a={"owner":TOKEN22,"data":{"parsed":{"type":"mint","info":{"isInitialized":True,"mintAuthority":None,"freezeAuthority":None,"supply":"100","extensions":[]}}}}
  self.assertEqual(ns.ns["screen_token_controls"](a)["status"],"PASS")
 def test_current_provider_flag_holds(self):
  self.p["developer"]["current_provider_flag"]=True
  self.assertEqual(self.checks()["developer_history"]["status"],"UNKNOWN")
 def test_developer_current_sale_rejects(self):
  self.p["history"]["events"]=[{"relation":"pump_amm_sell","source":DEV,"target":PAIR,"block_time":NOW,"signature":"sale"}]
  self.assertEqual(self.checks()["developer_history"]["status"],"REJECT")
 def test_verified_no_activity_window_is_not_missing_data(self):
  self.p["history"]["wallets"][1]["indexed_transactions"]=0
  self.assertEqual(self.checks()["wallet_clusters"]["status"],"PASS")
 def test_alert_pass_invokes_existing_sender_once(self):
  import sqlite3
  ns=prealert.PrealertTests();ns.setUp()
  review={"policy":"crypto-prealert-v1","chain":"solana","mint":MINT,"pair":PAIR,"checked_at":NOW,"checks":self.checks()}
  ns.ns["basic_security"]=Mock(return_value=ns.sec);ns.ns["collect_prealert_review"]=Mock(return_value=review);ns.ns["telegram"]=Mock()
  ns.sec.update(creator_pct=1,top10_raw_pct=94)
  db=sqlite3.connect(":memory:");db.execute("CREATE TABLE launches(mint,alert_level,last_alert_ts)");db.execute("INSERT INTO launches VALUES(?,0,0)",(MINT,))
  metrics={k:1 for k in ("mc","liq","pc5","pc1","vol5","vol1","vratio","b1","s1","buy_ratio","band","net")}
  with patch("time.time",return_value=NOW):
   ns.ns["alert"](db,(MINT,(NOW-3600)*1000,DEV,1,1,PAIR),{"pairAddress":PAIR},10,metrics,2)
  ns.ns["telegram"].assert_called_once()
  self.assertEqual(db.execute("SELECT alert_level FROM launches").fetchone()[0],2);db.close()

class ReceiptTests(unittest.TestCase):
 def tx(self):
  accounts=[PAIR,"seller","global",MINT,"So11111111111111111111111111111111111111112","ub","uq","pb","pq", "fee","feeata",TOKEN22,SPL]
  transfer=lambda a,b,n:{"programId":SPL,"parsed":{"type":"transfer","info":{"source":a,"destination":b,"amount":str(n)}}}
  return {"blockTime":NOW,"transaction":{"message":{"instructions":[{"programId":PUMP,"accounts":accounts,"data":b58encode(bytes([51,230,133,164,1,127,131,173])+int(10).to_bytes(8,"little"))}]}},
    "meta":{"err":None,"innerInstructions":[{"index":0,"instructions":[transfer("ub","pb",10),transfer("pq","uq",5)]}]}}
 def test_receipts_require_both_legs(self):
  tx=self.tx();self.assertEqual(len(sale_receipts(tx,"sig",PAIR,MINT)),1)
  tx["meta"]["innerInstructions"][0]["instructions"].pop();self.assertEqual(sale_receipts(tx,"sig",PAIR,MINT),[])
 def test_failed_or_wrong_pool_not_sale(self):
  tx=self.tx();tx["meta"]["err"]="failed";self.assertEqual(sale_receipts(tx,"sig",PAIR,MINT),[])
  self.assertEqual(sale_receipts(self.tx(),"sig","wrong",MINT),[])
class PaginationTests(unittest.TestCase):
 def test_disconnected_head_cannot_reuse_old_completion(self):
  with tempfile.TemporaryDirectory() as d:
   store=Store(pathlib.Path(d)/"db");client=Mock();client.store=store;client.left=1
   client.rpc.return_value=[{"signature":"old","blockTime":1,"err":None}]
   first=index_window(client,"wallet",86400,NOW);self.assertTrue(first["pagination_complete"])
   client.rpc.return_value=[{"signature":"new"+str(i),"blockTime":NOW-i,"err":None} for i in range(1000)]
   second=index_window(client,"wallet",86400,NOW+1);self.assertFalse(second["pagination_complete"]);store.db.close()

class TransactionVersionTests(unittest.TestCase):
 def test_version_one_round_trip_and_receipt(self):
  from full_screening import get_tx
  with tempfile.TemporaryDirectory() as d:
   store=Store(pathlib.Path(d)/"db");client=Mock();client.store=store
   tx=ReceiptTests().tx();tx["version"]=1
   tx["transaction"]["message"]["transactionConfig"]={"computeUnitLimit":200000}
   client.rpc.return_value=tx
   self.assertEqual(len(sale_receipts(get_tx(client,"v1"),"v1",PAIR,MINT)),1)
   self.assertEqual(client.rpc.call_args.args[1][1]["maxSupportedTransactionVersion"],1)
   self.assertEqual(get_tx(client,"v1"),tx);client.rpc.assert_called_once()
   store.db.close()
 def test_unknown_version_and_unparsed_message_not_cached(self):
  from full_screening import save_tx
  with tempfile.TemporaryDirectory() as d:
   store=Store(pathlib.Path(d)/"db")
   for bad in (dict(ReceiptTests().tx(),version=2),{"version":1,"meta":{},"transaction":{"message":{}}}):
    with self.assertRaises(ValueError):save_tx(store,"bad",bad)
   self.assertEqual(store.db.execute("SELECT count(*) FROM tx").fetchone()[0],0)
   store.db.close()


class RoutedReceiptTests(ReceiptTests):
 def routed(self):
  tx=self.tx();pool=tx["transaction"]["message"]["instructions"][0]
  pool["stackHeight"]=2
  transfers=tx["meta"]["innerInstructions"][0]["instructions"]
  for t in transfers:t["stackHeight"]=3
  tx["transaction"]["message"]["instructions"]=[{"programId":"router"}]
  tx["meta"]["innerInstructions"][0]["instructions"]=[pool]+transfers
  return tx
 def test_routed_both_legs(self):
  self.assertEqual(len(sale_receipts(self.routed(),"sig",PAIR,MINT)),1)
 def test_sibling_transfer_cannot_complete_receipt(self):
  tx=self.routed();tx["meta"]["innerInstructions"][0]["instructions"][-1]["stackHeight"]=2
  self.assertEqual(sale_receipts(tx,"sig",PAIR,MINT),[])
 def test_missing_depth_cannot_certify_route(self):
  tx=self.routed();del tx["meta"]["innerInstructions"][0]["instructions"][0]["stackHeight"]
  self.assertEqual(sale_receipts(tx,"sig",PAIR,MINT),[])


class HolderDiscoveryTests(unittest.TestCase):
 def test_omitted_pool_vault_is_verified_separately(self):
  from full_screening import holder_addresses
  self.assertEqual(holder_addresses([{"address":MINT}],PAIR),[MINT,PAIR])
 def test_existing_pool_vault_is_not_double_counted(self):
  from full_screening import holder_addresses
  self.assertEqual(holder_addresses([{"address":MINT},{"address":PAIR}],PAIR),[MINT,PAIR])
 def test_duplicate_or_invalid_discovery_fails_closed(self):
  from full_screening import holder_addresses
  for rows in ([{"address":MINT},{"address":MINT}],[{"address":"bad"}],[]):
   with self.assertRaises(ValueError):holder_addresses(rows,PAIR)


class HistoryFairnessTests(unittest.TestCase):
 def test_bounded_pass_resumes_at_unvisited_address(self):
  from full_screening import history_packet
  with tempfile.TemporaryDirectory() as d:
   store=Store(pathlib.Path(d)/"db");client=Mock();client.store=store;client.left=4;client.deadline=time.monotonic()+140
   selection=[("a",100,"a"),("b",100,"b"),("c",100,"c")]
   seen=[]
   def visit(client,wallet,seconds,now):
    seen.append(wallet);client.left-=2
    return {"wallet":wallet,"window_start":now-seconds,"head_at":now,"pagination_complete":True,"null_timestamps":0}
   with patch("full_screening.index_window",side_effect=visit):
    first,_=history_packet(client,selection,NOW)
    client.left=4
    second,_=history_packet(client,selection,NOW)
   self.assertEqual(seen,["a","b"])
   self.assertEqual([w["wallet"] for w in first["wallets"]],["a"])
   self.assertEqual([w["wallet"] for w in second["wallets"]],["a","b"])
   self.assertEqual(second["wallets"][0]["head_at"],NOW)
   store.db.close()


class EarlyProvenanceTests(unittest.TestCase):
 def test_conflict_survives_provider_failure(self):
  import full_screening as f
  import requests
  with tempfile.TemporaryDirectory() as root:
   client=MagicMock();client.left=8
   client.rpc.side_effect=[{"value":{},"context":{"slot":1}},
       {"value":[{"owner":SPL,"data":{"parsed":{"type":"mint","info":{"supply":"100"}}}},{},{},{}],
        "context":{"slot":2}},RuntimeError("sharing_unavailable"),RuntimeError("rpc_unavailable"),ValueError("missing_holder_accounts")]
   client.session.get.side_effect=requests.Timeout()
   state={"base_mint":MINT,"quote_mint":f.WSOL,"coin_creator":PAIR,
          "lp_mint":MINT,"base_vault":PAIR,"quote_vault":MINT}
   with patch.object(f,"ScreenClient",return_value=client),patch.object(f,"pool_state",return_value=state),patch.object(f,"token_controls",return_value={"status":"PASS"}),patch.object(f,"liquidity_observation",return_value={"status":"OBSERVED","outstanding_lp_supply":0}),patch.object(f,"render"):
    result=f.collect(MINT,MINT,PAIR,root,budget=8)
   self.assertEqual(result["screening_packet"]["creator"],MINT)
   self.assertEqual(result["screening_packet"]["creator_provenance"]["status"],"CONFLICT")
   self.assertIn("creator_identity_conflict",result["issues"])
   self.assertEqual(result["screening"]["checks"]["liquidity_control"]["reason"],"creator_identity_conflict")


class FastRefreshTests(unittest.TestCase):
 def test_background_reject_cannot_be_erased_by_fast_refresh(self):
  import full_screening as f
  for name in ("wallet_clusters","developer_history","top_holder_ownership","wallet_age"):
   with self.subTest(name=name),tempfile.TemporaryDirectory() as root:
    previous={"schema":"wallet-intelligence-v3","generated_at":1,
      "screening_packet":{"mint":MINT,"pair":PAIR,"creator":MINT},
      "screening":{"checks":{name:{"status":"REJECT"}}},"issues":[]}
    path=pathlib.Path(root)/(MINT+".json");path.write_text(json.dumps(previous));before=path.read_bytes()
    with patch.object(f,"ScreenClient") as cls:
     out=f.collect(MINT,MINT,PAIR,root,research=False,time_budget=60)
    cls.return_value.rpc.assert_not_called()
    self.assertEqual(path.read_bytes(),before)
    self.assertEqual(out["generated_at"],1)
    self.assertEqual(out["fast_refresh_deferred"],"background_rejection_requires_research")
 def test_fast_pass_skips_history_and_keeps_original_timestamp(self):
  import full_screening as f
  with tempfile.TemporaryDirectory() as root:
   old_history={"wallets":[],"events":[],"observed_at":1,"evidence_refs":["old"]}
   previous={"schema":"wallet-intelligence-v3","screening_packet":{"mint":MINT,"pair":PAIR,"creator":MINT,"history":old_history}}
   (pathlib.Path(root)/(MINT+".json")).write_text(json.dumps(previous))
   def account(kind,info):return {"owner":SPL,"data":{"parsed":{"type":kind,"info":info}}}
   mint_account=account("mint",{"supply":"100"})
   vault=account("account",{"mint":MINT,"state":"initialized","owner":PAIR,"tokenAmount":{"amount":"80"}})
   client=MagicMock();client.left=40
   client.rpc.side_effect=[{"value":{},"context":{"slot":1}},
     {"value":[mint_account,{},{},{}],"context":{"slot":2}},
     {"value":[{"address":PAIR}]},
     {"value":[vault],"context":{"slot":3}},{"value":[]},[]]
   client.session.get.return_value.json.return_value={"mint":MINT,"creator":MINT,"topHolders":[{"address":PAIR}]}
   state={"base_mint":MINT,"quote_mint":f.WSOL,"coin_creator":MINT,
          "lp_mint":MINT,"base_vault":PAIR,"quote_vault":MINT}
   with patch.object(f,"ScreenClient",return_value=client),patch.object(f,"pool_state",return_value=state),patch.object(f,"token_controls",return_value={"status":"PASS"}),patch.object(f,"liquidity_observation",return_value={"status":"OBSERVED","outstanding_lp_supply":0}),patch.object(f,"render"),patch.object(f,"history_packet") as history:
    out=f.collect(MINT,MINT,PAIR,root,research=False,time_budget=60)
   history.assert_not_called()
   self.assertEqual(out["collection_lane"],"fast")
   self.assertEqual(out["screening_packet"]["history"],old_history)
   self.assertEqual(out["screening_packet"]["ownership"]["unseen_pct"],20)
   self.assertEqual(out["screening"]["checks"]["wallet_clusters"]["status"],"UNKNOWN")
   self.assertTrue((pathlib.Path(root)/(MINT+".json")).exists())

class DurableHistoryTests(unittest.TestCase):
 def test_partial_error_keeps_success_and_missing_owner_unknown(self):
  with tempfile.TemporaryDirectory() as d:
   store=Store(pathlib.Path(d)/"db");client=Mock();client.store=store;client.left=20;client.deadline=time.monotonic()+140
   def visit(client,wallet,seconds,now):
    client.left-=1
    if wallet=="bad":raise RuntimeError("rpc_error_code_-32019_method_getSignaturesForAddress")
    return {"wallet":wallet,"window_start":now-seconds,"head_at":now,"pagination_complete":True,"null_timestamps":0}
   with patch("full_screening.index_window",side_effect=visit):
    body,issues=history_packet(client,[("good",100,"owner"),("bad",100,"owner")],NOW)
   self.assertTrue(issues)
   self.assertEqual(body["wallets"][0]["addresses_reviewed"],1)
   self.assertFalse(body["wallets"][0]["pagination_complete"])
   store.db.close()
 def test_cached_head_is_not_redated_and_longer_window_not_certified(self):
  with tempfile.TemporaryDirectory() as d:
   store=Store(pathlib.Path(d)/"db");client=Mock();client.store=store;client.left=20;client.deadline=time.monotonic()+140
   item={"wallet":"dev","window_start":NOW-100,"head_at":NOW,"pagination_complete":True,"null_timestamps":0}
   with patch("full_screening.index_window",return_value=item):
    history_packet(client,[("dev",100,"dev")],NOW)
   client.left=0
   body,_=history_packet(client,[("dev",1000,"dev")],NOW+400)
   self.assertEqual(body["wallets"][0]["head_at"],NOW)
   self.assertFalse(body["wallets"][0]["pagination_complete"])
   store.db.close()


class CoverageCollectionTests(unittest.TestCase):
 def collect_case(self,native_error=False,provider_error=False):
  import full_screening as f
  import requests
  def account(kind,info):return {"owner":SPL,"data":{"parsed":{"type":kind,"info":info}}}
  def token(owner,amount):return account("account",{"mint":MINT,"state":"initialized","owner":owner,"tokenAmount":{"amount":str(amount)}})
  extra=b58encode(bytes([3])*32);holder=b58encode(bytes([4])*32)
  state={"base_mint":MINT,"quote_mint":f.WSOL,"coin_creator":MINT,"lp_mint":MINT,"base_vault":PAIR,"quote_vault":MINT}
  client=MagicMock();client.left=40
  def rpc(method,params):
   if method=="getAccountInfo":return {"value":{},"context":{"slot":1}}
   if method=="getTokenLargestAccounts":
    if native_error:raise RuntimeError("rpc_error_code_-32019_method_getTokenLargestAccounts")
    return {"value":[{"address":holder},{"address":PAIR}]}
   if method=="getMultipleAccounts":
    if len(params[0])==4:return {"value":[account("mint",{"supply":"100"}),{},{},{}],"context":{"slot":2}}
    return {"value":[token(PAIR,80) if a==PAIR else token(holder,10) for a in params[0]],"context":{"slot":3}}
   if method=="getTokenAccountsByOwner":return {"value":[{"pubkey":extra,"account":token(MINT,1)}]}
   if method=="getSignaturesForAddress":raise requests.Timeout()
   raise AssertionError(method)
  client.rpc.side_effect=rpc
  client.session.get.return_value.json.return_value={"mint":MINT,"creator":MINT,"topHolders":[{"address":PAIR}]}
  if provider_error:client.session.get.side_effect=requests.Timeout()
  with tempfile.TemporaryDirectory() as root,patch.object(f,"ScreenClient",return_value=client),patch.object(f,"pool_state",return_value=state),patch.object(f,"token_controls",return_value={"status":"PASS"}),patch.object(f,"liquidity_observation",return_value={"status":"OBSERVED","outstanding_lp_supply":0}),patch.object(f,"render"):
   return f.collect(MINT,MINT,PAIR,root,research=False)
 def test_native_union_and_extra_creator_are_counted_once(self):
  out=self.collect_case();ownership=out["screening_packet"]["ownership"]
  self.assertEqual(ownership["verified_total_raw"],"91")
  self.assertEqual(ownership["verified_account_count"],3)
  self.assertEqual(ownership["unseen_pct"],9)
  self.assertEqual(ownership["pool_vault_raw"],"80")
 def test_native_failure_falls_back_without_fabricating_coverage(self):
  out=self.collect_case(native_error=True)
  self.assertEqual(out["screening_packet"]["ownership"]["unseen_pct"],19)
  self.assertEqual(out["screening"]["checks"]["top_holder_ownership"]["status"],"UNKNOWN")
 def test_provider_failure_still_collects_native_accounts(self):
  out=self.collect_case(provider_error=True)
  self.assertEqual(out["screening_packet"]["ownership"]["verified_total_raw"],"91")
  self.assertIn("provider_holder_discovery_unavailable",out["issues"])
 def test_sale_timeout_retains_collected_ownership(self):
  out=self.collect_case()
  self.assertIn("sale_probe_incomplete:Timeout",out["issues"])
  self.assertEqual(out["screening"]["checks"]["trading_mechanics"]["status"],"UNKNOWN")

class HistoryRetryTests(unittest.TestCase):
 def test_unavailable_transaction_remains_pending_during_cooldown(self):
  import full_screening as f
  with tempfile.TemporaryDirectory() as d:
   store=Store(pathlib.Path(d)/"db");client=Mock();client.store=store;client.left=5;client.deadline=time.monotonic()+140
   store.db.execute("INSERT INTO signatures VALUES(?,?,?,?)",("dev","missing",NOW,0));store.db.commit()
   item={"wallet":"dev","window_start":NOW-100,"head_at":NOW,"pagination_complete":True,"null_timestamps":0}
   with patch.object(f,"index_window",return_value=item),patch.object(f,"get_tx",return_value=None) as tx:
    first,_=history_packet(client,[("dev",100,"dev")],NOW)
    second,_=history_packet(client,[("dev",100,"dev")],NOW+1)
   self.assertEqual(tx.call_count,1)
   self.assertEqual(second["wallets"][0]["pending_transactions"],1)
   store.db.close()


class CensusTests(unittest.TestCase):
 def run_census(self,mutate=None):
  import full_screening as f
  store=Store(":memory:");client=Mock();client.store=store;client.last_evidence_ref="rpc:fixture"
  state={"base_vault":PAIR}
  def row(address,owner,amount):
   return {"pubkey":address,"account":{"owner":TOKEN22,"executable":False,"data":{"parsed":{"type":"account","info":{"mint":MINT,"owner":owner,"state":"initialized","tokenAmount":{"amount":str(amount)}}}}}}
  response={"context":{"slot":10},"value":[row(PAIR,PAIR,80),row(MINT,MINT,20)]}
  if mutate:mutate(response)
  client.rpc.return_value=response
  return f,store,client,state
 def test_complete_census_and_cache_preserve_original_time(self):
  f,store,client,state=self.run_census()
  with patch("full_screening.time.time",return_value=NOW):
   result=f.census_ownership(client,MINT,MINT,PAIR,state,TOKEN22,100,9,NOW)
  own,owners,accounts=result
  self.assertEqual(own["unseen_pct"],0)
  self.assertEqual(own["creator_total_pct"],20)
  self.assertEqual(own["verified_account_count"],2)
  self.assertNotIn({"dataSize":165},client.rpc.call_args.args[1][1]["filters"])
  again=f.census_ownership(client,MINT,MINT,PAIR,state,TOKEN22,100,11,NOW+100)
  self.assertEqual(again[0]["observed_at"],NOW);client.rpc.assert_called_once()
  store.db.close()
 def test_partial_duplicate_wrong_mint_and_stale_context_fail_closed(self):
  mutators=[lambda r:r["value"].pop(),
    lambda r:r["value"].append(r["value"][0]),
    lambda r:r["value"][1]["account"]["data"]["parsed"]["info"].update(mint=PAIR),
    lambda r:r["context"].update(slot=8)]
  for mutate in mutators:
   f,store,client,state=self.run_census(mutate)
   with self.assertRaises(ValueError):f.census_ownership(client,MINT,MINT,PAIR,state,TOKEN22,100,9,NOW)
   self.assertEqual(store.db.execute("SELECT count(*) FROM holder_census").fetchone()[0],0)
   store.db.close()
 def test_expired_cache_is_refetched(self):
  f,store,client,state=self.run_census()
  with patch("full_screening.time.time",return_value=NOW):
   f.census_ownership(client,MINT,MINT,PAIR,state,TOKEN22,100,9,NOW)
  with patch("full_screening.time.time",return_value=NOW+241):
   result=f.census_ownership(client,MINT,MINT,PAIR,state,TOKEN22,100,9,NOW+241)
  self.assertEqual(client.rpc.call_count,2);self.assertEqual(result[0]["observed_at"],NOW+241)
  store.db.close()

class DeveloperPriorityTests(unittest.TestCase):
 def test_developer_token_account_precedes_holder_addresses(self):
  import full_screening as f
  store=Store(":memory:");client=Mock();client.store=store;client.left=7;client.deadline=time.monotonic()+140
  seen=[]
  def visit(client,wallet,seconds,now):
   seen.append(wallet);client.left-=2
   return {"wallet":wallet,"window_start":now-seconds,"head_at":now,"pagination_complete":True,"null_timestamps":0}
  selection=[("dev",100,"dev"),("holder",100,"holder"),("dev-token",100,"dev")]
  with patch.object(f,"index_window",side_effect=visit):
   body,_=history_packet(client,selection,NOW,priority_owner="dev")
  self.assertEqual(seen,["dev","dev-token"])
  self.assertTrue(body["wallets"][0]["pagination_complete"])
  self.assertEqual(body["wallets"][0]["addresses_reviewed"],2)
  store.db.close()
 def test_null_timestamp_recovery_does_not_accumulate_duplicates(self):
  store=Store(":memory:");client=Mock();client.store=store;client.left=1
  client.rpc.return_value=[{"signature":"sig","blockTime":None,"err":None}]
  self.assertEqual(index_window(client,"wallet",100,NOW)["null_timestamps"],1)
  self.assertEqual(index_window(client,"wallet",100,NOW+1)["null_timestamps"],1)
  client.rpc.return_value=[{"signature":"sig","blockTime":NOW,"err":None}]
  self.assertEqual(index_window(client,"wallet",100,NOW+2)["null_timestamps"],0)
  store.db.close()


class LaunchV2Tests(unittest.TestCase):
 def instruction(self,migrate=False):
  from protocol_screening import PUMP_LAUNCH_PROGRAM
  accounts=[MINT]*27
  if migrate:
   disc=[187,203,18,31,206,237,254,41];args=b""
   accounts[8]="11111111111111111111111111111111";accounts[9]=PUMP
   accounts[19]=TOKEN22;accounts[20]=SPL;accounts[21]=TOKEN22
   accounts[22]="ATokenGPvbdGVxr1b2hvZbsiqW5xWH25efTNsLJA8knL"
  else:
   disc=[184,23,238,97,103,197,211,61];args=(10).to_bytes(8,"little")+(20).to_bytes(8,"little")
   accounts[3]=TOKEN22;accounts[4]=SPL;accounts[5]="ATokenGPvbdGVxr1b2hvZbsiqW5xWH25efTNsLJA8knL"
   accounts[24]="11111111111111111111111111111111"
  accounts[26]=PUMP_LAUNCH_PROGRAM
  return {"programId":PUMP_LAUNCH_PROGRAM,"accounts":accounts,"data":b58encode(bytes(disc)+args)}
 def test_reviewed_buy_and_migration_produce_events(self):
  from protocol_screening import launch_v2_instruction,protocol_events
  from full_screening import supported_instruction
  for migrate in (False,True):
   ins=self.instruction(migrate)
   self.assertTrue(supported_instruction(ins))
   e=launch_v2_instruction(ins)
   self.assertEqual(e["relation"],"pump_launch_migrate_v2" if migrate else "pump_launch_buy_v2")
   tx={"meta":{"err":None},"transaction":{"message":{"instructions":[ins]}}}
   self.assertEqual(len(protocol_events(tx,"sig")),1)
   tx["meta"]["err"]="failed";self.assertEqual(protocol_events(tx,"sig"),[])
 def test_wrong_layout_and_unknown_instruction_remain_unsupported(self):
  from full_screening import supported_instruction
  for mutate in (lambda x:x["accounts"].pop(),lambda x:x["accounts"].__setitem__(26,MINT),
    lambda x:x.update(data=b58encode(bytes([9])*24)),lambda x:x.update(data=b58encode(bytes([184,23,238,97,103,197,211,61])))):
   ins=self.instruction();mutate(ins);self.assertFalse(supported_instruction(ins))


class DeveloperAssociationTests(unittest.TestCase):
 def test_authenticated_lp_is_recorded_as_infrastructure_only(self):
  from full_screening import developer_associations
  pool={"authenticated":True,"state":{"lp_mint":"lp"},"liquidity":{"status":"OBSERVED"},"evidence_refs":["pool:verified"]}
  events=[{"relation":"mint_authority_at_initialization","source":PAIR,"target":"lp","transaction_signers":[DEV],"signature":"lp-create"},
   {"relation":"mint_authority_at_initialization","source":DEV,"target":"other-coin","signature":"other-create"}]
  associated,infrastructure=developer_associations(events,DEV,PAIR,pool)
  self.assertEqual(associated,{"other-coin"});self.assertEqual(infrastructure[0]["mint"],"lp")
  for changed in (dict(pool,authenticated=False),dict(pool,liquidity={"status":"UNKNOWN"})):
   self.assertIn("lp",developer_associations(events,DEV,PAIR,changed)[0])
  events[0]["source"]="unverified-authority"
  self.assertIn("lp",developer_associations(events,DEV,PAIR,pool)[0])


class CreatorSharingTests(unittest.TestCase):
 def fixture(self):
  import base64,hashlib
  from protocol_screening import b58decode,b58encode
  program="pfeeUxB6jkeY1Hxd7CsFCAjcbHA9rWtchMGdZ6VojVZ"
  raw=bytearray(1024);raw[:8]=bytes([216,74,9,0,56,140,93,75]);raw[8:11]=bytes([255,2,1])
  raw[11:43]=b58decode(MINT);raw[43:75]=b58decode(MINT);raw[75]=1
  raw[76:80]=(1).to_bytes(4,"little");raw[80:112]=b58decode(PAIR);raw[112:114]=(10000).to_bytes(2,"little")
  address=b58encode(hashlib.sha256(b"sharing-config"+b58decode(MINT)+bytes([255])+b58decode(program)+b"ProgramDerivedAddress").digest())
  p=fixture();p["creator"]=MINT;p["pool"]["state"]["coin_creator"]=address;p["pool"]["context_slot"]=10
  p["pool"]["creator_sharing"]={"address":address,"context_slot":11,"observed_at":NOW,"evidence_refs":["rpc:sharing"],
   "account":{"owner":program,"executable":False,"data":[base64.b64encode(raw).decode(),"base64"]}}
  return p,raw
 def test_authenticated_fee_role_preserves_original_creator_and_rejects(self):
  from screening_policy import screen_creator_link
  p,raw=self.fixture()
  self.assertTrue(screen_creator_link(p["pool"],MINT,MINT,NOW))
  checks=screen_packet(p,MINT,PAIR,MINT,NOW)
  self.assertEqual(checks["liquidity_control"]["status"],"PASS")
  p["ownership"]["creator_total_pct"]=3
  self.assertEqual(screen_packet(p,MINT,PAIR,MINT,NOW)["top_holder_ownership"]["status"],"REJECT")
  ns=prealert.PrealertTests();ns.setUp()
  self.assertEqual(ns.ns["screen_packet"](p,MINT,PAIR,MINT,NOW),screen_packet(p,MINT,PAIR,MINT,NOW))
  self.assertEqual(p["creator"],MINT)
 def test_tampered_owner_mint_admin_layout_shares_and_address_fail_closed(self):
  import base64
  from screening_policy import screen_creator_link
  for index in (0,9,10,11,43,112):
   p,raw=self.fixture();raw[index]^=1
   p["pool"]["creator_sharing"]["account"]["data"][0]=base64.b64encode(raw).decode()
   self.assertFalse(screen_creator_link(p["pool"],MINT,MINT,NOW))
  for field,value in (("observed_at",NOW-301),("context_slot",9),("address",MINT),("evidence_refs",[])):
   p,raw=self.fixture();p["pool"]["creator_sharing"][field]=value
   self.assertEqual(screen_packet(p,MINT,PAIR,MINT,NOW)["liquidity_control"]["reason"],"creator_identity_conflict")
  p,raw=self.fixture();p["pool"]["creator_sharing"]["account"]["owner"]=SPL
  self.assertFalse(screen_creator_link(p["pool"],MINT,MINT,NOW))
 def test_self_asserted_resolution_does_not_clear_conflict(self):
  p=fixture();p["pool"]["state"]["coin_creator"]="other"
  p["creator_provenance"]={"status":"AUTHENTICATED_FEE_SHARING"}
  self.assertEqual(screen_packet(p,MINT,PAIR,DEV,NOW)["liquidity_control"]["reason"],"creator_identity_conflict")

class StableHistoryCursorTests(unittest.TestCase):
 def test_holder_changes_do_not_reset_rotation(self):
  store=Store(":memory:");client=Mock();client.store=store;client.left=4;client.deadline=time.monotonic()+140
  seen=[]
  def visit(client,wallet,seconds,now):
   client.left-=2;seen.append(wallet)
   return {"wallet":wallet,"window_start":now-seconds,"head_at":now,"pagination_complete":True,"null_timestamps":0}
  with patch("full_screening.index_window",side_effect=visit):
   history_packet(client,[("b",100,"b"),("c",100,"c")],NOW,scope_key="mint:stable")
   client.left=4
   second,_=history_packet(client,[("a",100,"a"),("b",100,"b"),("c",100,"c")],NOW+1,scope_key="mint:stable")
  self.assertEqual(seen,["b","c"])
  self.assertEqual(second["coverage_summary"]["owners_missing"],1)
  store.db.close()


class PartialEvidenceRejectionTests(unittest.TestCase):
 def test_missing_holder_cannot_mask_known_developer_age_failure(self):
  p=fixture();p["history"]["wallets"]=p["history"]["wallets"][:1]
  p["history"]["wallets"][0]["activity_age_lower_bound"]=100
  checks=screen_packet(p,MINT,PAIR,DEV,NOW)
  self.assertEqual(checks["wallet_age"]["status"],"REJECT")
  self.assertEqual(checks["wallet_clusters"]["status"],"UNKNOWN")
 def test_missing_holder_cannot_mask_observed_excess_linked_exposure(self):
  p=fixture();p["history"]["wallets"].pop()
  p["history"]["events"]=[{"relation":"native_transfer","source":"shared","target":"w"+str(i),"block_time":NOW,"signature":str(i)} for i in range(6)]
  checks=screen_packet(p,MINT,PAIR,DEV,NOW)
  self.assertEqual(checks["wallet_clusters"]["status"],"REJECT")
  self.assertEqual(checks["wallet_clusters"]["details"]["owners_missing"],1)
 def test_partial_good_evidence_never_certifies_age_or_clusters(self):
  p=fixture();p["history"]["wallets"].pop()
  checks=screen_packet(p,MINT,PAIR,DEV,NOW)
  self.assertEqual(checks["wallet_clusters"]["status"],"UNKNOWN")
  self.assertEqual(checks["wallet_age"]["status"],"UNKNOWN")

if __name__=="__main__":unittest.main()

class IncompleteAgeEvidenceTests(unittest.TestCase):
 def test_short_partial_history_is_unknown_not_young(self):
  p=fixture()
  p["history"]["wallets"][0]["activity_age_lower_bound"]=100
  p["history"]["wallets"][0]["pagination_complete"]=False
  checks=screen_packet(p,MINT,PAIR,DEV,NOW)
  self.assertEqual(checks["wallet_age"]["status"],"UNKNOWN")
  ns=prealert.PrealertTests();ns.setUp()
  self.assertEqual(ns.ns["screen_packet"](p,MINT,PAIR,DEV,NOW),checks)

class SharedHistoryIndexTests(unittest.TestCase):
 def test_transaction_body_is_reused_across_address_lookups(self):
  from full_screening import get_tx
  store=Store(":memory:");client=Mock();client.store=store
  body={"meta":{"err":None},"transaction":{"message":{"instructions":[]}}}
  store.db.execute("INSERT INTO tx VALUES(?,?)",("shared",json.dumps(body)));store.db.commit()
  self.assertEqual(get_tx(client,"shared"),body)
  self.assertEqual(get_tx(client,"shared"),body);client.rpc.assert_not_called();store.db.close()
 def test_transaction_budget_rotates_past_busy_first_wallet(self):
  store=Store(":memory:");client=Mock();client.store=store;client.left=1;client.deadline=time.monotonic()+140
  store.db.execute("CREATE TABLE screen_windows(address TEXT PRIMARY KEY,body TEXT)")
  for a in ("a","b"):
   store.db.execute("INSERT INTO screen_windows VALUES(?,?)",(a,json.dumps({"wallet":a,"window_start":NOW-100,"head_at":NOW,"pagination_complete":True,"null_timestamps":0})))
  for a,sig in (("a","a1"),("a","a2"),("b","b1")):
   store.db.execute("INSERT INTO signatures VALUES(?,?,?,?)",(a,sig,NOW,0))
  store.db.commit();seen=[]
  def fetch(c,sig):c.left-=1;seen.append(sig);return None
  with patch("full_screening.get_tx",side_effect=fetch):
   history_packet(client,[("a",100,"a"),("b",100,"b")],NOW,scope_key="mint:rotate")
   client.left=1
   result,_=history_packet(client,[("a",100,"a"),("b",100,"b")],NOW+1,scope_key="mint:rotate")
  self.assertTrue(seen[0].startswith("a"));self.assertEqual(seen[1],"b1")
  self.assertEqual(result["index_metrics"]["transaction_attempts"],1);store.db.close()
