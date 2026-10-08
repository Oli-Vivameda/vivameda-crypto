# Crypto interpretation repair

Activated on Hetzner on 2026-10-05. See [activation verification](INTERPRETATION_ACTIVATION_20261005.md).

This directory contains the exact reviewed replacement agent/proxy and the hash-checked repair installer. It applies to the existing isolated runtime in `../runtime/`; it is not a fresh-host installer. The company integrations and original runtime bundle remain frozen.

The crypto model is `qwen3:4b-instruct-2507-q4_K_M`; Ollama and the host remain shared. No crypto-specific weight training is claimed. The installer waits for the authenticated model socket before starting the worker, checks the real queue and isolation, creates a source backup, and restores original source if activation fails. Only the two crypto services are restarted. Already repaired installations are intentionally refused by the original-source hash gate.

Reviewed bundle SHA256: `6814bcdae171d25851a4a2be1c3fa6dfba6559cd4dd4e03d28b06165037323a2` (crypto_agent.py, model_proxy.py, install_interpretation.py, test_interpretation.py).

Run the nine repair tests with `python3 -m unittest discover -s agent/interpretation -p test_interpretation.py`. The 18 existing runtime regressions were also run on Hetzner against the replacement modules, for 27 tests total. Unix peer-credential tests require Linux.

Private runtime data and company source are excluded. The real answer took 130 seconds; the response timeout is five minutes. Interpretation is a bounded evidence summary, not validated trading performance. Live execution remains disabled.


## Factual acceptance correction — 8 October

The 5 October activation verified completion, routing and isolation. The 6 October factual check failed; generation completion is not factual acceptance. The reviewed [8 October guard and activation gate](INTERPRETATION_ACTIVATION_20261008.md) passed 10/10 fixed synthetic facts with zero invented explanations in 29.845 seconds, plus 17 tests. This is constrained evidence selection; unrestricted prose remains unverified. Owner activation and gateway postflight are pending. Installed production source has not been replaced by this review.

## Installed answer contract — 8 October

The factual guard was owner-installed at 12:26:48 UTC. **Crypto explain now returns constrained evidence selection, not free-text interpretation**, falling back to the evidence table when validation or evidence availability fails. Production postflight returned 111 evidence rows in 0.278 seconds. Installed hashes were independently verified. The earlier 10/10 synthetic candidate score is not a new live-gateway ten-question score; that check remains pending. See the existing activation receipt for hashes and backup.
