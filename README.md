# Vivameda Crypto

Solana early-breakout scanning, wallet screening, Telegram alerts, forward outcome tracking and experimental research.

**Release status:** scanner, wallet, V2 learning and crypto-agent source are published. The full live setup is still incomplete: survivor/watchlist and pool-monitor source await an owner export from protected directories. See [coverage](docs/COMPLETENESS.md). Full cluster/age evidence is not guaranteed.

## Included
- 11 equal-weight scoring signals; alert thresholds 8 and 10.
- Seven screening checks: three mandatory PASS checks; every explicit REJECT blocks; background UNKNOWN disclosed.
- Creator reconciliation, ownership census, durable wallet history indexing, clusters, activity-age bounds, maps and capacity diagnostics.
- ALERT/SHADOW forward learning, crypto-only agent context and research rules.
- Numerical training, experimental fitted coefficients, tests, configuration example and systemd units.

## Documentation
| Guide | Contents |
|---|---|
| [Signals](SIGNALS.md) | Candidate gates, scoring and regimes |
| [Screening](scout/SCREENING_V2.md) | All seven checks and thresholds |
| [Wallet operations](scout/WALLET_INTELLIGENCE.md) | Queue, budgets and coverage |
| [Architecture](docs/ARCHITECTURE.md) | Components and data flow |
| [Setup](docs/SETUP.md) | Dependencies, installation and health |
| [Agent](agent/README.md) | Standalone context integration |
| [Research](research/README.md) | Model, data schema and limits |
| [Completeness](docs/COMPLETENESS.md) | Missing protected components |
| [Validation](docs/VALIDATION.md) | Checks performed and remaining gaps |
| [Security](SECURITY.md) | Publication boundary |

## Offline checks
```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt -r research/requirements.txt
.venv/bin/python -m unittest discover -s scout -p 'test_*.py'
.venv/bin/python -m unittest discover -s research -p 'test_*.py'
.venv/bin/python -m unittest discover -s agent -p 'test_*.py'
python3 scripts/verify_release.py
```

A score is not a probability. Activity age is a lower bound, not a creation date. Transfer links do not prove common ownership. Peak multiples are not realized profit. Missing evidence stays missing.

The experimental model used 42 training and 18 test tokens and underperformed its baseline (Brier 0.11047 vs 0.10034). It is not used for alerts. No Qwen fine-tuning, automated trading or guaranteed returns are claimed.

Production credentials, keys, databases, chat records, client data and the separate workforce stack are excluded. This repository has fresh Git history. No license grant has yet been selected.
