# Confirmatory selection protocol V2 — DRAFT ONLY

Task D receipt, 8 October 2026. Not activated, preregistered or approved. Prepared after Task C's availability-source review and E's candidate logging review; no pilot outcomes, endpoint values or prediction-ledger contents informed this draft. Owner approval and a frozen reviewed bundle are required **after the existing 20 October 2026 stop**. No pilot amendment, extension or backfill.

## Question and cycle acceptance

Estimate selection association for first score >=8 versus lower-scored eligible controls in the measurable current scanner feed. Population is capped/filtered observed Solana small-cap candidates, not every Solana token and not screened/delivered alerts. Thresholds, 11 signals, weights and seven-check screening remain unchanged.

Proposed V2 rule: account for every selected candidate, skip only an explicitly unavailable pair, and retain the contemporaneous valid scored pairs. Reject the whole cycle for incomplete candidate accounting, invalid scores/timing, integrity failure, unknown error or broken runtime binding. Never reconstruct omitted rows, accept zero as missing data, change pair or initiate a new provider/follow-up request. Record rejected-pair counts and eligible measurable candidate counts by UTC hour/day.

Whole-cycle rejection preserves a common complete evaluated set, but conditions enrollment on the availability of every capped candidate: one unavailable pair removes all valid peers and may disproportionately remove high-volume, volatile or illiquid periods. Per-pair rejection retains more observed information but conditions each token on provider/pair availability, which may correlate with liquidity, age and deterioration. Neither is unbiased for all tokens. The V2 estimand must explicitly condition on measurable available pairs; report provider/availability strata and selection exclusions. This change is only a proposed confirmatory capture rule, never a production-alert policy change.

Task C establishes that rejected-cycle rows were discarded. It cannot quantify unique additional qualified events or matched controls. Per-pair rejection has no empirical yield claim yet. Choosing this rule is contingent on the owner reviewing C's aggregate funnel and this bias argument before freeze. If that evidence is insufficient, retain whole-cycle rejection and revise the sampling/power assumptions before activation; no rule switch during collection.

## Fresh events and control selection

Exclude all pre-activation known/pilot tokens via frozen membership, without ledger-value access. Capture exact current inputs before screening; four history points spanning 600 seconds; market cap $30k–$750k; liquidity >=$25k; one-hour volume >=$20k; input age <=120 seconds. Qualified event is first score >=8 with prior alert level zero. Keep qualified events with no control in operational counts; only matched events enter the primary paired estimand.

Controls: same retained cycle, different token, basic eligible, score <8, no prior alert, not previously qualified, age within 900 seconds, cap and liquidity ratios each 0.5–2. Select at most three by normalized age difference plus absolute log cap/liquidity ratios; ties by mint. Never match outcomes, future qualification, momentum components or wallet verdict. Each token participates once in the primary sample: a selected control cannot later enroll as a new primary event or another control. Later qualification does not remove its original control observation. This proposed no-reuse rule differs from the pilot's allowed reuse and can lower matched yield; disclose the induced population restriction and its lost-event counts.

Risk verdict and delivery remain separate descriptive stages. No control is retrospectively required to pass screening; this tests score qualification, not the value of security screening.

## Yield and planned sample

Owner count-only snapshot at 14:09:27 UTC: 23 qualified events, 3 matched events, 5 control entries (4 unique tokens, 1 repeated entry) over 2.30473 days. Constant-rate planning reference: 9.98 qualified/day, **1.30 matched events/day**, 2.17 control entries/day. These are observed cumulative rates, not forecasts. Per-pair acceptance might raise rates; no-reuse may reduce them. C now verifies 16 of 23 events had eligible same-cycle candidates before age/size matching; 32 eligible relationships fall to 6 after age matching and 5 after size/liquidity matching. Net V2 yield under proposed per-pair acceptance and no reuse remains unverified.

Planning duration is 56 calendar days after a separately approved future activation, then 3,780 seconds passive follow-up. At 0.5/1.30/3.0 matched events/day, expected matched-event counts are 28/73/168 respectively. These are explicit low/reference/high scenarios, not inferred counterfactual results. Do not assert an expected sample from availability alone. Owner must freeze a rate scenario and acceptable effect/power target before activation.

## Primary endpoint and inference

For entry i, Y_i = log(MC at earliest valid same-pair local receipt in index+3,600 to index+3,780 seconds / exact input MC). Event contrast D_i = Y_qualified minus the arithmetic mean of its preselected control log endpoints. Each matched event receives equal weight; controls receive 1/k within that event. Require all selected endpoints for a complete primary contrast; missing values are never zero/loss and no partial control substitution is allowed. Later receipts, different pairs, peaks and backfills cannot substitute. This is a market-cap endpoint association, not net trading return, causality or realized profit.

Primary estimate: event-weighted mean D_i, two-sided 95% interval and test of zero, clustered by UTC index day. Use day-clustered wild-bootstrap inference with predeclared seed 20261008 and 9,999 repetitions; report day counts, cluster sizes and finite-sample limits. No-reuse prevents a token linking independent days through repeated primary roles; market-wide serial dependence can still cross days. Prespecified sensitivity: two-day contiguous blocks and day-equal weighting. At fewer than 20 populated matched days, label inference inadequate; do not rescue it with unclustered significance.

## Minimum detectable effect — assumptions, not pilot estimates

For 80% power and two-sided 5%, planning approximation MDE = 2.85 × sigma_D × sqrt(DE/N), using a conservative finite-day critical-value allowance. sigma_D is the unknown contrast standard deviation; **no pilot endpoint variance was used**. DE = 1+(m−1)rho is an illustrative equal-cluster design effect, not a measured correction. Actual heterogeneous/serial clusters require a frozen simulation before activation.

At reference N=73, assuming 40 populated matched days (mean m=1.825) and within-day rho=0.10: DE≈1.0825 and MDE≈0.347 sigma_D. If sigma_D is 0.25/0.50/1.00, MDE is approximately 0.087/0.174/0.347 log units, corresponding to about 9.1%/19.0%/41.5% ratios of endpoint multiples. With DE=2 stress assumption, MDE≈0.472 sigma_D; at sigma_D=0.50, about 0.236 log units (26.6%). Planning target delta=0.20 log units (~22% endpoint-multiple ratio) is a proposed owner decision, not a profit claim; at sigma_D=0.50, the reference sample may detect it under modest clustering but not DE=2. If the owner requires smaller effects or yield is lower, redesign before activation; never extend after seeing results.

## Stop and analysis gates

Enrollment ends at activation+56 days regardless of scores, matches, coverage, outcomes, effects or significance. Follow-up ends 3,780 seconds later. No interim outcome/effect reporting, sample-size rescue, restart or extension. Existing safety/integrity failures may stop capture early; retain that deviation and do not activate a replacement to improve results.

At fixed stop, require >=40 complete matched contrasts and >=20 populated matched UTC days for an interpretable primary test. Report all enrolled events, unmatched fractions, reuse exclusions and missingness. Require endpoint presence >=90% separately for selected events and selected controls, and absolute coverage difference <=5 percentage points; otherwise fail the confirmatory coverage gate and treat complete-case results as descriptive. These quality gates do not control stopping or authorize extra collection.

Before owner approval: review C's now-appended aggregate funnel, resolve passive endpoint ascertainment limits, freeze cycle/no-reuse rules, sample/power assumptions, inference implementation/tests and timestamps. Existing passive reuse does not guarantee symmetric follow-up, especially for deteriorating tokens; if symmetry cannot be defended without new requests, do not activate a confirmatory claim. No outcome inspection may tune this protocol.


## 9 October follow-up — age-window planning (draft only)

Use only Task C's 8 October funnel: 23 events over 2.30473 days; 16 events with eligible controls; 32 otherwise eligible relationships, 6 within ±15 minutes, 5 also passing cap/liquidity, and 3 matched events. There is no age-difference distribution or event-level assignment table. Exact yields for ±30/±60-minute or age-band matching are NOT identifiable. No new pilot data or outcomes were read.

The following arithmetic is a scenario, not an empirical counterfactual: assume locally uniform absolute age differences so survival doubles from 15 to 30 minutes and quadruples to 60 (capped at 32); retain the observed 5/6 cap/liquidity survival and the observed 3/5 matched-event-to-control-entry conversion. Hold cycle acceptance and pilot reuse fixed solely for this comparison; V2 per-pair acceptance and no-reuse effects are not estimated. A 30-minute absolute token-age band is floor(age_seconds/1800); require the same band. Under locally uniform within-band phase, assume it retains half the pairs admitted by ±30 minutes. These assumptions are unverified and ignore event occupancy and correlations.

| Proposed age rule | Scenario age survivors /32 | Scenario after size/liquidity | Matched events/day | Control entries/day | Comparability cost |
|---|---:|---:|---:|---:|---|
| ±15 minutes | 6 observed | 5 observed | 1.30 observed | 2.17 observed | Tight absolute age agreement; strongest measured availability loss (26/32). |
| ±30 minutes | 12 assumed | 10 assumed | 2.60 scenario | 4.34 scenario | Can compare tokens at substantially different launch/migration stages; age-dependent liquidity/volume must remain disclosed. |
| ±60 minutes | 24 assumed | 20 assumed | 5.21 scenario | 8.68 scenario | Greater developmental-stage mismatch and residual age confounding; higher yield is not better identification. |
| Same 30-minute absolute age band | 6 assumed | 5 assumed | 1.30 scenario | 2.17 scenario | Coarse stage balance and differences <30 minutes; arbitrary band boundaries can reject close neighbors and admit distant within-band pairs. |

For nested wider windows with all OTHER pilot matching rules fixed, 3 observed matched events is a lower reference and the 16 eligible-candidate events is an upper ceiling: approximately 1.30–6.94 matched events/day at that historical exposure. This is not a V2 forecast: no-reuse may reduce yield, and per-pair acceptance changes the population. For band matching the same 3-event lower reference is invalid because bands are not nested: 0–6.94/day is the logical bound from these event counts. Control relationship ceilings do not establish unique control yield, endpoint coverage or retained complete contrasts. Do not feed these scenarios into the primary power calculation as measured sample sizes.

Owner decides after 2026-10-20T06:50:39Z. Freeze one age rule before any new confirmatory activation; retain age-stratum counts and unmatched-event rates as diagnostics. No matching on outcomes or tuning against pilot endpoints. No pilot rule changed. Receipt: one existing funnel reviewed; zero new pilot queries; four planning alternatives; exact alternative matched yields unverified. Next gate: owner selects comparability/yield tradeoff after the fixed stop and separately reviews V2 freeze/power assumptions.
