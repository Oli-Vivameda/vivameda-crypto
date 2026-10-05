# Crypto interpretation activation — 2026-10-05

Activated at 2026-10-05T17:41:40.707775Z on Hetzner. The production queue completed a crypto evidence interpretation in 130.38 seconds. The installed agent and proxy hashes match the reviewed source.

- Model: `qwen3:4b-instruct-2507-q4_K_M`, an existing public Instruct checkpoint, not crypto-trained weights.
- Repair bundle SHA256: `6814bcdae171d25851a4a2be1c3fa6dfba6559cd4dd4e03d28b06165037323a2`.
- Agent SHA256: `75b58cf48ae1ec4d3bdf7cbfa800a8979331fadad2b450672a0a5648e9853a3a`.
- Proxy SHA256: `6893358dc8ce3a57dfd6d2c63fa977871f24b3f677e2f3093e9bfbe25fd2f615`.
- 27 regression tests passed: nine repair/readiness checks and 18 existing runtime checks.
- Both crypto runtime services active; company workspace, connection and scanner services active.
- Crypto worker still has a separate queue and private storage; internet sockets blocked and company paths hidden.
- Company model default, scanner policy and live-execution controls unchanged. Live execution remains disabled.

The original Thinking-only checkpoint was incompatible with the fixed non-thinking request. A larger installed model timed out in the initial bound. The Instruct variant passed generation tests, then a temporary production-equivalent sandbox check. Initial production installation attempts failed immediately and rolled back. The installer now waits for an authenticated model-proxy socket response before starting the worker; production activation then passed. Startup timing is the leading explanation for those earlier generic errors; their original exception was not captured conclusively.

The host and Ollama inference process remain shared. Response time is approximately two minutes on this CPU-only server, with a bounded five-minute request timeout. Crypto interpretation uses bounded fresh evidence, not a full-history search or live-price feed. This focused smoke test does not establish broad LLM reliability, predictive edge or profitable trading. Model summaries still require evidence review.

The initial runtime sources and installation receipt are preserved as a frozen version. This repair supersedes their model-interpretation blocker. Private activation JSON, conversation databases, queue records, evidence payloads, company source and credentials are excluded from GitHub.

