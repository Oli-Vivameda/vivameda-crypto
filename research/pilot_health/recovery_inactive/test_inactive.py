import unittest
import health

class RecoveryInactive(unittest.TestCase):
    def report(self, status='collecting', now=1000):
        return dict(status=status, checked_at=now, reason=None)

    def test_recovery_is_inactive_and_clears_incident_state(self):
        calls=[]
        state,result=health.notify(self.report(),{'sent_incident':'stalled'},calls.append)
        self.assertEqual(calls,[])
        self.assertEqual(result,'recovery_suppressed')
        self.assertIsNone(state['sent_incident'])
        state,result=health.notify(self.report(now=1100),state,calls.append)
        self.assertEqual(result,'idle')

    def test_pending_recovery_does_not_retry(self):
        state,result=health.notify(self.report(),{'pending':'recovered','retry_at':2000,'last_attempt':999},lambda _:self.fail('send'))
        self.assertEqual(result,'recovery_suppressed')
        self.assertIsNone(state['pending'])
        self.assertEqual(state['retry_at'],0)

    def test_incident_after_recovery_still_sends(self):
        calls=[]
        state,_=health.notify(self.report(),{'sent_incident':'stalled'},calls.append)
        state,result=health.notify(self.report('stalled',2000),state,calls.append)
        self.assertEqual(result,'sent')
        self.assertEqual(len(calls),1)
        self.assertTrue(calls[0].startswith('Crypto pilot health incident'))
        self.assertEqual(state['sent_incident'],'stalled')

    def test_incident_dedup_unchanged(self):
        state,result=health.notify(self.report('stalled'),{'sent_incident':'stalled'},lambda _:self.fail('send'))
        self.assertEqual(result,'idle')

    def test_incident_failure_retry_unchanged(self):
        def fail(_):raise ValueError('synthetic')
        state,result=health.notify(self.report('paused'),{},fail)
        self.assertEqual(result,'delivery_failed')
        self.assertEqual(state['pending'],'paused')
        self.assertEqual(state['retry_at'],1300)

if __name__=='__main__':unittest.main()
