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
