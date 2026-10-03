# Meme Gem agent learning rules v1
2 October 2026. Saved policy for research and challenger learning. Production thresholds: 8 / 10.
Scope: audit/replay and candidate design. No live signal promotion or trained weights.

1. Identify a call by chain + mint + exact emitted timestamp + alert level. Symbols are display names only. Same symbol across mints is never merged. Keep the initial call and upgrades separate; group the same mint when estimating uncertainty or splitting data.

2. Preserve the emitted score. All 65 exactly matched calls agree with their logged score in this capture. Earlier calls and upgrades nevertheless have different emitted scores and must remain separate. Do not overwrite the former with a replay calculation. Freeze features, score, failed gates, pair, source version and acquisition timestamps at emission. Label retrospective replay as reconstructed.

3. Record four independent dimensions: horizon endpoint return, observed within-horizon peak, observed within-horizon downside, and liquidity/survival. A token can hit 2x and subsequently fail. Never let a peak label suppress a failure flag. UDR demonstrates this for a sent call; Vortex and Ouroboros demonstrate it in shadow observations.

4. Do not confuse opportunity with profit. A sampled MC multiple is not a realized trade. Missing execution, position size, pool quotes, price impact, fees and exit order mean realized P&L is unknown. Do not infer stop/target order from unordered extrema. No invented optimal exit.

5. Learn only from valid timed outcomes. Timestamp must equal decision time + horizon seconds + lateness, with lateness 0–180 seconds. Require a genuine forward observation path for peak/downside labels, max gap <=180 seconds, exact mint/pair continuity and positive valid entry. Keep incomplete histories and unresolved horizons unscored; report their counts.

6. Never fill historical checkpoints now, use provider/global ATH labels, or interpret initialization at 1x as a complete pre-tracking path. Old imported alerts have gaps between decision and tracking. Current retained endpoint logs cover fewer rows than the DB; absence is a gap, not a failure.

7. Compare ALERT and SHADOW separately. SHADOW is not a delivered call. An early shadow peak cannot be credited to a later alert. AUTONOM, Library and OnionWeb motivate an earlier-entry challenger; they do not justify lower production gates. Include all sampled shadow failures when testing it.

8. Security UNKNOWN is unknown. Missing RPC/holder/bundle/LP evidence cannot be a safety pass or zero concentration. Transaction buy ratios are not unique wallets. Do not retrospectively explain a collapse as a confirmed rug or bundle without contemporaneous supporting evidence. Test security completeness as a challenger covariate when genuine snapshots exist.

9. Test timing and survival separately. Candidate hypotheses: earlier qualification using observed liquidity/volume acceleration and sufficient history; post-alert liquidity deterioration; score upgrade delay; distinguishing wash-like transaction concentration. Only features captured before the decision can drive a candidate. These are unvalidated hypotheses, not winning rules.

10. Freeze one candidate, baseline, cohort and horizons before the next evaluation. Use existing production as the reference on the same eligible token/horizon sample. Control for token age, entry MC, entry liquidity, volume/MC, market period and observation density where captured. Avoid outcome-selected winner cohorts. Keep development cases out of the forward holdout.

11. Report joint opportunity/failure counts, missingness, clustered uncertainty, alert burden and adverse excursions. Higher score is not a calibrated probability. Small, correlated samples and incomplete paths cannot establish promotion. Never search many cutoffs and then present the best one as pre-registered.

12. Keep new policies in challenger/V2 until the forward holdout beats the frozen baseline on the registered useful objective, including failure burden and alert quality. Production thresholds remain 8/10. Any reviewed deployment is separate from promotion; no self-modifying production thresholds.

13. Preserve every new emitted event in an append-only ledger; latest-alert state alone loses earlier calls. Store security snapshots and exact input values without credentials. Export forward observations and coverage through a scoped owner-authorized read-only route. Do not bypass server permissions.

14. Make learning explicit. These rules and the audit are persistent policy/replay artifacts on Hetzner. Saving them does not fine-tune Qwen, alter weights, or install a live consumer. Until a tested consumer is deployed, live services retain their current behavior.

Evidence basis: capture_20261002.json and audit.json. See audit.md for each retained call, scope gaps and selected paired observations.

