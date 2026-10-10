# Separate fire watchlist relay — 10 October 2026

Owner request: send a separate candidate message through the existing Telegram bot,
starting with 🔥. Build reviewed; owner installation and real delivery remain pending.

This is a notification relay for existing successfully sent scanner alerts, filtered
to an exploratory $100,000–$500,000 alert-snapshot valuation range. It is not a new
100× prediction model, independent discovery feed, scam certificate or trade signal.

## Boundaries and delivery
- Reads only launches, snapshots and prealert_reviews from the scanner DB using
  SQLite URI mode=ro, query_only=ON, WAL visibility, a 200ms busy timeout and a
  two-second query deadline. No capture, ledger or outcome reads.
- Rechecks fresh persisted admission and the three required evidence checks.
  Any reported REJECT blocks delivery. Background UNKNOWN stays visible.
- Does not modify/restart the scanner, learning, pilot, archiver or their units.
- Reuses existing bot credentials and chat locally; never exports credentials.
- Own delivery state; one attempt per mint; maximum one message per five minutes.
  A network-ambiguous delivery is not retried automatically. Some candidates may
  expire during the cooldown; this is deliberately a bounded stream.
- Checks every minute and sends no candidate messages after activation + 21 days.
  The timer may still run an inexpensive expiry check after that date.
- Only Telegram delivery requests; no new market-provider calls or purchases.
- No automated trading. Snapshot values are not executable buy/sell quotes.
- State file cap 1 MiB; maximum 2,000 ledger keys. No automatic history deletion.

## Review receipt
20 synthetic tests passed on server Python 3.12; both systemd units passed syntax
verification. Tests include WAL-visible reads, stale/future/identity rejection,
unknown/rejected screening, valuation limits, no history backlog, deduplication,
ambiguous-delivery handling, rate limiting, expiry and the stop marker.
No synthetic Telegram message was sent. Live installation and real Telegram
delivery have not been verified. Full-stack release validation is not claimed.

Reviewed deployment bundle:
9c19b132ebc65cbcd3c92825d6346d8be7104ea6b61a1ffa0996e889c417bf21

Owner terminal:
python3 /var/lib/vivameda-engineering/repo/client_learning/crypto_100x_watchlist_20261010/install.py --install --expected-sha256 9c19b132ebc65cbcd3c92825d6346d8be7104ea6b61a1ffa0996e889c417bf21

Inspect the new component:
cat /var/lib/vivameda-100x-watchlist/status.json
systemctl status vivameda-100x-watchlist.timer --no-pager

Stop only the new relay:
systemctl disable --now vivameda-100x-watchlist.timer
systemctl stop vivameda-100x-watchlist.service

## Handover
Do not describe this relay as a validated 100× finder or fully audited candidate
recommendation. Independent catalyst, ownership continuity, organic growth and
executable exit assessment still require separate review. Installation is
hash-bound, refuses existing component state (no activation reset), uses the
existing dedicated health user and verifies frozen source/unit hashes.
No Directive 2/3 rerun, holdout access, new g, pilot outcome read or pilot change
is authorized by this notification request.
