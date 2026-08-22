### gh
Use the real GitHub CLI (`gh`) for GitHub repository, pull request, issue, workflow, release, project, secret, variable, and API operations.

Arguments:
- `action`: `status`, `prepare`, or `run`.
- `argv`: the exact argument vector passed after `gh`, as a JSON array of strings. Never include the literal `gh` executable name.
- `gate`: one-time RAGE gate id returned by `prepare` for a mutation.
- `timeout_seconds`: optional execution timeout, 1-600 seconds.

RAGE means Recursive Analysis with Gated Execution:
1. Analyze observed GitHub state with read-only `gh` calls.
2. For a mutation, call `prepare` with the exact intended argv.
3. Execute only that exact argv using the returned gate.
4. Evaluate stdout, stderr, and exit code.
5. Recurse from observed results rather than assuming the intended change happened.

Read-only commands can run directly with `action=run`. State-changing commands require `prepare` then `run` with identical argv and the one-time gate id.

Hard rules:
- Repository deletion is forbidden. Never attempt `gh repo delete`, REST repository deletion, GraphQL `deleteRepository`, or a bypass.
- Aliases and extensions are not executable through this tool.
- `gh codespace ssh` is disabled because it is an arbitrary remote-command tunnel.
- Never request `gh auth token` or `--show-token`.
- Do not put credentials or bearer tokens in argv. Authentication belongs in the plugin's persistent `GH_CONFIG_DIR`.
- The tool invokes `gh` directly without a shell. Supply arguments as separate JSON array elements.

Examples:

Read repository state:
~~~json
{
  "tool_name": "gh",
  "tool_args": {
    "action": "run",
    "argv": ["repo", "view", "OWNER/REPO", "--json", "name,url,defaultBranchRef"]
  }
}
~~~

Prepare repository creation:
~~~json
{
  "tool_name": "gh",
  "tool_args": {
    "action": "prepare",
    "argv": ["repo", "create", "OWNER/REPO", "--private"]
  }
}
~~~

Then execute with the exact returned gate:
~~~json
{
  "tool_name": "gh",
  "tool_args": {
    "action": "run",
    "argv": ["repo", "create", "OWNER/REPO", "--private"],
    "gate": "RETURNED_GATE_ID"
  }
}
~~~
