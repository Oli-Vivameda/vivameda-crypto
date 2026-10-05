# Daily crypto case learning

Status: 5 October 2026. Installed at 12:11:52 UTC; both timers active and first review/journal runs verified successful. The daily ChatGPT supervision task is enabled for approximately 09:00 Cyprus time, starting 6 October. It checks operation, reviews evidence and updates GitHub. It is separate from the server timers and cannot substitute for installation.

## What changes

The existing crypto agent receives a fresh, bounded case-memory summary when a new crypto worker answers a question. Historical first calls are compared with failures in the same regime, similar score, cap, liquidity, age and call time. A separate prospective paper journal saves current market snapshots, screening evidence, timestamps and policy hashes for ENTER_REVIEW / WATCH / SKIP recommendations. No orders are placed.

The daily review runs at 08:00 Asia/Nicosia after installation. The paper journal runs about 60 seconds after its previous pass completes. Both use local data only, no network or provider purchases, and read the scanner database in read-only mode. The installer leaves scanner rules, model coefficients and existing services unchanged. Already-running conversational workers need a new process to load the context wrapper.

## Evidence boundaries

- Exclude every mint in `pl_predictions`, regardless of outcome or eligibility. Never read `pl_results` or model probabilities.
- Review the earliest retained ALERT per mint. SHADOW and LEDGER_ALERT rows are not included.
- A matched winner has a valid 60-minute endpoint >=2x; a matched failure <=0.55x. Matching uses the fixed calipers in policy.json and does not reuse a failure control.
- Require checkpoint coverage, exact observed time and lateness <=180 seconds. Missing endpoints remain missing. Tracked peaks are displayed as descriptive cases, never lifetime ATH or realized returns.
- Historical features are reconstructed, their capture-time knowledge is unestablished, and historical policy versions are unknown. Feature differences are exploratory, not causal findings or validated entry rules. No significance or confidence interval is invented.
- New paper decisions must be recorded within 180 seconds of an alert and after activation, with a snapshot <=120 seconds old. They occur at their own decision time, not retroactively at the alert time.
- ENTER_REVIEW requires all seven screening checks to PASS with fresh evidence references and matching mint/chain/pair, plus the frozen paper market filter. Missing, stale or invalid evidence yields WATCH; explicit screening REJECT yields SKIP. This is stricter than production scanner admission and does not change that admission.
- No execution quote, fill, exit simulation or net PnL is supplied. ENTER_REVIEW means a paper research candidate, not a buy order.

## Source and state

| File | Purpose |
|---|---|
| daily_learning.py | Read-only case review and append-only prospective journal |
| policy.json | Frozen matching and paper recommendation rules |
| context.py | Bounded crypto context; rejects stale (>36h), future or invalid memory |
| install_daily_learning.py | Hash-locked fixed-path owner installer with backups and network-isolated systemd jobs |
| test_daily_learning.py | 12 tests covering leakage exclusion, timing/coverage, policy freeze, stale data, current journal and agent patch |

Production state is `/var/lib/vivameda-crypto-learning/learning.sqlite`. It stores daily reviews, decisions and a sequential hash-chain event record. SQL triggers reject UPDATE/DELETE; this is tamper evidence, not protection against a privileged database administrator. `latest_memory.json` is a bounded local retrieval summary. `public_summary.json` contains aggregate counts only. Private case records and runtime databases stay off GitHub.

The policy hash is locked when state is first created. Daily runs do not fit weights or alter policies. Owner feedback can inform a separately reviewed amendment after adequate prospective evidence; it does not automatically fine-tune Qwen. A failure to produce valid memory leaves the agent on its existing context, not a fabricated result.

## Install the reviewed bundle

Engineering-server tests passed: 12/12. Installer validation passed without changing production. Run this once in the existing owner maintenance terminal:

```sh
python3 /var/lib/vivameda-engineering/repo/client_learning/crypto_daily_learning_v1/install_daily_learning.py --install --expected-sha256 d63bc98534fa81af7357a6c9b802e1d4ae7ea20578b61538c62b0601a0207a9e
```

The digest covers the five implementation/test files, in the installer-defined order. It does not cover this README. The installer backs up the conversational source, previous learning files and units in `/opt/vivameda-operations/crypto-learning-backup-*`, creates the first local review and enables both timers. If installation fails, report the exception and backup path; do not assume activation completed. Deployment verified on 5 October at approximately 12:12 UTC: both timers active; both service runs Result=success and ExecMainStatus=0. The initial review contains 139 development tokens, 78 eligible 60-minute endpoints, 61 missing/incomplete endpoints and six exploratory matched pairs; eight frozen-ledger identifiers excluded. These are case counts, not independent trades or demonstrated profitability. Backup: /opt/vivameda-operations/crypto-learning-backup-20261005T121152Z. Full source publication remains pending because browser upload timed out and the connector write was denied.

Verify activation and fresh-context retrieval after installation:

```sh
systemctl status vivameda-crypto-review.timer vivameda-crypto-journal.timer --no-pager
systemctl status vivameda-crypto-review.service --no-pager
journalctl -u vivameda-crypto-journal.service -n 20 --no-pager
```

The review service is a oneshot and can be inactive after a successful run; check its exit status, timer and dated memory. Confirm a new crypto agent worker reports the dated summary and its limitations. To stop learning, disable both timers; restore backed-up conversational source if reverting the integration. Existing scanner and wallet services continue independently.

## Offline checks

```sh
python3 -m unittest discover -s learning -p 'test_*.py' -v
python3 learning/install_daily_learning.py --expected-sha256 d63bc98534fa81af7357a6c9b802e1d4ae7ea20578b61538c62b0601a0207a9e
```

Daily GitHub updates should publish dates, aggregate evidence coverage, service/test receipts and any reviewed source changes. They must distinguish case-memory updates from trained weights and pending installation from verified operation.
