# Prospective paper decision evaluation

Installed 5 October 2026 at 12:29:55 UTC. Direct post-install check verified the journal timer active, the new endpoint wrapper selected by ExecStart, and the first run successful (exit status 0). The first aggregate report has zero recorded decisions and zero eligible endpoints in every group; collection must accumulate before evaluation or training. Backup: /opt/vivameda-operations/crypto-endpoints-backup-20261005T122955Z. The frozen base bundle and policy remain unchanged. This evaluates paper recommendations, not filled trades.

`paper_outcomes.py` reads the saved journal and scanner market snapshots. The horizon is 3,600 seconds from the paper decision timestamp, with maximum endpoint lateness and observation gap of 180 seconds. It uses the earliest retained snapshot at/after the target, discovered before the deadline. An endpoint first discovered after the deadline stays MISSING, even if historical data later exists. No V2 alert outcome is substituted for this separate decision-time endpoint. Frozen-ledger identifiers are checked before reading market outcomes and excluded.

It appends one immutable endpoint record per mint, with decision and observation hashes, and writes aggregate `paper_summary.json`. ENTER_REVIEW, WATCH and SKIP are reported separately with recorded, pending, eligible, missing and excluded counts. Eligible endpoint >=2x and <=0.55x proportions have descriptive Wilson 95% intervals; no interval is reported for an empty group. These selected groups are observational, not randomized treatment effects, and omitted observations can bias comparisons. A price/cap multiple is not executable PnL. This is neither an exit backtest nor a profitable-strategy claim.

## Model separation and training

The crypto seven-feature logistic scorer is a separate artifact from workforce/company models and does not drive production alerts. The existing conversational runtime can serve both lanes with domain-specific context. No dedicated crypto-trained Qwen weights have been created. Daily case memory is retrieval, not fine-tuning. The first live retrieval-response check on 5 October timed out; the context wrapper is present, but a completed response remains unverified.

Collect these prospective decision-time features and endpoint labels before fitting a crypto challenger. Before any fit, freeze the target, eligible cohort, chronological development/test split and mint separation, baseline, metrics and stopping/promotion rules. Do not reuse the existing frozen-ledger cohort, select variants by its outcomes, or fine-tune the company-analysis model on token calls. Compare calibration/discrimination and coverage on untouched later observations; evaluate execution costs separately before any trading claim. Historical first-call matched analyses remain exploratory material, not prospective training labels. No fit, second model variant, automatic promotion or weight update is authorized by daily scheduling.

## Activation

18 tests passed locally and on the engineering server (12 base + 6 endpoint tests). The installer dry run validates the reviewed extension hash. The following owner command was completed at 12:29:55 UTC; retained for installation provenance:

```sh
python3 /var/lib/vivameda-engineering/repo/client_learning/crypto_daily_learning_v1/install_paper_outcomes.py --install --expected-sha256 f6bf9bfa741e3fe88f1225673b31c63054ea1514ada2c5c4597edcc260c8f1d9
```

The installer verifies the installed base digest, backs up prior extension files/drop-in, and changes only the journal service's ExecStart through a systemd drop-in. The existing approximately minute-spaced, network-isolated journal pass records recommendations then checks their endpoints. The daily reviewer, scanner, frozen policy and weights remain unchanged. Earlier decisions whose one-hour deadline expired before installation are MISSING, not retroactively scored.

Verify the journal service result and dated `/var/lib/vivameda-crypto-learning/paper_summary.json`. No eligible outcomes or real-data model improvement are claimed until verified. On rollback, stop the journal service, restore/remove its backed-up drop-in, daemon-reload and restart its timer; preserve all existing append-only evidence.

Daily supervision must review `paper_summary.json` and publish aggregate evidence/status only. The saved source and activation documentation are published alongside this guide. Publication completion requires remote hash verification; the verification receipt is kept in the engineering checkout.
