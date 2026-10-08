# Crypto pilot operational health

A read-only sidecar for the activated forward capture pilot. It never writes the pilot database, changes scanner source, resets activation or exposes model predictions, prices, returns, raw inputs, mint/pair identities or credentials.

`health.py` runs every two minutes through a dedicated systemd oneshot/timer, under the existing scanner user. It reads the pilot with SQLite `mode=ro` and `query_only`, projects timestamps/counts and publishes `/var/lib/vivameda-crypto-pilot-health/status.json` atomically, mode0644. Notification dedup state is separate, mode0600. `read_status.py` lets the bounded engineering connection read that sanitized report without access to the private pilot database. A report older than five minutes is labelled `monitor_stale`.

Report fields include collecting/paused/stalled/stopped state, last successful scoring-cycle time, cycle/qualification/control/screening/observation counts, database-file bytes and service health. Coverage counts use only closed 60-minute windows, identical pair identity and local receipt window [index+3600,index+3780]. Qualifying token entries and controls are reported separately. Shared controls count once per cohort entry. Zero denominator yields null coverage, not zero. Qualification is not Telegram delivery. Coverage does not establish empirical comparability, profitability or scanner advantage.

Ten minutes without a successful cycle triggers a stalled incident, including after initial activation. A pause marker, unavailable health read or inactive production service also triggers an incident. Notification uses the existing configured Telegram bot/destination only. One notification per incident state plus recovery when collecting resumes; messages contain counts and fixed reasons only. Failed sends retry after five minutes; a global five-minute minimum attempt interval bounds flapping. No market/RPC/provider calls or paid services. Telegram requests are additional operational messages. Network exceptions and response bodies are never published or logged.

Limitations: notification delivery has the usual send/state-write crash window and can duplicate a message after a crash. The monitor cannot announce its own complete outage; a stale report exposes that during a status check. There is no independent external watchdog. A five-second SQLite query budget may report unavailable on large/slow files; this is honest missing operational evidence. Systemd caps memory192MiB, CPU20%, runtime45seconds. No claim of full-feed capacity or chain integrity is made by this monitor. The scanner's existing chain checks remain responsible for capture integrity.

Installed by the owner on 6 October 2026 at 07:37 UTC; backup `/opt/vivameda-operations/crypto-health-backup-20261006T073739Z`. Timer and a healthy collecting report were subsequently verified. See `../forward_capture/STATUS_20261008.md` for today's counts and explicit missing incident-history evidence. The following describes the original installer, not a request to reinstall. `install_health.py --install --expected-sha256 HASH` verifies the complete monitor bundle and both currently deployed pilot source hashes, requires an existing readable pilot, compiles source and validates unit syntax before installation. It installs only its own files/timer and never restarts scanner/tracker or opens their private database for writing. A differing existing monitor requires a separately reviewed update. Postflight returns sanitized health and timer state. A paused pilot is reported, never automatically cleared.

Run `python3 -m unittest discover -s client_learning/crypto_pilot_health_20261006 -p 'test_*.py'` on Hetzner. Tests use temporary synthetic data and mocked sends, never production endpoints or credentials.

## E1 append-only incident/send audit

The installed logging update appends sanitised state, reason code, UTC epoch time and send result to incident_send_log.jsonl. Pending and final results preserve crash/failed-send ambiguity; neither proves recipient delivery. Health/dedup/retry rules and the pilot remain unchanged. Logging failures appear as audit_log=unavailable. Historical incident history cannot be backfilled.

## Corrected E logging review and owner installation — 8 October

Both components were installed by the owner using reviewed bundle `7afa8275f9d2d8c2ffce2eaa0bac99cffb359e69a2a41c62060caf044282ae5a`. Nine focused tests passed. Health backup: `/opt/vivameda-operations/crypto-evidence-logs-health-2ptrb4db`; movement backup: `/opt/vivameda-operations/crypto-evidence-logs-movement-jg4encuv`.

| Installed source | SHA-256 |
| --- | --- |
| health.py | f5684d83e4912bc02325ec653c0c5271c742b112823f64f72fa78568c0683f86 |
| monitor.py | 152978ece511b3c0d2974f1867deec80996017bdfb788c0b49ab1f35417fa613 |
| exchange.py | 852e2cd1b5441482f2ccca83c06e2dea7e6af04bb50ec3f6a6fe956ff185f78b |

Owner postflights verified source hashes and existing service/timer. Installer sent no alarm; cadence, units, permissions, policy and pilot were unchanged. Read-only public health status at **2026-10-08T16:25:31Z** reports `audit_log=available`, `status=stalled`, `reason=no_successful_cycle_for_10_minutes`, `notification=idle`. This verifies a normal timer logging path completed; private log rows and any new incident send were not independently inspected. A real alarm observation-to-Telegram-API acknowledgement delay remains unverified. No synthetic alarm or backfill is authorized.

The old `b29c87e37c6f112a6703e3d5a5c0e38dd4689c566af0a014c4aa7515eef4c97d` bundle was refused because deployed health.py was `408fdcdbc731f5c35faa034300c9711a87beb00a80da8bf19b889e8d1896c47b`, not the older engineering base `70f923c3b09dc258b1baaf45c17699d4fe87588dc7c32b186046fd31ce5f3717`. The corrected candidate preserves all deployed rejected-cycle diagnostics and adds a synthetic regression for them. Unchanged-function AST checks passed. Earlier 49-test validation belongs to the original candidate; the corrected candidate has nine focused tests verified. A fresh broad system-Python run lacked httpx; no fresh full-suite pass is claimed. Do not reinstall either successful component. The corrected public files are reviewed source records, not an instruction to activate another pilot or change its binding.
