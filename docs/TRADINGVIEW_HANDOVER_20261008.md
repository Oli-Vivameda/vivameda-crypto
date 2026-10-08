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
