# Forward candidate capture core

This engineering candidate addresses the failed historical comparable-control gate. It records common-cycle score decisions, fixed outcome-blind controls, separate screening/delivery events and identical timed same-pair endpoints. No production integration or activation is included. [PROTOCOL.md](PROTOCOL.md) defines the fixed 14-day measurement pilot and remaining adapter/research gates.

Run `python3 -m unittest discover -s client_learning/crypto_forward_capture_20261005 -p 'test_*.py'` from the server checkout. Tests use synthetic, in-memory SQLite only. `capture.py` is standard-library code with no network or import side effects. A caller must supply a private connection, exact emitted inputs and actual receipt times.

The core deliberately does not turn incomplete measurements into a scanner-edge verdict. The next work is reviewed scanner/tracker integration, resource/failure validation, then explicit activation under the hashed protocol. The existing model-ledger test remains independent.
