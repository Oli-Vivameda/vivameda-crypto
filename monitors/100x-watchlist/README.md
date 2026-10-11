# Separate 🔥 research watchlist — 11 October 2026

The existing bot and chat remain in use, with a separate 🔥 message per candidate. The owner installed indefinite operation and the latest-screen classification update. **This public-research update is tested and staged; owner activation is pending.**

An alert used to explain only scanner admission. The new step gathers evidence tied to the exact mint and pool, assesses recent activity, reads a provider-linked project website and explains why attention is weak or supported.

## Research and classification

- One free DexScreener pair request, plus at most one linked HTTPS website request per research attempt. Sources, fetch times, response hashes, measured observations, developer screening and reasons are saved in private relay research records.
- The pair must match Solana, the pinned pool and base-token mint. An identity mismatch blocks delivery.
- Read up to three nonoverlapping five-minute windows from the last 30 minutes of the same mint/pool scanner snapshots. At least two buy-heavy windows and liquidity holding within 10% classify **ACTIVITY-SUPPORTED WATCH**. This is an activity proxy; transaction counts do not establish unique buyers, organic growth, business adoption or a 100× probability.
- A website title/description or relevant visible passage is explicitly a **project claim**, never verified revenue or adoption. A displayed mint establishes association only. Readable pages are not independent due diligence.
- Claims about creator fees funding repeated token purchases get **THIN THESIS — FEE-FUNDED BUYBACK CLAIM**. Recirculated trading fees require outside demand and sustainable fee revenue; they do not establish either.
- Claims about volume-generating tools get **THIN THESIS — ACTIVITY TOOLING CLAIM**. This does not assert fraud or wash trading without evidence.
- Current public liquidity falling more than 20% below the alert snapshot weakens the classification. A public price above 2× the snapshot discloses chasing risk.
- Weak, new or incomplete candidates remain permitted as **THIN THESIS**, with gaps visible. Public-source failure cannot create a stronger classification. Any latest scanner rejection still blocks delivery.
- Developer behaviour uses the existing fresh developer-history screen and its reason. **Independent developer investigation, organic buyer attribution, catalysts, audited adoption/revenue and executable exit quotes are not implemented and remain UNVERIFIED.** This is a bounded evidence-and-rules research step, with no LLM or validated investment-selection model.

The latest persisted screening is read again after public research and before Telegram. A newer HOLD/REJECT, stale required check, changed pool or stop marker suppresses delivery. This does not promise detection of events after the final check.

## Boundaries

No scanner scoring/threshold, scanner source/unit, learning source, pilot, holdout, prediction ledger, capture or outcome changes. SQLite opens read-only with query-only mode, WAL visibility and bounded queries on launches, snapshots and prealert_reviews. No paid calls, purchases or trading.

Public fetches have an eight-second total research budget, HTTPS certificate verification, public-address DNS validation pinned to the connection, no redirects, two requests maximum and a 256 KiB response cap. Website content is parsed as data, never executed. Unknown facts stay unknown.

Operation has **no end date**. Resource caps can pause the relay and require maintenance: 1 MiB per state record, 2,000 delivery keys and 2,000 research files. No automatic history deletion. One research attempt per five minutes, one Telegram delivery attempt per mint; ambiguous sends are not automatically retried. Same bot/chat, existing dedicated service user and unchanged unit sandbox.

## Validation and activation

50 tests pass on server Python 3.12. Tests cover research identity, project claims, fee-funded buybacks, activity versus organic demand, nonoverlapping windows, same-pool/future exclusion, liquidity/price warnings, public-source failure, URL/DNS/response limits, research deadline, fresh developer evidence, latest rejection during research, stop, saved audit, message size, existing deduplication and read-only boundaries. No test sends Telegram.

A live free public-metadata check matched VOLUMIZER's exact screenshot mint and pool, and read its linked site. It used no production history or Telegram and is not a reconstructed entry decision.

For the owner-installed classified relay, use the server engineering checkout:
```bash
python3 /var/lib/vivameda-engineering/repo/client_learning/crypto_100x_watchlist_20261010/update_research.py --expected-sha256 fd12f4a19f42e4d2a8340cd4902acbceb67bf7d9562af96ac7c39ccc93e8cb66
```

The updater binds exact source/test hashes, requires root/server Python 3.12 and the installed classified source, reruns tests as the engineering user, backs up the relay, stops only its own timer/service, preserves configuration/activation/delivery history, installs two source files and verifies first-run health. It restores the previous relay on a failed update. It refuses unknown or partially changed installations.

Fresh installations must use the current install.py --bundle output; historic hashes are not valid for this source. Historical remove_expiry.py and update_classification.py are retained only for audit, not applied after this update.

Inspect: /var/lib/vivameda-100x-watchlist/status.json and its private research/<mint>.json. Stop only this relay with systemctl disable --now vivameda-100x-watchlist.timer, then systemctl stop vivameda-100x-watchlist.service.
