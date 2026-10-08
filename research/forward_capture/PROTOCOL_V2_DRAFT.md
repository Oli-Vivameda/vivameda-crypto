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
