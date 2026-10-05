# Crypto repository maintenance policy

Owner instruction, recorded 5 October 2026: GitHub must be updated whenever the crypto setup changes. The repository is the shareable reference for the whole crypto setup, with live, experimental and planned components labelled explicitly. This is an operator workflow, not an automatic GitHub synchronization service.

For each crypto change:

1. Update the relevant public source and tests. Keep credentials, private configuration, databases, messages, signing keys and client/workforce material excluded.
2. Update README/FULL_SETUP and the affected signal, architecture, setup or status guide when behavior or deployment status changes. Record date, scope, evidence and unresolved limits. A snapshot must not be presented as continuous live status.
3. Run checks appropriate to the change. Record real results; passing fixtures do not establish live coverage or profitability.
4. Refresh MANIFEST.json hashes and run scripts/verify_release.py. Distinguish source publication from actual production deployment.
5. Commit and publish to this GitHub repository. Verify the published result. Report the commit and any deployment receipt separately.
6. If publishing is blocked, retain the tested change, state that GitHub synchronization is pending and finish it when access is restored. Do not report the task fully synchronized before verification.

Production changes preserve reviewed deployment hashes, backups and alert gates. Newly built or tested components stay experimental until integration and deployment are verified. Retain dated experiment results, including negative findings. This policy does not authorize publishing private runtime data or activating live trading.

Daily learning updates publish only dated aggregate review counts and verified operational/test receipts. Keep case identities, detailed traces, raw snapshots, runtime databases and frozen outcomes private. Publish reviewed code alongside any behavior changes; label case-memory updates separately from weight training and keep activation status explicit.
