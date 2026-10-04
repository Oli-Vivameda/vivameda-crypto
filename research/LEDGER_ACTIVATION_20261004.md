# Prospective ledger runtime amendment — 2026-10-04

Owner requested live activation. This implementation amendment supplements, without editing, the frozen specification in CRYPTO_AUDIT_20261004.md.

The deployed runtime lives in scout/early_scout.py and scout/scout_learning_v2.py because the reviewed deployment mechanism installs those two files. research/prediction_ledger.py remains the earlier standalone storage prototype; it is not the production runtime.

## Enrollment and provenance

Activation is an atomic SQLite transaction. Every mint already in launches, snapshots or V2 cases is excluded, and the exclusion-set count and SHA-256 are frozen. Activation records the full fixed model, its canonical-JSON hash, preprocessing source hash, frozen-plan document hash, UTC start and 30-day deadline. Restart reuses activation; it never resets the cohort.

The scanner copies the exact history rows used at scoring time and records their local capture timestamp. After existing screening passes, before attempting Telegram delivery, it commits numerical inputs, raw source rows and their hash, both probabilities, entry market cap, decision time, and model/preprocessor hashes. These are local knowledge-time records, not a claim that provider timestamps establish an earlier observation time. Historical minute-bucket timestamps remain in the raw input unchanged.

Each new mint gets one attempt. Invalid first attempts remain exclusions and cannot be replaced by a later valid attempt. The model is the existing seven-feature logistic regression; the comparison probability stays 3/42. No fit or model selection occurs.

An ALERT means the scanner's admitted decision, not successful Telegram transport. Delivery success/failure is appended separately. Failed delivery does not erase or replace the decision. Ledger errors stop the evaluation and log the failure while preserving existing scanner alert behavior. Alert thresholds and screening gates are unchanged.

## Outcomes and stopping

Valid predictions create dedicated LEDGER_ALERT cases. Existing V2 fetching tracks them without a new provider or paid calls. Their only endpoint is 60 minutes; they are excluded from legacy challenger summaries and cease tracking once the endpoint is saved or its 180-second allowance expires. Historical ALERT and SHADOW cases are never imported into the ledger.

Matching requires exact decision + 3,600 + lateness timestamps, lateness 0–180 seconds, coverage_ok=1, maximum gap <=180 seconds and positive finite market cap. Missing checkpoints stay missing. Labels use the observed endpoint multiple, never lifetime or provider ATH.

The cohort is selected in decision order. Enrollment stops when the first 200 eligible decisions are resolved, with every earlier decision resolved or excluded, or at the 30-day deadline. Overlapping decisions can already be in flight when the 200th eligible case resolves. The immutable stop receipt records cutoff_seq; predictions beyond that sequence are operational records and must be excluded from the primary sample. A time-limit stop waits for already enrolled cases to mature. Matching continues after enrollment stops. No comparative scores are logged and no automatic promotion occurs.

## Integrity and operational verification

SQLite transactions and unique constraints serialize enrollment. Triggers reject ordinary updates/deletions of ledger tables. Events form a SHA-256 chain; activation and health logs expose chain-head receipts for external retention. A privileged database owner can still rewrite the database or truncate a tail; this is not cryptographic protection against the owner. Preserve off-server receipts and backups for independent comparison.

The existing deployment takes a source and SQLite backup before activation. Operational health logs show activation time, deadline, exclusion count, record counts, matched/eligible counts, stop reason and chain head without comparative scores or positive-rate summaries.

## Data assessment preceding activation

Owner-run inventory at 2026-10-04 06:20:28 UTC: ALERT 75 eligible unique tokens, including 15 new/disjoint tokens and one new positive; SHADOW 328 eligible unique tokens, including 141 new/disjoint tokens and six new positives. ALERT exclusions: 55 missing endpoints and six incomplete histories. These remain retrospective and are excluded from prospective enrollment by the activation snapshot.

## Verification

Seventeen integration tests cover capture timing, exact V2 feature equivalence, duplicate and old-token exclusions, restart identity, immutable records, endpoint timing/coverage, missing outcomes, the 30-day deadline, ordered 200-case stopping, event hashes, tracking duration, and persistence before successful or failed Telegram delivery. Full server-suite results and the deployment receipt are recorded in MANIFEST.json after deployment.
