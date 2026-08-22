## prolog_rlm

Use `prolog_rlm` to delegate bounded recursive reasoning to the Prolog RLM runtime.

Use it when a task benefits from explicit decomposition, context slicing, recursive model calls, or an independent verification pass. Prefer it when the user explicitly asks for Prolog/RLM reasoning or when you are uncertain and a bounded recursive pass can reduce uncertainty.

Actions:

- `status`: inspect whether SWI-Prolog and the persisted prolog-rlm checkout are ready.
- `reason`: run the public `prolog-rlm rlm` CLI and return its structured JSON result.

`reason` arguments:

- `query` (required): the precise question or reasoning task.
- `context`: only the relevant observed facts, code excerpts, constraints, or prior tool results. Do not dump the whole chat by default.
- `model`: optional OpenRouter model name. If omitted, prolog-rlm uses its configured default.
- `endpoint`: optional OpenAI-compatible endpoint URL.
- `credential_env`: environment-variable name for a custom endpoint credential. Never pass a raw credential.
- `no_credential`: use only for a custom endpoint that requires no credential.
- `max_tokens`, `max_cost_usd`, `time_limit`, `context_bytes`: bounded runtime controls.
- `timeout_seconds`: outer Agent Zero subprocess timeout.

The bridge does not execute arbitrary Prolog goals and does not authorize mutations. Treat returned reasoning as evidence. Continue with Agent Zero tools for external actions, then verify observed state after any mutation.
