# Crypto-only agent integration

`context.py` extracts the automatic knowledge-context selector from the installed Vivameda agent activation source. The private conversational agent and its non-crypto data are not bundled. Import `automatic_knowledge_context(query, session_dict)` and append its returned text to your own agent's dated evidence context. Keep the session dictionary separate per user/session.

The function selects non-shadow crypto knowledge for explicit crypto queries and relevant follow-ups, explains research-model limitations, and performs no model call, network request, trade or notification. It has no action permissions. The knowledge cards are frozen observations dated 2026-10-03, not live prices or a current portfolio. Historical limitations in that file describe the capture at that time; the later fixed-horizon baseline is documented under research/.

Prompt context is not a substitute for application-level permission checks. Retrieval and saved rules are not Qwen weight training. The numerical model is separate and not promoted. See AGENT_LEARNING_RULES.md for the original dated research policy; statements about installation there describe its original capture, not the present extraction.
