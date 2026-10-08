# Paper journal zero-decision diagnosis — 8 October 2026

Task 2 read-only engineering receipt; **runtime gate counts pending owner export**. Task 1 status and manifest were published and remotely byte-verified before this task began (`d8b43591049d72de1d8c019d5fe785e3f23677b9`). No scanner rule, screening policy, pilot, endpoint, ledger prediction value, weight or execution gate was changed. No new provider or paid call.

## Verified running source and counts

The installed learning source matches the reviewed engineering source: `daily_learning.py` SHA-256 `370ca35a27033b7278f45470f8519e2ea2da0e8a5a00707d40e496b9bc00f468`; `paper_outcomes.py` `d113c22b879936912d9709e04dde39b37376a9d15665f3bd4c4af0dbb0b50768`; `policy.json` `b77dbbcc94562894529b5247dcfe5b1834d6abd5645ea19c61e5ca9465367d36`.

At **2026-10-08T10:39:14Z**, the journal's latest service run completed successfully (exit 0); its timer is active. An inactive oneshot between timer runs is normal. The actual configured source is `/opt/vivameda-crypto-early-scout/data/early_scout.sqlite`; target `/var/lib/vivameda-crypto-learning`. The service runs as vivameda-scout, retaining existing permissions. The current sanitised paper summary has **ENTER_REVIEW 0, WATCH 0, SKIP 0**.

The engineering user cannot read the protected scanner database or the mode-0600 journal database. Permissions were not changed. Exact table-column presence, per-day source totals and exclusion/freshness gate counts therefore remain unverified in live data, rather than zero.

| Gate / question | Current evidence |
|---|---|
| Retained candidates per UTC day | owner export pending; reports retained source cases separately from actual historic journal pass inputs |
| Source selection | SQL selects v2_cases source=ALERT only; SHADOW and LEDGER_ALERT do not enter this query |
| Join | requires corresponding launches row and selects pinned_pair; live missing-join count pending |
| Timing | decision_ts must be >= activation and within the latest 180 seconds; live counts pending |
| Exclusion | frozen ledger membership exclusion occurs before snapshots; opaque aggregate membership only; live count pending |
| Pass limit / dedup | oldest eligible cases first, limit 40, then existing decision by mint is skipped; counts pending |
| Snapshot | last snapshot <=120 seconds old and sufficient finite history; failure still yields WATCH |
| Screening | bound mint/chain/pair, fresh review and referenced checks <=300 seconds old; failure still yields WATCH |
| Seven PASS | required only for ENTER_REVIEW; UNKNOWN yields WATCH, explicit REJECT yields SKIP when prior data checks succeed |
| Paper decisions written | all three groups zero at latest successful run |
| Historical actual input counts / timing drops | no retained per-pass input audit; cannot be reconstructed exactly from retained cases |

## Is the all-seven rule suppressing WATCH/SKIP?

**Not in the installed journal decision/writer code.** `decision()` returns SKIP on explicit rejection and WATCH on incomplete checks. `journal()` writes whichever resulting action is produced and converts caught freshness/schema errors to WATCH. The complete learning regression suite passed **24 tests**, including six diagnostic tests. These exercise this behavior, opaque exclusion projection, timing/source filtering, aggregate-only output and read-only refusal of mutation.

There is an upstream population restriction: the journal waits for recent delivered-alert-type ALERT cases rather than every scored/scanner-screened candidate. The published V2 source creates ALERT cases from recorded alert timestamps. This may explain missing negative WATCH/SKIP inputs, but an exact live cause cannot be established without the source gate counts and timing evidence. It is not legitimate to patch policy/population or claim a screening bug from zero totals alone. Also, all historical poll inputs cannot be retrospectively certified without an input audit.

## Reviewed minimal owner-run count export

`diagnose_journal_counts.py` opens both databases with mode=ro and PRAGMA query_only, hashes the installed learning source/policy before reading, limits query time and current candidate detail to the existing 40-row pass bound. It prints aggregates only. SQL uses opaque NOT EXISTS/EXISTS for exclusion membership and never projects prediction bodies, probabilities, labels or identities. It does not import/run the journal, read market endpoint outcomes, write paper rows, restart services, change file permissions or call a provider. Fixture tests establish that no mutation or private-row output occurs.

Reviewed diagnostic bundle SHA-256 (exporter + its tests): **bf80b0818fb0e648fffe4f13dc30f9dcd380d246ac1bca3a144b7a462a695f3e**. This is a diagnostic run, not a production installation; no backup or service restart is needed because it cannot modify production. No fix bundle has been proposed yet.

Owner command in the existing root server terminal:

```bash
python3 /var/lib/vivameda-engineering/repo/client_learning/crypto_daily_learning_v1/diagnose_journal_counts.py --expected-sha256 bf80b0818fb0e648fffe4f13dc30f9dcd380d246ac1bca3a144b7a462a695f3e
```

Next gate: record the returned per-day and per-gate aggregate counts here; identify the actual zero-decision cause. If a fix is warranted, freeze unchanged policy hashes, test it, present the reviewed bundle/SHA, create backup during owner install and verify the first non-zero recorded action aggregate after installation. Do not backfill missed decisions or endpoints. **Task 2 is not complete, and Tasks 3–5 remain unstarted under the owner's ordering rule.** No non-zero activation receipt is claimed.
