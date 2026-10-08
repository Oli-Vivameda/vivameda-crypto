# Vivameda Crypto Lab

A continuously running Solana small-cap observation and research system on Hetzner: early-breakout discovery, on-chain wallet screening, Telegram notifications, wallet maps and forward outcome tracking.

**Start here:** [Full setup showcase](docs/FULL_SETUP.md). This repository is the public source and documentation of the crypto setup. It describes live components, offline experiments and unfinished integrations separately. It is a dated reference, not a live dashboard or a guarantee of profitable trading.

## The system at a glance

| Layer | What it does | Current status |
|---|---|---|
| Discovery and scoring | Collect launches and snapshots; score 11 signals; thresholds 8 / 10 | Live |
| Wallet intelligence | Authenticate pools/creators/holdings; index histories; draw wallet-link maps; seven screening checks | Live; cluster/age/history coverage incomplete |
| Notifications | Scanner admissions plus separate configured-token watchlist and pool/developer observations | Existing server components; source published |
| Forward learning | ALERT/SHADOW cases, timed outcomes, regimes and horizon statistics | Live V2 tracker |
| Prediction ledger | Freeze shadow predictions and later eligible labels for a prospective baseline comparison | Activated; no completed validation claim |
| Numerical model | Seven-feature logistic baseline, published coefficients and evaluation | Experimental; underperformed baseline; does not drive alerts |
| Daily case learning | Matched first-call reviews, fresh agent memory and prospective paper journal | Daily review live; journal dormant by design until the prediction ledger closes (200 eligible or 2026-11-03T06:45:43Z); population frozen |
| Dedicated Crypto Lab agent | Separate conversations, crypto-only read tools and local evidence interpretation | Isolated runtime active; generation completes, factual acceptance failed on 6 October; constrained guard installed 8 October; evidence-table postflight verified; new live 10-question acceptance pending; separate queue, storage and permissions |
| Agent context | Select dated crypto knowledge and limitations for an agent session | Public extraction; private conversational runtime excluded |
| Trading-agent layer | Paper proposal records, owner feedback and versioned playbook | Scaffold; no continuous agent or live execution |
| Transaction-decoder experiments | Offline DFlow/Pump endpoint reconciliation | Not promoted into production |
| TradingView and market movements | Account/watchlist sync plus independent BTC/SOL measurements | Watchlists verified; TradingView quotes/candles blocked; exchange adapter installed; partial fresh-price coverage; BTC/SOL windows and fresh sync verified; other spot/perpetual windows verified in owner aggregate; two real sent records; SOL absent from that export; latency and 24-hour refresh pending ([handover](docs/TRADINGVIEW_HANDOVER_20261008.md)) |
| Broad survivor discovery / live trading | Universe-wide survivor discovery and broker/wallet execution | Not implemented |

## How it fits together

```mermaid
flowchart TD
    A[Public launch and market feeds] --> B[Scanner: candidates and 11 signals]
    B --> C[Wallet queue and evidence collection]
    C --> D[Seven-check policy and wallet maps]
    D --> E[Scanner admission and Telegram]
    B --> F[V2 ALERT and SHADOW tracking]
    F --> G[Timed outcomes and research]
    B --> H[Frozen shadow prediction ledger]
    H --> G
```

The watchlist and pool monitor run separate observation rules; their messages do not inherit scanner screening. The trading scaffold is separate and is not connected to this alert loop.

## Explore the setup

| Guide | Contents |
|---|---|
| [Full setup](docs/FULL_SETUP.md) | Purpose, component inventory, schedules, agents/models, live snapshot and boundaries |
| [Signals](SIGNALS.md) | All 11 score conditions, eligibility gates, regimes and outcome labels |
| [Screening](scout/SCREENING_V2.md) | Seven decisions, freshness and admission policy |
| [Wallet operations](scout/WALLET_INTELLIGENCE.md) | Queue, RPC budgets, coverage and storage guardrails |
| [Monitor signals](docs/MONITORS.md) | Watchlist, pool levels, activity, controls, account and vesting observations |
| [Architecture](docs/ARCHITECTURE.md) | Source entry points, data flow and external effects |
| [Research](research/README.md) | Baseline result, training schema and evaluation limits |
| [Daily case learning](learning/README.md) | Matching rules, paper journal, agent integration, daily schedules and activation |
| [Dedicated Crypto Lab agent](agent/CRYPTO_LAB.md) / [Earlier activation](agent/CRYPTO_AGENT_ACTIVATION_20261005.md) / [Runtime separation](agent/runtime/RUNTIME_SEPARATION.md) / [Runtime activation](agent/runtime/RUNTIME_ACTIVATION_20261005.md) / [Interpretation repair](agent/interpretation/README.md) | Domain boundary, dedicated queue/services, installation status and model limitations |
| [Trading scaffold](agent_trader/README.md) | Paper proposals, feedback and execution integration requirements |
| [Setup](docs/SETUP.md) | Dependencies, installation, health checks and rollback |
| [Coverage](docs/COMPLETENESS.md) / [Validation](docs/VALIDATION.md) | Included source, tests and unresolved gaps |
| [TradingView handover](docs/TRADINGVIEW_HANDOVER_20261008.md) | Verified watchlist inventory, market-data errors, BTC/SOL status and agreed exchange-feed next step |
| [Update policy](docs/REPOSITORY_POLICY.md) | Required GitHub synchronization for crypto changes |
| [Security](SECURITY.md) | Public/private boundary |

## Verify the source

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt -r research/requirements.txt
.venv/bin/python -m unittest discover -s scout -p 'test_*.py'
.venv/bin/python -m unittest discover -s research -p 'test_*.py'
.venv/bin/python -m unittest discover -s agent -p 'test_*.py'
.venv/bin/python -m unittest discover -s agent_trader -p 'test_*.py'
python3 -m unittest discover -s learning -p 'test_*.py'
python3.12 scripts/verify_release.py
```

A score is not a probability. Activity age is a lower bound, not a creation date. Transfer links do not establish common ownership. Peak multiples are not realized profit. Missing evidence remains missing.

The experimental model used 42 training and 18 test tokens: Brier 0.11047 versus baseline 0.10034 (lower is better). No profitable strategy, completed prospective validation, Qwen weight training or automated trade execution is claimed.

Credentials, private live configuration, databases, messages, client material and the separate workforce stack remain server-side. Source templates do not reproduce private runtime state. Fresh-host installation remains unverified. No license grant has yet been selected.


Owner decision, Directive 2 continuation: keep the frozen journal population. The journal is **dormant by design until the prediction ledger closes (200 eligible or 2026-11-03T06:45:43Z)**. No amendment is authorized. After closure, re-check ALERT-to-writer admission under the frozen rules and publish the first non-zero aggregate; future non-zero volume is not guaranteed.

Release interpreter: Python 3.12. Other versions are explicitly refused before the release check; frozen AST scorer hashes and pilot bindings are unchanged. Directive 2 availability analysis and next protocol: [control availability](research/forward_capture/CONTROL_AVAILABILITY_20261008.md), [V2 draft](research/forward_capture/PROTOCOL_V2_DRAFT.md). Incident/alarm logging is reviewed but awaits owner installation; live acceptance and private aggregate diagnostics remain pending.
