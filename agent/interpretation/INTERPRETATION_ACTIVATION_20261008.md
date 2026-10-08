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
