# Full crypto setup showcase

Status reference: 5 October 2026. Maintained alongside crypto changes. For an introduction, read the repository README; for exact thresholds, follow the linked source guides. This is the Crypto Lab lane, separate from Vivameda's workforce intelligence and client delivery stack.

## Purpose and scope

The system observes early Solana small-cap launches, measures price/liquidity/activity, applies bounded on-chain risk screening and records subsequent outcomes. Telegram notifications support review. The learning layer captures both ALERT and SHADOW candidates so failed alerts and observed missed opportunities can be studied without rewriting their history. An opportunity score and an observed multiple are not a trade return.

Important code, services and evidence live on Hetzner independently of a laptop. GitHub distributes the crypto source, example configuration, tests and explanatory record. It does not host the running scanner, credentials or databases.

## Complete component inventory

| Component | Source | Function and status |
|---|---|---|
| Early scanner | `scout/early_scout.py` | Live discovery, snapshots, 11-point score and final Telegram admission |
| Candidate exporter | `scout/wallet_candidates.py` | Live local queue with mint/pair/creator identities and deferred identity reporting |
| Wallet worker | `scout/wallet_worker.py` | Live research and fast-refresh lanes, retries, persistent focus and capacity guardrails |
| Evidence collection | `scout/full_screening.py`, `wallet_intelligence.py`, `wallet_analysis.py` | Holdings, pool/creator relationships, history indexing, JSON evidence and HTML maps |
| Policy / protocol | `scout/screening_policy.py`, `protocol_screening.py`, `pool_screening.py` | PASS/UNKNOWN/REJECT evidence checks and supported protocol validation |
| V2 learner | `scout/scout_learning_v2.py` | Live cases, timed outcomes, regimes and horizon statistics |
| Prospective ledger | `research/prediction_ledger.py`; scanner integration | Frozen shadow model/baseline predictions; later endpoint labels; does not alter alerts |
| Three-token watchlist | `monitors/watchlist/watch.py` | Existing configured-token +10% observation monitor |
| Pool and developer monitor | `monitors/pool-monitor/monitor.py`, `developer_checks.py` | Existing configured price/cap/activity/liquidity observations, mint authorities, watched accounts and vesting checks |
| Crypto context | `agent/context.py`, `knowledge_cards.json` | Extracted deterministic context selection; full private conversational runtime not distributed |
| Paper proposal agent | `agent_trader/agent.py` | Offline software scaffold with feedback/playbook storage; no Qwen decision loop or continuous service |
| Numerical baseline | `research/train_numerical_v1.py`, `published_baseline/` | Experimental logistic regression; original fit underperformed |
| DFlow/Pump experiments | `scout/dflow_*`, replay/freeze scripts | Offline candidate decoders and paired cache diagnostics; not deployed |
| Browser evidence helper | `scout/dex_browser_worker.py` | Optional evidence capture; always HOLD; fresh installation unverified |
| Operator connector | `scripts/wallet_ops.py`, installer and diagnostics tests | Public wallet-operation extension for the existing private server connector; not the complete connector |
| Legacy learner | `legacy/scout_learning.py` | Archived retrospective source; not the current prospective label source |

## Running jobs and timing

| Job | Schedule / budget | Result |
|---|---|---|
| Scanner | Launch refresh about 20 seconds; scoring about 60 seconds | Candidate scores and screened notifications |
| Candidate exporter | Approximately every minute | Persistent wallet inbox and pending identities |
| Wallet research | 60 RPC requests / 90 seconds per scheduled research lane | Indexed histories and screening evidence |
| Wallet fast refresh | 20 RPC requests / 45 seconds; follows research | Fresh mandatory checks; idle/deferred lanes may make no calls |
| Wallet worker timer | Approximately two minutes after completion | At most 80 requests across the scheduled pair of lanes |
| Watchlist | Exported oneshot timer approximately every minute | +10% from persisted armed reference, then rearm |
| Pool monitor | Continuous configured polling; source accepts 15-60 seconds | Pinned-token observations with cooldown/outbox state |
| V2 outcomes | Horizons 1, 5, 15, 30, 60, 120, 180, 360, 720, 1440 minutes | Timed outcome records and coverage-aware statistics |

Monitor settings in the repository are examples. Earlier server observations recorded 20-second pool polling and 900-second cooldown; this publication does not reverify private live configuration. Service templates are installation aids, not a dump of every live systemd override.

## Signals and screening

The 11 equal-weight signals cover liquidity, volume relative to market cap, buy ratio, restrained short-term price changes, compact price range, constructive net change, higher lows, liquidity stability, volume acceleration and transaction activity. Score 8 triggers EARLY SCOUT and 10 PRE-BREAKOUT only after admission. Exact definitions and discovery eligibility are in [SIGNALS.md](../SIGNALS.md).

Seven screening checks examine wallet links, developer history, ownership concentration, wallet activity age, token controls, liquidity control and trading mechanics. The scanner independently recomputes policy from evidence no older than 300 seconds: token controls, liquidity control and trading mechanics require PASS; every explicit REJECT blocks; background UNKNOWN is disclosed and non-blocking under current policy. The collector's all-seven verdict is distinct from scanner admission. See [SCREENING_V2.md](../scout/SCREENING_V2.md).

Wallet maps visualize observed links and reasons. They do not certify beneficial ownership, independence of people or complete lifetime history. Full holder census and full historical transaction coverage are different requirements. Cluster, developer and age evidence can remain UNKNOWN even when other checks pass.

The watchlist and pool/developer monitor have separate signal rules documented in [MONITORS.md](MONITORS.md); their observations do not carry scanner screening. Broad universe-wide multi-day survivor discovery is not implemented. The three-token watchlist is not that feature.

## Models, agents and learning

Production ranking is deterministic scoring. The seven-feature logistic model is experimental: 42 training tokens and 18 later test tokens; Brier 0.1104709613 versus 0.1003401361 baseline; log loss 0.4430391655 versus 0.3591023452 baseline. Both metrics favor the baseline. The outcomes had been inspected; this is exploratory evidence, not a sealed result. No confidence intervals are supplied by that published evaluation, and none are invented here.

The prospective shadow ledger was activated on 4 October 2026 at 06:45:43 UTC. The frozen record targets 200 eligible observations with a deadline of 3 November at 06:45:43 UTC. Previously seen mints are excluded. Missing or late endpoints stay excluded; global ATH is not used to fill missing labels. No completed validation or successful model promotion is claimed. See [ledger activation](../research/LEDGER_ACTIVATION_20261004.md).

Agent context selects dated knowledge; it is not new model weights. The paper proposal scaffold records evidence hashes, thesis, exit-plan text and ACCEPT/REJECT/EDIT feedback. Feedback versions a playbook; it does not fine-tune Qwen. It does not autonomously read feeds, choose trades or execute orders. An APPROVED feedback state is not an authenticated execution approval.

A separate internal paper-execution core exists on the server. Its documented scope includes synthetic limit orders, authenticated approval verification callbacks, reservations, partial fills, fees, pause and reconciliation. Its source is outside this crypto distribution. There is no deployed owner approval UI, trusted live quote adapter, broker connection, signing wallet or continuous trading service. Exit-plan text is not a stop-loss order. See [trading scaffold](../agent_trader/README.md).

## Live evidence snapshot and known limits

Direct server check on 5 October around 04:39 UTC found the scanner and V2 learner active; wallet timers active, with the intelligence service starting a collection pass. Source hashes for scanner and V2 learner matched this release. Counts: 199,451 launches; 23,628 snapshots; 699 V2 cases; 6,089 timed outcomes; 8,006 evaluations. These are collection counts, not independent trades, successes or a profitability denominator.

The latest saved worker verdict was HOLD with wallet links, developer history and activity age UNKNOWN; ownership, controls, liquidity and trading mechanics PASS. A recorded research pass observed 62 of 1,254 required owners and zero complete-fresh owners. That candidate-specific snapshot is not an estimate of population coverage. Complete cluster/age evidence is still unresolved.

The 5 October storage patch raised the top-level evidence-file cap from 2 to 4 GiB and retained the 3 GiB free-disk reserve; collection resumed. It does not solve RPC throughput, history freshness or unsupported transaction semantics. Source commit and deployment receipt are in [capacity notes](../scout/EVIDENCE_CAPACITY_20261005.md).

The frozen offline DFlow/Pump convenience cohort matched endpoint amounts in 238 of 243 transactions, versus 156 baseline, with five unresolved and no baseline regressions. It remains development evidence, not representative history coverage or a promoted production decoder.

## Public distribution and private operation

Published: crypto source, monitor source, tests, example configuration, units, model coefficients/evaluation, ledger protocol and decoder research. Private: credentials, live configuration/state, runtime evidence/maps/databases, messages, backup contents, private captures, workforce/client material and the full conversational agent/server connector. Runtime files are not required to understand the design, but their absence prevents reconstruction of current private state and independent reproduction of the original fit.

Fresh-host installation and real message delivery have not been reproduced as part of this publication. Optional browser capture is not established as a live service. No user capital is allocated by the scaffold. The repo explains the whole crypto setup and its dependencies without claiming that every private cross-market component is bundled.

## Review and operation

Use [SETUP.md](SETUP.md) for offline checks and named service installation, [ARCHITECTURE.md](ARCHITECTURE.md) for entry points, [COMPLETENESS.md](COMPLETENESS.md) for distribution scope and [VALIDATION.md](VALIDATION.md) for test provenance. Do not enable archived units indiscriminately. Reviewed deployments preserve backups, hashes and existing thresholds; UNKNOWN is never cleared to force an alert.

Every crypto code, rule, model, configuration behavior or deployment change must be reflected in GitHub under [REPOSITORY_POLICY.md](REPOSITORY_POLICY.md). New experiments must be labelled offline until actually deployed; stale historical records remain dated and point to current status rather than being rewritten as successful outcomes.
