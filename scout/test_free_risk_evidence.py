import unittest
from free_risk_evidence import holder_summary, activity_summary, valid
A = "5F1Se9J2L16YcK1fpk18NhSvnPjtyjQSaczKGLDoV1Uy"
class EvidenceTests(unittest.TestCase):
    def test_grouping_not_pool_adjusted(self):
        s=holder_summary({"topHolders":[{"owner":A,"pct":2},{"owner":A,"pct":3}]})
        self.assertEqual(s["owners"][0]["reported_pct"],5)
        self.assertFalse(s["pool_adjusted"])
    def test_bad_percent_not_clean(self):
        s=holder_summary({"topHolders":[{"owner":A,"pct":float("nan")}]})
        self.assertEqual(s["unusable_rows"],1)
    def test_missing_activity_unknown(self):
        self.assertEqual(activity_summary([],100)["status"],"UNKNOWN")
    def test_activity_is_not_creation(self):
        s=activity_summary([{"blockTime":80,"err":None},{"blockTime":50,"err":{}},{"blockTime":101,"err":None}],100)
        self.assertEqual(s["observed_activity_age_lower_bound_seconds"],20)
        self.assertIsNone(s["wallet_creation_time"])
        self.assertFalse(s["full_history_verified"])
    def test_invalid_address(self):
        self.assertFalse(valid("../secret"))
if __name__ == "__main__": unittest.main()

class RetryTests(unittest.TestCase):
 def test_backoff_capped_and_error_classification(self):
  from free_risk_evidence import candidate_retry_delay,transient_issue,evidence_error
  self.assertEqual([candidate_retry_delay(i) for i in (0,1,2,3,100)],[120,240,480,600,600])
  issue=evidence_error(RuntimeError("rpc_error_code_-32019_method_getSignaturesForAddress"))
  self.assertTrue(transient_issue(issue))
  self.assertFalse(transient_issue("creator_identity_conflict"))
 def test_rpc_failure_stays_unknown_and_records_candidate_retry(self):
  import tempfile,json
  from unittest.mock import Mock,patch
  import free_risk_evidence as f
  session=Mock();session.headers={};session.get.return_value.json.return_value={"mint":A,"creator":A,"topHolders":[]}
  session.post.return_value.json.return_value={"error":{"code":-32019}}
  with tempfile.TemporaryDirectory() as d,patch.object(f.requests,"Session",return_value=session):
   result,_=f.collect(A,d)
  self.assertEqual(result["verdict"],"HOLD")
  self.assertEqual(result["retry_scope"],"candidate")
  self.assertEqual(result["wallet_activity"][A]["status"],"UNKNOWN")
  self.assertIn("-32019",result["errors"][0]);self.assertEqual(session.post.call_count,1)
