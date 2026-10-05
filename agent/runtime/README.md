# Crypto runtime separation

Activated and verified on Hetzner on 2026-10-05. See [activation verification](RUNTIME_ACTIVATION_20261005.md) for the live receipt, service checks and remaining limitations. [Runtime separation](RUNTIME_SEPARATION.md) is the frozen build reference; its activation-pending status is superseded by the receipt.

For the frozen v1 installer, restart `vivameda-connect.service` after installation to refresh the direct connection, then verify status. Do not rerun an installed bundle blindly. The host and inference process remain shared. Full model interpretation currently returns `MODEL_MODE_UNSUPPORTED`; deterministic crypto tools remain available.
