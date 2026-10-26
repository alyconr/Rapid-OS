---
title: Capabilities and Permissions
description: How Rapid OS models what a coding harness declares it can do and how that relates to risk, workspaces, and evidence.
---

# Capabilities and Permissions

In Rapid OS, "permissions" are modeled mainly as **capabilities declared by the harness**. They are not operating system permissions or a security sandbox.

A capability answers:

> Does the selected harness declare that it can perform this kind of operation?

## Canonical catalog

| Capability | Category | Meaning |
|---|---|---|
| `context.consume` | context | Can consume compiled context. |
| `repository.read` | repository | Can read the repository. |
| `repository.write` | repository | Can modify repository files. |
| `workspace.current` | workspace | Can work in the current workspace. |
| `workspace.isolated` | workspace | Can work in an isolated workspace. |
| `shell.execute` | execution | Can run shell commands. |
| `tests.execute` | testing | Can run tests. |
| `git.inspect` | git | Can inspect Git. |
| `git.modify` | git | Can modify Git state. |
| `mcp.invoke` | integration | Can invoke MCP tools. |
| `subagents.delegate` | delegation | Can delegate work to subagents. |

## Support states

Each capability can have one of three states:

- `supported`: the profile declares support;
- `unsupported`: the profile explicitly declares that it does not support it;
- `unknown`: Rapid OS has insufficient declarative evidence to assume support.

`unknown` does **not** mean `supported`.

## Built-in profiles

Built-in profiles are conservative. They declare only these capabilities as `supported`:

- `context.consume`
- `repository.read`
- `workspace.current`

All others start as `unknown`.

To create a profile you can edit:
```bash
rapid harness init codex
```

This creates `.rapid-os/harnesses/codex.json`. When a project profile exists, it completely replaces the built-in profile for that harness; there is no silent merge.

## How required capabilities are derived

Rapid OS derives requirements from the `ExecutionContract`:

- Always requires `context.consume` and `repository.read`.
- If the contract has tasks, requires `repository.write`.
- If the current workspace is used, requires `workspace.current`.
- If risk requires isolation, requires `workspace.isolated`.
- If `gate.tests` exists, requires `tests.execute`.
- `--require <capability-id>` adds more requirements.

## Risk and isolation

Execution policy classifies a run as `low`, `medium`, `high`, or `critical`.

By default, `low` and `medium` risk allow the current workspace; `high` and `critical` require an isolated workspace.

Rapid OS declares this requirement in the contract, and `rapid start` stops in `blocked` until an isolated workspace exists. Only `rapid start --worktree` creates a Git worktree (`../<repo>-<run-id>`, branch `rapid/<run-id>`); Rapid OS never creates containers or sandboxes.

## What Rapid OS does and does not execute

- Plumbing commands (`rapid spec`, `rapid run`, `rapid harness`, `rapid evidence`, `rapid eval`, and others) do not execute repository code. A capability such as `tests.execute` is only **declared** and **checked against evidence**.
- Porcelain commands execute only `test_command` from `.rapid-os/config.json` or the argv passed to `rapid check`, then record its result as evidence (`rapid:check`).
- Rapid OS never invokes agents or approves human gates; a person runs `rapid approve`.

## Resolve compatibility

```bash
rapid harness show codex
rapid harness resolve --run checkout-r1-run-001
rapid harness resolve --run checkout-r1-run-001 --require-compatible
```

Results:
- `compatible`: all requirements are `supported`;
- `incompatible`: at least one is `unsupported`;
- `unresolved`: none are `unsupported`, but at least one is `unknown`.

With `--require-compatible`, `incompatible` and `unresolved` return `RAPID1110` and exit code `1`.

## A capability is not evidence

A declared capability does not prove that it was used. For example, a profile may declare `tests.execute = supported` and a run may require `gate.tests`; evaluation is still `UNVERIFIED` if there is no valid evidence that tests ran.

```text
Capability = what the harness declares it can do
Evidence   = what was observed to happen
Eval       = what Rapid OS can conclude from that evidence
```
