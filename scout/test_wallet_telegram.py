import unittest
from wallet_telegram import wallet_text,strict_eligible
class Tests(unittest.TestCase):
 def test_missing(self): self.assertIn("INCOMPLETE",wallet_text(None,"m",1000))
 def test_mismatch(self): self.assertIn("INCOMPLETE",wallet_text({"mint":"x"},"m",1000))
 def test_stale(self): self.assertIn("STALE",wallet_text({"mint":"m","generated_at":1},"m",1000))
 def test_partial_visible(self):
  t=wallet_text({"mint":"m","generated_at":1000,"wallet_histories":[],"issues":["rpc_error"]},"m",1000)
  self.assertIn("not safety-cleared",t);self.assertIn("Provider errors",t)
 def test_research_never_certifies(self):
  self.assertFalse(strict_eligible({"admission":{"status":"PASS"}}))
if __name__=="__main__": unittest.main()
