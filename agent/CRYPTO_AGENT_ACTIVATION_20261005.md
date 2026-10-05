# Crypto Lab agent activation — 2026-10-05

Activated at **2026-10-05T13:32:54Z** on Hetzner. This receipt supersedes the activation-pending status in the frozen build documentation, `CRYPTO_LAB.md`.

## Verified installation

- Reviewed bundle SHA-256: `53701ea8ce3a1e9795fb05bc98bb5c958b98e0993b7791ff2848ef0dd8b12bbc`.
- Previous live routing SHA-256: `c54a2d53f12da6414b63f2759538c86e1ae79ff26cd46498f31f0e1787991e87`.
- Installed live routing SHA-256: `6d39a40679b2cbe35f28fc51a6987b82f2b166da6f5a257275082950924b4924`.
- The concurrent company-brief route was reviewed and preserved.
- Installer backup and successful installation receipt retained privately on the server.
- 19 boundary tests passed before installation.
- Post-install connector request `Crypto status` succeeded in under one second; crypto memory and paper summary were available.
- A company-analysis request in the same pinned crypto session returned `DOMAIN_OR_ACTION_BLOCKED`.
- Production scanner and V2 tracker services were active after installation.

## Separation and limits

Crypto sessions use their own conversation database and crypto-only read tools. Company tools are unavailable to this route. Existing mixed history was not migrated. This is application-level separation, not an operating-system sandbox.

The local `qwen3:4b` inference engine is shared. Dedicated crypto weights have not been trained. The first full evidence interpretation request timed out after 150 seconds before activation; no completed model interpretation has yet been verified. Successful deterministic status and boundary checks do not establish model quality or predictive validity.

Scanner source, alert policy, weights and live execution controls were not changed. Live trading remains disabled. No paid API calls were added.

Only source, documentation, hashes and aggregate verification are published. Conversations, runtime databases, case records, credentials and company source remain private.
