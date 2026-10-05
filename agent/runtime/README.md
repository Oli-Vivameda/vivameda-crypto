# Crypto runtime separation

Activated and verified on Hetzner on 2026-10-05. See [activation verification](RUNTIME_ACTIVATION_20261005.md) for the live receipt, service checks and remaining limitations. [Runtime separation](RUNTIME_SEPARATION.md) is the frozen build reference; its activation-pending status is superseded by the receipt.

For the frozen v1 installer, restart `vivameda-connect.service` after installation to refresh the direct connection, then verify status. Do not rerun an installed bundle blindly. The host and inference process remain shared. The original model-mode blocker was resolved by the [activated interpretation repair](../interpretation/INTERPRETATION_ACTIVATION_20261005.md). These v1 source files remain the frozen initial runtime bundle; the current agent/proxy replacement source is in `../interpretation/`.

