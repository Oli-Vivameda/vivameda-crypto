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
Work holds below 3 GiB free disk or above 4 GiB of top-level evidence files (5 October capacity release; see EVIDENCE_CAPACITY_20261005.md). Rate limits, missing/pruned history and unsupported instructions remain coverage constraints.

Code: /opt/vivameda-wallet-intelligence. Private runtime state: /var/lib/vivameda-wallet-intelligence/data. Candidate exporter has no network; worker cannot access the scanner directory. Dedicated accounts own runtime state; root owns installed code.

See ../docs/SETUP.md. The installer validates bundled hashes; without --install it changes no services. Cloning does not deploy.

## Collection audit — 4 October 2026

Deployed and verified on 4 October 2026 (see MANIFEST.json collection_audit): deferred fast passes make zero RPC calls and now report zero instead of reusing a previous research count. Saved rejection evidence and its timestamp remain unchanged. Coverage summaries now count missing address parts, incomplete pagination, pending transactions, null timestamps, unsupported programs and stale heads separately. These counts overlap and exclude wholly unobserved owners (already reported as owners_missing).

The existing collector rotates addresses and transactions and caches transaction bodies. Complete history requires all required addresses, decoded transactions and supported programs, with heads at most 300 seconds old. Hundreds or thousands of required addresses compete within a 60-request research budget across the candidate queue. Cache reuse does not make old observations fresh. This is a capacity constraint, not evidence of clean wallets. No RPC budget, screening threshold or alert gate was changed.

85 screening and wallet-pipeline tests passed on Hetzner, including zero-call deferral, original timestamp preservation, missing address counts and stale cache counts. The local test attempt lacked requests; it did not run. Further work should measure a fixed cohort's blocker counts and address/transaction throughput before changing scheduling or purchasing capacity. Full cluster/age coverage is not claimed.

## Focused collection release — 4 October 2026

Deployed and hash-verified on 4 October 2026 (see MANIFEST.json focused_collection); population-level coverage improvement remains unproven. Research holds one eligible token for a 900-second lease, reserves every fourth eligible research pass for another queued token, and rotates the focus at lease expiry. Missing/changed identities and explicit research rejections release the focus. Candidate backoff and the fresh inbox requirement still apply. The fast lane skips the focused token during its lease so it cannot postpone research.

Holder addresses are ordered by owner then address, using a new durable owner/address cursor. Budget exhaustion can still split an owner; the next visit resumes after the last address. Developer priority is retained. The old cursor table is retained for rollback.

Incomplete historical tails reuse heads at most 120 seconds old, preserving the original head_at. Successful head progress is committed before requesting the next backward page. Older or disconnected heads still require refreshed continuity evidence. Complete histories, unsupported instructions and missing transactions retain the existing policy gates. Research remains 60 RPC / 90 seconds, fast remains 20 RPC / 45 seconds.

133 tests passed. The first run failed the old alternating-priority assertion because the new design deliberately reserves three focus passes; the replacement integration assertion proves the fourth pass serves the waiting lower-priority token. Fixed-budget deterministic fixtures (not live outcomes): with two paired owners, four mock requests completed 0 owners under the old ordering and 1 under grouped ordering, while owners entirely missing increased from 0 to 1. In a mixed single/paired-owner fixture, completed owners stayed 1 vs 1. A failed-tail fixture verifies resumption needs one backward request rather than repeating the head, with no timestamp renewal. These demonstrate mechanics and trade-offs, not population-level coverage gains.

Live validation still required: observe the same focus token across successive cycles, compare owners_complete_fresh, missing owners and activity-age coverage, check RPC use stays within limits, and confirm exploration/lease rotation. Do not declare coverage complete from fixture results. No paid calls, alert thresholds, screening gates or automated trading changes.
