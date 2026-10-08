# Control availability — 8 October 2026

Task C owner receipt at **2026-10-08T14:09:27.698106Z**. Hash-bound exporter `d58553ea9a95ae98f3004924aff531a9e403ad7a81a4f3f20320174263da9ae9` used a read-only SQLite snapshot, projecting aggregates only. Source review: `capture.matched_controls`, `record_cycle` and recovery `fc_emit_cycle`. Owner output reports pilot_modified=false, outcomes_read=false, endpoint_values_read=false, identities_exported=false and provider_requests=0. No permission widening or pilot changes.

358 accepted and 2,779 rejected cycles: 3,137 recorded cycles, 11.41% accepted. These are stored cycle records, not certification of every process attempt. 23 qualified events; 3 matched (13.04%); 20 unmatched. Five control entries use four unique tokens, with one repeated control entry. Frozen code allows reuse; no candidate was rejected for reuse.

## Rejected cycles by UTC day

Candidate and unavailable counts are repeated pair entries across cycles, not unique instruments. First and last days are partial. Hourly and daily totals were independently summed and agree.

| UTC day | Rejected cycles | Candidate pairs | Unavailable pairs | Discarded batch entries |
|---|---:|---:|---:|---:|
| 2026-10-06 | 738 | 8057 | 1631 | 3657 |
| 2026-10-07 | 1273 | 11665 | 3456 | 3589 |
| 2026-10-08 | 768 | 7435 | 2622 | 2157 |
| Total | 2779 | 27157 | 7709 | 9403 |

## Rejected cycles by UTC hour

| UTC hour | Rejected cycles | Candidate pairs | Unavailable pairs | Discarded batch entries |
|---|---:|---:|---:|---:|
| 2026-10-06T08:00Z | 43 | 333 | 81 | 144 |
| 2026-10-06T09:00Z | 36 | 280 | 40 | 97 |
| 2026-10-06T10:00Z | 22 | 166 | 22 | 68 |
| 2026-10-06T11:00Z | 37 | 200 | 60 | 54 |
| 2026-10-06T12:00Z | 48 | 299 | 100 | 90 |
| 2026-10-06T13:00Z | 18 | 87 | 22 | 18 |
| 2026-10-06T14:00Z | 59 | 440 | 145 | 126 |
| 2026-10-06T15:00Z | 58 | 610 | 128 | 216 |
| 2026-10-06T16:00Z | 58 | 555 | 144 | 205 |
| 2026-10-06T17:00Z | 40 | 309 | 94 | 40 |
| 2026-10-06T18:00Z | 43 | 462 | 61 | 190 |
| 2026-10-06T19:00Z | 43 | 699 | 82 | 294 |
| 2026-10-06T20:00Z | 58 | 775 | 118 | 390 |
| 2026-10-06T21:00Z | 58 | 1049 | 140 | 600 |
| 2026-10-06T22:00Z | 59 | 993 | 188 | 667 |
| 2026-10-06T23:00Z | 58 | 800 | 206 | 458 |
| 2026-10-07T00:00Z | 53 | 601 | 105 | 358 |
| 2026-10-07T01:00Z | 51 | 416 | 65 | 264 |
| 2026-10-07T02:00Z | 47 | 348 | 68 | 207 |
| 2026-10-07T03:00Z | 38 | 217 | 76 | 101 |
| 2026-10-07T04:00Z | 51 | 267 | 102 | 112 |
| 2026-10-07T05:00Z | 44 | 257 | 72 | 122 |
| 2026-10-07T06:00Z | 37 | 139 | 66 | 57 |
| 2026-10-07T07:00Z | 58 | 293 | 133 | 59 |
| 2026-10-07T08:00Z | 57 | 294 | 104 | 94 |
| 2026-10-07T09:00Z | 57 | 388 | 112 | 162 |
| 2026-10-07T10:00Z | 59 | 520 | 135 | 192 |
| 2026-10-07T11:00Z | 58 | 520 | 202 | 155 |
| 2026-10-07T12:00Z | 58 | 446 | 169 | 83 |
| 2026-10-07T13:00Z | 58 | 562 | 169 | 152 |
| 2026-10-07T14:00Z | 59 | 664 | 171 | 251 |
| 2026-10-07T15:00Z | 43 | 651 | 87 | 213 |
| 2026-10-07T16:00Z | 40 | 641 | 59 | 176 |
| 2026-10-07T17:00Z | 56 | 890 | 107 | 283 |
| 2026-10-07T18:00Z | 58 | 822 | 179 | 201 |
| 2026-10-07T19:00Z | 58 | 801 | 228 | 207 |
| 2026-10-07T20:00Z | 58 | 489 | 489 | 0 |
| 2026-10-07T21:00Z | 59 | 325 | 176 | 7 |
| 2026-10-07T22:00Z | 58 | 401 | 169 | 12 |
| 2026-10-07T23:00Z | 58 | 713 | 213 | 121 |
| 2026-10-08T00:00Z | 58 | 736 | 284 | 256 |
| 2026-10-08T01:00Z | 59 | 640 | 165 | 276 |
| 2026-10-08T02:00Z | 51 | 500 | 74 | 195 |
| 2026-10-08T03:00Z | 57 | 497 | 121 | 199 |
| 2026-10-08T04:00Z | 58 | 526 | 272 | 104 |
| 2026-10-08T05:00Z | 58 | 696 | 379 | 177 |
| 2026-10-08T06:00Z | 58 | 475 | 236 | 86 |
| 2026-10-08T07:00Z | 58 | 632 | 326 | 147 |
| 2026-10-08T08:00Z | 58 | 664 | 217 | 236 |
| 2026-10-08T09:00Z | 58 | 565 | 183 | 139 |
| 2026-10-08T10:00Z | 53 | 446 | 98 | 102 |
| 2026-10-08T11:00Z | 58 | 391 | 131 | 89 |
| 2026-10-08T12:00Z | 56 | 477 | 107 | 92 |
| 2026-10-08T13:00Z | 25 | 167 | 26 | 53 |
| 2026-10-08T14:00Z | 3 | 23 | 3 | 6 |

## Same-cycle matching funnel

Counts below are candidate/event relationships, so a candidate can occur against more than one event. They are cumulative survivors in rule order, not unique-token counts. Of 23 qualified events, **16** had at least one eligible candidate before age/size matching, and **7** did not. Thirteen of those 16 events ultimately remained unmatched. Event-level drop-offs at each individual rule are not separately exported.

| Sequential rule | Remaining candidate relationships | Dropped at rule |
|---|---:|---:|
| Other same-cycle entries | 75 | — |
| Score below 8 | 54 | 21 |
| Basic eligibility | 54 | 0 |
| Not excluded, not previously qualified, no prior alert | 32 | 22 |
| Age within 15 minutes | 6 | 26 |
| Market cap and liquidity each within factor 2 | 5 | 1 |
| Reuse | 5 | 0; reuse allowed |

The strongest measured matching loss is age proximity: 26 of 32 otherwise eligible relationships fail it. This does not authorize changing the frozen matching policy. Combined exclusion/prior-qualification/prior-alert losses cannot be split further from this aggregate.

## Counterfactual counting limit

The rejection hook writes time, selected count, unavailable-pair count, discarded batch size and amendment hash, then returns before input/cycle/cohort persistence. Owner export confirms **9,403 discarded batch entries** but no retained scored rows for rejected cycles. Exact additional qualified events and matched controls under per-pair rejection are therefore **not identifiable**, not zero. Zero is a possible lower bound for each. The 9,403 figure is only a gross input-entry ceiling, not distinct new events, eligible controls or an estimated yield. Missing score, eligibility, identity and matching fields prevent a credible point estimate; do not reconstruct contemporaneous scores from later history or consult outcomes.

## Planning receipt and next gate

Elapsed exposure since activation 2026-10-06T06:50:39Z: 2.30473 days. Cumulative count-only rates: 9.98 qualified events/day, **1.30 matched events/day**, 2.17 control entries/day. Rates are operational planning references, not forecasts, evidence of returns or a per-pair counterfactual. The pilot's fixed deadline remains 2026-10-20T06:50:39Z.

Task C's retained day/hour/funnel/reuse counts are now verified from owner aggregates; exact discarded-cycle yield and event-level rule-by-rule losses remain unverified. Next gate: owner reviews the inactive V2 draft's bias, no-reuse yield and power assumptions after the existing fixed stop. No pilot amendment, extension, backfill or outcome review informs this protocol.

Owner exporter command (read-only; re-running is not necessary for this receipt):

```bash
python3 /var/lib/vivameda-engineering/repo/client_learning/crypto_directive2_20261008/export_control_availability.py --expected-sha256 d58553ea9a95ae98f3004924aff531a9e403ad7a81a4f3f20320174263da9ae9
```
