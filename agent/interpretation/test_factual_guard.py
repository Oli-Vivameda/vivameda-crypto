import json,pathlib,tempfile,unittest
from unittest.mock import Mock,patch
import factual_guard as g,acceptance_facts as a
class FactGuardTests(unittest.TestCase):
 def test_date_and_threshold_format(self):
  f=g.facts(a.PACKET);self.assertEqual(f['memory.data.generated_at'],'2026-10-06T06:50:39Z');self.assertEqual(f['thresholds.matched_failure_endpoint'],'0.55x');self.assertNotIn('1791269439',json.dumps(f))
 def test_unsupported_numeric_date_and_explanation_fail(self):
  f=g.facts(a.PACKET)
  for raw in [{'facts':['memory.data.cases.0.last_multiple'],'statements':['The last multiple is 0.055x.']},{'facts':['2025-10-06T06:50:39Z'],'statements':[]},{'facts':['missingness.cause'],'statements':['Gaps occurred because the provider failed.']}]:
   with self.assertRaises(ValueError):g.validate(json.dumps(raw),f)
 def test_no_marker_means_no_model_call(self):
  model=Mock()
  with tempfile.TemporaryDirectory() as d:r=g.explain('what happened',a.PACKET,model,d)
  model.assert_not_called();self.assertEqual(r['mode'],'evidence_table_only');self.assertEqual(r['supported_statements'],[])
 def test_bad_generation_falls_back_and_no_history_or_epoch_sent(self):
  model=Mock(return_value='Invented 0.055x in 2025 due to a gap')
  with patch('factual_guard.accepted',return_value=True):r=g.explain('what happened',a.PACKET,model,'.')
  self.assertEqual(r['mode'],'evidence_table_only');self.assertEqual(r['validation'],'failed_closed');self.assertEqual(model.call_args.args[2],());self.assertNotIn('1791269439',json.dumps(model.call_args.args[1]))
 def test_number_cannot_be_swapped_to_another_field(self):
  f=g.facts(a.PACKET)
  with self.assertRaises(ValueError):g.validate(json.dumps({'facts':['memory.data.summary.eligible_60m_endpoints=3'],'statements':[]}),f)
 def test_all_ten_fixed_expected_facts(self):
  model=Mock(return_value=json.dumps({'answers':{i:k for i,q,k,v in a.QUESTIONS}}))
  result=a.run(model);self.assertEqual(result['facts_correct'],10);self.assertTrue(result['passed']);self.assertFalse(result['free_text_interpretation_verified'])
 def test_bad_fixed_answer_fails_acceptance(self):
  answers={i:k for i,q,k,v in a.QUESTIONS};answers['last']='memory.data.cases.0.tracked_peak_multiple'
  result=a.run(Mock(return_value=json.dumps({'answers':answers})));self.assertEqual(result['facts_correct'],9);self.assertFalse(result['passed'])
 def test_invalid_future_numeric_evidence_refused(self):
  with self.assertRaises(ValueError):g.facts({'x':float('nan')})
if __name__=='__main__':unittest.main()
