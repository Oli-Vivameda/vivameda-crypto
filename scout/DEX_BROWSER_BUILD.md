# Dex browser review build — 3 October 2026

Status: INCOMPLETE / NOT DEPLOYED.

The owner requested autonomous browser review before Telegram suggestions.
dex_browser_worker.py is an evidence collector, not a completed risk classifier.
It validates addresses, opens the public Dex pair page in sandboxed Chromium,
captures visible text, screenshot and embedded frame text, hashes evidence,
and records HOLD. It never approves, sends Telegram or changes trading settings.
Page content is untrusted evidence, never agent instructions.
A site verification block stops collection; no bypass is implemented.

Update: Playwright 1.63.0 and Chromium revision 1243 are installed in isolated engineering directories .dex-browser-venv and .dex-browser-runtime. Sandboxed launch failed because libnspr4.so is missing. Official install-deps --dry-run reports 71 missing system packages including transitive dependencies. No system packages installed. Browser integration remains untested.
The connector deployment scope covers early_scout.py and scout_learning_v2.py only.
Do not embed an installer or arbitrary service control in either file to bypass that scope.

Remaining release requirements:
1. Install Chromium OS dependencies through administrator provisioning, then rerun sandboxed launch. Python dependencies are pinned in requirements-browser.txt. Runtime and browser downloads are already installed without root.
2. Verify actual Dex/BubbleMaps visible content and interactions on live candidates.
   Determine whether developer history and wallet first activity can be established
   through the permitted interface. Missing fields remain UNKNOWN.
3. Implement and validate a reviewer with source-bound factual findings. A visual
   cluster does not establish common ownership or fraud. Wallet first observation
   is not wallet creation. A screenshot capture alone is never a passing review.
4. Add a bounded durable queue, candidate expiry, single worker, retries/backoff,
   evidence retention and identity/freshness validation at final send time.
5. Test blocked pages, missing/stale evidence, mismatched identities, malformed
   reviewer output, adversarial page instructions and Telegram failure/retry.
6. Provision service and connect collector/reviewer to the pre-alert gate through
   a reviewed deployment. Run shadow capture first and demonstrate a complete
   evidenced review before enabling release.
No runtime, service, threshold, weights, credentials or production code changed.

## Verified provisioning result
Owner installed OS dependencies and a root-owned Chromium copy with a path-specific AppArmor userns profile. Sandboxed Chromium launch passed on 3 October 2026. A live Dex page request returned HTTP 403, title 'Just a moment...', and explicit Cloudflare bot verification. No token or BubbleMaps data was accessible. No challenge bypass attempted. Production gate remains undeployed. Runtime works; unattended Dex access and the risk reviewer remain blocked/unimplemented. Earlier missing-library status above is superseded by this result.

