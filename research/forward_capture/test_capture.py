import copy
import json
import sqlite3
import unittest
import capture as c


def candidate(mint='alert', score=8, **kwargs):
    s = {k: i < score for i, k in enumerate(c.SIGNALS)}
    row = dict(mint=mint, pair=mint+'-pair', created_ts=1000, captured_ts=2800,
               snapshot_ts=2760, points=5, history_seconds=600, mc=100000.,
               liq=30000., vol1=25000., score=score, signals=s,
               prior_alert_level=0, input_sha256='a'*64)
    row.update(kwargs)
    return row


class CaptureTests(unittest.TestCase):
    def setUp(self):
        self.con = sqlite3.connect(':memory:')
        c.initialize(self.con, 2000, ['excluded'], 'b'*64)
        self.alert = candidate()
        self.control = candidate('control', 7)

    def cycle(self, rows=None, key='one', ts=2810):
        return c.record_cycle(self.con, key, ts, rows or [self.alert, self.control], 'c'*64)

    def test_matching_not_score_component_similarity(self):
        cohorts = self.cycle()
        self.assertEqual([r['mint'] for r in cohorts[0]['controls']], ['control'])
        self.assertEqual(cohorts[0]['screening'], 'not_yet_observed')

    def test_wrong_age_size_liquidity_and_prior_alert_refused(self):
        for changes in ({'created_ts':0}, {'mc':210001}, {'liq':65000}, {'prior_alert_level':1}):
            row = candidate('control', 7, **changes)
            self.assertEqual(c.matched_controls(self.alert, [row]), [])

    def test_low_history_and_base_gate_refused(self):
        for changes in ({'points':3}, {'history_seconds':599}, {'mc':29999}, {'liq':24999}, {'vol1':19999}):
            self.assertFalse(c.eligible(candidate(**changes)))

    def test_future_stale_and_preactivation_rejected(self):
        for changes in ({'captured_ts':2811}, {'snapshot_ts':2801}, {'snapshot_ts':2679},
                        {'captured_ts':1900,'snapshot_ts':1860}):
            with self.assertRaises(ValueError): self.cycle([dict(self.alert, **changes)])

    def test_no_outcomes_credentials_or_unexpected_fields(self):
        for key in ('outcome', 'profit', 'wallets', 'api_key'):
            with self.assertRaises(ValueError): self.cycle([dict(self.alert, **{key:1})])

    def test_signal_score_and_nonfinite_values_rejected(self):
        for changes in ({'score':9}, {'mc':float('nan')}, {'liq':float('inf')}, {'score':True},
                        {'signals':{}}, {'input_sha256':'bad'}):
            with self.assertRaises(ValueError): self.cycle([dict(self.alert, **changes)])

    def test_atomic_invalid_cycle(self):
        with self.assertRaises(ValueError): self.cycle([self.alert, dict(self.control, mc=float('nan'))])
        self.assertEqual(self.con.execute('SELECT count(*) FROM fc_events').fetchone()[0], 0)

    def test_duplicates_rejected(self):
        with self.assertRaises(ValueError): self.cycle([self.alert, self.alert])

    def test_replay_idempotent_conflict_rejected(self):
        self.cycle(); before = c.verify(self.con)
        self.assertEqual(self.cycle(), [])
        self.assertEqual(c.verify(self.con), before)
        with self.assertRaises(ValueError): self.cycle([candidate(mc=100001), self.control])

    def test_first_qualification_only_and_later_control_alert_allowed(self):
        self.cycle()
        # A control that qualifies later is retained in the original cohort.
        self.cycle([candidate('control', 8)], 'two')
        self.assertEqual(self.con.execute("SELECT count(*) FROM fc_events WHERE kind='cohort'").fetchone()[0],2)
        cohort=json.loads(self.con.execute("SELECT body FROM fc_events WHERE kind='cohort' AND event_key='alert'").fetchone()[0])
        self.assertEqual(cohort['controls'][0]['mint'], 'control')
        self.assertEqual(self.cycle([self.alert], 'three'), [])

    def test_activation_exclusions_and_prior_alerts(self):
        self.assertEqual(self.cycle([candidate('excluded'), candidate('old', prior_alert_level=1)]), [])

    def test_zero_matches_retained_not_dropped(self):
        cohort=self.cycle([self.alert])[0]
        self.assertEqual(cohort['controls'], [])

    def test_append_only_and_activation_frozen(self):
        self.cycle()
        for sql in ('DELETE FROM fc_events', "UPDATE fc_activation SET body='{}'"):
            with self.assertRaises(sqlite3.IntegrityError): self.con.execute(sql)
        with self.assertRaises(ValueError): c.initialize(self.con,2001,['excluded'],'b'*64)

    def test_integrity_detects_corruption(self):
        self.cycle()
        self.con.execute('DROP TRIGGER fc_events_no_UPDATE')
        self.con.execute("UPDATE fc_events SET body='{}' WHERE seq=1")
        with self.assertRaises(ValueError): c.verify(self.con)

    def test_screening_separate_no_delivery_without_pass(self):
        self.cycle()
        c.record_screening(self.con,'alert','one',2811,'HOLD',False)
        with self.assertRaises(ValueError): c.record_screening(self.con,'alert','one',2811,'HOLD',True)
        with self.assertRaises(ValueError): c.record_screening(self.con,'control','one',2811,'PASS',True)

    def test_screening_wrong_cycle_and_future_cohort_relation(self):
        self.cycle()
        for key, ts in (('wrong',2811),('one',2809)):
            with self.assertRaises(ValueError): c.record_screening(self.con,'alert',key,ts,'PASS',False)

    def test_endpoint_window_and_earliest_valid_same_pair(self):
        self.cycle()
        for pair,ts,mc in [('wrong',6410,999999), ('alert-pair',6409,300000),
                           ('alert-pair',6591,500000), ('alert-pair',6500,200000),
                           ('alert-pair',6410,110000)]:
            c.record_observation(self.con,'alert',pair,ts,mc)
        with self.assertRaises(ValueError): c.endpoint(self.con,self.alert,2810,6590)
        r=c.endpoint(self.con,self.alert,2810,6591)
        self.assertEqual(r['multiple'],1.1)
        self.assertEqual(r['lateness'],0)

    def test_missing_stays_missing_and_late_180_inclusive(self):
        self.cycle()
        r=c.endpoint(self.con,self.alert,2810,6591)
        self.assertFalse(r['eligible']); self.assertIsNone(r['multiple'])
        c.record_observation(self.con,'alert','alert-pair',6590,200000)
        self.assertEqual(c.endpoint(self.con,self.alert,2810,6591)['multiple'],2)

    def test_pair_change_cannot_substitute(self):
        c.record_observation(self.con,'alert','another-pair',6410,200000)
        self.assertFalse(c.endpoint(self.con,self.alert,2810,6591)['eligible'])

    def test_observation_validation_and_replay(self):
        for value in (0,-1,float('nan'),True):
            with self.assertRaises(ValueError): c.record_observation(self.con,'alert','alert-pair',6410,value)
        h=c.record_observation(self.con,'alert','alert-pair',6410,110000)
        self.assertEqual(c.record_observation(self.con,'alert','alert-pair',6410,110000),h)
        with self.assertRaises(ValueError): c.record_observation(self.con,'alert','alert-pair',6410,120000)

    def test_outcome_independent_fixed_pilot_stop(self):
        deadline=2000+14*86400
        with self.assertRaises(ValueError): self.cycle(key='stop',ts=deadline)
        with self.assertRaises(ValueError): c.record_observation(self.con,'alert','alert-pair',deadline+3781,1)

    def test_scanner_population_age_and_cycle_cap(self):
        for created in (1001, 0):
            row=candidate(created_ts=created, captured_ts=22000, snapshot_ts=21960)
            if created == 1001:
                row=candidate(created_ts=1001)
            with self.assertRaises(ValueError): self.cycle([row],ts=row['captured_ts'])
        with self.assertRaises(ValueError): self.cycle([candidate(str(i),7) for i in range(61)])

    def test_contradictory_free_liquidity_point_rejected(self):
        row=copy.deepcopy(self.alert)
        row['signals']['liq25k']=False
        row['signals']['txns100']=True
        with self.assertRaises(ValueError): self.cycle([row])


if __name__ == '__main__': unittest.main()
