# GitHub CLI Plugin Instructions

## Contract

- Use the real `gh` executable through an argv list. Never introduce a shell wrapper.
- Runtime auth comes from the persistent `GH_CONFIG_DIR` under `/a0/usr/state/github_cli/`.
- Never log or return GitHub tokens.
- Keep tool prompt, policy, tests, and README synchronized.

## Hard denials

These are invariants, not suggestions:

- No repository deletion by `gh repo delete`, REST API, GraphQL `deleteRepository`, aliases, extensions, or command-execution tunnels.
- No `gh auth token` or `--show-token`.
- No `gh codespace ssh`.

Do not weaken a hard denial to make a task pass.

## RAGE

RAGE means **Recursive Analysis with Gated Execution**.

- Read-only commands may execute immediately.
- GitHub mutations require a one-time gate bound to the exact argv and Agent Zero context.
- Consume the gate before execution so it cannot be replayed.
- Record exit status/stdout/stderr as evidence and recurse from the observed result.
- Do not store raw gated argv; persist only its digest and gate metadata.

## Verification

Run:

```sh
python -m compileall -q plugins/github_cli
python -m unittest discover -s plugins/github_cli/tests -p 'test_*.py' -v
```
