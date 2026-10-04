# Wallet connector diagnostics

Deployed and live-verified 4 October 2026 on the existing Vivameda connector host. Engineering commit: 6a4be80.

The connector now returns the last 20 capacity observations (at most two runs each), numeric history coverage, RPC request counts, index counters and the pending identity count. It reads fixed JSON report paths, refuses symlinks, limits file size and strips arbitrary fields from the new diagnostics payload. It does not open wallet databases, change permissions or send transactions. Existing status fields retain their prior behavior.

The installer is for an existing private Vivameda connector deployment, not a standalone installation. It verifies the exact extension hash, backs up current files and restarts the connector/helper with rollback on failure. Scanner rules and wallet collection behavior do not change.

Run the diagnostic tests with `python3 -m unittest discover -s scripts -p 'test_wallet_diagnostics.py'`. On the engineering server, 12 combined existing and diagnostic tests passed and installer validation passed. Live diagnostics verified: the latest primary observation covered 116 of 1,215 owners, with activity-age evidence for 75 and zero complete-and-fresh owner histories. All 20 recent primary runs used their 60 RPC requests. One identity conflict remains. These are operational snapshots, not performance results; cluster/age completeness and creator reconciliation remain unresolved.

The owner exported eight survivor/watchlist, pool-monitor, legacy-learning and service files with no missing exports. Those files still require publication review and are not included in this update.

Every future crypto change must be reflected in this public repository with tests and documentation; never publish credentials or private runtime data.

