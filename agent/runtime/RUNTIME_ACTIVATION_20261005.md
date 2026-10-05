# Crypto runtime activation — 2026-10-05

Activated on Hetzner at **2026-10-05T14:31:55.972709Z**, then verified through the restored direct connection. This record supersedes activation-pending statements in the frozen runtime build documentation.

## Verified

- Installed bundle SHA-256: `ffc7a1176509a54728862e17ea00893559b807330f0d086d4e3c13a6c290e98d`.
- Dispatcher SHA-256: `771a8bb8d210c4bcb3259336903fd0555149d723feb5196f1a7d9ca4843a9eb4`.
- Workspace SHA-256: `9a5930af9c6f4e92f4ceeea4fd0ce513812e3b841e36e8ff27a6676957159861`.
- Helper SHA-256: `99b75123a64c82015c350f3719c313e0141a5052d7c65e1e47688cd907c9a6a4`.
- Installed package and all three routing hashes matched the installation receipt.
- Crypto runtime, model gateway, company workspace, helper, direct connector, scanner and V2 tracker services were active.
- Dedicated worker runs as `vivameda-crypto`, with 1 CPU quota, 256 MiB memory limit and `AF_UNIX` only.
- Installer's live isolation check reported internet socket creation blocked and company paths invisible.
- Connector crypto status and an unprefixed follow-up completed in the private runtime queue. Fresh crypto memory and paper summary were available.
- Company-analysis request inside that crypto session returned `DOMAIN_OR_ACTION_BLOCKED`.
- A separate company help request succeeded through the original company route.
- 18 runtime tests passed on Hetzner before installation, including Unix peer credentials and queue responsiveness.
- A live interpretation request failed quickly with `MODEL_MODE_UNSUPPORTED`; no partial model answer was returned.

## Connector refresh after installation

The frozen v1 installer restarts the helper and workspace, but not the direct connector. After installation the helper was active while connector calls returned internal errors. The owner ran:

```bash
systemctl restart vivameda-connect.service
```

Direct checks succeeded afterward. The exact transport-level cause was not established. For this v1 package, include the connector restart in the installation procedure and verify a direct status call. Do not blindly rerun the installer: existing runtime paths intentionally require review.

## Remaining shared components and limits

The host, kernel, disks, authenticated ingress and Ollama inference process remain shared. Worker limits do not cap computation inside shared Ollama. Dedicated model weights have not been trained. The installed `qwen3:4b` thinking-only variant is incompatible with the crypto agent's `think=false` request. Full evidence interpretation remains unavailable until a compatible configuration is reviewed and tested.

The company workspace is active and its help route passed; no claim is made here that every company research workflow or mobile browser flow was exercised. Old crypto history remains preserved in its earlier private directory and was not migrated. New crypto jobs/conversations use the new private state directory.

Scanner policy, weights and live execution were unchanged. Live trading and paid calls remain disabled. Runtime data, conversations, credentials, cases, backups and company source are excluded from GitHub.
