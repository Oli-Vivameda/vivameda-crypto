# Components and data flow

| Component | Entry point | Responsibility | External effects |
|---|---|---|---|
| Early scanner | scout/early_scout.py | Discover launches, collect pair snapshots, score 11 signals, independently recompute pre-alert policy | Public market requests; Telegram after admission |
| Candidate exporter | scout/wallet_candidates.py | Read scanner DB; queue complete mint/pair/creator identities and record deferred identities | Local JSON only |
| Wallet worker | scout/wallet_worker.py | Research lane followed by fast refresh, persistent queue and candidate-specific retries | Bounded public RPC/provider reads; local evidence |
| Screening collector | scout/full_screening.py | Authenticate pool, creator, holdings, receipts; index available histories | Public reads; SQLite and reports |
| Policy evaluator | scout/screening_policy.py | Seven PASS/UNKNOWN/REJECT evidence decisions | None |
| Protocol decoder | scout/protocol_screening.py | Supported Pump AMM/token controls and instruction decoding | None |
| Research tools | wallet_intelligence.py, wallet_analysis.py, free_risk_evidence.py, pool_screening.py | Evidence collection and HTML wallet maps | Public reads; local artifacts |
| V2 learner | scout/scout_learning_v2.py | ALERT/SHADOW cases, timed outcomes, regimes, horizon coverage | Public market reads; SQLite |
| Agent context | agent/context.py | Select dated crypto rules and model limitations for a caller's session | No network, model calls or actions |
| Numerical baseline | research/train_numerical_v1.py | Fit/evaluate an exploratory one-hour endpoint model | Local files only |
| Browser evidence | scout/dex_browser_worker.py | Capture visible evidence for review | Browser page requests; no PASS or Telegram |
| Configured-token watchlist | monitors/watchlist/watch.py | Three-token +10% observed move and rearm | Public requests and separate Telegram notices |
| Pool/developer monitor | monitors/pool-monitor/monitor.py and developer_checks.py | Configured levels, cap, liquidity, activity, authorities, accounts and vesting | Public reads and separate Telegram notices |

Public sources in the copied code: Pump launch feed, DexScreener pair API, Solana mainnet RPC, PublicNode history RPC and Rugcheck reports. Their availability and free capacity are not guaranteed. No paid-provider account is enabled by this package.

The scanner database is `/opt/vivameda-crypto-early-scout/data/early_scout.sqlite`. Candidate inbox and wallet reports live below `/var/lib/vivameda-wallet-intelligence/`. Wallet maps and raw evidence are runtime data, excluded from public Git. The full Vivameda agent, workforce models, connectors, client records and conversations are separate and are not required for the crypto scanner.

There is no automated trade execution, signing, stop-loss order manager or promoted predictive model in this source distribution.

## Research and proposal layers

The live prospective ledger is implemented in research/prediction_ledger.py and called by the scanner. Its frozen shadow probabilities do not authorize alerts. Offline DFlow/Pump candidate decoders are not integrated into the production collector. agent_trader/agent.py is a paper proposal and feedback scaffold, not a continuous trader; its local APPROVED state is not an authenticated execution approval. The separate internal paper-execution core is described in FULL_SETUP.md and is not bundled.

See [FULL_SETUP.md](FULL_SETUP.md) for the dated operating inventory and [REPOSITORY_POLICY.md](REPOSITORY_POLICY.md) for required publication updates. Runtime databases/maps remain private.
