import base64,struct,unittest
from protocol_screening import *
A="5F1Se9J2L16YcK1fpk18NhSvnPjtyjQSaczKGLDoV1Uy"
B="BSDuf5ka7xz5rCaNQJBx1ThNWgKa4mS1hFhAZoihzw9J"
def mint():
 return {"owner":SPL,"executable":False,"data":{"parsed":{"type":"mint","info":{"isInitialized":True,"supply":"100","mintAuthority":None,"freezeAuthority":None}}}}
class Tests(unittest.TestCase):
 def test_base58_roundtrip(self):
  for raw in [bytes(32),bytes(range(32)),b"\0\0hello"]:self.assertEqual(b58decode(b58encode(raw)),raw)
 def test_revoked_plain_mint_passes_controls_only(self):
  self.assertEqual(token_controls(mint())["status"],"PASS")
 def test_active_authority_rejects(self):
  x=mint();x["data"]["parsed"]["info"]["mintAuthority"]=A
  self.assertEqual(token_controls(x)["status"],"REJECT")
 def test_unknown_extension_holds(self):
  x=mint();x["owner"]=TOKEN22;x["data"]["parsed"]["info"]["extensions"]=[{"extension":"transferHook"}]
  self.assertEqual(token_controls(x)["status"],"UNKNOWN")
 def test_wrong_program_holds(self):
  x=mint();x["owner"]=A;self.assertEqual(token_controls(x)["status"],"UNKNOWN")
 def test_pool_layout(self):
  raw=POOL+b"\0"*3+bytes(range(32))*6+struct.pack("<Q",123)+bytes(32)
  state=pool_state({"owner":PUMP,"data":[base64.b64encode(raw).decode(),"base64"]})
  self.assertEqual(state["recorded_lp_supply"],123);self.assertFalse(state["advanced_controls_verified"])
 def test_wrong_pool_discriminator(self):
  with self.assertRaises(ValueError):pool_state({"owner":PUMP,"data":[base64.b64encode(bytes(271)).decode(),"base64"]})
 def test_sell_withdraw_and_failed(self):
  for disc,(kind,idx) in OPS.items():
   tx={"meta":{"err":None},"transaction":{"message":{"instructions":[{"programId":PUMP,"accounts":[A,B,B],"data":b58encode(disc+struct.pack("<Q",10))}]}}}
   self.assertEqual(protocol_events(tx,"sig")[0]["relation"],"pump_amm_"+kind)
   tx["meta"]["err"]={};self.assertEqual(protocol_events(tx,"sig"),[])
 def test_zero_amount_not_sell(self):
  disc=next(d for d,k in OPS.items() if k[0]=="sell")
  tx={"meta":{"err":None},"transaction":{"message":{"instructions":[{"programId":PUMP,"accounts":[A,B],"data":b58encode(disc+bytes(8))}]}}}
  self.assertEqual(protocol_events(tx,"sig"),[])
if __name__=="__main__":unittest.main()
