import unittest,tempfile,json
from pathlib import Path
from unittest.mock import patch
import wallet_ops as w
class DiagnosticsTests(unittest.TestCase):
 def test_bounded_redacted(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d); entry={"observed_at":12,"secret":"NEVER","runs":[{"status":"SCREENED_HOLD","rpc_requests_used":60,"history_coverage":{"owners_required":719,"owners_observed":48,"secret":"NEVER"},"index_metrics":{"transaction_attempts":9,"scope":"NEVER"}}]*5}
   (p/"capacity_observations.json").write_text(json.dumps([entry]*30))
   (p/"identity_pending.json").write_text(json.dumps({"count":3,"checked_at":12,"candidates":["NEVER"]}))
   with patch.object(w,"DATA",p): result=w.diagnostics()
   self.assertEqual(len(result["capacity_observations"]),20)
   self.assertEqual(len(result["capacity_observations"][0]["runs"]),2)
   self.assertNotIn("NEVER",json.dumps(result))
   self.assertEqual(result["identity_pending"]["count"],3)
 def test_symlink_rejected(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d); (p/"other").write_text("[]");(p/"capacity_observations.json").symlink_to(p/"other")
   with patch.object(w,"DATA",p): self.assertEqual(w.diagnostics()["capacity_access"],"unavailable")
 def test_invalid_numbers(self):
  self.assertEqual(w.numbers({"a":True,"b":-1,"c":float("inf")},("a","b","c")),{})
if __name__=="__main__":unittest.main()
