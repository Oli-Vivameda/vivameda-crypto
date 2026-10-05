# Crypto screening v2 — 3 October 2026

Scope: Solana Pump AMM pools quoted in native wrapped SOL. Unsupported mandatory evidence HOLDs admission. Background missing evidence remains UNKNOWN and is non-blocking under the current admission policy. No trades, signing keys, paid APIs, hosted language models or automatic overrides.

This is bounded risk screening, not proof of safety, complete lifetime wallet history or verified beneficial ownership. Default breakout scores remain 8 / 10. No V2 learning labels or model weights change.

## Evidence and release

The candidate exporter reads scanner data without writing it. Recent pre-alert candidates get queue priority. A dedicated wallet service collects public evidence, keeps SQLite history progress and produces a JSON report plus a wallet map. The scanner recomputes policy and requires fresh PASS for token controls, liquidity control and trading mechanics. Every explicit REJECT in any of the seven checks blocks. The four other UNKNOWN checks are disclosed and non-blocking. Evidence freshness is at most 300 seconds. A report's own PASS label cannot authorise a message. The collector's all-seven screening verdict is distinct from scanner admission.

Holder discovery uses public-provider hints and RPC account census where available. Account owners, balances, mint controls, pool/vault/LP relationships and creator balances are authenticated against Solana RPC. Provider detection dates are not snapshot dates. A complete holdings census is not complete transaction-history coverage.

## Seven decisions

1. Wallet links: review the provider-returned 24-hour history of sampled owners and their discovered token accounts. All indexed successful transactions in the window must be available; disconnected pagination, missing timestamps and unsupported programs HOLD. Observed transfer/shared-sender components above 10% sampled supply reject; creator-linked components above 2% reject. These are exposure rules, not accusations or proof of common control.
2. Developer: compare the candidate creator with the on-chain coin-creator address. Review 30 days of supported address/account history. A supported liquidity withdrawal or sale of the current Pump AMM pool rejects under this conservative policy. Associated mint reports must be present; unresolved or flagged provider risk holds. Address association is not verified real-world identity.
3. Ownership: sampled single-owner share at most 5%, top-ten sampled owners at most 30%, total creator holding at most 2%, and unsampled supply at most 10%. Exclude only the authenticated pool vault. Other infrastructure is not excluded merely by provider label. Holdings outside the sample may share control with sampled wallets.
4. Activity age: creator activity lower bound at least seven days; other reviewed wallets at least one day, with no more than 5% sampled supply in younger wallets. These are activity lower bounds, not creation dates.
5. Token controls: explicit revoked mint/freeze authorities; initialized supported token mint. Unsupported Token-2022 extensions HOLD.
6. Liquidity: authenticated vaults with positive reserves, expected authorities, zero currently redeemable LP supply, supported pool layout, no mayhem mode and no editable/nonzero pool creator fee. Protocol administration and upgrades remain residual risks.
7. Trading: at least three distinct non-creator addresses with successful direct Pump AMM sell instructions within five minutes, matching base-token input and wrapped-SOL output transfers. Verify the accepted global configuration still enables selling. Routed/unsupported sales cannot certify. Distinct addresses do not establish independent people; observed sales do not guarantee future execution.

## Operations

The scheduled batch runs research first (60 RPC calls / 90 seconds) and fast refresh second (20 RPC calls / 45 seconds), at most 80 requests total. RPC rate limits and network errors use bounded candidate-specific retry. Research-budget exhaustion and unsupported transaction responses do not create a global outage. History indexing and rotation persist in SQLite. See WALLET_INTELLIGENCE.md for operations and direct-call defaults.

The map shows PASS/HOLD/REJECT and reasons, plus evidence and wallet links. Raw evidence remains server-side. Storage guardrails remain 3 GiB free disk and 4 GiB top-level evidence-file size (updated 5 October 2026; see EVIDENCE_CAPACITY_20261005.md); reaching them holds work.

Only the scanner sends Telegram. No message is sent by tests or the collector. Public-provider limits can prevent sufficient evidence and therefore prevent alerts. The live probe is not a passing candidate and no profitable trading performance has been established.

## Deployment

The connector deploys the hash-reviewed scanner files. The separate root-owned collector is installed using:
python3 scout/install_wallet_intelligence.py --install

Installer verifies its source manifest before changing dedicated collector files. Existing provider cooldowns are respected. Installation success does not mean a candidate passed.
