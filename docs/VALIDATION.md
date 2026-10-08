# Validation record — 3 October 2026

- 140 scanner/wallet tests passed on the engineering server and with isolated local dependencies.
- 9 call-audit tests and 4 standalone context tests are checked for this distribution.
- Manifest verification compares all listed file hashes and detects unlisted source files.
- Wallet installer hashes are refreshed to the bundled code and validated without installation.
- Static publication scan checks common secret formats, sensitive literal assignments and forbidden runtime filenames. This is not proof that every possible secret is detectable.

Not verified: full fresh-host installation, optional browser installation, full real-wallet coverage, profitable execution or independent reproduction of the private-data fit.

No production rules or running services changed for publication. Scanner/wallet provenance starts at engineering bdc9c2d; initial staging c3e86f5. Docs, unit templates, context extraction and release tooling are distribution additions.

## Publication update - 5 October 2026

Monitor source and thresholds have been published and documented in MONITORS.md; fresh-host installation remains unverified. The capacity release recorded 136 passing wallet tests on the server. Scanner and V2 learner live source hashes matched this distribution at the 5 October status check. Trading scaffold tests use synthetic temporary databases; they establish storage behavior only. Current publication checks are recorded below after execution. See FULL_SETUP.md for the current component inventory; dated test totals above are not a single cumulative suite.

This showcase update: three paper-scaffold tests passed; local relative documentation links checked; release manifest regenerated and verified. No production source, services, budgets or gates changed. No Telegram/provider calls were made by these publication checks.

## Daily learning, 5 October 2026

12 learning tests passed locally and in the engineering-server checkout: exact endpoint coverage, matched controls, frozen policy, append-only/hash-chain records, read-only production access, holdout exclusion, memory staleness/relevance, additive crypto agent patch, nonfinite data and current prospective journalling. The hash-locked installer passed non-install validation. Synthetic fixture results are not real-market performance evidence. Production base activation was verified around 12:12 UTC: successful review/journal runs; 139 development tokens, 78 eligible 60-minute endpoints and 61 missing/incomplete, with six exploratory matched pairs and eight frozen-ledger identifiers excluded. Endpoint extension activation was verified at 12:29:55 UTC; first run successful with zero initial aggregate counts. 18 base/endpoint tests passed locally and on the engineering server. No performance or training claim follows from activation; see [learning](../learning/README.md).

## Directive 2 Task B — interpreter gate

The release check now explicitly supports Python 3.12 and refuses every other major/minor before reading the manifest or starting tests. This is the owner-permitted version-refusal option, not a scorer regeneration or pilot-binding change. Server run: 442 tests, 13 isolated suites and 202 file hashes passed on Python 3.12. Two refusal regressions cover Python 3.13 and 3.14 before file/process access. The displayed Python 3.13 refusal was exercised by substituting version_info in a 3.12 test process; an actual 3.13 interpreter was not available/run. Individual frozen-builder tests may still fail under an unsupported interpreter; no cross-version full-suite claim is made.

Message: `Release blocked: supported interpreter is Python 3.12; Python 3.13 is unsupported because frozen scorer AST hashes are version-bound. Use Python 3.12; deployed source and pilot binding must not be regenerated.`

Next gate: use Python 3.12 for release. No deployed scanner, tracker, scoring policy, frozen fixture or capture activation bytes changed.
