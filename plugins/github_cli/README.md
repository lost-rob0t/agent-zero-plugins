# GitHub CLI Agent Zero Plugin

Agent Zero tool for GitHub automation through the real `gh` executable.

## Properties

- Uses `gh` directly with an argv array. No shell wrapper.
- Persists GitHub CLI configuration under `/a0/usr/state/github_cli/gh`.
- If `GH_TOKEN` or `GITHUB_TOKEN` exists when setup runs, setup persists that authentication using `gh auth login --with-token` rather than storing the environment variable itself.
- Supports repository creation and other normal GitHub mutations.
- Repository deletion is hard-disabled, including `gh repo delete`, REST deletion through `gh api`, and GraphQL `deleteRepository`.
- `gh auth token`, `--show-token`, aliases, and extensions are blocked.
- State-changing commands use one-time exact-command RAGE gates.

## Install

Copy the plugin into Agent Zero's user plugin directory:

```sh
cp -a plugins/github_cli /a0/usr/plugins/github_cli
```

Run its `execute.py` from Agent Zero's Plugins UI. Setup:

1. creates persistent state;
2. writes the persistent `GH_CONFIG_DIR` location to `/a0/usr/state/github_cli/env`;
3. migrates an existing `~/.config/gh/hosts.yml` when useful;
4. installs `gh` using a supported system package manager if it is absent;
5. persists `GH_TOKEN`/`GITHUB_TOKEN` into GitHub CLI authentication when one is present.

For interactive authentication inside the Agent Zero container:

```sh
GH_CONFIG_DIR=/a0/usr/state/github_cli/gh gh auth login
```

The standard Agent Zero Docker setup should persist `/a0/usr` on the host, for example:

```sh
docker run -d \
  --name agent-zero \
  --restart unless-stopped \
  -p 50080:80 \
  -v "$PWD/agent-zero-usr:/a0/usr" \
  -v "$PWD/agent-zero-nix:/nix" \
  agent0ai/agent-zero:latest
```

## Tool

Tool name: `gh`

### Status

```json
{
  "action": "status"
}
```

### Read-only command

```json
{
  "action": "run",
  "argv": ["repo", "view", "lost-rob0t/agent-zero-plugins"]
}
```

### Mutation

First analyze and admit the exact command:

```json
{
  "action": "prepare",
  "argv": ["repo", "create", "lost-rob0t/example", "--private"]
}
```

Then execute exactly the same argv with the returned gate:

```json
{
  "action": "run",
  "argv": ["repo", "create", "lost-rob0t/example", "--private"],
  "gate": "..."
}
```

A gate is context-bound, exact-argv-bound, expires after 15 minutes, and is consumed once. Failed executions do not magically become successful evidence; the agent evaluates the actual exit code/output and begins the next RAGE iteration from that state.

## RAGE

RAGE is **Recursive Analysis with Gated Execution**:

1. Analyze observed state.
2. Gate the exact mutation.
3. Execute only the admitted mutation.
4. Evaluate observed output and exit status.
5. Recurse from evidence.

Read-only operations do not need an execution gate.
