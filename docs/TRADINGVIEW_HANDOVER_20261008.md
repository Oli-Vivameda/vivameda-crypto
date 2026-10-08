# TradingView connection and market monitoring — 8 October 2026

Evidence cut-off: 08:19 UTC (11:19 Cyprus). This is a dated operational handover, not a live dashboard.

## Verified state

| Component | Evidence and status |
|---|---|
| Independent server connection | TradingView OAuth client runs on Hetzner. After the restart repair, authenticated initialization succeeded without another browser approval. Long-duration refresh remains unverified. |
| Watchlist retrieval | Three account watchlists were read. The monitored universe contains 63 unique symbols, including 55 recognized crypto symbols and the monitor's core BTC/SOL pairs. These are inventory counts, not confirmed price coverage. |
| TradingView quotes | A focused BTC batch-quote request returned HTTP 429 from TradingView's API. |
| TradingView candles | A focused BTC candle request returned `failed to fetch bars: tvws: dial: websocket: bad handshake`. |
| Existing BTC/SOL monitoring | The separate Coinbase spot monitor remains operational; the latest check had 35 retained samples per product, both below configured movement thresholds. |
| Other watchlist coin alarms | Fresh prices and end-to-end Telegram movement delivery remain unverified. |
| Trading | Live execution remains disabled. |

The errors were returned by the official TradingView MCP tools. The underlying reason for the rate limit and handshake failure is unknown. Do not infer that every symbol is unavailable from the single-symbol diagnostic, or that authenticated access proves working market data.

## Installed engineering

The server client uses a fixed allowlist of four read operations: watchlist listing, watchlist retrieval, batch symbol data and OHLCV. Discovery now resolves the observed hyphenated tool names. Quote-tool failures are recorded explicitly and do not abort subsequent candle checks. Candle checks remain sequential; the first full data pass was still running at the last server check.

The OAuth restart correction restores saved token expiry and the approved provider's validated refresh metadata before the SDK refresh flow. Authorization material stays in private server storage. This does not prove indefinite unattended operation.

The latest installed application SHA-256 is:

`1d1f638eb74a9ef263f03d3881e813711b13721da7d979448d0845949b37b5db`

Reviewed restart bundle SHA-256:

`3026ab6e49d1daf82692e76a429aca6a6983187b524ae648d23fbb22ca1d498f`

The owner reported successful installation. The engineering suite passed **38 tests**, including observed tool names, partial-provider failures, expiry restoration and refusal of an unexpected refresh endpoint. These fixtures do not establish live provider coverage.

This update publishes the operational record. TradingView's cross-market connection source and private integration configuration remain in the server engineering checkout; this document is not a complete source release of that integration.

## Current movement rules

The independent Coinbase monitor measures BTC at ±1% and SOL at ±2% over a forward-observed 15-minute window, with a 30-minute cooldown. TradingView's added-coin worker is configured for ±2% over the same window and cooldown; exact core BTC/SOL symbols retain their existing delivery to avoid duplicate alarms.

The worker requests fresh source timestamps, refuses stale candles and gaps, and does not backfill a movement window. Non-crypto watchlist symbols receive quote snapshots only. Configured rules are not a claim that TradingView movement alarms currently work.

## Agreed next implementation

On 8 October, the owner agreed to retain **TradingView for watchlist synchronization** and use **direct exchange feeds for movement detection and Telegram alarms**. The exchange-feed adapter for the full TradingView watchlist is **planned, not built or deployed**.

The next implementation must:

1. Resolve each watchlist symbol to a verified venue/pair, preserving quote currency and instrument type. Ambiguous or unsupported symbols stay unavailable.
2. Use documented exchange feeds with bounded request budgets, backoff and source freshness checks. No new paid service or live trading is enabled.
3. Keep BTC/SOL's existing monitor and avoid duplicate alarms.
4. Report synchronized inventory separately from fresh-price coverage, unavailable symbols and alert-delivery status.
5. Verify actual collection cadence supports the forward 15-minute window; preserve missing samples and timestamp gaps.
6. Validate symbol coverage and a controlled Telegram delivery check before declaring full-watchlist monitoring operational.

The production small-cap scanner's thresholds remain 8 / 10. Existing scanner screening and learning gates are not changed by this work.

## Implementation addendum — 8 October, after the evidence cut-off

The direct-exchange candidate is now built and validated in the engineering checkout; it is **not installed**. Earlier runtime observations above remain dated.

- 62 tests passed, including exact identity, spot/perpetual distinction, stale data, missing windows, rate limits, restart cooldown persistence, symbol removal/re-addition, owner-only coverage and the labelled synthetic notification path.
- Live public ETH probes from Hetzner returned fresh trades for Binance spot and USD-margined perpetual, Coinbase spot, and Bybit spot and linear perpetual markets. All five succeeded. Actual account watchlist price coverage and real Telegram delivery remain unverified until installation.
- Watchlist synchronization and exchange sampling run independently. Inventory refreshes every 10 minutes; collection targets once per minute, with concurrency four and a 45-second price-pass deadline. Saved inventory may bridge an authorization outage up to 24 hours, with age reported.
- Exact venue, quote currency and instrument type are retained. Unsupported venues, inactive/unlisted pairs and synthetic indices stay unavailable; no silent substitution. Bybit inverse perpetual parsing is implemented but was not live-probed.
- BTC uses ±1%; SOL and other coins ±2%, over a forward-observed 15-minute window and 30-minute attempt cooldown. Equivalent BTC/SOL stablecoin spot notifications delegate to the existing Coinbase USD monitor; perpetual instruments remain distinct. Removed/re-added symbols start a new window.
- The reviewed installer backs up and changes only the TradingView application and new exchange module, then checks fresh collection and one clearly labelled synthetic Telegram message. Failed postflight restores the previous application. OAuth/runtime data, scanner, existing BTC/SOL monitor and trading gates remain intact.
- Pending: owner-run installation, review actual per-symbol coverage, at least 15 minutes of live sample cadence, and a subsequent restart check. Full-watchlist monitoring is not yet declared operational.

Candidate application SHA-256: `c156e5d3a51ed072ec931887236a9df6f52ee48bdd66219edb98dd2c667666c8`.

Reviewed deployment bundle SHA-256: `e25bed8577d75afdd66a8bfd991fd61f2fc4e90424155d2a93978deaccd324b4`.

This addendum publishes the candidate's status and evidence. The cross-market connection source remains in the server engineering checkout.
## Installation-check correction — 8 October

The owner attempted installation of the first exchange candidate; it failed and the prior application remains installed. Engineering inspection found that the installer expected aggregate exchange results from `/tradingview/health`, but that handler returned only the TradingView report. The corrected handler uses the existing public aggregate report and continues to omit watchlist symbols. A regression test exercises the actual health handler and asserts fresh-price and Telegram-test fields plus omission of private symbols. All 62 tests and the revised installer dry-run passed. The installer now reports a fixed failure stage without private exception details.

The revised reviewed hashes above supersede the first candidate. Activation, actual watchlist coverage and live movement windows remain pending; no successful deployment is claimed.
## Deployment receipt — 8 October, 10:17–10:20 UTC

The corrected exchange candidate was successfully installed by the owner. The installer passed 62 tests, saved backup `/opt/vivameda-operations/tradingview-exchange-_zenqdca`, and confirmed fresh collection plus the labelled synthetic Telegram test as sent. A subsequent engineering check verified the deployed application and exchange hashes against the reviewed candidate.

The installation snapshot covered three watchlists: 61 account symbols, 53 crypto and eight non-crypto. Forty crypto symbols returned fresh prices; thirteen were unavailable: eleven unsupported venues, one unsupported instrument and one pair not listed. A later live health snapshot reported 39 fresh and 14 unavailable, so coverage is variable and full-watchlist availability is not claimed. The installed collector cycles completed in approximately 7–9 seconds. The cached watchlist inventory was under three minutes old at the follow-up check; the new OAuth watchlist-sync pass was still starting, so a successful post-restart synchronization remains to be verified.

Earlier counts of 63 symbols / 55 crypto included the two additional core Coinbase BTC/SOL symbols. The exchange collector reports the account inventory; core BTC/SOL retain their separate existing monitor. This count change does not by itself demonstrate removed watchlist entries.

Remaining: verify at least 15 minutes of forward samples and gap-free measuring status, observe a completed fresh TradingView inventory sync, review actual unavailable symbols and add exact supported adapters where appropriate. Synthetic test delivery is verified by the sender result; real threshold-triggered watchlist alerts and full-watchlist coverage remain unverified. Live trading stays disabled.
