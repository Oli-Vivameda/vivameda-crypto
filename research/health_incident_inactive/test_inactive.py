import json
import tempfile
from pathlib import Path
import unittest
from unittest.mock import patch
import health

class IncidentInactive(unittest.TestCase):
    def report(self,status='stalled'):
        return dict(status=status,checked_at=1000,reason='no_successful_cycle_for_10_minutes')
    def test_all_incident_states_suppressed(self):
        for status in ('paused','stalled','unhealthy','unavailable'):
            with self.subTest(status=status):
                state,result=health.notify(self.report(status),{},lambda _:self.fail('send'))
                self.assertEqual(result,'incident_suppressed')
                self.assertEqual(state['sent_incident'],status)
    def test_pending_failed_incident_cleared_without_retry(self):
        state,result=health.notify(self.report(),{'pending':'stalled','retry_at':2000},lambda _:self.fail('send'))
        self.assertEqual(result,'incident_suppressed')
        self.assertIsNone(state['pending']);self.assertEqual(state['retry_at'],0)
    def test_recovery_remains_inactive(self):
        state,result=health.notify(self.report('collecting'),{'sent_incident':'stalled'},lambda _:self.fail('send'))
        self.assertEqual(result,'recovery_suppressed');self.assertIsNone(state['sent_incident'])
    def test_normal_status_idle(self):
        for status in ('collecting','stopped','not_activated'):
            _,result=health.notify(self.report(status),{},lambda _:self.fail('send'))
            self.assertEqual(result,'idle')
    def test_incident_audit_retains_state_for_kill_switch(self):
        with tempfile.TemporaryDirectory() as d,patch.object(health,'STATE',Path(d)):
            report=self.report();health.append_audit(report,'incident_suppressed')
            row=json.loads((Path(d)/'incident_send_log.jsonl').read_text())
            self.assertEqual(row,dict(time=1000,state='stalled',reason_code='no_successful_cycle_for_10_minutes',send_result='incident_suppressed'))
            self.assertEqual(report['audit_log'],'available')
if __name__=='__main__':unittest.main()
