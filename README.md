# Agent Zero Plugins

Personal Agent Zero plugin collection.

## Plugins

- `plugins/github_cli` - GitHub CLI integration using `gh`, persistent authentication/config state, and RAGE-style gated mutation execution.

## Install

Copy or symlink a plugin directory into Agent Zero's user plugin tree:

```sh
cp -a plugins/github_cli /a0/usr/plugins/github_cli
```

Agent Zero discovers custom plugins from `/a0/usr/plugins/<name>/` when a `plugin.yaml` is present.

Persistent plugin runtime state belongs under `/a0/usr/state/`, which survives normal container replacement when `/a0/usr` is mounted from the host.
