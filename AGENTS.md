# Agent Zero Plugins Agent Instructions

## Scope

This repository contains user/community-style Agent Zero plugins under `plugins/<name>/`.

## Before changing anything

Observe current state first. Read the plugin's `README.md`, `plugin.yaml`, prompts, tools, and tests before editing behavior.

## Agent Zero contract

- Runtime install target: `/a0/usr/plugins/<name>/`.
- Every plugin requires `plugin.yaml`.
- Plugin tools derive from `helpers.tool.Tool` and return `helpers.tool.Response`.
- Every agent-facing tool needs a matching prompt under `prompts/`.
- Keep secrets out of logs, tool results, tests, and Git.
- Persistent runtime state belongs under `/a0/usr/state/<plugin>/` unless the plugin documents another durable location.

## RAGE

RAGE means **Recursive Analysis with Gated Execution**.

For state-changing integrations:

1. Analyze observed state and constraints.
2. Gate the exact mutation before execution.
3. Execute only the command admitted by that gate.
4. Evaluate actual output and exit status.
5. Recurse from the observed result.

A plan or green test is evidence, not proof that an unrelated mutation was approved. Gates must bind to the exact operation they admit.

## Verification

For each changed plugin:

- compile Python sources;
- run plugin unit tests;
- inspect `git diff --check`;
- verify prompts match the implemented tool argument contract;
- never claim external behavior was tested unless it actually ran.
