# Agent Zero Plugins

Personal Agent Zero plugin collection.

## Plugins

- `plugins/github_cli` - GitHub CLI integration using `gh`, persistent authentication/config state, and RAGE-style gated mutation execution.
- `plugins/prolog_rlm` - structured bridge from Agent Zero to prolog-rlm for bounded recursive reasoning and verification.

## Install

Copy or symlink a plugin directory into Agent Zero's user plugin tree:

```sh
cp -a plugins/github_cli /a0/usr/plugins/github_cli
cp -a plugins/prolog_rlm /a0/usr/plugins/prolog_rlm
```

Agent Zero discovers custom plugins from `/a0/usr/plugins/<name>/` when a `plugin.yaml` is present.

Persistent plugin runtime state belongs under `/a0/usr/state/`, which survives normal container replacement when `/a0/usr` is mounted from the host.
