"""Prospective crypto ledger core. Explicit activation; no network or trading.

Call record() synchronously at the decision boundary, never from retrospective
V2 capture. SQLite triggers prevent ordinary edits; hashes detect tampering.
This is not protection against a privileged database owner rewriting history.

Release status (2026-10-04): tested storage component, NOT wired to the scanner
and NOT activated. Remaining integration: capture exact preprocessor input at
the alert decision, snapshot all pre-activation mints, pair timed outcomes,
enforce the 200-eligible-case stop, and persist an external chain-head receipt.
No evaluation cohort exists until that integration and activation are verified.
"""
import hashlib
import json
import math
import sqlite3
import time
from pathlib import Path

FEATURES = ('band','pc5','pc1','buy_ratio','vol_mc','liq_change','vol_accel')
BASELINE = 3/42

def canonical(value):
    return json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False)

def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()

def finite(v):
    return type(v) in (int,float) and math.isfinite(v)

def model_check(m):
    if m['features'] != list(FEATURES):raise ValueError('feature schema mismatch')
    if len(m['mean'])!=7 or len(m['scale'])!=7 or len(m['coefficients'])!=8:
        raise ValueError('model dimensions')
    if not all(finite(x) for k in ('mean','scale','coefficients') for x in m[k]):
        raise ValueError('nonfinite model')
    if min(m['scale'])<=0:raise ValueError('invalid scale')

def probability(m,x):
    if not all(finite(x.get(k)) for k in FEATURES):raise ValueError('invalid features')
    z=m['coefficients'][0]+sum(w*(x[k]-mu)/sd for k,mu,sd,w in
        zip(FEATURES,m['mean'],m['scale'],m['coefficients'][1:]))
    return 1/(1+math.exp(-max(-40,min(40,z))))

class Ledger:
    def __init__(self,path,readonly=False):
        target=Path(path).resolve().as_uri()+'?mode=ro' if readonly else path
        self.con=sqlite3.connect(target,uri=readonly,timeout=10,isolation_level=None)
        if readonly:
            self.con.execute('PRAGMA query_only=ON')
            return
        self.con.execute('PRAGMA synchronous=FULL')
        self.con.execute('PRAGMA busy_timeout=10000')
        self.con.executescript('''
        CREATE TABLE IF NOT EXISTS activation(id INTEGER PRIMARY KEY CHECK(id=1),body TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS excluded(mint TEXT PRIMARY KEY);
        CREATE TABLE IF NOT EXISTS entries(seq INTEGER PRIMARY KEY,kind TEXT NOT NULL,
          mint TEXT UNIQUE NOT NULL,body TEXT NOT NULL,previous_hash TEXT NOT NULL,hash TEXT NOT NULL);
        ''')
        for table in ('activation','excluded','entries'):
            for op in ('UPDATE','DELETE'):
                self.con.execute(f"CREATE TRIGGER IF NOT EXISTS no_{op}_{table} BEFORE {op} ON {table} BEGIN SELECT RAISE(ABORT,'append only'); END")
        self.con.execute("CREATE TRIGGER IF NOT EXISTS freeze_exclusions BEFORE INSERT ON excluded WHEN EXISTS(SELECT 1 FROM activation) BEGIN SELECT RAISE(ABORT,'exclusions frozen'); END")

    def activate(self,model_bytes,plan_bytes,preprocessing_bytes,excluded_mints):
        m=json.loads(model_bytes);model_check(m)
        a={'activated_at_ns':time.time_ns(),'model':m,
           'model_sha256':hashlib.sha256(model_bytes).hexdigest(),
           'plan_sha256':hashlib.sha256(plan_bytes).hexdigest(),
           'preprocessing_sha256':hashlib.sha256(preprocessing_bytes).hexdigest(),
           'baseline_probability':BASELINE,'duration_days':30,'status':'activated'}
        exclusions=sorted(set(excluded_mints))
        a['excluded_mints_sha256']=digest(canonical(exclusions));a['excluded_mints_count']=len(exclusions)
        self.con.execute('BEGIN IMMEDIATE')
        try:
            if self.con.execute('SELECT 1 FROM activation').fetchone():raise ValueError('already activated')
            self.con.executemany('INSERT INTO excluded VALUES(?)',[(x,) for x in exclusions])
            self.con.execute('INSERT INTO activation VALUES(1,?)',(canonical(a),))
            self.con.execute('COMMIT')
        except BaseException:self.con.execute('ROLLBACK');raise
        return a

    def record(self,mint,case_id,features,source_snapshot,feature_capture_ns,preprocessing_sha256):
        """First attempt consumes mint even when invalid; no replacement selection.

        Source snapshot must be the exact locally captured input used by the
        pinned preprocessor. Caller must supply authentic capture time. This API
        cannot prove upstream timestamps; the production hook must be verified.
        """
        self.con.execute('BEGIN IMMEDIATE')
        try:
            row=self.con.execute('SELECT body FROM activation WHERE id=1').fetchone()
            if not row:raise ValueError('not activated')
            a=json.loads(row[0]);now=time.time_ns()
            if now<a['activated_at_ns'] or now>=a['activated_at_ns']+30*86400*10**9:
                raise ValueError('outside enrollment window')
            if self.con.execute('SELECT 1 FROM excluded WHERE mint=?',(mint,)).fetchone():
                raise ValueError('pre-activation mint')
            if self.con.execute('SELECT 1 FROM entries WHERE mint=?',(mint,)).fetchone():
                raise ValueError('mint already attempted')
            reason=None;p=None
            if type(feature_capture_ns) is not int or not a['activated_at_ns']<=feature_capture_ns<=now:
                reason='invalid_capture_time'
            elif preprocessing_sha256!=a['preprocessing_sha256']:reason='preprocessing_mismatch'
            else:
                try:p=probability(a['model'],features)
                except (ValueError,TypeError,AttributeError):reason='invalid_features'
            # Invalid numerical objects are not serialized as JSON NaN.
            clean={k:features.get(k) if finite(features.get(k)) else None for k in FEATURES} if isinstance(features,dict) else {}
            source=canonical(source_snapshot)
            body=canonical({'case_id':case_id,'source':'ALERT','decision_ts_ns':now,
                'feature_capture_ns':feature_capture_ns,'features':clean,
                'source_snapshot':source_snapshot,'source_snapshot_sha256':digest(source),
                'model_sha256':a['model_sha256'],'preprocessing_sha256':preprocessing_sha256,
                'model_probability':p,'baseline_probability':BASELINE,'exclusion_reason':reason,
                'horizon_seconds':3600})
            last=self.con.execute('SELECT seq,hash FROM entries ORDER BY seq DESC LIMIT 1').fetchone()
            seq=last[0]+1 if last else 1;previous=last[1] if last else digest(canonical(a))
            kind='excluded' if reason else 'prediction'
            h=digest(canonical([seq,kind,mint,body,previous]))
            self.con.execute('INSERT INTO entries VALUES(?,?,?,?,?,?)',(seq,kind,mint,body,previous,h))
            self.con.execute('COMMIT')
            return {'seq':seq,'kind':kind,'hash':h,**json.loads(body)}
        except BaseException:self.con.execute('ROLLBACK');raise

    def verify(self):
        row=self.con.execute('SELECT body FROM activation').fetchone()
        if not row:raise ValueError('not activated')
        a=json.loads(row[0]);previous=digest(canonical(a));n=0
        exclusions=[r[0] for r in self.con.execute('SELECT mint FROM excluded ORDER BY mint')]
        if digest(canonical(exclusions))!=a['excluded_mints_sha256']:raise ValueError('exclusions changed')
        for seq,kind,mint,body,prev,h in self.con.execute('SELECT * FROM entries ORDER BY seq'):
            n+=1
            if seq!=n or prev!=previous or h!=digest(canonical([seq,kind,mint,body,prev])):
                raise ValueError('hash chain broken')
            previous=h
        return {'entries':n,'head_sha256':previous,'chain_valid':True,
                'warning':'Privileged rewrite or tail truncation needs an external saved head to detect.'}

    def close(self):self.con.close()

if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser(description='Verify an existing ledger; no activation from CLI.')
    p.add_argument('database');args=p.parse_args()
    if not Path(args.database).is_file():p.error('existing database required')
    ledger=Ledger(args.database,readonly=True)
    try:print(json.dumps(ledger.verify(),indent=2))
    finally:ledger.close()
