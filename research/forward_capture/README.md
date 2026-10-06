# Forward candidate capture core

This engineering candidate addresses the failed historical comparable-control gate. It records common-cycle score decisions, fixed outcome-blind controls, separate screening/delivery events and identical timed same-pair endpoints. The [integration](integration) now contains a deterministic two-file runtime candidate and hash-bound owner activation script. The pilot remains dormant until explicitly activated. [PROTOCOL.md](PROTOCOL.md) defines the fixed 14-day measurement pilot and remaining empirical coverage/research gates.

Run `python3 -m unittest discover -s client_learning/crypto_forward_capture_20261005 -p 'test_*.py'` from the server checkout. Tests use synthetic, in-memory SQLite only. `capture.py` is standard-library code with no network or import side effects. A caller must supply a private connection, exact emitted inputs and actual receipt times.

Run the integration suite separately with `python3 -m unittest discover -s client_learning/crypto_forward_capture_20261005/integration -p 'test_*.py'`. 23 core and 20 integration tests pass. Tests include 500 changing-input cycles, dormant behavior, immutable exclusions, private activation, 100ms lock contention and exact production-function invariance. No extra provider requests are introduced. Synthetic tests do not prove real candidate/control endpoint symmetry.

The core deliberately does not turn incomplete measurements into a scanner-edge verdict. The next gate is reviewed deployment and explicit owner activation, followed by the fixed measurement pilot. The existing model-ledger test remains independent. See [HANDOVER_20261006.md](HANDOVER_20261006.md) for the integration review and deployment state.
