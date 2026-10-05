# Dedicated Crypto Lab agent

Built 5 October 2026. The crypto-only agent is separate from the company-analysis agent: its own conversation database, fixed read tools, instructions and evidence selection. It shares the existing local Qwen3 4B inference engine, with a stateless request containing crypto context only. No dedicated crypto-trained weights are claimed.

Engineering status: boundary tests and direct status/memory reads succeeded. The first live model interpretation request timed out after 150 seconds; a completed natural-language interpretation remains unverified. Connector routing activation is pending the hash-locked owner installation. This is an application/tool boundary, not an OS sandbox against privileged users.

## Supported tools

| Command | Result |
|---|---|
| `Crypto status` | Domain, tool boundaries, model identity and evidence availability |
| `Crypto rules` | Dedicated operating instructions |
| `Crypto memory: topic or mint` | At most six dated case cards and three matched examples, with selection scope disclosed |
| `Crypto paper status` | Fresh decision-time endpoint aggregates, separate from filled trades |
| `Crypto explain: question` | Local model interpretation of fresh crypto evidence; model output cannot call tools |

Crypto has no company/workforce/client/provider tools and no trade-signing, service mutation or training actions. Only the fixed crypto memory and paper summary JSON files are readable through its tools. Symlinks, wrong-domain evidence, stale/future timestamps, oversized packets and incomplete model responses fail closed. Retrieved content is data, never tool authority. The model can still make factual mistakes; no language-model reliability or predictive edge is established by isolation tests.

Conversation state is stored separately under `/var/lib/vivameda-crypto-agent/` with a crypto domain marker. Existing shared conversations are not imported. The new dispatcher executes before the company conversation database is opened. Sessions named `crypto` or starting `crypto-` / `crypto_` are pinned to crypto for all follow-ups and history. An explicit `Crypto ...` command in another session maps to a distinct crypto session; it never writes company history. Company context no longer automatically attaches crypto rules or baseline results. Use separate sessions for the two lanes.

## Activation

Engineering tests and a non-install validation precede owner installation. The installer accepts an exact reviewed bundle hash and exact current live company-entrypoint hash; concurrent changes abort installation. It backs up the entrypoint, installs dependencies first, patches only domain dispatch/context selection, creates private state and verifies a crypto status response. It does not restart scanner, journal, wallet or company services. Fresh queued workers load the route; an already-running worker finishes with its old code.

Use `python3 install_crypto_agent.py --expected-sha256 BUNDLE --expected-live-sha256 LIVE` to validate. Add `--install` only in the existing owner maintenance terminal. This package being published does not establish activation. Check the installation receipt and a new `submit_agent_request` using session `crypto-lab` and question `Crypto status` before reporting the connector route live.

The independent engineering check runs `crypto_agent.py --state /var/lib/vivameda-engineering/crypto-lab-agent --session crypto-build-check "Crypto status"`. This is a private verification namespace, not the deployed conversation store.

## Validation and rollback

Run `python3 -m unittest discover -s . -p 'test_crypto_agent.py'`. Test cases use synthetic temporary evidence and conversation files; they establish boundary behavior, not market performance. Root-owned installation requires the existing owner maintenance path because the direct engineering connector runs without root permissions.

Rollback restores `session_agent.py` and any previous sibling modules from the named backup. Keep the separate append-only conversation/evidence files for audit; do not delete or merge them. The runtime, conversation database and evidence remain private on Hetzner. Only this crypto package, tests and aggregate status are public; no company agent source is included.

## Training boundary

Crypto numerical artifacts remain separate from workforce models. Daily retrieval does not train weights. Collect prospective decision-time features and timely endpoints outside the frozen ledger cohort. Before a fit, freeze target/cohort, chronological and mint-separated splits, baseline, metrics and stopping/promotion rules. No training, automatic promotion, production alert-policy amendment or live execution follows from installing this agent. A dedicated crypto language-model adapter is a later evaluated artifact, not part of this separation release.
