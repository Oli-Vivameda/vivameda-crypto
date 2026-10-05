import copy,json,sqlite3,unittest
import audit_selection as a
import export_history as e

def case(mint,source,t=100000,mc=100000,liq=30000):
    return dict(id=mint+':'+source,mint=mint,source=source,decision_ts=t,
        score=8,level=1,regime='OTHER',entry_mc=mc,entry_liq=liq,
        features=dict(points=5,history_min=12,mc=mc,liq=liq,vol1=30000,pc1=10,pc5=0,band=.2,net=.1),outcomes={})

def endpoint(r,value=1.2,h=60):
    ts=r['decision_ts']+h*60
    r['outcomes'][str(h)]=dict(observed_ts=ts,lateness=0,multiple=value,
        metric_ts=ts,coverage_ok=1,max_gap=60,max_mult=value,liq=30000)

class SelectionTests(unittest.TestCase):
    def test_invalid_timing_and_path_refused(self):
        r=case('a','ALERT');endpoint(r)
        self.assertEqual(a.endpoint(r,60),(1.2,'eligible'))
        r['outcomes']['60']['observed_ts']+=1
        self.assertEqual(a.endpoint(r,60)[1],'invalid_timing')
        endpoint(r);r['outcomes']['60']['max_gap']=181
        self.assertEqual(a.endpoint(r,60)[1],'incomplete_coverage')
        endpoint(r);r['outcomes']['60']['metric_ts']-=1
        self.assertEqual(a.endpoint(r,60)[1],'incomplete_coverage')

    def test_matching_ignores_outcomes(self):
        rows=[case('a','ALERT'),case('b','SHADOW',99900),case('c','SHADOW',99800)]
        before=[(x['id'],y['id']) for x,y in a.match(rows)[0]]
        for r in rows:endpoint(r,100 if r['mint']=='c' else .01)
        self.assertEqual(before,[(x['id'],y['id']) for x,y in a.match(rows)[0]])

    def test_later_alert_permitted_prior_alert_refused(self):
        rows=[case('a','ALERT'),case('b','SHADOW',99900),case('b','ALERT',100100)]
        self.assertEqual(a.match(rows)[0][0][1]['mint'],'b')
        rows[-1]['decision_ts']=99800
        self.assertFalse(a.match(rows)[0])

    def test_future_and_insufficient_controls_refused(self):
        r=case('b','SHADOW',100001)
        self.assertFalse(a.match([case('a','ALERT'),r])[0])
        r['decision_ts']=99900;r['features']['points']=1
        self.assertFalse(a.match([case('a','ALERT'),r])[0])

    def test_repeat_alert_not_replaced_for_missing_outcome(self):
        r=case('a','ALERT');s=case('a','ALERT',100100);endpoint(s,3)
        self.assertEqual(a.first_alerts([s,r]),[r])

    def test_missingness_not_failure(self):
        r=case('a','ALERT');s=case('b','SHADOW',99900);endpoint(r,2)
        data=dict(schema='crypto-selection-history-v1',cutoff_ts=200000,cutoff_utc='test',
            cases=[r,s],live_ledger_results_read=False)
        out=a.audit(data)
        self.assertEqual(out['matched_horizons']['60']['complete_pairs'],0)
        self.assertEqual(out['matched_horizons']['60']['control_2x'],0)
        self.assertEqual(out['matched_horizons']['60']['excluded_pairs'],{'eligible / missing_endpoint':1})

    def test_active_cohort_rejected(self):
        data=dict(schema='crypto-selection-history-v1',cutoff_ts=100001,cutoff_utc='test',
            cases=[case('a','ALERT')],live_ledger_results_read=False)
        with self.assertRaisesRegex(ValueError,'Active-cohort'):a.audit(data)

    def test_feature_whitelist_removes_unrelated_payload(self):
        self.assertEqual(e.clean_features(json.dumps({'pc1':10,'unrelated':'sensitive','pc5':True})),{'pc1':10})

    def test_export_readonly_and_pre_activation_only(self):
        c=sqlite3.connect(':memory:')
        c.executescript('''CREATE TABLE pl_activation(id INTEGER,body TEXT);
            CREATE TABLE v2_cases(id TEXT,mint TEXT,decision_ts INTEGER,source TEXT,score INTEGER,
            level INTEGER,regime TEXT,features TEXT,entry_mc REAL,entry_liq REAL);
            CREATE TABLE v2_outcomes(id TEXT,horizon INTEGER,observed_ts INTEGER,lateness INTEGER,multiple REAL,liq REAL);
            CREATE TABLE v2_horizon_metrics(id TEXT,horizon INTEGER,observed_ts INTEGER,coverage_ok INTEGER,max_gap INTEGER,max_mult REAL);''')
        c.execute('INSERT INTO pl_activation VALUES(1,?)',(json.dumps({'activated_at':200000}),))
        for source,ts in [('ALERT',100000),('SHADOW',199999),('LEDGER_ALERT',100000)]:
            c.execute('INSERT INTO v2_cases VALUES(?,?,?,?,?,?,?,?,?,?)',(source,source,ts,source,8,1,'OTHER','{}',100000,30000))
        c.commit();before=c.total_changes
        # No prediction/result tables exist: exporter cannot depend on their contents.
        out=e.extract(c)
        self.assertEqual(len(out['cases']),1);self.assertEqual(c.total_changes,before)
        with self.assertRaises(sqlite3.OperationalError):c.execute('DELETE FROM v2_cases')
        c.close()

if __name__=='__main__':unittest.main()
