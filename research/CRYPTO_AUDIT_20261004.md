# Crypto audit and frozen evaluation specification — 2026-10-04

Status: audit completed; prospective specification frozen, NOT activated. No refit, production promotion, threshold change, or paid calls.

## Collection
Focused collection was deployed and hash-verified on 2026-10-04 (reviewed bundle b948040c90c65afc31761a0a085c9d111adab4539821aaa5cfd06cfc45e0d116; 133 tests passed).
Two post-deployment research observations with 552 required owners reported 43 then 54 observed owners and 37 then 48 with age evidence. Complete-and-fresh histories remained zero. These are partial observations, not a controlled improvement estimate or complete bubble-map coverage. An empty identity-pending queue does not prove creator conflicts resolved.

## Model audit
Frozen predictions reproduce to floating-point tolerance. Train/test mint overlap: zero; all training labels precede test decisions; selected endpoints pass timing/coverage checks. Scaling is train-only.
42 training tokens (3 positives), 18 test tokens (2 positives).
Model Brier 0.1104709613; constant baseline 0.1003401361.
Paired difference +0.0101308253 (positive is worse); exploratory 95% IID-token bootstrap interval [-0.0033514448, 0.0256816890], 10,000 draws, seed 20261004. Shared-market dependence and the tiny sample limit this interval.
No demonstrated predictive advantage. Existing results are exploratory, previously inspected, and not an independent forward test.
ALERT features were reconstructed from saved pre-decision snapshots; export timestamps do not establish exact knowledge-time provenance. Lifetime peak labels are not the 60-minute endpoint target. Wallet cluster/age are not among the seven model inputs, so incomplete wallet coverage does not directly explain this model's score.
The audited server model byte hash below can differ from the public artifact's formatting/redaction hash; public release identity remains in MANIFEST.json.

## Fresh outcome inventory
At 2026-10-04 06:13:31 UTC, logs showed 4,215 endpoint records, zero invalid timing records, 4,092 horizon-metric records, and 3,841 coverage-qualified horizon records. These span multiple horizons and sources, not independent 60-minute ALERT tokens.
Exact new eligible, disjoint token counts remain BLOCKED: the engineering account cannot open the live database. The owner-run read-only inventory source is included below. It uses no paid calls, changes no database, and emits aggregate counts only. New retrospective rows must not be called prospective validation.

## Frozen specification: crypto_forward_v2_20261004
1. Freeze the existing seven-feature model and constant probability 3/42. No refit, variants, feature selection or threshold search in this evaluation.
2. Activation requires a verified append-only decision/prediction ledger, with UTC activation time, model/preprocessing hashes, case identifier, decision timestamp, feature capture timestamp and source snapshot hash, numerical inputs, and both probabilities recorded before outcomes. Record activation as a separate immutable artifact. Until then this specification is NOT running.
3. Include the first ALERT decision per new mint after activation; exclude every mint present before activation, including all old export mints. Never substitute a later case because the first has missing evidence. SHADOW cases are a separate diagnostic cohort.
4. Target: observed market-cap multiple >=2 at 60 minutes. Require endpoint lateness 0–180 seconds and exact timestamp consistency, coverage_ok=1, maximum observation gap <=180 seconds, finite non-boolean inputs and positive finite multiple. Never substitute lifetime/global ATH or backfill missed endpoints. This is not executable P&L.
5. Stop at the first 200 eligible unique tokens or 30 UTC days after activation, whichever occurs first; allow the final enrolled case 3,780 seconds to mature. Report all attempted, excluded, missing and eligible cases with reasons. Do not extend based on results. Operational health can be inspected; comparative scores stay hidden until stopping.
6. Primary metric: paired mean Brier difference, model minus frozen baseline. Report a 95% percentile bootstrap interval using decision-day clusters (10,000 draws, seed 20261004), retaining all tokens of sampled days and weighting by token count. Require at least 20 distinct decision days and 20 positives and 20 negatives for a decision; otherwise inconclusive. Report IID-token interval only as secondary exploratory sensitivity.
7. Secondary: log loss (clip probabilities to [1e-12,1-1e-12]), counts, positive rate and calibration summaries. No secondary metric overrides primary.
8. An upper primary interval bound below zero permits a proposal for independent replication, not production promotion. Otherwise retain baseline and report no established advantage. A revised model requires a separately frozen development/evaluation amendment before testing.
9. Any change to this specification gets a new dated file and rationale; never silently overwrite this frozen section.

## Outstanding work
- Run owner inventory and review exact 60-minute ALERT eligibility.
- Implement and verify the prospective ledger, then record activation.
- Continue wallet collection until complete, fresh evidence is demonstrated; creator identity conflicts remain a separate evidence check.
- Public setup is still incomplete: survivor/watchlist, pool-monitor and legacy-learning sources have not been reconciled into this repository.

## Audit result
```json
{
  "audit_type": "frozen_artifact_reproduction_no_refit",
  "source_sha256_matches": true,
  "model_sha256": "2134513ce3d5ca270187c04799e7480b1afef9f217b4837fbac8d9c522ed5915",
  "train_n": 42,
  "test_n": 18,
  "train_positive": 3,
  "test_positive": 2,
  "sources": [
    "ALERT"
  ],
  "split_mint_overlap": 0,
  "unique_selected_mints": 60,
  "train_labels_before_test_decisions": true,
  "invalid_endpoint_timing": 0,
  "incomplete_selected": 0,
  "feature_boolean_values": 0,
  "max_prediction_reproduction_error": 5.551115123125783e-17,
  "model_brier": 0.11047096132679542,
  "base_rate_brier": 0.10034013605442177,
  "base_probability": 0.07142857142857142,
  "brier_delta_model_minus_baseline": 0.010130825272373653,
  "paired_bootstrap_95pct_interval": [
    -0.0033514447893947994,
    0.025681688957797544
  ],
  "bootstrap_seed": 20261004,
  "bootstrap_draws": 10000,
  "interval_scope": "Exploratory IID-token bootstrap conditional on the frozen fitted model; small single-period sample and shared market dependence limit inference. Not a forward confidence guarantee.",
  "limitations": [
    "Only two held-out positives",
    "ALERT-only selection",
    "Previously inspected exploratory outcomes",
    "Feature capture-time provenance not established by export",
    "Endpoint market cap is not executable return",
    "No model refit or production promotion"
  ]
}
```

## Reproduction source: audit_model_v1.py
```python
"""Read-only audit of frozen crypto predictions; never trains or modifies weights."""
import argparse, hashlib, json, math, random
from pathlib import Path

def audit(export, artifacts):
    raw=Path(export).read_bytes(); data=json.loads(raw)
    artifacts=Path(artifacts)
    model=json.loads((artifacts/'model.json').read_text())
    split=json.loads((artifacts/'split_manifest.json').read_text())
    predictions=json.loads((artifacts/'test_predictions.json').read_text())
    by={r['id']:r for r in data['rows']}
    train=[by[i] for i in split['train']];test=[by[i] for i in split['test']]
    base=sum(r['multiple']>=2 for r in train)/len(train)
    by_pred={r['id']:r for r in predictions}
    delta=[];errors=[];model_losses=[];base_losses=[]
    for r in test:
        f=json.loads(r['features']);w=model['coefficients']
        z=w[0]+sum(c*(f[k]-mu)/sd for k,mu,sd,c in zip(model['features'],model['mean'],model['scale'],w[1:]))
        p=1/(1+math.exp(-max(-40,min(40,z))));y=int(r['multiple']>=2)
        errors.append(abs(p-by_pred[r['id']]['p']))
        model_losses.append((p-y)**2);base_losses.append((base-y)**2)
        delta.append((p-y)**2-(base-y)**2)
    rng=random.Random(20261004);n=len(delta)
    boot=sorted(sum(rng.choice(delta) for _ in range(n))/n for _ in range(10000))
    selected=train+test
    return {
      'audit_type':'frozen_artifact_reproduction_no_refit',
      'source_sha256_matches':hashlib.sha256(raw).hexdigest()==model['source_sha256'],
      'model_sha256':hashlib.sha256((artifacts/'model.json').read_bytes()).hexdigest(),
      'train_n':len(train),'test_n':len(test),'train_positive':sum(r['multiple']>=2 for r in train),'test_positive':sum(r['multiple']>=2 for r in test),
      'sources':sorted({r['source'] for r in selected}),
      'split_mint_overlap':len({r['mint'] for r in train}&{r['mint'] for r in test}),
      'unique_selected_mints':len({r['mint'] for r in selected}),
      'train_labels_before_test_decisions':max(r['observed_ts'] for r in train)<min(r['decision_ts'] for r in test),
      'invalid_endpoint_timing':sum(not (r['horizon']==60 and 0<=r['lateness']<=180 and r['observed_ts']==r['decision_ts']+3600+r['lateness']) for r in selected),
      'incomplete_selected':sum(r['coverage_ok']!=1 or r['max_gap']>180 for r in selected),
      'feature_boolean_values':sum(type(json.loads(r['features']).get(k)) is bool for r in selected for k in model['features']),
      'max_prediction_reproduction_error':max(errors),
      'model_brier':sum(model_losses)/n,'base_rate_brier':sum(base_losses)/n,
      'base_probability':base,'brier_delta_model_minus_baseline':sum(delta)/n,
      'paired_bootstrap_95pct_interval':[boot[249],boot[9749]],
      'bootstrap_seed':20261004,'bootstrap_draws':10000,
      'interval_scope':'Exploratory IID-token bootstrap conditional on the frozen fitted model; small single-period sample and shared market dependence limit inference. Not a forward confidence guarantee.',
      'limitations':['Only two held-out positives','ALERT-only selection','Previously inspected exploratory outcomes','Feature capture-time provenance not established by export','Endpoint market cap is not executable return','No model refit or production promotion']}

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--export',required=True);p.add_argument('--artifacts',required=True);p.add_argument('--output',required=True);a=p.parse_args()
    result=audit(a.export,a.artifacts)
    with open(a.output,'x') as f:json.dump(result,f,indent=2);f.write('\n')
    print(json.dumps(result))

```

## Owner inventory source: outcome_inventory.py
```python
"""Owner-run, read-only aggregate inventory. No predictions, refit, or raw identities."""
import collections, json, math, sqlite3, time
from pathlib import Path

DB='/opt/vivameda-crypto-early-scout/data/early_scout.sqlite'
OLD=Path('/var/lib/vivameda-engineering/repo/client_learning/crypto_alert_audit_20261003/fixed_horizon_training_export.json')
FEATURES=('band','pc5','pc1','buy_ratio','vol_mc','liq_change','vol_accel')

def main():
    old=json.loads(OLD.read_text())['rows']
    old_mints={r['mint'] for r in old}
    cutoff=max(r['decision_ts'] for r in old)
    now=int(time.time()); groups=collections.defaultdict(collections.Counter)
    seen=collections.defaultdict(set)
    con=sqlite3.connect('file:'+DB+'?mode=ro',uri=True,timeout=10)
    con.execute('PRAGMA query_only=ON')
    rows=con.execute('''SELECT c.mint,c.decision_ts,c.source,c.features,
        o.observed_ts,o.lateness,o.multiple,m.coverage_ok,m.max_gap
        FROM v2_cases c LEFT JOIN v2_outcomes o ON o.id=c.id AND o.horizon=60
        LEFT JOIN v2_horizon_metrics m ON m.id=c.id AND m.horizon=60
        WHERE c.decision_ts+3600<=? ORDER BY c.decision_ts,c.id''',(now,))
    for mint,ts,source,features,observed,late,multiple,coverage,gap in rows:
        g=groups[source];g['due_cases']+=1
        if observed is None:g['missing_endpoint']+=1;continue
        if late is None or not 0<=late<=180 or observed!=ts+3600+late:
            g['invalid_timing']+=1;continue
        if coverage!=1 or gap is None or gap>180:g['incomplete_coverage']+=1;continue
        try:f=json.loads(features)
        except (ValueError,TypeError):f={}
        if not all(type(f.get(k)) in (int,float) and math.isfinite(f[k]) for k in FEATURES):
            g['invalid_features']+=1;continue
        if type(multiple) not in (int,float) or not math.isfinite(multiple) or multiple<=0:
            g['invalid_outcome']+=1;continue
        g['eligible_cases']+=1
        if mint in seen[source]:g['repeat_eligible_mint']+=1;continue
        seen[source].add(mint);g['eligible_unique_mints']+=1
        g['positive_unique_mints']+=int(multiple>=2)
        if mint not in old_mints and ts>cutoff:
            g['new_disjoint_unique_mints']+=1
            g['new_disjoint_positive_mints']+=int(multiple>=2)
    con.close()
    print(json.dumps({'observed_at':now,'horizon_minutes':60,'old_export_last_decision':cutoff,
        'groups':dict(groups),'prospective_validation':False,
        'note':'New rows remain retrospective; capture-time feature provenance is not established.'},indent=2))

if __name__=='__main__':main()

```

Owner command (already staged on Hetzner):
```bash
python3 /var/lib/vivameda-engineering/repo/client_learning/crypto_alert_audit_20261003/outcome_inventory_20261004.py
```

