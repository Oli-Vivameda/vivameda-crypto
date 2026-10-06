# Recovery activation — 6 October 2026

1. Scope: outcome-blind operational recovery under AMENDMENT_20261006.md; no predictive evaluation.
2. Owner installation: validated and installed bundle 68dec2254b472c482ce59094bb6eef7b6039689c7fca2f9a50559c34fbcd48af. The owner receipt reported collecting and a usable cycle.
3. Independent verification: connector confirmed both services active and the deployed scanner/tracker hashes. Fresh count-only health report checked_at 1791274473 was 38 seconds old, collecting, reason null, with one valid cycle; last_successful_cycle_ts 1791274471.
4. Runtime: scanner 765aba08982c3f0c562b52755ab9122cdaabfc396b78e7fed878089db87fa54e; unchanged tracker a519ad19680ba72f0d593c4627fe5faa2d8dfa93fcd112eaba21abcf5a6da9b6.
5. Preserved measurement: activation1791269439, deadline1792479039 (20 October 2026, 09:50:39 Cyprus), immutable exclusions and original protocol. No extended window, backfill or model-ledger change.
6. Audit: private backup /opt/vivameda-operations/crypto-capture-recovery-skwbqk3h; original pause archived; chained amendment/gap repair head d8fbee6e012f75062041f211fe2ad6c13cc198f04b5702117f9b387ec249d9d7.
7. Counts: owner receipt one cycle, one cycle_health, two private inputs and one runtime_repair. Health qualified events0, controls0, matched events0, timed observations0. Coverage is null while no windows have closed; it is not zero or a performance result.
8. Validation and limits: 15 synthetic recovery tests passed on Hetzner and locally; 20 original integration checks passed locally. First usable live cycle verified. Exact original failure cause remains unknown; continued provider availability and endpoint symmetry remain unproven.
9. Privacy/execution: only reviewed source and aggregate receipts are published. Private input rows, identities, endpoints, exclusions and databases remain on Hetzner. No added provider request, paid call or live execution.
10. Next gate: let the original window run, monitor valid and rejected cycles, qualified/control counts and identical closed-window endpoint coverage. The existing timer alarms on pauses, service failure and no successful cycle for ten minutes. Do not tune thresholds or inspect sealed model results to rescue the pilot.
