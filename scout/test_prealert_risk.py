import ast, copy, hashlib, json, logging, pathlib, re, sqlite3, time, unittest
from unittest.mock import Mock
P=pathlib.Path(__file__).with_name("early_scout.py")
class PrealertTests(unittest.TestCase):
 def setUp(self):
  tree=ast.parse(P.read_text())
  body=[n for n in tree.body if isinstance(n,ast.FunctionDef) or
        (isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id.startswith("PREALERT_") for t in n.targets))]
  self.ns=dict(json=json,logging=logging,time=time,hashlib=hashlib,re=re,Path=pathlib.Path)
  exec(compile(ast.Module(body=body,type_ignores=[]),"scout_functions","exec"),self.ns)
  self.sec={"mint_authority":"REVOKED","freeze_authority":"REVOKED"}
  self.review={"policy":"crypto-prealert-v1","chain":"solana","mint":"mint","pair":"pair","checked_at":1000,
   "checks":{n:{"status":"PASS","evidence_refs":["fixture:raw"],"observed_at":1000}
             for n in self.ns["PREALERT_CHECKS"]}}
 def decide(self,r=None):
  return self.ns["evaluate_prealert_review"](self.review if r is None else r,"mint","pair",self.sec,1000)[0]
 def test_all_current_required_reviews(self): self.assertEqual(self.decide(),"PASS")
 def test_missing_each_check(self):
  for name in self.ns["PREALERT_REQUIRED"]:
   r=copy.deepcopy(self.review);del r["checks"][name];self.assertEqual(self.decide(r),"HOLD")
 def test_stale_future_identity(self):
  for field,value in [("checked_at",699),("checked_at",1001),("mint","wrong"),("chain","eth"),("pair","wrong")]:
   r=copy.deepcopy(self.review);r[field]=value;self.assertEqual(self.decide(r),"HOLD")
 def test_missing_or_stale_underlying_evidence(self):
  for field,value in [("evidence_refs",[]),("observed_at",699),("status","UNKNOWN")]:
   r=copy.deepcopy(self.review);r["checks"]["trading_mechanics"][field]=value;self.assertEqual(self.decide(r),"HOLD")
 def test_confirmed_risk_rejects(self):
  self.review["checks"]["wallet_clusters"]["status"]="REJECT";self.assertEqual(self.decide(),"REJECT")
 def test_active_and_unknown_authorities(self):
  self.sec["mint_authority"]="ACTIVE";self.assertEqual(self.decide(),"REJECT")
  self.sec["mint_authority"]="UNKNOWN";self.assertEqual(self.decide(),"HOLD")
 def test_unconnected_collector_cannot_pass(self):
  r=self.ns["collect_prealert_review"]("mint","dev",{"pairAddress":"pair"},self.sec)
  self.assertEqual(self.decide(r),"HOLD")
 def test_alert_holds_without_send_or_alert_state_change(self):
  c=sqlite3.connect(":memory:")
  self.ns["basic_security"]=Mock(return_value=self.sec)
  self.ns["telegram"]=Mock(side_effect=AssertionError("must not send"))
  self.ns["alert"](c,("mint",0,"dev",0,0,None),{"pairAddress":"pair"},10,{},2)
  self.ns["telegram"].assert_not_called()
  self.assertEqual(c.execute("select verdict from prealert_reviews").fetchone()[0],"HOLD")
  c.close()
 def test_collector_error_holds(self):
  c=sqlite3.connect(":memory:");self.ns["basic_security"]=Mock(return_value=self.sec)
  self.ns["collect_prealert_review"]=Mock(side_effect=RuntimeError("offline"))
  self.ns["telegram"]=Mock()
  self.ns["alert"](c,("mint",0,"dev",0,0,None),{"pairAddress":"pair"},10,{},2)
  self.ns["telegram"].assert_not_called()
  self.assertEqual(c.execute("select verdict from prealert_reviews").fetchone()[0],"HOLD")
  c.close()
 def test_partial_report_cannot_self_certify(self):
  from unittest.mock import MagicMock
  mint="5F1Se9J2L16YcK1fpk18NhSvnPjtyjQSaczKGLDoV1Uy"
  p=MagicMock();p.stat.return_value.st_size=100
  p.read_bytes.return_value=json.dumps({"schema":"wallet-intelligence-v2","mint":mint,"generated_at":int(time.time()),"admission":{"status":"PASS"}}).encode()
  root=MagicMock();root.__truediv__.return_value=p;self.ns["Path"]=Mock(return_value=root)
  r=self.ns["collect_prealert_review"](mint,"dev",{"pairAddress":"pair"},self.sec)
  self.assertEqual(r["wallet_report_status"],"partial_research_loaded")
  self.assertTrue(all(c["status"]!="PASS" for c in r["checks"].values()))
 def test_missing_authority_fields_stay_unknown(self):
  self.ns["rpc"]=Mock(return_value={"value":{"data":{"parsed":{"info":{"supply":"100"}}}}})
  self.ns["n"]=lambda x:float(x or 0)
  sec=self.ns["basic_security"]("mint",None)
  self.assertEqual(sec["mint_authority"],"UNKNOWN");self.assertEqual(sec["freeze_authority"],"UNKNOWN")

 def test_unknown_background_nonblocking_and_visible(self):
  for name in self.ns["PREALERT_CHECKS"]:
   if name not in self.ns["PREALERT_REQUIRED"]:self.review["checks"][name]={"status":"UNKNOWN"}
  self.assertEqual(self.decide(),"PASS")
  summary=self.ns["screening_summary"](self.review,1000)
  self.assertEqual(summary.count(": UNKNOWN"),4)
 def test_every_explicit_reject_blocks_even_without_freshness(self):
  for name in self.ns["PREALERT_CHECKS"]:
   r=copy.deepcopy(self.review);r["checks"][name]={"status":"REJECT"}
   self.assertEqual(self.decide(r),"REJECT")
 def test_stale_background_pass_displayed_unknown(self):
  self.review["checks"]["wallet_age"]["observed_at"]=1
  self.assertEqual(self.decide(),"PASS")
  self.assertIn("wallet age: UNKNOWN",self.ns["screening_summary"](self.review,1000))
if __name__=="__main__":unittest.main()

