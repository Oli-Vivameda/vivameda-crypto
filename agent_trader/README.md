# Paper proposal and feedback scaffold

This is the crypto-relevant public copy of the server's cross-market paper proposal layer (engineering commit `1ff397c`). Domain identifiers also support equities, major crypto and prediction markets; that does not establish adapters or working strategies in those markets.

`agent.py` stores paper-only proposals, evidence hashes, thesis and exit-plan text in SQLite. ACCEPT/REJECT/EDIT feedback creates versioned playbook entries. It rejects UNKNOWN or unverified input evidence. The caller supplies the verified flag: this module does not independently authenticate providers. Three synthetic tests cover unverified input rejection, edit/playbook storage and rejection.

## Current boundary

There is no autonomous Qwen/feed decision loop, continuous service, broker call, wallet access, signing, live order or implemented stop-loss. Feedback is saved rules/examples, not trained weights. EDIT stores a suggested corrected payload but does not automatically rewrite the proposal. ACCEPT sets a local `APPROVED` state; feedback is unauthenticated in this scaffold and is not a trusted execution approval. Never route that state directly into trading.

The existing private server directory `client_learning/paper_execution_v1` contains a separate synthetic paper-execution engine. It is not included or integrated by this folder. Its documented engine supports limit-order simulations, reservations, partial fills, fees, pause, idempotency and reconciliation, and requires an external trusted approval verifier. A future integration needs a separate authenticated owner approval endpoint, exact asset and quantity binding, single-use receipts, a trusted archived bid/ask/depth adapter and independent execution reconciliation. No live adapter or deployed approval UI is claimed.

## Offline use

From repository root:

```sh
python3 -m unittest discover -s agent_trader -p 'test_*.py'
```

The CLI can initialize a local database, list drafts and record feedback. Draft creation is a Python function accepting caller-supplied evidence. Keep personal feedback, database files and account information out of public Git. No production service is installed by this publication.
