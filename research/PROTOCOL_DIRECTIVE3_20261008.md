# Directive 3 - Earlier entry research - 8 October 2026

Status: preregistration before any new study outcome access. Shadow only; not activated.
Owner instruction is the authority. This file is the single directive protocol, receipts and Astra handover.

## Scope and frozen boundaries
Work order C, A, B. Python 3.12 only. Do not modify or restart early_scout.py,
scout_learning_v2.py, the frozen scorer or the forward-capture pilot before
2026-10-20T06:50:39Z. No pilot amendment, extension or backfill. No new providers,
paid requests, execution or Telegram sends. Agent, journal, TradingView and trading
scaffold stay frozen, apart from existing scheduled checks. Publication: aggregates only.
Every installation requires reviewed source bundle, SHA-256, backup, owner install and postflight.
The 5 October audit numbers supplied by the owner motivate the question; they are not
new observations or a permitted source of pilot/ledger results.

## C - Run-onset study, frozen definitions
Data: existing snapshots and launches only. Use SQLite mode=ro, query_only and a read
transaction. Never import the production scanner (its top-level code has side effects).
Extract only the pure scorer function from hash-verified source into an isolated namespace.
Do not read pl_predictions.body, probabilities, valid flags, labels, pl_results, v2 outcomes,
pilot observations/endpoints, or any general private event body.

Exclusions must be applied BEFORE selecting market histories or outcomes:
all pl_predictions.mint, all pilot qualified mints and all pilot control mints.
An owner helper may project only cohort identity fields inside SQL for exclusion; do not
export identities. Membership is permitted for exclusion only, not for stratification.
Missing/unauthorised exclusion sources fail closed. Dynamic exclusions are refreshed
at every read; newly excluded study tokens must not enter later aggregates. This is not
permission to inspect pilot outcome rows. For activation before the stop the stronger
owner rule requires reading nothing the pilot writes; choose POST-STOP activation
unless an independently safe exclusion route is proven and approved.

Time cutoff: 2026-10-08T18:10:00Z (fixed historic cutoff, no later observations substituted).
Development: all available eligible UTC dates BEFORE 2026-10-08.
Holdout: UTC 2026-10-08 only, closed windows by cutoff; never opened for rule tuning.
Both prehistory and the full outcome window must lie in the same split, so development
windows crossing midnight into holdout are excluded. Record retained date ranges,
coverage exclusions and populated UTC dates without treating expired data as available.
No pre-study outcomes are fetched from backups or reconstructed.

Unit: one mint/pair/local snapshot minute, not an independent token or a precise causal
onset. Retain only positive finite MC/price, stable same-pair history, age 30 min-6 h and
MC $30k-$750k with scorer prerequisites (>=4 observations, >=10 min span, liquidity
>=$25k, hourly volume >=$20k). Historical last-trade time, top-60 selection and historical
pump ATH are not retained in snapshots: exact historic scanner-universe membership
cannot be certified. Report a SNAPSHOT-OBSERVED CANDIDATE-MINUTE baseline, not a
baseline for all launches or a direct comparable denominator for the 7% ALERT rate.
Show a full-30-minute-prehistory subset and a partial-history diagnostic separately.
Primary features require history reaching t0-1800 within 180 seconds, >=4 positive
observations, max gap <=180 seconds, and no pair switch.

Run-onset label: max observed same-pair MC in (t0,t0+3600] / MC(t0) >=2.0.
Non-run: maximum <1.35. Intermediate [1.35,2) is retained in the all-minute denominator
but omitted from the run/non-run feature contrast. The maximum excludes the late
endpoint grace period. Require the earliest positive same-pair endpoint in
[t0+3600,t0+3780], lateness <=180, and maximum observation gap <=180 including
t0 through that endpoint; future window not yet closed is immature, not negative.
Missing/zero/invalid MC is missing, never a failed run. Also report endpoint multiple.
Overlapping positive windows are not independent discoveries: report unique mints and
non-overlapping 60-minute episodes (earliest qualifying t0, suppress that mint until
t0+3600), alongside all candidate-minute labels.

Compute only information stored at or BEFORE t0: gain vs first retained same-pair
snapshot MC; age; hourly and five-minute buy ratios; hourly volume/MC;
vol_m5/(vol_h1/12); 30-minute price band and net change; transaction counts;
liquidity change; all 11 unchanged scorer signals recomputed over production's
35-minute history. Record separate 30-minute study and 35-minute scorer provenance.
Latest launches.ath_mc/current_mc/last_trade_ts are mutable: current pump ATH ratio
may be shown only as a present-day metadata diagnostic, not a historical feature or
rule input. A dated historical ATH field is required for an as-of ATH feature.
First stored MC is a retention-dependent anchor, NOT launch MC.

Non-run comparison sampling: within the same UTC day/hour, deterministic SHA-256
ordering (seed 20261008), select up to one non-run window per run window, without
replacement. Report strata with no comparisons. Full base rate uses ALL eligible
covered minutes, never the matched sample. Feature distributions: n, missing, median,
p25/p75 for runs and sampled non-runs; pass counts for every existing signal.

Visibility diagnosis: report first-retained observation age, pc_h1>22% and gain since
first retained observation at earliest observed positive episode. Count "already
extended when first observed" only when pc_h1 is available and >22%.
Number of runs never visible before candidacy is NOT IDENTIFIABLE without a
pre-candidacy path; do not equate a high first-observed pc_h1 with an unseen 2x run.

Rule search: at most two candidates. A1 is frozen: unchanged score>=8 AND
h1_not_extended PASS. A2 adds MC(t0)/first-retained same-pair MC <=g.
g grid = 1.10,1.25,1.50,2.00. Missing anchor rejects A2. Select g using development
ONLY: highest run precision among choices retaining >=20 positive minutes and >=20
non-run minutes across >=2 development UTC dates; ties choose the smaller g.
Report retention and all grid comparisons. If no choice qualifies, do not invent/freeze
a threshold and do not open holdout. Overlap means these counts alone do not prove power.
Freeze rule JSON, source/input digests and selection receipt in a git commit BEFORE
opening holdout. No changes after one holdout access. Holdout exporter creates an
exclusive, durable one-shot marker before reading labels; failures also consume access
unless owner reviews a technical repair without inspecting/changing the rule.

Holdout outputs: frozen A1/A2 precision, >=2x rate, retention, endpoint multiple and
differences vs A0; unique tokens, episodes, coverage and decision-day counts.
UTC decision-day clustered 2,000-resample bootstrap, seed 20261008; fewer than
10 populated decision days is descriptive with no reliable inference claim.
With the current 48-hour snapshot retention a one-day holdout is expected to be
descriptive only. A frozen rule must subsequently be tested prospectively.

## A - Separate shadow scorer, preregistration candidate
Same CURRENT scanner candidate query (age, last trade, MC/ATH, top 60) in a
read-only scanner transaction. Own SQLite only. No production imports or writes,
providers, Telegram or pilot outcome access. Do not poll or install before owner approval.
A0: recompute unchanged scorer over 35 minutes; record full score and would-alert
level (0/1/2). Compare stored alert_level as a delivery-state DIAGNOSTIC; it is not an
exact score because stored levels follow attempts/admission and do not reset.
Exact in-process candidate/cycle parity is unverified for an independently polling service:
launches mutate and snapshots are minute-rounded. Log freshness/universe fingerprints
and do not claim polling is the original scanner timestamp. Deployment must resolve
candidate/time parity or explicitly pre-register the independent-poll estimand.
A1: A0 with mandatory h1_not_extended. A2: A1 with development-frozen g and
first-observed anchor established at activation; never silently re-anchor after retention.
Historical retained anchors and prospective activation anchors differ; disclose that shift.
No post-outcome rule tuning. Each arm records its first eligible decision per mint,
plus an upgrade diagnostic separately. Excluded tokens cannot become controls.
R: draw one eligible non-index candidate uniformly at each A0 first-alert timestamp;
seed 20261008, stable sorted universe, seed/draw/universe hash recorded. Score is
not matched; risk screening is not modified. Empty universe is unmatched.
"Eligible" uses the same age/candidate and scorer prerequisites, not score>=8.
One random draw per A0 decision, not one per market cycle with no A0 decision.

Commit timestamp, exact inputs, policy/source version, anchor provenance and
same-pair entry MC before follow-up. Passive scanner snapshots only; 60-minute
endpoint earliest same-pair receipt at +3600 to +3780, lateness<=180 and
continuous observed max gap<=180. Local minute stamps do not certify provider
receipt time; publish that limitation. Token aging out of scanner candidacy yields
missing follow-up, not new requests or backfill. If passive reads cannot support
the endpoints, report missingness and a proposed request budget; wait for approval.

Primary: 60-minute MC multiple and >=2x endpoint rate; observed within-window 2x
is secondary and is NOT the same endpoint. UTC decision-day clustered comparisons;
R matched by A0 timestamp; A1/A2 nested selection contrasts are associations.
Proposed stop (not approved): first of all arms attaining 100 decisions (R counts
successful draws) or 2026-11-17T06:50:39Z. Stop applies globally with no extensions.
First outcome-independent stop receipt; passive follow-up ends 3780 seconds later.
Minimum readable: >=40 complete decisions/arm and >=10 populated decision days;
>=90% endpoint coverage/arm and coverage difference<=5 percentage points for
primary comparisons. Otherwise descriptive only. No outcome-driven rescue.
Owner must approve N/date, parity estimand, rule freeze and sample gate before activation.

## B - Pre-candidacy launch path, build only
Preferred post-stop hook in existing upsert_pump loop; zero additional requests.
Own append-only launch_path(mint,ts,mc,ath_mc,complete,last_trade_ts) with
observed local receipt milliseconds. Store each returned launch observation,
not invented creation-to-first-observation points. Polling the newest 100 launches
and recently traded 100 does not guarantee every launch or observation from creation.
State discovery lag and coverage. Null/invalid MC stays missing. Same receipt/mint
duplicates deduplicate; conflicting data at that key reject and log an aggregate.
Never reset timestamps or reconstruct paths from latest launch metadata.
Retention candidate: 30-day active partitions, immutable archived/private manifests,
maximum 512 MiB including journal/WAL and 3 GiB minimum free disk. At cap, stop
path appends and record a sanitized local incident; do not stop scanner or erase rows.
No deletion under the guise of append-only. Rotation/reclamation requires separately
reviewed archive policy. Log dropped observations and disk/cap stops.
Estimated bound at 200 rows/20s is 864,000 rows/day; actual unique rate, row bytes
and 30-day fit are unverified. Cap takes precedence over planned retention.
Before-stop separate collector is NOT selected (would add provider requests).
Deliver tested hook candidate, hash manifest, installer with hard stop-time check,
source backup, unchanged-function/scorer checks, and rollback plan. No installation
before fixed stop AND reviewed owner approval. Re-audit live source hash then;
never install a patch built against a stale source.

## Wallet scope
One aggregate line only: complete and fresh required-owner histories / required owners,
with evidence freshness <=300s and coverage denominator. Not yet verified.
No wallet-quality research or feature build.

## Receipts (append only)
2026-10-08 source/access preflight: engineering source early_scout.py SHA-256
3e73978a41e2e21e090a7eea92bbdc1a52dc190ce229ac262a3c6a2b0af6a043 inspected;
not asserted as live installed bytes. Source confirms 48-hour snapshot deletion,
mutable launch metadata, 35-minute score history and current candidate limits.
Scanner DB permission denied to engineering. No market histories/outcomes, ledger
values or pilot endpoints read. No deployment, restart, provider call or Telegram.
Next gate C: reviewed owner-only exclusion-aware development export after protocol commit.
C actual eligible/run/non-run counts: UNAVAILABLE pending that export.
A status: threshold/parity/owner activation gates unresolved; not activated.
B status: post-stop candidate build; installation forbidden before stop/review.

## Astra handover protocol
1. Read this file and the owner's Directive 3; preserve downstream and pilot freezes.
2. Verify protocol commit and remote SHA-256 before any study outcome access.
3. Review exporter SQL authorizer, identity-only exclusions, coverage and date boundaries.
4. Run development only as owner if DB remains private; publish sanitized aggregates only.
5. Report unidentifiable pre-candidacy runs and mutable-ATH limitations explicitly.
6. Freeze at most A1/A2 with a qualifying development-only threshold; commit/hash it.
7. Open holdout exactly once; no iteration. Sparse date clusters remain descriptive.
8. Review A service parity, passive endpoint coverage, exclusion provenance and N/date;
   default activation after pilot stop. Owner approves reviewed bundle before install.
9. B install only after 2026-10-20T06:50:39Z, live-source rebase/review, SHA-256,
   backup and owner install; inspect postflight and preserve rollback.
10. Append each receipt here. No separate handover documents, model/agent/trading
    features, new providers, extra requests or Telegram tests.

