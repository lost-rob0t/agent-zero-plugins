# Prolog RLM for Agent Zero

Structured bridge from Agent Zero to [`lost-rob0t/prolog-rlm`](https://github.com/lost-rob0t/prolog-rlm).

## Architecture

```text
Agent Zero
  -> prolog_rlm tool
     -> structured query/context/options
        -> SWI-Prolog
           -> prolog-rlm public CLI (`rlm ... --json`)
              -> recursive reasoning result
  <- observed JSON result
  -> Agent Zero verifies / executes external effects with its normal tools
```

This is deliberately not a raw Prolog shell. Version 0.1 exposes `status` and `reason` only. The tool cannot pass arbitrary Prolog goals, shell commands, or raw SWI flags.

## Install

Copy or symlink this directory into Agent Zero:

```sh
cp -a plugins/prolog_rlm /a0/usr/plugins/prolog_rlm
```

Requirements:

- Git
- SWI-Prolog (`swipl`)
- network access for setup and whichever model provider you use

Run the plugin setup from Agent Zero's Plugins UI, or directly:

```sh
python /a0/usr/plugins/prolog_rlm/execute.py
```

Setup clones/updates `prolog-rlm` under `/a0/usr/state/prolog_rlm/repo`, so the checkout persists when `/a0/usr` is durable.

## Provider configuration

The default prolog-rlm provider is OpenRouter and resolves `OPENROUTER_API_KEY` from the environment at execution time. The bridge never accepts raw API keys as tool arguments.

For an OpenAI-compatible endpoint, the tool accepts `endpoint`, `model`, and either a credential environment-variable name or `no_credential=true`.

## Runtime overrides

- `A0_PROLOG_RLM_STATE_DIR`: persistent plugin state root.
- `A0_PROLOG_RLM_REPO`: use an existing prolog-rlm checkout instead of the default persisted path.
- `A0_PROLOG_RLM_REPO_URL`: setup clone URL.
- `A0_PROLOG_RLM_REF`: setup branch/tag, default `main`.

## Agent-facing actions

### `status`

Checks `swipl`, the persisted checkout, and the public CLI entrypoint.

### `reason`

Builds a structured `prolog-rlm rlm QUERY --json ...` invocation. Relevant Agent Zero observations go in `context`; provider credentials remain environment-only.

The returned RLM answer is evidence, not mutation authority. External effects stay in Agent Zero until a future RAGE-gated effect bridge is designed and reviewed.

## Next slices

1. Add an Agent Zero lifecycle hook that can consult RLM automatically for selected complex tasks without forcing every turn through it.
2. Add a typed effect proposal schema so RLM can propose Agent Zero tool calls without executing them.
3. Add exact RAGE gates around explicitly approved effect execution.
4. Add long-lived daemon/stdio transport once prolog-rlm has a stable protocol, avoiding one SWI process per reasoning call.
