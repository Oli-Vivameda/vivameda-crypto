# Validation record — 3 October 2026

- 140 scanner/wallet tests passed on the engineering server and with isolated local dependencies.
- 9 call-audit tests and 4 standalone context tests are checked for this distribution.
- Manifest verification compares all listed file hashes and detects unlisted source files.
- Wallet installer hashes are refreshed to the bundled code and validated without installation.
- Static publication scan checks common secret formats, sensitive literal assignments and forbidden runtime filenames. This is not proof that every possible secret is detectable.

Not verified: full fresh-host installation, optional browser installation, protected survivor/pool-monitor code and thresholds, full real-wallet coverage, profitable execution or independent reproduction of the private-data fit.

No production rules or running services changed for publication. Scanner/wallet provenance starts at engineering bdc9c2d; initial staging c3e86f5. Docs, unit templates, context extraction and release tooling are distribution additions.
