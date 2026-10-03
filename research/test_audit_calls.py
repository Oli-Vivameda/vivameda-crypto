import unittest
from audit_calls import dimensions,event,checkpoints
class AuditTests(unittest.TestCase):
 def case(self,**kw):
  return dict(id='mint:alert:1000',mint='mint',source='ALERT',decision_ts=1000,entry_mc=100,max_mult=3,min_mult=.01,last_mc=1,last_liq=2000,status='ACTIVE',**kw)
 def test_peak_cannot_hide_failure(self):
  r=dimensions(self.case());self.assertEqual(r['assessment'],'PEAK_THEN_FAILURE_OBSERVED');self.assertFalse(r['realized_profit_verified'])
 def test_missing_path_never_training_label(self):
  self.assertEqual(dimensions(self.case())['horizon_verdict'],'UNSCORED_NO_COMPLETE_PATH_EXPORTED')
 def test_unknown_liquidity_not_zero(self):
  c=self.case();c.update(last_mc=300,last_liq=None)
  r=dimensions(c);self.assertFalse(r['failure_observed']);self.assertTrue(r['liquidity_missing'])
 def test_invalid_entry_not_success(self):
  c=self.case();c['entry_mc']=0
  self.assertEqual(dimensions(c)['assessment'],'INVALID_ENTRY')
 def test_not_yet_hit_is_not_final_failure(self):
  c=self.case();c.update(max_mult=1.2,min_mult=.9,last_mc=110,last_liq=30000)
  self.assertEqual(dimensions(c)['assessment'],'NO_2X_OBSERVED_YET')
 def test_event_emitted_score_preserved(self):
  r=event('2026-10-01 13:10:28,969 INFO ALERT mint level=1 score=9')
  self.assertEqual(r['logged_score'],9);self.assertEqual(r['id'],'mint:alert:'+str(r['decision_ts']))
 def test_late_or_wrong_timestamp_rejected(self):
  lines=['v2 checkpoint id=mint:alert:1000 horizon_min=1 observed_ts=1061 lateness_s=2 multiple=3.0',
   'v2 checkpoint id=mint:alert:1000 horizon_min=5 observed_ts=1481 lateness_s=181 multiple=3.0']
  self.assertTrue(all(not r['timing_valid'] for r in checkpoints(lines,[self.case()])))
 def test_timed_log_still_no_path_label(self):
  r=checkpoints(['v2 checkpoint id=mint:alert:1000 horizon_min=1 observed_ts=1062 lateness_s=2 multiple=3.0'],[self.case()])[0]
  self.assertTrue(r['timing_valid']);self.assertFalse(r['training_eligible'])
 def test_unknown_case_never_labelled(self):
  r=checkpoints(['v2 checkpoint id=other:shadow horizon_min=1 observed_ts=1062 lateness_s=2 multiple=3.0'],[self.case()])[0]
  self.assertFalse(r['timing_valid'])
if __name__=='__main__':unittest.main()

