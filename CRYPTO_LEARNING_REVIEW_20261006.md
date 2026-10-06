# Crypto learning review — 6 October 2026

Direct read-only checks completed on 6 October 2026. This report contains aggregate evidence and verification receipts only. No runtime databases, case identities, snapshots, private messages or frozen-model outcomes are published.

## Operation and installation

- Scanner and V2 tracker active. Status snapshot: 899 V2 cases, 8,076 timed outcome rows and 10,367 evaluation rows. These are rows, not independent trades or validated wins. Latest recorded production alert: 5 October 2026, 23:06:00 UTC.
- Both learning timers active. Daily review completed successfully at 05:00:03 UTC on 6 October. Journal and endpoint evaluator completed successfully at 06:42:28 UTC; both exit status 0. Inactive oneshot services after successful completion are expected.
- Separate paper endpoint extension installed and selected by the journal service's ExecStart. No owner installation is pending for these learning components.
- Installed base bundle matches reviewed SHA-256 `d63bc98534fa81af7357a6c9b802e1d4ae7ea20578b61538c62b0601a0207a9e`.
- Installed endpoint bundle matches reviewed SHA-256 `f6bf9bfa741e3fe88f1225673b31c63054ea1514ada2c5c4597edcc260c8f1d9`.
- All 18 learning tests passed again on Hetzner. No production source or behavior was changed in this review.
- Crypto runtime and model gateway active. Installed agent/proxy hashes match the published interpretation source and current MANIFEST.

## Daily first-call evidence

The public summary and bounded memory were generated at **2026-10-06 05:00:03 UTC**.

| Measure | Count |
|---|---:|
| Development tokens | 139 |
| Recorded alert events | 159 |
| Eligible 60-minute endpoints | 78 |
| Missing or incomplete endpoints | 61 |
| Eligible endpoint >=2x | 6 |
| Eligible endpoint <=0.55x | 24 |
| Exploratory matched winner/failure pairs | 6 |
| Frozen-ledger identifiers excluded | 17 |

Eligible one-hour coverage is 78/139, **56.1%**. The main development cohort and matched-pair counts are unchanged from the first installed review; the excluded-identifier count increased from eight to 17. Exclusion applies to every `pl_predictions` mint regardless of its eligibility or outcomes. No frozen-model labels, predictions or result tables were inspected.

The bounded memory retains 12 case cards and five matched examples from the six-pair aggregate. Five examples were inspected without publishing identities. Four are in CONTINUATION and one in RECLAIM; winner endpoints span 2.06–3.23x and matched failures 0.0059–0.477x. Feature differences have mixed directions, including buy-ratio and volume-to-cap differences. These few reconstructed comparisons do not establish a stable entry rule, causal explanation or model improvement. Historical feature availability and policy versions remain unverified.

Tracked peaks are sampled tracked maxima, not lifetime ATH, executable returns or realized profit. Missing/incomplete coverage stays missing.

## Prospective paper evaluation

Aggregate snapshot generated at **2026-10-06 06:42:28 UTC**. Counts refer to the separate paper recommendation journal, not the historical first-call review or another forward-capture study.

| Action | Recorded | Pending | Eligible | Missing | Excluded holdout | >=2x Wilson 95% | <=0.55x Wilson 95% |
|---|---:|---:|---:|---:|---:|---|---|
| ENTER_REVIEW | 0 | 0 | 0 | 0 | 0 | Unavailable; n=0 | Unavailable; n=0 |
| WATCH | 0 | 0 | 0 | 0 | 0 | Unavailable; n=0 | Unavailable; n=0 |
| SKIP | 0 | 0 | 0 | 0 | 0 | Unavailable; n=0 | Unavailable; n=0 |

The service runs successfully, but it has recorded no paper decisions in this snapshot. There is no usable prospective comparison or training cohort here yet. The cause of zero captured decisions was not established by these bounded aggregate checks; it must not be inferred from missing wallet evidence alone. The engineering user could not open the protected scanner database for an optional diagnostic. Access controls were preserved, and no alternative database access was attempted.

The fixed horizon remains 3,600 seconds from each saved decision's timestamp. Endpoint lateness and coverage gaps are capped at 180 seconds; the saved baseline must meet the existing freshness rules. Late observations are not backfilled. All frozen-ledger mints remain excluded. Eligible market endpoints are observational evidence, not fills, fees, net PnL or causal treatment effects. Empty groups have no rate or interval.

## Fresh worker retrieval and interpretation

A new crypto-session worker completed the deterministic memory command. It returned AVAILABLE memory dated 1791262803 (2026-10-06 05:00:03 UTC), the exact aggregate counts above and bounded selection metadata: 12 available cards, six selected cards and at most three matched examples. This verifies live fresh-memory retrieval rather than wrapper installation alone.

A separate new-session local Qwen interpretation also completed in approximately 167 seconds. It used today's memory and a fresh paper summary, but **failed factual acceptance**:
- Unix timestamps were converted to an incorrect calendar year.
- The <=0.55x endpoint threshold was misstated as <=0.055x.
- An unsupported one-hour gap explanation was invented.
- It incorrectly said predictive validation requires live execution or randomized trials, despite supplied instructions.

These are aggregate findings from a focused check; the private question, answer and evidence packet are not published. Retrieval is verified; reliable interpretation is not. A completed generation is not a passed content check. Unreviewed explanations should not be used to change call selection or make performance claims.

The crypto numerical scorer remains a separate artifact from workforce models. The currently installed conversational crypto agent uses a dedicated runtime, queue, storage and existing public `qwen3:4b-instruct-2507-q4_K_M` checkpoint; the host and Ollama inference process remain shared. It has no crypto-trained weights. The later runtime separation and interpretation activation supersede the earlier shared-worker arrangement and initial 5 October timeout; today's factual failures remain unresolved.

## Publication and controls

The saved 5 October checkpoint records verified publication at commit `5cd148df74ab897e84852b2a29bc8738ce4ebfc8`. The previous permission/browser blocker has been resolved through the independently authorized signed-in browser. No writes were attempted through the read-only GitHub connector.

Current remote SHA-256 verification covered all 15 non-manifest files in the earlier pending update plus both published scanner sources and both interpretation sources: **19/19 match current MANIFEST**. Fourteen of the earlier files still match the saved update bytes; the root README has newer authorized agent information and was preserved. The current manifest contains 165 file entries before this report. This check does not claim a full re-verification of all 165 files.

Today's publication adds only this aggregate review and its manifest entry, preserving all existing manifest hashes and metadata. Publication completion requires a separate remote byte/hash verification receipt; a server git commit alone is not publication.

Frozen paper policy and evaluation preserved. No fit, weight update, threshold change, late backfill, paid call, transaction signing or live order occurred. Next evidence priority: establish why no qualifying paper decisions are being captured and collect timely prospective endpoints; interpretation needs factual reliability before unattended use.
