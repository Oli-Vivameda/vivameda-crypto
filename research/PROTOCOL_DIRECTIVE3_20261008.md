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

## Build receipts — 2026-10-08 (no real study outcomes opened)

C: the protocol was committed before study access, published on GitHub main in
commit 69499d5, and its exact remote bytes verified against preregistration
SHA-256 b664efae1447f0cbffff9d53de51141577daf3f8e5f28efd9011d1a2ed099822.
The exclusion-aware exporter is built. Engineering access was refused without
changing permissions. Actual development candidate-minutes, run/non-run counts,
feature distributions and qualifying thresholds remain UNAVAILABLE. No holdout
has been opened and no rule has been frozen. Never-visible pre-candidacy runs
cannot be counted from retained snapshots/latest launch metadata.
Next gate: owner runs the following read-only development command and returns
only its aggregate JSON. This opens development labels, never pilot endpoints
or prediction bodies; exclusion identities stay private.

```bash
python3 /var/lib/vivameda-engineering/repo/client_learning/crypto_directive3_20261008/research/earlier_entry.py --phase development --expected-sha256 8a8a7e54d3807e583fb07a1eefbfe0ec3378daf803ee8100c3c4c1dfc49ce60c
```

Wallet coverage: complete-and-fresh required-owner histories / required owners =
UNAVAILABLE pending the same owner export; no wallet-quality feature was built.

A: separate read-only shadow candidate, own append-only SQLite, deterministic R
control draws, passive covered endpoints and refusal gates built; activation
count 0. A2 threshold remains null and owner_approved remains false. Stored
alert_level is delivery state, so exact current-score parity is not verified.
Independent polling does not guarantee the scanner's exact cycle or timestamp;
owner must approve that estimand or require a separately reviewed parity route.
No extra provider requests are included. Candidate request budget is 0.
The exclusion view reads pilot cohort membership, so before-stop activation does
not meet the requirement to read nothing the pilot writes and is not selected.
Next gate: development-qualified rule freeze, committed hashes, service-user
read-only access verification and owner approval of estimand, sample and stop.
Installer leaves the new timer disabled; no activation command is authorized now.

B: append-only launch-path module and a separate scanner text candidate built;
no deployed scanner bytes changed. Candidate scanner SHA-256:
0f178cac4b45bf972aa8dd5c6f1b399b4dbc1b5211123ca384bb5109fd6adba6.
Hook uses only existing upsert_pump observations; extra requests 0. All-launch
creation coverage and disk fit remain unverified. 512 MiB cap, 3 GiB free-space
gate and 30-day archive-review stop are implemented without automatic deletion.
Both installers conservatively refuse until 2026-10-20T07:53:39Z (pilot stop plus
63-minute passive-follow-up allowance); this is a deployment guard, not a change
to the pilot stop or research outcomes. Source backup and source-hash postflight
are implemented; service restart/activation is left to the reviewed owner action.
Rollback: restore backed-up scanner bytes, retain private captured path data,
remove or leave the new module inactive, and owner-restart only after stop.
Next gate: post-stop live-source re-audit, reviewed bundle SHA-256, owner install,
normal-cycle path-write postflight and aggregate cap/coverage receipt.

Validation across C/A/B: 49 focused synthetic tests passed on server Python 3.12
(0.580 seconds) and local Python 3.12. No actual development or holdout results,
production installs, pilot changes, restarts, new provider requests or Telegram
sends occurred. This is candidate-build validation, not live parity or efficacy.
The accompanying bundle_manifest.json binds every candidate file by SHA-256.
Final publication requires verification of every changed file's remote bytes.

## Astra handover — current next gates

1. Preserve the fixed pilot stop, frozen production files and downstream layers.
   Use Python 3.12. Read this protocol and verify the review manifest first.
2. Obtain only the owner development aggregate from the command above. Do not
   widen private permissions or read prediction bodies/pilot endpoints. If the
   exporter refuses, diagnose its reviewed guard instead of bypassing it.
3. Append actual development counts and distributions here. Label invisible
   pre-candidacy counts unidentifiable and report retention/ATH limitations.
4. If the preregistered development qualifications pass, freeze at most A1/A2,
   commit the rule bytes and hashes, then permit the one-shot holdout route.
   Do not iterate after opening; inadequate date clusters stay descriptive.
5. Keep shadow activation blocked until parity/estimand, read-only access,
   development threshold, sample, stop and owner approval gates are satisfied.
   Respect the conservative post-stop installer time gate; no new requests.
6. After stop and review, install B only against matching live source with a
   backup, exact bundle SHA-256 and owner install. Verify source hashes and the
   first normal-cycle append without sends; retain rollback and private data.
7. Append short receipts and all subsequent handover updates to this file only.
   Publish aggregates only and verify remote hashes after every publication.

## Owner development receipt — 2026-10-08

This append supersedes the pending development-export status above. Source:
owner-supplied aggregate JSON from the reviewed development exporter; cutoff
2026-10-08T18:10:00Z. No private rows were supplied or inspected by engineering.
Input digest: 28e1a8169a7128dad3b4bd160de9663a7a42c9260b4b7c38326e843a1a331fa4.
79 excluded mints; identities exported false, ledger values read false, pilot
outcomes read false, provider requests 0, production changed false, holdout
opened false. Pure live function bytes match the reviewed source. Live full
source digest 765aba08982c3f0c562b52755ab9122cdaabfc396b78e7fed878089db87fa54e
DIFFERS from the engineering source digest. This is not evidence of a production
change by this directive. The post-stop scanner patch installer must refuse
that full-source mismatch and require a fresh source review/rebase.

### C counts, scope and development result

7,388 nonexcluded observed minutes: 4,783 base/invalid exclusions, 43 age/pair,
242 coverage gaps, 1,248 missing endpoint, 528 scorer-history exclusions, 60
split/immature and 484 covered windows. These sum to 7,388. Of the 484 covered,
208 have partial prehistory and are separated; 276 meet the full-history study
eligibility. UTC-date counts: 6 October 103; 7 October 173.
Full-history labels: 76 run, 67 non-run, 133 intermediate (sum 276). Base run
rate 76/276 = 27.54%. This is a retained snapshot-observed candidate-minute
baseline, not all launches, original top-60 scanner cycles, independent tokens
or the historical 7% alert endpoint-doubling baseline. Run-onset label means a
within-60-minute peak; endpoint doubling is a different quantity.
Partial-history labels: run 50, non-run 76, intermediate 82 (sum 208), excluded
from the primary development analysis. The 76 run minutes represent six tokens
and six nonoverlapping episodes; overlapping minutes are not independent.
Only 20 same-hour/day non-run comparisons were sampled; two run hours had no
comparison. Feature contrasts below use all 76 run minutes vs those 20 selected
comparisons, so imbalance and clustering limit any generalization.

| Development selection | Minutes | Tokens | Days | Run / non-run minutes | Run rate | Median 60m MC multiple | 60m endpoint >=2x |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| A0 current score | 56 | 9 | 2 | 5 / 29 | 8.93% | 1.0752 | 0/56 |
| A1 h1 hard gate | 6 | 2 | 2 | 1 / 2 | 16.67% | 1.6573 | 0/6 |
| Each A2 grid gate (1.10, 1.25, 1.50, 2.00) | 4 | 1 | 1 | 1 / 0 | 25.00% | 1.6758 | 0/4 |

These are repeated eligible minutes, not forward shadow decisions or executions.
A1 retains 6/56 A0 minutes (10.71%) and drops 50/56 (89.29%). A0 selects 5/76
run-labelled minutes (6.58%); A1 selects 1/76 (1.32%). These are minute overlaps,
not unique-episode recall. A1's higher median and peak rate are descriptive:
only two tokens, six minutes, two dates, zero endpoint doubles. All four A2
thresholds select the same four minutes; no threshold discrimination is present.
Each fails the frozen gate of >=20 run minutes, >=20 non-run minutes and >=2
UTC dates. Therefore proposed_g=null and rule_freeze_ready=false. A2 final arm
has zero decisions because no threshold was frozen. No rule file is created.
No clustered inferential claim is made with only two development dates.

### Development feature distributions

Median [p25, p75]; run n=76 vs hour/day-matched non-run n=20 throughout unless
missing is stated. Fractions use decimal units; pc fields are percentage points.

| Feature | Run | Matched non-run |
| --- | --- | --- |
| Age seconds | 5219 [4208.75,10527] | 5442 [5157,6554] |
| MC / first retained MC | 2.6471 [2.2035,3.3868] | 5.3654 [4.9537,6.0476] |
| MC gain since first retained observation | 1.6471 [1.2035,2.3868] | 4.3654 [3.9537,5.0476] |
| First retained age seconds | 2099 [2027.5,4092] | 1812 [1812,2099] |
| First retained pc_h1 | 1.55 [-22.87,6.85] | 1.55 [1.55,1.55] |
| 30m band | 1.8646 [1.5504,2.5374] | 2.2701 [2.0827,2.4632] |
| 30m net MC change | 1.0897 [0.4112,1.5217] | 2.1140 [1.2726,2.3827] |
| Hour buy ratio | 0.5542 [0.5199,0.5647] | 0.5466 [0.5389,0.5706] |
| 5m buy ratio | 0.5694 [0.5151,0.6017] | 0.5016 [0.4412,0.5733] |
| Liquidity USD | 30900.92 [27944.42,35529.22] | 45392.57 [43545.91,48325.73] |
| 30m liquidity change | 0.4996 [0.2123,0.6639] | 0.8308 [0.5610,0.9132] |
| MC USD | 126550 [100916.5,139964.75] | 261183.5 [241140.75,294390.25] |
| pc_h1 | 180 [116.25,260.75] | 499.5 [449,562] |
| pc_m5 | 13.47 [-1.56,36.79] | 18.225 [8.0025,41.2975] |
| Score | 6 [6,6] | 6 [6,7] |
| Hour transactions | 3721 [516.5,4568.5] | 758 [693.75,3717.5] |
| 5m transactions | 192.5 [81.75,278.75] | 119 [87.5,349.75] |
| Volume acceleration | 0.7106 [0.5353,1.1024] | 1.5540 [1.1454,2.1030] |
| Hour volume / MC | 2.2129 [0.2624,2.6275] | 0.2386 [0.2135,1.3662] |
| 30m history seconds | 1800 [1800,1800] | 1800 [1800,1800] |
| 35m history seconds | 2100 [2040,2100] | 2100 [2100,2100] |
| Historical MC / pump ATH | unavailable; 76 missing | unavailable; 20 missing |

Descriptive pattern: runs were less extended than matched non-runs, but already
had median +180% hourly change and 2.65x first-retained MC. These data do not
establish pre-run accumulation detection or a profitable entry rule. No new
feature, weight, threshold or signal is selected from these contrasts.

| Existing signal | Run passes /76 | Matched non-run passes /20 |
| --- | ---: | ---: |
| band_compact | 2 | 0 |
| buy52 | 56 | 20 |
| h1_not_extended | 3 | 0 |
| higher_low | 65 | 20 |
| liq25k | 76 | 20 |
| liq_stable | 74 | 20 |
| m5_not_extended | 17 | 6 |
| net_constructive | 11 | 0 |
| txns100 | 76 | 20 |
| vol_mc25 | 63 | 9 |
| volume_accel | 17 | 14 |

First observed episode age: median 3095.5 seconds [1884.5,5191.5], n=6.
Two episodes were first observed extended. This is NOT the number of runs
never visible before candidacy: that count remains unidentifiable/null.
Historical pump ATH and historical candidate trade/top-60 state are absent;
48-hour retention makes the first retained observation an incomplete anchor.

Wallet coverage (single aggregate line): 0 complete/fresh owner-token requirements
of 111 KNOWN required; 1/7 current nonexcluded candidate reports verified; full
required-owner denominator unverified; freshness limit 300 seconds. No build.

C next gate: stop at the preregistered insufficient-development result. Holdout
stays closed. Do not rerun against a moving retained-history population, relax
qualifications, change dates, add thresholds or collect a new research sample
under this protocol. A separately reviewed owner amendment would be required.

### A/B receipts after development

A: 0 activated services and 0 forward shadow decisions. No development-qualified
A2 threshold, no frozen rule and no permission for holdout/activation. Exact
scanner-cycle parity remains unverified. The candidate stays inactive; the
existing 49 synthetic tests do not establish efficacy. Next gate: separately
reviewed owner decision on the insufficient sample, preserving the holdout.

B: unchanged zero-request append-only candidate; 0 installs and no production
bytes changed. Full live-source mismatch above is now verified by owner output.
Keep the installer refusal. After pilot stop plus passive-follow-up allowance,
re-read live source and build/review a patch against its actual bytes before
owner installation; do not substitute a hash to bypass review. Creation-path
coverage and disk fit remain unverified. Retain current backup/rollback gates.

## Astra handover — development result supersedes pending-export steps

1. Treat this owner receipt as the development result for input digest above;
   previous pending-export instructions are historical. Publish aggregates only.
2. Preserve g=null, rule_freeze_ready=false and holdout_opened=false. Do not
   freeze a rule or invoke holdout. Do not repeat development or alter its gates.
3. Explain that the 27.54% base rate is overlapping candidate-minutes and peaks;
   A0's 8.93% and A1's 16.67% are not endpoint doubling or independent trials.
4. Keep A inactive. Any proposal for a larger development sample requires a new
   reviewed owner amendment with an untouched holdout and outcome-independent
   collection plan; no automatic extension or backfill is authorized.
5. Keep B build-only until the post-stop review. Audit the changed live source
   before rebasing; never alter the frozen production scorer or running pilot.
6. Wallet evidence remains insufficient (0/111 known, denominator incomplete).
   Build no wallet-quality feature. Downstream layers and scheduled checks stay
   under their existing directives. Append future receipts to this file only.

## 2026-10-08 — Directive 3 Amendment 1: owner-authorised snapshot custody

This amendment supersedes the previous prohibition on collecting a new research
sample. The owner explicitly permits the separate read-only archiver despite the
pilot's indirect dependency: early_scout.history() reads snapshots, then scoring
passes history into fc_emit_cycle(). No scanner, scorer, capture or pilot bytes,
inputs or records are changed. This permission does not authorise pilot analysis.

### Custody installation and operational gate

The new hourly oneshot opens only scanner.snapshots with URI mode=ro,
query_only=ON and busy_timeout=500ms; immutable is forbidden so committed WAL rows
are visible. An SQL authorizer denies every other source table. No capture.sqlite
access, ledger-table access, provider requests, network or Telegram calls occur.
The existing non-root health service user is reused only after owner approval of
that identity. New service filesystem isolation makes scanner and health paths
read-only and capture's directory inaccessible. Engineering permissions, existing
units and production sources are not changed. Nice=19; I/O scheduling is idle.

Each source read transaction selects at most 5,000 rows ordered by (ts,mint),
then rolls back immediately before archive writes or checks. A one-second query
progress limit, 20-second overall copying bound and 20-batch bound limit load.
Busy/locked/interrupted batches are skipped without a retry loop; next hourly run
resumes from the archived composite checkpoint. Rows newer than two minutes are
left for a later run because scanner minute rows can still be updated. Archive
keys are (mint,ts); repeated keys retain their first copied values. UPDATE/DELETE
triggers protect both snapshots and checkpoints. No automatic deletion occurs.

The same B limits apply: 512 MiB cap, 3 GiB minimum free, with a conservative
reserve for rollback journaling and logs. At a storage guard the new timer is
disabled and an aggregate incident remains in its own state. Row logs contain
only count, copied timestamp range and runtime, never mint, pair or source values.
Copies can include excluded tokens in private custody, but no archived token rows
are queried for study, exported or summarised until the existing pilot/ledger-mint
exclusion is applied. Initial retained rows before activation are custody only;
they are not new development decision-minutes or a pilot backfill.

Because existing read_status.py has current counters rather than a retained
hourly history, installation begins with a two-hour baseline and zero copied
rows. Counts come only from the existing sanitized read_status route, whose bytes
are pinned; no pilot DB is opened. At the first copy attempt after that baseline,
a durable, non-resetting activation record fixes the collection dates before any
snapshot read. Any failure does not reset the dates. The before and after reports
include their actual status timestamps, accepted/rejected count deltas, last
successful-cycle age, scanner WAL size and batch runtimes. The first after report
spanning at least two hours is retained separately in private operational state;
actual elapsed duration is shown if hourly status timing exceeds exactly two hours.

Material rejected-rate rise is predeclared as >=5 percentage points over baseline
once each comparison has >=20 observed cycles. A smaller baseline fails closed.
An existing health incident logged during any run, any WAL growth relative to the
previous copy-run measurement, missing/stale health evidence or guard failure also
requests an immediate stop. A root ExecStopPost checks the sanitized existing
incident audit and disables ONLY vivameda-snapshot-archive.timer. It accepts no
other unit names or command text. No scanner/pilot diagnosis or restart occurs.
An ordinary WAL growth can therefore conservatively stop collection; owner review
is required before any resumption. Source/user/access drift also refuses install.

Reviewed rollback: disable/stop only the new timer; leave its archive and logs in
place, with no deletion and no production restore required. The installer backs
up the unchanged scanner and learning source, records their hashes and verifies
unchanged existing unit/source hashes after install. It refuses an existing new
component rather than resetting activation or overwriting its archive. B still
requires a freshly reviewed post-stop patch against the actual live scanner hash.

### New dated development and sealed holdout

Let T be the activation timestamp written immediately before the first copy
attempt after the two-hour baseline. Development decision-times are [T,T+21d);
holdout decision-times are [T+21d,T+28d). Only the existing 60-minute labels,
<=180-second lateness/gap coverage, features, exclusions and temporal safeguards
apply. Endpoint maturation and archive coverage at boundaries must be enforced;
no decisions outside these fixed windows are added or backfilled. Collection
stops independently of outcomes at T+28d. Holdout stays closed until qualifying
rules are frozen. A failed/insufficient window does not automatically extend.

Qualifications remain >=20 run minutes, >=20 non-run minutes and >=2 UTC dates;
also report episodes, unique tokens, date counts and decision-day clustered
uncertainty so repeated minutes are not treated as independent trials. Incomplete
prehistory, historical candidate/trade state and missing ATH remain limitations.
The post-stop launch-path change can create differing observation coverage within
this window: report coverage by date and anchor type; do not equate a first stored
candidate MC with launch MC or retrospectively invent pre-candidacy paths.

A1 is comparison-only: h1_not_extended removed 73/76 development run minutes;
combined score+A1 selected just 1/76. g remains null; no A2 choice was qualified.
No new shadow service, agent, wallet feature, signal or trading feature is activated.

### Second-leg continuation family: grid frozen before new outcomes

The existing development contrast motivates a continuation hypothesis: median
five-minute buy ratio was 0.569 for runs versus 0.502 for matched non-runs, and
hourly volume/MC was 2.213 versus 0.239. These are six episodes over two dates,
not evidence of a predictive edge. Define S independently of A1's hour-extension
hard gate and without requiring the current score threshold. Existing candidacy,
coverage and exclusions remain mandatory. Fixed gates: first stored same-pair
anchor multiple >=2; current MC/prior-30-minute peak >=0.5; five-minute buy ratio
>=0.55; five-minute transactions >=100. The peak uses only snapshots strictly
before t0, and the anchor is the first available archived same-pair MC, not launch.

Exactly two tunable parameters and their full grid are frozen now:

| Parameter | Frozen values |
|---|---|
| Maximum current MC / strictly prior 30-minute peak | 0.75, 0.90, 1.00 |
| Minimum hourly volume / current MC | 0.25, 1.00, 2.00 |

The nine choices cannot be enlarged after collection. Select the qualifying choice
with highest development run precision; ties prefer smaller maximum peak ratio,
then larger minimum volume/MC. Qualification applies to selected run/non-run
minutes, not all development labels. At most two candidate rules can be frozen:
one qualified A2 and one qualified S. A1 remains a comparison. A family with no
qualifying choice produces no rule; no qualifying rule means no holdout opening.
Open holdout once, report decision-day clustered results, and do not iterate.
The machine-readable grid is archiver/second_leg_grid.json. Production thresholds
and weights remain frozen; these are research definitions only.

### Amendment receipts and remaining gates

Custody build: 20 Python 3.12 synthetic tests passed locally and on the engineering
server (Python 3.12.3); all 49 existing Directive 3 tests also passed (69 total).
Both new systemd units passed syntax verification. Tests include WAL
visibility, forbidden source-table access, read transaction closure, bounded
batches, dedupe/resume, append-only triggers, busy skip, storage guards, rate/WAL/
health kills, fixed-unit stop authority, preserved two-hour postflight and metadata
receipt without archive access and symlink-safe privileged marker writes. No real snapshot rows were read by engineering.
Actual install, first copied row count/time range, effective service access and the
live two-hour after comparison remain unverified until the owner installs and
returns the aggregate receipt. Provider requests=0; new Telegram sends=0.

B receipt: unchanged build-only; 0 installs. Re-audit actual live source after
2026-10-20T06:50:39Z and existing follow-up constraints before reviewed owner install.
A/C receipt: historical development insufficient (6 episodes, 2 dates); new window
not activated by engineering, holdout closed, g=null, 0 new shadow decisions.
Wallet scope stays frozen: 0 complete/fresh of 111 known owner-token requirements;
full denominator unverified. No new wallet work.

Owner recovery-notification receipt: recovery messages inactive, incidents active;
health source 611bb7f873f985af55b76bc29efe11a1ac88a56bf3048336be17ab736a089ddf;
backup /opt/vivameda-operations/crypto-health-recovery-inactive-f2nbx87u; five tests
passed, no restart, pilot or unit changes. Normal-cycle recovery_suppressed evidence
remains pending. The archiver observes incident states regardless of send result.

### Astra handover — Amendment 1 is controlling

1. Preserve this amendment's permission boundary: custody only; no pilot outcomes,
   ledger contents, production changes or downstream builds. The prior small-sample
   no-new-collection gate is superseded solely by the fixed archive window above.
2. Verify published source hashes and the owner bundle digest before owner install;
   use the approved existing health user, without expanding engineering access.
3. Record installation backup, zero-row baseline receipt, activation timestamp,
   first-copy row count/time range and per-batch runtimes in THIS protocol only.
   Obtain aggregate metadata with archiver/read_receipt.py; do not inspect its DB.
4. Check the preserved two-hour postflight and timer state. Any kill condition must
   leave only the new timer disabled. Do not investigate by touching pilot/scanner.
5. Keep g null and holdout closed; apply existing exclusions BEFORE study queries.
   Do not read new development outcomes until the fixed development window closes.
   Do not enlarge the nine-choice S grid, iterate holdout or extend collection.
6. Keep A inactive; keep B pending post-stop live-source re-audit. Publish aggregates
   only, bind changed files by SHA-256 and verify those hashes on the public remote.


### 2026-10-08T19:25Z — owner archiver installation refused

The owner ran the reviewed 012afbd8d1fd635c89edafe11cbb895d899e0c539bb0f2230b5b438493cdd73b
installer and received its generic refusal. The failed stage and whether new
component files were partially created are NOT established by that message.
Do not claim installed, unchanged production, or an inactive timer without the
read-only diagnostic. No reinstall, permission expansion or cleanup is authorised
by the refusal. Engineering cannot inspect the protected production source paths.

A separate owner-only check_install_preflight.py diagnoses fixed installer stages
without opening production databases or installing/restarting any component. It
reports sanitized stage flags, hash checks, fresh-status metadata and the NEW
timer's ActiveState/UnitFileState. Exceptions expose category only. Its synthetic
tests use temporary fixture databases; four diagnostic tests passed on Python 3.12
locally and on the engineering server. The original eight-file install bundle is
unchanged; this diagnostic has its own source SHA-256. No providers or Telegram.

Next gate for Astra: obtain the diagnostic aggregate and identify the actual failed
stage. If there is a partial install, preserve all archive state and activation dates.
Repair only reviewed new-component code or installation assumptions, without
relaxing the owner's read-only, health, disk or frozen-source gates. Any revised
installer requires a new bundle hash, owner install and postflight. Holdout remains
closed and g remains null. Append the diagnosis and subsequent receipt here only.


### 2026-10-08T19:45Z — owner archiver installed; baseline only

Owner diagnostic: all 11 preflight stages passed. Scanner/status-route hashes
matched, existing service user vivameda-scout had the required path readability,
health report was collecting and five seconds old, all six frozen source/unit
files were readable, and all four new-component existence flags were false.
The new timer was inactive. The earlier generic refusal was not reproduced; its
actual cause remains unknown. No source changes or new bundle were needed.

Owner installation then succeeded and validated the same reviewed bundle:
012afbd8d1fd635c89edafe11cbb895d899e0c539bb0f2230b5b438493cdd73b.
Backup: /opt/vivameda-operations/snapshot-archiver-source-backup-g2i7g2s2.
The installer verified unchanged frozen scanner/learning source and existing unit
hashes, installed only the separate component, and enabled/checked its new timer.
This is owner-reported install postflight, not an independent live filesystem audit.

| Baseline field | Owner-reported value |
|---|---:|
| Health checked_at (Unix seconds UTC) | 1791488646 |
| Health checked_at UTC | 2026-10-08T19:44:06Z |
| Accepted cycles, cumulative | 414 |
| Rejected cycles, cumulative | 3047 |
| Last successful cycle age, seconds | 521 |
| Scanner WAL bytes | 18313432 |
| First-run copied rows | 0 |

First-run copied timestamp range is null. These cumulative cycle counters are the
starting baseline, NOT two-hour deltas or a post-install rejection rate comparison.
No first copy has been verified. collection_activation_pending=true: the development
and holdout dates are not yet assigned; T must come from the durable activation
record at the first copy attempt after the baseline, not the install timestamp.
Engineering permissions unchanged; scanner_changed=false; pilot_modified=false;
provider_requests=0; telegram_sends=0. Holdout remains closed and g remains null.

Next gate: obtain the owner metadata receipt after the first copy and again once
the two-hour after-window report is available. Record actual activation date,
first copied row count/time range, batch runtimes, accepted/rejected deltas, last
successful-cycle ages, WAL measurements and any scoped timer stop. No outcomes,
archive identities, database queries or production restarts are needed.

```bash
python3 /opt/vivameda-snapshot-archive/read_receipt.py
```

Astra: the installed baseline receipt supersedes the previous pending-install
gate. Do not reinstall, reset activation or delete archive state. Honour the
existing immediate timer kill conditions. Keep A inactive, B pending post-stop
source re-audit, and all downstream layers frozen. Append future receipts here only.
