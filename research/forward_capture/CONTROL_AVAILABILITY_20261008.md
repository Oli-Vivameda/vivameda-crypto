# Control availability — 8 October 2026

Task C receipt. Pilot unchanged; no observations, outcomes or endpoint values queried. Source review: `capture.matched_controls`, `record_cycle` and recovery `fc_emit_cycle`. Read-only engineering exporter returned `private_source_unavailable`; permissions remain unchanged. A tested owner-run SQL exporter is staged in `client_learning/crypto_directive2_20261008/export_control_availability.py`, SHA-256 `d58553ea9a95ae98f3004924aff531a9e403ad7a81a4f3f20320174263da9ae9`. It projects hourly/daily counts, sequential matching-rule counts and control reuse, with identity joins confined to SQLite. A synthetic one-event/one-control and rejected-cycle fixture passed.

Last retained aggregate, 10:32:27 UTC: 315 accepted cycles; 2,613 rejected cycles; 21 qualified events; 3 matched events; 5 control entries. This is a dated snapshot, not a new measurement.

| Requested count | Verification |
|---|---|
| Rejected-cycle candidate/unavailable pairs by UTC day/hour | Retained in `rejected_cycle.selected` and `.pair_unavailable`; owner export pending |
| Eligible same-cycle candidate before age/size matching | Retained accepted rows permit count; owner export pending |
| Score <8, basic eligibility, exclusion/prior qualification/prior alert, age, size/liquidity drop-offs | Sequential SQL projections prepared; owner export pending |
| Control reuse | Frozen code allows reuse; no rejection at this rule. Export counts reused entries |
| Exact additional events/controls under per-pair rejection | Not identifiable: rejected cycles omit scored rows and exact inputs |

The rejection hook writes only time, selected count, unavailable-pair count, discarded batch size and amendment hash, then returns before input/cycle/cohort persistence. Zero additional retained events/controls is a possible lower bound. Summed discarded-batch entries are at most a gross input-entry ceiling, not distinct new events or matched controls. Missing score, eligibility, identity and matching fields prevent a credible numerical estimate. Existing history snapshots must not be reconstructed as contemporaneous discarded scores. No result-dependent assumptions or endpoints are used.

Owner command:

```bash
python3 /var/lib/vivameda-engineering/repo/client_learning/crypto_directive2_20261008/export_control_availability.py --expected-sha256 d58553ea9a95ae98f3004924aff531a9e403ad7a81a4f3f20320174263da9ae9
```

Next gate: append that aggregate output here. A per-pair rule would require a separate post-stop prospective protocol; this exporter neither changes nor backfills the pilot.
