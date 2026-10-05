# Wallet evidence capacity — 2026-10-05

The collector paused at its 2 GiB evidence quota. The observed data directory held 2.002 GiB, including a 1,755,058,176-byte shared SQLite database. No evidence was removed.

The worker now permits 4 GiB of evidence and retains the 3 GiB free-disk safeguard. This is bounded collection headroom, not an archival or retention policy; collection will pause again at the new cap.

Validation: 136 wallet tests passed, including acceptance of the existing 2.002 GiB dataset, holding above 4 GiB, and holding below 3 GiB free. The installer hash was updated. Server engineering commit: a7a7f52.

Deployment bundle: 788995591365cd496b2258df9f35654f49202106f403a4d5591a1ece44f53885. Source backup: 20261005T041359Z-ihg2wca0. Both collection lanes resumed. A later live run collected 779 events across 72 wallets; that candidate was REJECTED, with developer history and wallet age still UNKNOWN. This is operational recovery, not complete coverage or a profitability result.

Scanner policy, alert thresholds, paid-provider restrictions and evidence gates were unchanged. Private databases and reports remain excluded from this public repository.
