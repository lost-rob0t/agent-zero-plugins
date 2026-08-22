# Prolog RLM Plugin Instructions

## Scope

This plugin bridges Agent Zero to `lost-rob0t/prolog-rlm` without modifying Agent Zero core.

## Boundary

- Agent Zero owns orchestration and external effect execution.
- `prolog-rlm` owns recursive reasoning, bounded model calls, context slicing, and returned verification evidence.
- The agent-facing tool exposes structured arguments only. Do not add arbitrary Prolog goals, raw SWI command-line flags, shell execution, or `consult/1` passthrough.
- State-changing capabilities must be added separately and use exact RAGE gates.
- Never put provider credentials in arguments, logs, traces, tests, or Git. Pass credential environment-variable names only.

## Runtime

- Persistent checkout: `/a0/usr/state/prolog_rlm/repo` by default.
- Override checkout with `A0_PROLOG_RLM_REPO`.
- Setup/update behavior belongs in `execute.py`.
- The runtime adapter calls the public `bin/prolog-rlm.pl` CLI and requests JSON output.

## Verification

- Compile Python sources.
- Run `plugins/prolog_rlm/tests`.
- Keep the prompt contract synchronized with `tools/prolog_rlm.py`.
- Do not claim a live provider request was tested unless it actually ran with credentials.
