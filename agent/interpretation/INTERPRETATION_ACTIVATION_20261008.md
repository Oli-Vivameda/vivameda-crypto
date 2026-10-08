# Task 3 — reviewed candidate and activation gate

Generation completes in the installed 5 October version; factual acceptance failed on 6 October. That installed source remains unchanged by this review. This is a candidate receipt, not an activation claim.

Reviewed bundle SHA-256: `de9d4a24f43f38f2f5f7793f2365c612f3ace98b6b7843910003f07b2f154ba0`. Its eight files are the exact FILES tuple in install_factual_guard.py; FACTUAL_ACCEPTANCE.json binds the candidate agent and guard hashes. All 17 guard/agent tests passed. The final existing-local-model run scored 10/10 facts, zero invented explanations, in 29.845 seconds for one batch of ten fixed synthetic questions. Earlier development runs scored 8/10 and failed closed respectively. No production evidence, prediction-ledger contents, endpoints or identities were used.

The candidate deterministically formats numeric timestamps as ISO UTC and thresholds as strings before model input. No earlier prose is reused as model history. JSON field selection is rendered from exact evidence values; a post-generation validator rejects unknown fields, numbers, dates, free prose and causal statements outside a fixed approved list. This verifies constrained evidence selection, not unrestricted free-text interpretation. Without a matching 10/10 certificate, or on validation failure, Crypto explain returns the evidence table only. Unavailable memory also forces the table.

Owner installation in the existing server root terminal:

```bash
python3 /var/lib/vivameda-engineering/repo/client_learning/crypto_interpretation_v1/install_factual_guard.py --install --expected-sha256 de9d4a24f43f38f2f5f7793f2365c612f3ace98b6b7843910003f07b2f154ba0
```

The installer checks installed source 75b58cf4…, drains neither queued nor running work, requires an idle queue, takes a source backup, and restarts only the crypto runtime service. It preserves scanner, policy, capture pilot and model service. Failure restores prior code. Postflight runs through the existing isolated gateway and publishes only answer mode, evidence-row count, response time, source hashes and backup location.

Not verified: owner installation, activation time, backup and live gateway postflight. The available engineering connection cannot perform the required root activation. Next gate: owner install output; append its aggregate postflight receipt here. Do not call production interpretation repaired before that receipt.

## Owner activation and independent hash verification — 12:26:48 UTC

Installed reviewed bundle `1eaa0d9373e669eeb69859162236f51a3c9a210ad857ca61f0e875af2fb0b255`; 20 tests passed. Installer now waits for the runtime gateway and persists a sanitised receipt. Earlier installer attempts failed; a startup race was identified as a possible cause, not proven retrospectively. Backup: `crypto-factual-guard-ce2ck54a`.

Installed application SHA-256: `ddd57fea740ce087122482a89ad1ea65d18516f2a077264d0bc6f593b8dd2423`. Guard SHA-256: `352e9369fd986df447d172b40e3de08f6b4c4fd9bcf9d3d05adbf83cc8d7db74`. Both independently matched after installation.

Live gateway postflight: evidence_table_only, 111 evidence rows, 0.278 seconds. Scanner, policy, pilot and live-execution settings unchanged. The installed answer contract is constrained evidence selection, with evidence-table fallback and no free-text interpretation. The receipt includes the earlier synthetic candidate acceptance: 10/10 facts, zero invented explanations, 29.845 seconds. This is NOT a new ten-question live-gateway acceptance run; that remains pending. Engineering gateway access was rejected; no permissions were widened.

Next gate: the ten-question acceptance set through an authorised live-gateway access path. Activation is verified; full Task A2 acceptance is not yet closed.
