import unittest,tempfile
from pathlib import Path
from wallet_intelligence import decode,Store,render,SYSTEM
A="5F1Se9J2L16YcK1fpk18NhSvnPjtyjQSaczKGLDoV1Uy"
B="BSDuf5ka7xz5rCaNQJBx1ThNWgKa4mS1hFhAZoihzw9J"
def fixture():
 return {"slot":1,"blockTime":10,"meta":{"err":None},"transaction":{"message":{"accountKeys":[],"instructions":[{"programId":SYSTEM,"parsed":{"type":"transfer","info":{"source":A,"destination":B,"lamports":1}}}]}}}
class Tests(unittest.TestCase):
 def test_transfer(self):
  self.assertEqual(decode(fixture(),"sig")[0]["relation"],"native_transfer")
 def test_failed_tx_excluded(self):
  tx=fixture();tx["meta"]["err"]={};self.assertEqual(decode(tx,"sig"),[])
 def test_fake_program_excluded(self):
  tx=fixture();tx["transaction"]["message"]["instructions"][0]["programId"]=A
  self.assertEqual(decode(tx,"sig"),[])
 def test_inner_instruction(self):
  tx=fixture();ins=tx["transaction"]["message"]["instructions"].pop()
  tx["meta"]["innerInstructions"]=[{"index":0,"instructions":[ins]}]
  self.assertEqual(decode(tx,"sig")[0]["instruction"],"0.0")
 def test_evidence_dedup(self):
  with tempfile.TemporaryDirectory() as d:
   s=Store(Path(d)/"db");self.assertEqual(s.evidence("rpc",{"a":1}),s.evidence("rpc",{"a":1}))
   self.assertEqual(s.db.execute("SELECT count(*) FROM evidence").fetchone()[0],1);s.db.close()
 def test_html_escapes_external_content(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/"map.html";render({"events":[],"wallet_histories":[],"developer":None,"bad":"<script>alert(1)</script>"},p)
   self.assertNotIn("<script>",p.read_text())

class RpcBoundTests(unittest.TestCase):
 def test_rate_limit_is_method_scoped_and_survives_client_restart(self):
  import requests
  from unittest.mock import Mock,patch
  from wallet_intelligence import Client
  store=Store(":memory:");client=Client(store,5);client.session=Mock()
  response=Mock();response.status_code=429;response.headers={"Retry-After":"180"}
  response.raise_for_status.side_effect=requests.HTTPError(response=response)
  client.session.post.return_value=response
  with patch("wallet_intelligence.time.sleep"),patch("wallet_intelligence.time.time",return_value=1000):
   with self.assertRaises(requests.HTTPError):client.rpc("getTokenLargestAccounts",[])
   other=Client(store,5);other.session=Mock()
   with self.assertRaisesRegex(RuntimeError,"rpc_method_cooldown"):other.rpc("getTokenLargestAccounts",[])
   other.session.post.assert_not_called()
   ok=Mock();ok.status_code=200;ok.json.return_value={"result":1};other.session.post.return_value=ok
   self.assertEqual(other.rpc("getSlot",[]),1)
  store.db.close()
 def test_oversized_census_response_is_closed_and_not_saved(self):
  from unittest.mock import Mock,patch
  from wallet_intelligence import Client
  store=Store(":memory:");client=Client(store,5);client.session=Mock()
  response=Mock();response.status_code=200;response.iter_content.return_value=[b"x"*(8*1024*1024+1)]
  client.session.post.return_value=response
  with patch("wallet_intelligence.time.sleep"):
   with self.assertRaisesRegex(RuntimeError,"rpc_response_size_limit"):client.rpc("getProgramAccounts",[])
  response.close.assert_called_once()
  self.assertEqual(store.db.execute("SELECT count(*) FROM evidence").fetchone()[0],0)
  store.db.close()


class HistoryEndpointTests(unittest.TestCase):
 def test_chain_verified_before_history_and_no_paid_indexed_route(self):
  from unittest.mock import Mock,patch
  from wallet_intelligence import Client,RPC,HISTORY_RPC,MAINNET_GENESIS
  store=Store(":memory:");client=Client(store,5);client.session=Mock()
  def response(value):
   r=Mock();r.status_code=200;r.json.return_value={"result":value};return r
  client.session.post.side_effect=[response(MAINNET_GENESIS),response([]),response({"value":[]})]
  with patch("wallet_intelligence.time.sleep"):
   self.assertEqual(client.rpc("getSignaturesForAddress",["wallet"]),[])
   client.rpc("getTokenLargestAccounts",["mint"])
  calls=client.session.post.call_args_list
  self.assertEqual([c.args[0] for c in calls],[HISTORY_RPC,HISTORY_RPC,RPC])
  self.assertEqual(calls[0].kwargs["json"]["method"],"getGenesisHash")
  self.assertEqual(client.left,2)
  store.db.close()
 def test_wrong_chain_fails_before_history_request(self):
  from unittest.mock import Mock,patch
  from wallet_intelligence import Client
  store=Store(":memory:");client=Client(store,5);client.session=Mock()
  r=Mock();r.status_code=200;r.json.return_value={"result":"wrong-chain"};client.session.post.return_value=r
  with patch("wallet_intelligence.time.sleep"):
   with self.assertRaisesRegex(RuntimeError,"history_rpc_wrong_chain"):client.rpc("getTransaction",["sig"])
  self.assertEqual(client.session.post.call_count,1)
  store.db.close()

if __name__=="__main__":unittest.main()
