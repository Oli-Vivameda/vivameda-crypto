# Current pre-alert admission

Source: early_scout.py; policy three-required-any-reject-v1.

Before Telegram, the scanner verifies exact chain/mint/pair identity, policy, review age <=300 seconds and explicitly revoked mint/freeze authorities. It recomputes policy from evidence; a report-supplied PASS cannot authorize a message.

Three checks require PASS, fresh observations and nonempty evidence references: token_controls, liquidity_control, trading_mechanics.

Explicit REJECT in any of the seven categories blocks. The other four (wallet_clusters, developer_history, top_holder_ownership, wallet_age) may be UNKNOWN without blocking, but the alert discloses their status. Missing/stale background evidence is displayed as UNKNOWN.

HOLD/REJECT/PASS is persisted in prealert_reviews before notification; HOLD does not advance the sent alert level. Scores remain 8/10. Admission is not a safety guarantee.

Earlier documents describing all-HOLD or all-seven-PASS are historical stages. This document and executable source describe the current policy. See SCREENING_V2.md and ../docs/COMPLETENESS.md.
