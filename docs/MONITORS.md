# Exported monitor components — 4 October 2026

These are the existing server sources, not newly invented survivor logic. No running service was changed by this publication. No credentials, live configuration, state, databases or messages are included.

## Signals

| Component | Trigger or behavior | Interpretation |
|---|---|---|
| Three-token watchlist | JEANPHIL, 20xx, CHIIKAWA; price >=110% of persisted armed reference; rearm at notified price | Observed move only; first observation sets reference |
| Pool price levels | Upward crossing of configured level; configurable rearm percent and cooldown | Startup/gap above a level produces baseline notice, not a claimed crossing |
| Pool market-cap targets | First qualifying observation at/above target, or strictly above when configured | One-shot state persists across gaps/restarts; FDV never substitutes for market cap |
| Pool liquidity | USD liquidity <=85% of observation about five minutes earlier | Valuation can change; LP removal is not verified |
| Pool activity | Earlier five-minute volume >=100; current >=2x earlier; >=20 transactions; buys >=60%; rising price >=95% of lowest watch level; liquidity >=95% of reference | Counts are not unique buyers; holders/security remain unverified |
| Feed health | Failure lasts >=60 seconds; optional recovery and six-hour heartbeat | Signals blocked when identity/data checks fail |
| Mint controls | Mint/freeze authority active initially or newly changed to active address | Authority observation, not creator verification |
| Watched accounts | Verified account balance falls >=0.1% of current supply | Does not establish a sale |
| Streamflow vesting | Changed risk flags, withdrawals or terms; remaining cliff amount available/within 24h/within 7d | Unlock eligibility and withdrawals do not establish sales |

Pool identity pins chain, DEX, pool, base mint and quote mint. Responses with HTTP cache Age over 60 seconds, or an HTTP date more than 120 seconds from the local clock, are rejected. Provider quote time is unavailable. Price observations alone cannot certify a token. `marketcap_only` suppresses other market-data notices for that token; developer observations are a separate component.

Developer checks verify token-program ownership, mint/account identity, Streamflow program/layout and expected mint/sender/recipient/escrow. Missing or mismatched evidence is UNKNOWN. An empty developer registry checks mint controls only and leaves creator identity unverified. Maximum batch is 100 unique accounts. The worker backs off on failures.

The simple watchlist validates returned pool address but has less complete identity guarding than the pool monitor. It performs network and notification work at module top level: do not import it as a harmless library. Its generic error log can contain provider exception text; keep runtime logs private.

## Files and setup

- `monitors/watchlist/watch.py` installs at `/opt/vivameda-crypto-watchlist/watch.py`; requires Python standard library and `/usr/bin/curl`. Credentials (`bot_token`, `chat_id`) and state/logs live beside it. The exported timer runs a oneshot approximately every 60 seconds.
- `monitors/pool-monitor/monitor.py` and `developer_checks.py` install together at `/opt/vivameda-crypto-pool-monitor/`. They use the Python standard library. Supply `config.json`, `developer_watch.json` and mode-600 `credentials.json` locally. Database/outbox state lives in `data/`.
- Both units require a dedicated `vivameda-monitor` system user/group and writable respective directories. Review/install only their named service/timer files from `deploy/`, run `systemctl daemon-reload`, then enable only the desired component after configuration. Do not install every unit indiscriminately.
- Pool configuration requires provider (`dexscreener` or `geckoterminal`), poll_seconds (15–60), max_gap_seconds, rearm_percent, cooldown_seconds, alert_ttl_seconds, retention_days, and 1–20 enabled tokens. Each token needs name, chain (`solana`), contract, pool, dex and quote, plus levels, marketcap_levels or monitor_only. Optional controls include marketcap_strict_above, notifications, notify_recovery and notify_heartbeat.
- `config.example.json` is intentionally disabled and will fail validation until real pinned identities are provided. Its numeric choices are examples, not exported live settings. Copy `developer_watch.example.json` to `developer_watch.json`; `{}` provides no verified creator accounts/vesting coverage. Add entries only after independently verifying their identities against the decoder's required schema.
- `--dry-run --once` suppresses Telegram and uses `dryrun.sqlite`, but still calls providers and writes state. It is not an offline test. `--test-alert` sends a real message. Neither was run during this publication.

## Legacy source

`legacy/scout_learning.py` and `deploy/vivameda-scout-learning.service` are archived for reproducibility. Do not enable the legacy service as part of the current installation. It uses provider/global ATH in peak labels and retrospective reconstruction. Those labels must not feed the prospective ledger or justify model improvement. Use the active V2 tracker and frozen live-ledger protocol instead.

Fresh-host installation and live message delivery remain unverified in this publication pass. Syntax checks establish parseability only.
