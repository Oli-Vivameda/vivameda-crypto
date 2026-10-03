# Wallet intelligence — current source, 3 October 2026

The dedicated worker gathers evidence; only the scanner sends Telegram and independently recomputes admission.

## Queue
Read-only export examines up to 200 recent eligible launches, records missing pair/creator identities separately and queues up to 40 complete identities. Recent pre-alert candidates have priority. Identity changes reset leases/backoff so corrected candidates can be reconsidered.

Scheduled run_batch() executes research first (60 RPC / 90 seconds), then fast refresh (20 RPC / 45 seconds): at most 80 RPC total. An idle lane may do no work. Direct cycle() calls retain separate defaults. Persistent SQLite stores queue, pagination, pending transactions and address/transaction rotation. Provider failures use bounded candidate-specific retries. Unsupported pools retry later. No global permanent freeze is inferred from one candidate.

Candidate export runs approximately every minute; the worker timer runs two minutes after completion. Locks prevent overlapping runs. identity_pending.json, worker_status.json, per-token reports, maps and the last 200 capacity_observations.json records expose progress.

## Evidence
Holdings and pool relationships are authenticated against RPC. Provider infrastructure labels alone do not remove production exposure. Creator identity can match directly or through an authenticated mint-specific fee-sharing PDA; original addresses are retained, unresolved mismatches stay UNKNOWN.

Cluster PASS requires all selected supported 24-hour histories. Observed excessive links can reject before coverage completes. Developer review needs supported 30-day coverage and attribution. Age is an activity lower bound; unfinished short history is UNKNOWN, not proof of a young wallet.

Complete holder discovery does not establish cluster/age completeness. Public-provider capacity may leave most holders unreviewed while mandatory checks pass.

## Capacity and installation
Work holds below 3 GiB free disk or above 2 GiB of top-level evidence files. Rate limits, missing/pruned history and unsupported instructions remain coverage constraints.

Code: /opt/vivameda-wallet-intelligence. Private runtime state: /var/lib/vivameda-wallet-intelligence/data. Candidate exporter has no network; worker cannot access the scanner directory. Dedicated accounts own runtime state; root owns installed code.

See ../docs/SETUP.md. The installer validates bundled hashes; without --install it changes no services. Cloning does not deploy.
