# DFlow decoder — engineering validation, 4 October 2026

Status: implemented and replay-tested offline in the engineering checkout. Not imported by production screening, not deployed, and not a claim of improved live coverage. The existing unsupported-program HOLD remains in place.

## Why this component

The owner export contained 260 owner-program incidences for `DF1ow4tspfHX9JwWJsAb9epbkA8hmpSEAtxXy1V27QBH` across 20 reports, compared with 89 for the Pump launch program. These counts overlap and are not unique owners. The latest exported candidate had 65/304 owners observed, one complete-fresh owner, 59 with pending transactions and 34 stale. Decoding alone does not fix collection capacity.

## Primary schema evidence

The Anchor interface was read directly from the finalized on-chain account `Cp2dCjxCWdktak2JiSrh87X6sz31EnDVKoTGtsHJvhYq` at slot 453187502. The account owner matched the DFlow program. The header `184662bf3a907b9e` matches SHA-256(`internal:IdlAccount`)[:8]. The initial read incorrectly expected the ordinary `account:` namespace and stopped at that assertion; the corrected interpretation was checked against Anchor's own source. This was a retrieval check failure, not a production change.

- Decompressed full interface SHA-256: `2d48c967de1fcfa93186c21cee90c2df362da5cbc4dc68219a8a2e8c31c29d82`.
- Published structural schema SHA-256: `0b849cec2747c875630bb021acfec2ce7aa6f2a28f78b03ed5cb44a2b135c021`.
- The live interface had 18 instructions; an independently located reference copy had 17. The live interface supplied the published schema. Documentation prose was omitted from the structural schema.
- Primary derivation/layout reference: https://github.com/coral-xyz/anchor/blob/v0.30.1/lang/src/idl.rs and https://github.com/coral-xyz/anchor/blob/v0.30.1/ts/packages/anchor/src/idl.ts .

An owned interface account documents a declared layout; it does not prove that all deployed execution semantics are understood. Upgrade handling and downstream execution remain separate checks.

## Implemented behavior

`scout/dflow_decoder.py` reads the hash-pinned `dflow_schema.json` and recognizes six top-level swap layouts: swap/swap2, their token-destination variants and their native-destination variants. It checks the program, required account count, fixed account addresses, signer, program account, discriminator, bounded Borsh structure, complete byte consumption and fee/slippage ranges. Unknown variants, malformed input, failed transactions, unsupported versions, truncation and trailing bytes return UNKNOWN. It performs no network calls, database writes, transaction construction or signing.

Its successful status is `LAYOUT_DECODED`, never PASS. Every result explicitly has `history_coverage_complete: false`. Route parameters are declared inputs, not executed amounts. Sponsor, destination and fee accounts are not automatically treated as common-owner links. The parser does not verify every account PDA, downstream program behavior or transfer effect.

## Validation

Ten offline tests passed locally and on Hetzner. Tests cover all six swap layouts, every truncation of the synthetic swap, trailing bytes, wrong program/fixed account, missing signer, failed/missing status, unknown discriminator/variant, vector/boolean/option bounds, invalid version/index, impossible fees and input immutability.

Five public finalized transactions were fetched for replay. All five top-level DFlow swap layouts decoded. Observed actions included PumpFunAmmBuy/Sell, BisonFiSwap, MeteoraDammV2Swap, WhirlpoolsSwap, dynamic routing and sponsor-account setup. All five retained UNKNOWN execution semantics. This tiny convenience sample is a compatibility check, not an estimated success rate or representative coverage result.

The first sample request encountered transaction version 1 while requesting support through version 0 and stopped. The retry explicitly supported version 1, matching the existing scanner's supported versions. Sampling used a maximum of six free public RPC calls per attempt; no paid provider or trading calls were made. Raw public transactions stay in the private engineering review, outside this repository.

The five transactions invoked 13 distinct inner programs, including other routers and venues. All sampled inner instructions had stack heights. Therefore an outer DFlow allowlist entry would hide unresolved downstream behavior.

## Next acceptance gate

Before production integration, reconcile instruction-level descendants and observed token/native effects, test sponsor/fee/destination separation and sibling-invocation isolation, and show that any candidate history marked complete has no remaining undecoded effects. Replay the collector's cached sample to measure actual reduction in unsupported-owner counts. Until then, do not add DFlow to `SUPPORTED`, change freshness limits or claim cluster/age completeness.

Run the standalone tests from repository root:

```sh
python3 -m unittest discover -s scout -p 'test_dflow_decoder.py'
```

## Downstream transfer accounting — follow-up

Implemented `scout/dflow_reconcile.py` and 17 additional tests. The combined suite now passes 27 tests locally and on Hetzner. It remains offline: no production import, gate change or deployment.

The reconciler reconstructs instruction-parent paths from root indices and stack heights. Token owners, transfer authorities and close authorities remain separate fields. Transfers under sibling invocations or other top-level instructions keep separate provenance. Declared sponsor actions do not turn their accounts into common-owner evidence. Platform-fee transfer purpose remains unverified; a matching amount alone does not label a fee or sale. No common-control edges are emitted.

Accounting covers explicit parsed token transfers, native transfers, account funding, network fee deduction and token-account close refunds/unwraps. It compares reconstructed amounts against transaction-wide token and lamport endpoint balances. Token owner changes stop reconciliation before subsequent receipts could use stale ownership; close-authority changes do not alter token ownership. Unsupported effects, missing traces, invalid stack heights, missing balances and residual differences remain blockers.

The same five saved public transactions replayed without network calls. Results are recorded in `research/dflow_reconciliation_results.json` (no account identities or transaction bodies):

| Sample | Accounting records | Token residuals | Lamport residuals | Full history complete |
|---|---:|---:|---:|---|
| 0 | 10 | 0 | 0 | No |
| 1 | 7 | 0 | 0 | No |
| 2 | 11 | 0 | 0 | No |
| 3 | 8 | 0 | 0 | No |
| 4 | 14 | 0 | 0 | No |

Total: 50 records = 38 token transfers, 3 native transfers, 5 account-funding records and 4 close refunds/unwraps. Network fees are separately deducted from the fee-payer balance during reconciliation. `ENDPOINT_AMOUNTS_MATCH` means the explicit accounting matches endpoints; it is not PASS, and offsetting unrecognized effects can still exist. Every result retains `history_coverage_complete: false` and `downstream_program_semantics_unverified`. Samples 0, 2 and 4 additionally flag Token-2022 extensions and new wrapped-SOL reserve verification.

This convenience sample is not a representative coverage estimate. The production collector's protected cache has not been replayed with this component. Actual unsupported-owner reduction and freshness/capacity remain unproven. No paid calls, trades, model changes or screening relaxations occurred.

Added tests cover authority/owner separation, inner-sibling and outer-root isolation, missing traces, stack jumps/duplicates, omitted transfers, incorrect fees/mints, missing balance sides, endpoint identity changes, close authority, owner changes, invalid amounts/underflows, failed transactions, duplicate balances, close-refund classification and input immutability.

Primary accounting references: https://solana.com/docs/rpc/json-structures and https://solana.com/docs/tokens/basics/close-account .

```sh
python3 -m unittest discover -s scout -p 'test_dflow*.py'
```

## Bounded collector-cache replay (prepared, not yet run on production cache)

`scripts/replay_wallet_cache.py` reads at most 1,000 most recently inserted SQLite rows, with a 25-second cooperative time limit, 2 MiB per body and 64 MiB total body budget. This is an insertion-order convenience sample, not a representative or chronological cohort. Only top-level DFlow transactions are reconciled. The database is opened read-only; no network requests, screening changes or deployment occur. Output contains aggregate counts and allowlisted reasons, never raw wallet histories. Four source hashes are pinned before imports.

Seven helper tests pass, including database preservation, sampling bounds, malformed input, privacy filtering, symlink refusal and rejection of unexpected complete-coverage claims. A temporary-cache replay of the five saved public transactions reproduces five endpoint matches and 50 receipts. These are fixture results, not a measurement of the production cache. All complete-history claims remain false.

The engineering account cannot read the protected production cache. From the owner maintenance terminal, run:

```sh
python3 -I /var/lib/vivameda-engineering/repo/client_learning/public_crypto_release_20261003/replay_wallet_cache.py
```

The command prints the private aggregate result path for engineering review. Production-cache results remain pending. Net endpoint agreement does not establish downstream semantics, historical Token-2022 extensions, or a historical wrapped-SOL reserve. No decoder is promoted into the coverage allowlist on this evidence alone.

## Production-cache replay result and targeted diagnosis

The owner-run replay at Unix timestamp 1791104031 examined 1,000 inserted cache rows: 254 DFlow transactions, 155 endpoint matches, 99 unresolved, 3,031 accounting records and zero complete-history claims. No rows were malformed or oversized and the time/byte budget did not stop the replay. This is a convenience sample, not a population estimate.

Overlapping blocker counts: native underflow 53, token underflow 20, unknown route layout 24, native residual 15, token residual 3, account reinitialization 5, historical wrapped-SOL reserve unverified 247, Token-2022 extensions unverified 172 and downstream semantics unverified 176. Early exits mean later blockers are not exhaustively counted. Endpoint agreement does not clear semantic blockers.

The aggregate does not identify the failing instruction or retain detailed layout rejection reasons. No causal fix is justified yet. `scripts/export_wallet_failure_samples.py` selects up to three native-underflow examples and three unknown-layout examples from a fresh bounded sample of at most 1,000 rows. It verifies pinned sources, opens the database read-only, makes no network calls and writes a private, mode-0600 JSON file for the engineering account. Generated transaction samples must never enter the public repository. Four tests check sample limits, database preservation, symlink refusal and rejection of coverage claims.

Owner maintenance command:

```sh
python3 -I /var/lib/vivameda-engineering/repo/client_learning/public_crypto_release_20261003/export_wallet_failure_samples.py
```

This is a new diagnostic sample; the earlier 1,000-row cohort was not frozen and cannot be claimed as an exact paired comparison. Diagnosis and regression fixes remain pending those private traces. Production screening is unchanged.

## Six private failure traces: diagnosis and auxiliary candidate

The private export returned three native-underflow traces and three unknown-layout traces. These are selected failures, not a random sample and not an estimate of prevalence.

All three native-underflow examples follow the same observed sequence: transfer 10,000,000 lamports to an account, spend 1,346,200 creating a PumpSwap-owned account, then attempt to return 10,000,000. The reconstructed balance is 8,653,800 at the return. Between creation and return, the trace contains PumpSwap discriminator `f945a4da9667548a`. The official PumpSwap IDL names it `close_user_volume_accumulator`. The present accounting code skips that raw instruction. An omitted direct close refund is the working explanation; the exact refund destination and runtime semantics are not certified by the IDL alone. No balancing amount has been invented or inserted.

Official reference: https://github.com/pump-fun/pump-public-docs/blob/main/idl/pump_amm.json. Retrieved bytes SHA256: `2091433899b07d003d98118ae6cd3c628960fd393b40710b6e15bce6d0e7f2d1`. This current reference is not historical deployed-bytecode proof.

The three unknown-layout examples contain two `wrap_sol` instructions and one `unwrap_sol` instruction, all present in the previously verified on-chain DFlow IDL. Added `scout/dflow_auxiliary.py` as an offline candidate dispatcher: it retains the existing six-swap decoder and adds strict auxiliary discriminator, length, account-count, message-membership and fixed-program/mint checks. It explicitly does not verify PDA roles, historical reserves or execution semantics. It is not imported by production or the original pinned cache reconciler.

Validation: 33 DFlow tests pass locally and on Hetzner, including six new auxiliary tests. All three previously unknown auxiliary instructions decode on the saved private traces; all nine top-level DFlow instructions across the six traces decode. Complete-history claims remain zero. This is a layout improvement only: native underflows and `syncNative` accounting remain unresolved. No revised 1,000-row cache match rate is claimed.

Next: establish PumpSwap close/refund semantics and account roles, then add explicit receipts and negative regression cases; separately establish historical WSOL reserve evidence before supporting `syncNative`. Production remains unchanged. Private samples are retained on Hetzner and are not published.

## Offline close-refund accounting candidate

Primary developer documentation explicitly states that `close_user_volume_accumulator` returns the accumulator's rent-exemption lamports to the signing user: https://t.me/s/pump_tech_updates/11. This supports refund direction independently of balance fitting; it is not verification of the historical deployed executable.

Added a separate `scout/dflow_reconcile_candidate.py` using auxiliary layout dispatch and a narrow PumpSwap close handler. It requires the exact eight-byte discriminator, four message accounts, correct program role, signing/writable user, writable accumulator, same-transaction creation owned by PumpSwap, zero accumulator endpoint balances, and no duplicate close. The refund uses the tracked account balance, never a hardcoded 1,346,200-lamport correction. It emits a distinct `program_account_close_refund` receipt. PDA derivation and historical deployed-version verification remain explicit blockers. The original pinned reconciler and production imports remain unchanged.

Paired replay on the six saved private failures: baseline zero endpoint matches; candidate four endpoint matches. All three native-underflow examples now reconcile, each recording a 1,346,200-lamport close refund. The unwrap example also reconciles. Both wrap examples remain UNKNOWN with `syncNative` unsupported and token underflow. No complete-history claim is made for any example. This deliberately selected six-case diagnostic set provides no estimate of the improvement over all cached transactions.

Validation: 37 DFlow tests pass locally and on Hetzner. Four additional test methods cover refund accounting, unchanged input, persistent semantic blockers, missing creation, bad discriminator length, bad roles/permissions/owner/endpoints, duplicate close and unchanged baseline behavior. The private replay is saved in engineering job `490c717ca0f25677f880eeae3db81a0d`; tests in `ff8ae37f1ee363112454cbfcdf31d527`.

This is an offline accounting candidate, not a production coverage release. Next work is PDA/historical-version evidence and historical wrapped-SOL reserve handling. A broader frozen paired replay is required before any claim about cache-wide improvement.

## Conditional same-transaction SyncNative candidate

The two remaining examples create, initialize, synchronize and close a legacy SPL wrapped-SOL ATA within one transaction. No token-account endpoint snapshot survives. Both observed creation instructions fund 1,488,440 lamports, but that number is not hardcoded as a reserve.

Primary source inspection confirms that the associated-token-account program's fresh-account branch funds `rent.minimum_balance(space).max(1)`, and token initialization records a native reserve. Current token source also recomputes rent during `syncNative`; historical stored-reserve behavior cannot be assumed universally. References and inspected byte hashes:

- https://github.com/solana-program/associated-token-account/blob/main/program/src/processor.rs — `e8bf0dd2d9ac87ebc488faf73dee2530df6d6dc83bc19907def973c5209953ca`
- https://github.com/solana-program/associated-token-account/blob/main/program/src/tools/account.rs — `92961c7884332d4f1ea3356034b6823cf1a9f086ab4249e9aeff4d17388ddb53`
- https://github.com/solana-program/token/blob/main/program/src/processor.rs — `400cdf9d6d5d18cb3cade83abda7ad4ffb3894ede5e29c189cf8fa2dfa5160a1`

The offline candidate now supports only a narrow conditional creation chain: parsed ATA create/createIdempotent parent, matching account/funder/mint/programs, direct system create of a 165-byte legacy SPL account, zero pre-existing lamports, funding greater than one lamport, matching initialization parent and wallet, and unchanged funding balance at initialization. `syncNative` updates token state without emitting a transfer or moving lamports. Pre-existing accounts, missing reserve evidence, Token-2022 native accounts, balance decreases and inconsistent identity remain UNKNOWN. This deliberately conservative subset does not claim support for every valid token-program version.

The creation amount is used conditionally as reserve evidence from the same transaction. It is not an archived state observation or verified historical executable. `ata_rent_and_historical_program_semantics_unverified` and existing semantic blockers remain. Historical current-state queries were not substituted for missing evidence.

Paired replay of the six selected saved failures now produces six endpoint matches, up from four with the prior candidate and zero with the original reconciler. Both SyncNative cases now match. All six still have `history_coverage_complete:false`; this is conditional accounting, not complete wallet coverage or a population estimate. Replay job: `483d1a8ec3831c656307d1983d9048f0`.

43 DFlow tests pass, including six added methods for conditional SyncNative state updates, wrong parents, invalid funding/size/owner, pre-existing balances, initialization identity and absence of fictitious transfer receipts. Production remains unchanged. PDA derivation, historical deployed-version verification, extension semantics and a broader frozen paired replay remain required before production promotion.

## Independent address verification and frozen-cohort capture

Using `solders==0.29.0` in an isolated temporary engineering dependency directory (not the production environment), independently derived addresses on the six private samples. All 3 PumpSwap closes matched the accumulator PDA (`user_volume_accumulator` plus user seed), event-authority PDA (`__event_authority`) and program role. All 11 parsed associated-token-account creations matched the wallet/token-program/mint-derived ATA. Three altered-user negative checks did not match the original accumulator. Job: `cc53aaa254c56867893ce1e822c24ef0`.

These are sample-specific cryptographic address checks. They are not yet integrated into the candidate runtime, do not establish historical executable semantics and do not clear the candidate's conservative blockers. SDK reference: https://kevinheavey.github.io/solders/tutorials/pubkeys.html.

Added `scripts/freeze_wallet_replay.py`: a root-run, read-only capture that reuses the hash-pinned bounded cache reader, saves all top-level DFlow transactions among at most 1,000 most recently inserted rows, and hashes their canonical JSON. It does not filter for failures or success. Existing limits remain: 2 MiB/body, 64 MiB scanned-body budget, 25-second cooperative time limit. The generated JSON is private (0600, engineering owner), is never uploaded publicly, and preserves exact input for repeated paired replay. No decoders execute during root capture, no network calls occur and no production files change. Two capture tests pass, covering input preservation, cohort hashing, invalid-row accounting and abort behavior, in addition to the existing bounded-reader tests.

Owner command:

```sh
python3 -I /var/lib/vivameda-engineering/repo/client_learning/public_crypto_release_20261003/freeze_wallet_replay.py
```

Broader paired results are pending this capture. The resulting convenience cohort will support a like-for-like decoder comparison, not a representative wallet-population estimate. The prior six-case result remains 6/6 conditional endpoint matches, with zero complete-history claims and 43 DFlow tests passing. Historical program and token-extension semantics remain unresolved; no deployment is performed.


## Frozen cohort: lifecycle and mint/burn accounting (2026-10-04)

The owner captured 243 DFlow transactions from 1,000 cached rows, without a bounded stop. Canonical transaction SHA-256: `52241298442326d0363bff5839e94c6e739b4a49e5642eb1b5adb11bbd4b3c51`. Raw transactions remain private.

| Offline reconciler | Endpoint matches | Unresolved |
|---|---:|---:|
| Original baseline | 156/243 (64.2%) | 87 |
| Previous candidate | 229/243 (94.2%) | 14 |
| Lifecycle and mint/burn candidate | 234/243 (96.3%) | 9 |

The new candidate handles observed token-account close/recreate sequences only when the tracked balance is zero and the token program matches. It also accounts for parsed mintTo/burn amounts with identity and amount bounds checks. Mint/burn state updates are not transfer receipts; authority and supply verification remain explicit blockers. Four recreation cases and one mint/burn case now reconcile. All 48 DFlow tests pass. Against the original baseline, 78 cases improve and zero regress. Complete-history claims remain zero.

Remaining accounting failures: three Token-2022 token residuals, one missing historical WSOL reserve, four native underflows, and one unsupported DFlow transfer_sol layout. Residuals are not automatically interpreted as fees or refunds. Historical executable semantics, extension state and wallet-history completeness remain unresolved even for endpoint matches.

This convenience cohort has now informed development. These percentages describe this fixed sample only; they are not held-out accuracy estimates or evidence of predictive performance. No population confidence interval is claimed. No production code, scanner threshold, or coverage gate changed.

Verification jobs: tests `bccfb7e9206af8e452c4ce46ca227952`; paired replay `c138980782e674644271e8fea77abe07`. Candidate SHA-256: `f3995a1f3cc419f50e5eff8cb69e3ce4c13ce803bfaca70c88ae734c53718171`.


## Pump bonding-curve close refunds (2026-10-04)

Tracing the four native underflows identified three omitted close refunds from the Pump bonding-curve program (`6EF8rrecthR5Dkzon8Nwu78hRvfCKubJ14M5uBEwF6P`). The previous candidate recognized this close instruction only under PumpSwap. The [official Pump IDL](https://github.com/pump-fun/pump-public-docs/blob/main/idl/pump.json) defines the same close_user_volume_accumulator discriminator (`f945a4da9667548a`) and four-account layout.

The offline candidate now allows the two explicit program IDs and checks that both the creation owner and executable account match the actual invoking program. Existing guards remain: exact instruction length, signer/writable permissions, same-transaction creation, zero endpoint balances and no duplicate close. Refund amounts come from tracked balances, never a fitted residual. No other program is admitted.

On the unchanged 243-transaction frozen cohort, endpoint matches rise from **234 to 237 (97.5%)**. Three cases improve; zero regress against either the previous candidate or the original baseline (156 matches). All **50 tests pass**, including rejection of cross-program ownership, incorrect executable, absent creation, nonzero endpoints and duplicate close. Independent derivation matches the accumulator and event-authority addresses in all three cases; these sample checks are not integrated runtime verification or historical executable verification.

Six cases remain UNKNOWN: three Token-2022 residuals, one historical WSOL reserve gap, one native underflow following a Pump sell, and one unsupported DFlow transfer_sol layout. The remaining sell case has a downstream native transfer with no preceding parsed native credit in the current accounting path. Resolving it requires supported decoding of the sell's direct balance effects; endpoint differences alone are insufficient evidence.

Complete-history claims remain zero. Production and screening gates are unchanged. This is the same development sample, not held-out validation.

Tests job: `3151088bf385c56c86dd6d7cfd685aa1`. Replay: `d7f321dfe540a75933a47fc0749d43d6`. Address audit: `486911ecd99f41ca6c107593bd888766`. The first replay submission exceeded command argument limits and did not run; the successful replay compares prior pass/fail membership from the saved previous replay. Candidate SHA-256: `69cd336365800876ce5a94792b559aaa5295685442bda35c3cb446f7148f6e0e`.
