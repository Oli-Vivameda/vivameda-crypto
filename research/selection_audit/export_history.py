"""Owner-run historical crypto export. No network, deployment or live ledger results."""
import argparse, datetime, hashlib, json, math, os, pathlib, pwd, sqlite3, tempfile

DB = pathlib.Path('/opt/vivameda-crypto-early-scout/data/early_scout.sqlite')
DEST = pathlib.Path('/var/lib/vivameda-engineering/crypto-selection-audit-20261005/history.json')
FEATURES = ('points','history_min','mc','liq','vol1','pc1','pc5','band','net','buy_ratio','vol_mc','liq_change','vol_accel','reclaim','low_pos')
HORIZONS = (60, 180, 360)

def clean_features(raw):
    try:
        d = json.loads(raw)
    except (ValueError, TypeError):
        return {}
    if not isinstance(d, dict):
        return {}
    return {k:d[k] for k in FEATURES if type(d.get(k)) in (int,float) and math.isfinite(d[k])}

def extract(c):
    # Read activation metadata only. Never query predictions, probabilities or results.
    c.row_factory = sqlite3.Row
    c.execute('PRAGMA query_only=ON')
    c.execute('BEGIN')
    try:
        row = c.execute('SELECT body FROM pl_activation WHERE id=1').fetchone()
        if row is None:
            raise ValueError('Verified ledger activation required for historical cutoff')
        cutoff = json.loads(row['body'])['activated_at']
        if type(cutoff) is not int or cutoff <= 0:
            raise ValueError('Invalid activation cutoff')
        records = []
        # Entire maximum follow-up must precede activation. No peek into active cohort.
        cases = c.execute('''SELECT id,mint,decision_ts,source,score,level,regime,
            features,entry_mc,entry_liq FROM v2_cases
            WHERE source IN ('ALERT','SHADOW') AND decision_ts+21780<?
            ORDER BY decision_ts,id''', (cutoff,)).fetchall()
        if len(cases)>100000:
            raise ValueError('Historical export exceeds reviewed bound')
        for r in cases:
            d = dict(r); d['features'] = clean_features(d['features']); d['outcomes'] = {}
            for h in HORIZONS:
                o = c.execute('''SELECT o.observed_ts,o.lateness,o.multiple,o.liq,
                    m.observed_ts AS metric_ts,m.coverage_ok,m.max_gap,m.max_mult
                    FROM v2_outcomes o LEFT JOIN v2_horizon_metrics m
                    ON m.id=o.id AND m.horizon=o.horizon
                    WHERE o.id=? AND o.horizon=? AND o.observed_ts<?''',
                    (d['id'],h,cutoff)).fetchone()
                if o is not None:
                    d['outcomes'][str(h)] = dict(o)
            records.append(d)
        return {'schema':'crypto-selection-history-v1',
            'exported_at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),
            'cutoff_utc':datetime.datetime.fromtimestamp(cutoff,datetime.timezone.utc).isoformat(),
            'cutoff_ts':cutoff,'cases':records,'live_ledger_results_read':False,
            'limitations':['Historical reconstructed features; exact emitted score not established',
                'Only stored first SHADOW observations; many may precede eligibility',
                'No live evaluation cohort or comparative scores exported']}
    finally:
        c.rollback()

def checked(path):
    if any(p.is_symlink() for p in (path,*path.parents)):
        raise ValueError('Symlink refused')

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--expected-sha256',required=True); a=p.parse_args()
    digest=hashlib.sha256(pathlib.Path(__file__).read_bytes()).hexdigest()
    if digest != a.expected_sha256:
        raise ValueError('Reviewed exporter source changed')
    checked(DB); checked(DEST)
    with sqlite3.connect(DB.resolve().as_uri()+'?mode=ro',uri=True,timeout=30) as c:
        data=extract(c)
    raw=(json.dumps(data,indent=2,allow_nan=False)+'\n').encode()
    if len(raw)>32*1024*1024:
        raise ValueError('Export exceeds 32 MiB bound')
    owner=pwd.getpwnam('vivameda-engineer')
    if os.geteuid()!=0:
        raise ValueError('Existing owner root terminal required for protected DB and private export')
    DEST.parent.mkdir(mode=0o700,exist_ok=True)
    checked(DEST)
    os.chown(DEST.parent,owner.pw_uid,owner.pw_gid); os.chmod(DEST.parent,0o700)
    if DEST.exists():
        raise ValueError('Existing export preserved; do not overwrite history')
    fd,name=tempfile.mkstemp(prefix='.history-',dir=DEST.parent)
    try:
        with os.fdopen(fd,'wb') as f:
            f.write(raw); f.flush(); os.fsync(f.fileno())
        os.chmod(name,0o600); os.chown(name,owner.pw_uid,owner.pw_gid)
        # Link publishes atomically and refuses a concurrently created destination.
        os.link(name,DEST)
    finally:
        if os.path.exists(name): os.unlink(name)
    print(json.dumps({'exported':True,'private_path':str(DEST),'cases':len(data['cases']),
        'cutoff_utc':data['cutoff_utc'],'sha256':hashlib.sha256(raw).hexdigest(),
        'production_changed':False,'live_ledger_results_read':False}))

if __name__=='__main__': main()
