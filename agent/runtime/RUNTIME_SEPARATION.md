# Crypto runtime separation v1

Built 2026-10-05. **Activation pending owner installation.** This extends the activated application boundary without changing the scanner or company model.

## Components

| Component | Role | Limit |
|---|---|---|
| `vivameda-crypto-runtime.service` | Dedicated crypto queue, worker and conversation database | 1 CPU, 256 MiB, 32 tasks; Unix sockets only |
| `vivameda-crypto-model.service` | Fixed-model inference gateway | 0.25 CPU, 96 MiB, 8 tasks; localhost only |
| `runtime_gateway.py` | Connector, mobile workspace and CLI routing | Crypto never falls back to the company worker |

The worker uses a dedicated locked OS user. Its mount namespace hides `/var`, `/opt`, `/mnt`, `/run` except for its own application/state, crypto learning evidence and required Unix sockets. Home directories are hidden. Evidence is read-only; binding its directory preserves daily atomic file replacements. The worker cannot open internet sockets. The inference gateway accepts only the fixed model, bounded chat options and messages; it exposes no model administration, tools, file reads or arbitrary URLs. Unix peer credentials restrict queue access to the existing authenticated owner gateway user and model access to the crypto user.

The source patch changes only routing entry points. Company code, credentials, data and client material are never bundled. Company requests continue through the existing queue. Both connector and mobile job listings merge authorized results from the separate stores without copying crypto records into the company database. Legacy CLI crypto requests wait on the crypto queue; new connector/mobile requests bypass the company worker. Runtime unavailability fails crypto submissions explicitly. Company listings remain available if crypto is down.

## Shared infrastructure

The physical server, kernel, disks, authenticated ingress and existing Qwen/Ollama inference process remain shared. Resource limits apply to the new queue/gateway processes **not** to model computation performed by the shared Ollama process. Crypto inference can still contend with company inference. Separate model serving or a second host is a later step after capacity measurements. This is service/user/mount isolation, not a separate VM. Privileged administrators can cross these boundaries.

## Model diagnostic

The installed `qwen3:4b` alias reports Qwen3-4B-Thinking-2507, `general.finetune=Thinking`, and supported thinking modes `[true]`. The agent's `think=false` setting is incompatible. The official model card states this variant supports only thinking mode:
https://huggingface.co/Qwen/Qwen3-4B-Thinking-2507

This mismatch is a likely contributor to the earlier timeout, not proof of its sole cause. The restricted gateway returns `MODEL_MODE_UNSUPPORTED` before generation for this configuration; it does not silently change weights, switch to 8B, trim evidence or accept incomplete output. Deterministic crypto status, rules, memory and paper status remain usable. Full interpretation requires a separately reviewed compatible model configuration and successful evidence tests. No training or prediction-quality claim is made.

## Installation and rollback

`install_runtime.py` requires the reviewed package hash and current hashes of the company dispatcher, mobile workspace and connector helper. Unknown sources, duplicate installations and concurrent changes stop installation. Source/units are backed up privately. It validates unit syntax, starts the new services, checks that the worker cannot see company paths or create internet sockets, and verifies crypto status under the owner gateway user before switching routing. It checks and locks the existing queue before stopping the workspace so a running company request is not killed. Pending legacy crypto requests must drain first. A brief workspace/helper restart is required to load routing. Scanner services are not restarted.

Failures restore changed integration files and prior services. Runtime data and backups are retained for diagnosis; reinstalling after a failure requires review of existing runtime paths. New users are locked and have no login shell. Old isolated crypto conversation history remains preserved in its prior server directory; it is not automatically migrated. No company history is copied. New conversations and jobs are private in `/var/lib/vivameda-crypto-runtime`.

Post-install checks must cover actual unit activation, mount/network restrictions, peer credentials, separate request queue, crypto follow-ups, company rejection and company route preservation. Tests before installation cannot substitute for these live checks.

Only code, units, documentation, hashes and aggregate verification belong on GitHub. Runtime databases, conversations, cases, credentials, backups and private company source remain server-side. Paid calls, live execution and weight training remain disabled.
