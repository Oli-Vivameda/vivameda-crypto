# Full crypto setup showcase

Operational status reference: 8 October 2026, with separately dated snapshots below. The 5 October snapshot is historical. TradingView/market-monitoring addendum: 8 October 2026; see the dated handover below. Maintained alongside crypto changes. For an introduction, read the repository README; for exact thresholds, follow the linked source guides. This is the Crypto Lab lane, separate from Vivameda's workforce intelligence and client delivery stack.

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

## Live evidence snapshot — 8 October 2026

Read-only server check at approximately 11:07:46 UTC: scanner and V2 learner active; deployed scanner SHA-256 `765aba08982c3f0c562b52755ab9122cdaabfc396b78e7fed878089db87fa54e` and tracker `a519ad19680ba72f0d593c4627fe5faa2d8dfa93fcd112eaba21abcf5a6da9b6`. Aggregate retained counts: 377,192 launches; 19,698 snapshots; 1,340 V2 cases/state entries; 12,099 timed outcome records; 15,427 evaluations. Record counts alone reveal no outcomes or model performance. No prediction-ledger predictions, probabilities or labels were read. Snapshot retention means these counts need not grow monotonically.

Pilot health at 10:32:27 UTC: collecting; 315 accepted cycles, 2,613 rejected, 21 qualified events, three matched events, five controls. Closed qualified windows 20/20 covered; closed control windows 5/5 covered. Last successful cycle 10:30:53 UTC, 94 seconds before the report. Constant cumulative-rate projection is about 136 qualified events by the unchanged 20 October 06:50:39 UTC deadline; only about 19–20 matched events at the observed match fraction. Stationarity is unverified. Counts and draft next design: [pilot status](../research/forward_capture/STATUS_20261008.md). Pilot health was installed 6 October at 07:37 UTC, backup crypto-health-backup-20261006T073739Z; no reinstall or pilot change is requested.

The paper journal timer ran successfully but still reports zero ENTER_REVIEW, WATCH and SKIP decisions. Engineering cannot read the protected source database; [sanitised owner export and diagnosis](../learning/JOURNAL_DIAGNOSIS_20261008.md) await gate counts. Source shows the seven-PASS requirement applies to ENTER_REVIEW, not WATCH/SKIP. No unproven journal fix was deployed.

Crypto agent generation completes; its 6 October factual acceptance failed. The 8 October constrained candidate passed 10/10 fixed facts, zero invented explanations, 29.845 seconds for one batch, and 17 tests. Owner activation and production postflight are pending: [candidate receipt](../agent/interpretation/INTERPRETATION_ACTIVATION_20261008.md). No unrestricted-prose acceptance claim is made.

TradingView synced three watchlists freshly at 11:00:28 UTC: 61 account symbols, 53 crypto and eight non-crypto. Exchange snapshot at 11:04:26 UTC: 37 fresh prices, 16 unavailable. BTC/SOL each had 35 retained samples and complete below-threshold forward windows. Other spot/perpetual windows, exact unavailable-list owner review, a real alarm with measured delivery delay and 24-hour refresh survival remain pending. Synthetic Telegram test sent; real alarm verified=false. See [movement validation receipt](TRADINGVIEW_HANDOVER_20261008.md).

## Historical snapshot — 5 October 2026 and known limits

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

## Daily case-memory learning (activated 5 October)

[Daily learning source and activation guide](../learning/README.md) adds a local matched first-call review, a prospective paper decision journal and a fresh-memory wrapper for the existing crypto agent. Twelve engineering-server tests passed; production activation was verified on 5 October at approximately 12:12 UTC. A daily supervision automation is enabled around 09:00 Cyprus time starting 6 October; server review at 08:00 and paper journal approximately every minute are enabled following installation.

Every frozen-ledger mint is excluded before development outcomes are queried. Matching uses eligible 60-minute endpoints and fixed regime/score/cap/liquidity/age/time calipers. Historical reconstructed features remain exploratory. New paper recommendations save contemporaneous snapshots and screening references; all seven fresh checks must PASS for ENTER_REVIEW. This stricter paper filter does not alter scanner admission. Case memory does not imply newly trained weights, a demonstrated trading edge or live execution. Public daily updates contain aggregates and deployment receipts, not private runtime records.

The decision-time endpoint extension was activated at 12:29:55 UTC on 5 October. Its first run exited successfully; initial aggregate counts were zero in every action group. See [endpoint evaluation](../learning/PAPER_EVALUATION.md) and [activation receipt](../learning/ENDPOINT_ACTIVATION_20261005.md). No training or execution was enabled.

## TradingView and BTC/SOL movement monitoring (8 October)

[TradingView handover](TRADINGVIEW_HANDOVER_20261008.md) records authenticated server access and retrieval of three watchlists: 63 unique monitored symbols, including 55 recognized crypto symbols and core BTC/SOL pairs. This inventory does not establish fresh market-data coverage. A focused quote request returned HTTP 429; a candle request returned a WebSocket handshake failure. The underlying provider cause is unverified.

The independent Coinbase BTC/SOL movement monitor remains operational. TradingView-based added-coin alarms remain unverified. The owner agreed to keep TradingView for watchlist synchronization and use direct exchange feeds for movement alerts. The corrected exchange adapter is installed and passed 62 engineering tests plus five live public ETH price probes. Installation recorded 40 fresh prices among 53 crypto symbols across three account watchlists (61 total symbols); 13 had explicit availability gaps. A subsequent cycle reported 39 fresh / 14 unavailable. The labelled synthetic Telegram test was sent. These installation snapshots are historical. The 8 October live snapshot above verifies BTC/SOL windows and fresh post-restart synchronization; other symbol-class windows, long-duration refresh and real threshold-triggered delivery remain unverified. Live trading is disabled.

## Astra continuation protocol — 8 October directive

The five tasks were processed in order, each with a published receipt before the next began. A preliminary receipt can expose an unresolved owner gate; it is not evidence of completion. Keep all pending checks pending until new dated evidence arrives. Do not create another handover document; append receipts to the deliverables below and update MANIFEST.

| Task | Receipt and verified facts | Pending evidence / next gate |
|---|---|---|
| 1 — forward pilot | `research/forward_capture/STATUS_20261008.md`; collecting; 315 valid / 2,613 rejected cycles; 21 qualified, three matched, five controls; closed qualified 20/20 and control 5/5 coverage; constant-rate projection about 136 qualified / 19–20 matched. | Exact rejection-code distribution and complete health notification history are unavailable in the existing sanitised report. Do not reconstruct them from outcomes or treat stalled snapshots as sent incidents. Preserve the original pilot and deadline. Next design is a draft only. |
| 2 — paper journal | `learning/JOURNAL_DIAGNOSIS_20261008.md`; successful timer, zero decisions in all three groups; WATCH/SKIP writer is independent of the all-seven-PASS ENTER_REVIEW gate. Six export tests and 24 learning tests pass. | Owner runs the sanitised count exporter with bundle SHA-256 `bf80b0818fb0e648fffe4f13dc30f9dcd380d246ac1bca3a144b7a462a695f3e`. Distinguish retained source cases per day from historical actual ingestion, which was not logged. Establish the dropping gate before proposing a reviewed policy-preserving fix; require its installed first non-zero aggregate. No fix is yet justified or installed. |
| 3 — interpretation | `agent/interpretation/INTERPRETATION_ACTIVATION_20261008.md` and `FACTUAL_ACCEPTANCE.json`; candidate 10/10 fixed facts, zero invented explanations, 29.845 seconds; 17 tests. Bundle `de9d4a24f43f38f2f5f7793f2365c612f3ace98b6b7843910003f07b2f154ba0`. | Owner install through the command in the receipt; require backup, deployed agent/guard hashes and isolated gateway postflight. Production remains the prior version until that receipt. Only constrained evidence selection passed; never claim unrestricted prose verified. Missing certificate or validation mismatch must return the evidence table. |
| 4 — movements | `docs/TRADINGVIEW_HANDOVER_20261008.md`; BTC/SOL complete forward windows; fresh post-restart watchlist sync 11:00:28 UTC; three lists, 61 symbols; 37 fresh / 16 unavailable at the dated check; synthetic Telegram test sent. | Owner runs the aggregate class/reason export and privately reviews the exact unavailable list. No adapters added; any proposal needs owner approval and must respect no-new-provider scope. Require other spot/perpetual measuring evidence, first real threshold alarm with separately measured latency, and fresh sync after 9 October 10:20 UTC plus actual refresh evidence for the 24-hour claim. Existing state has no acknowledgement timing and cannot retrospectively measure delay. |
| 5 — written record / release | Corrected completion-versus-factual-acceptance claims, synthetic-versus-real Telegram flags, health installation records and dated snapshots. Tests explicitly bind frozen fixtures; deployed source is unchanged. `scripts/verify_release.py` now runs every test directory in a separate process and fails on any red suite. Clean public checkout on engineering Linux: 437 tests across 13 suites, 199 hashes, 17.655 seconds, all passed. | Publish this record repair as one final commit on main and compare the remote bytes/hashes of every changed file with the reviewed local candidate. Local restricted workspace cannot run the Unix-socket test and lacks requests; it correctly blocks release there. Server clean-checkout verification is the passing release evidence. |

Astra starts by checking the published main commit and MANIFEST hashes, then reads each receipt's evidence date and next gate. Reuse existing permissions and owner export paths; never chmod protected data or route around denied access. Owner installation is a gate, not a request to modify the pilot. On any changed source hash, stop that installation path and review the concurrent change. Publish only aggregate counts, fixed reason codes, hashes and receipts; keep exact unavailable symbols and all private rows in the owner's private view.

Scanner thresholds remain 8/10; screening, eleven signals and weights stay frozen. The prediction ledger remains sealed until its stop rule; do not inspect predictions, probabilities or labels. Do not extend/restart/reactivate the pilot, alter its protocol or backfill endpoints. No paid calls, new providers, signing or live orders. These constraints carry into every continuation step.
