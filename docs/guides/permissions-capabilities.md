---
title: Capabilities and Permissions
description: How Rapid OS models what a coding harness declares it can do, and how that relates to risk, workspace, and evidence.
---

# Capabilities and Permissions

In Rapid OS, "permissions" are modeled primarily as **capabilities declared by the harness**. They are not operating-system permissions or a security sandbox.

A capability answers:

> Does the selected harness declare that it can perform this class of operation?

## Canonical catalog

| Capability | Category | Meaning |
| --- | --- | --- |
| `context.consume` | context | Can consume the compiled context. |
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

Each capability can be in one of three states:

- `supported`: the profile declares support;
- `unsupported`: the profile explicitly declares that it does not support it;
- `unknown`: Rapid OS has no declarative evidence sufficient to assume support.

`unknown` is **not equivalent** to `supported`.

## Built-in profiles

Built-in profiles are conservative. They declare only the following as `supported`:

- `context.consume`
- `repository.read`
- `workspace.current`

All other capabilities start as `unknown`.

You can materialize a profile in order to edit it:

```bash
rapid harness init codex
```

This creates:

```text
.rapid-os/harnesses/codex.json
```

When a project profile exists, it completely replaces the built-in one for that harness; there is no silent merge.

## How required capabilities are derived

Rapid OS derives requirements from the `ExecutionContract`.

Main rules:

- it always requires `context.consume` and `repository.read`;
- if the contract contains tasks, it requires `repository.write`;
- if the workspace is the current one, it requires `workspace.current`;
- if the risk requires isolation, it requires `workspace.isolated`;
- if `gate.tests` exists, it requires `tests.execute`;
- `--require <capability-id>` adds extra requirements.

## Risk and isolation

The execution policy classifies the run as `low`, `medium`, `high`, or `critical`.

By default:

- `low` and `medium` allow the current workspace;
- `high` and `critical` require an isolated workspace.

Rapid OS declares this need in the contract and `rapid start` stops at `blocked` until the isolated workspace exists. Only `rapid start --worktree` creates the worktree (`../<repo>-<run-id>`, branch `rapid/<run-id>`); it never creates containers or sandboxes.

## What Rapid OS runs and what it does not

- The plumbing (`rapid spec`, `rapid run`, `rapid harness`, `rapid evidence`, `rapid eval`…) executes nothing from the repository: a capability such as `tests.execute` is only *declared* and *checked against evidence*.
- The porcelain runs only the `test_command` from `.rapid-os/config.json` or the argv passed to `rapid check`, and leaves that result as evidence (`rapid:check`).
- It never invokes agents or approves human gates; `rapid approve` is run by a person.

## Resolve compatibility

```bash
rapid harness show codex
rapid harness resolve --run checkout-r1-run-001
rapid harness resolve --run checkout-r1-run-001 --require-compatible
```

Results:

- `compatible`: all requirements are `supported`;
- `incompatible`: at least one is `unsupported`;
- `unresolved`: there is no `unsupported`, but at least one is `unknown`.

With `--require-compatible`, `incompatible` and `unresolved` produce error `RAPID1110` and exit code `1`.

## Capability is not evidence

A declared capability does not prove that it was used.

Example:

- the profile may declare `tests.execute = supported`;
- the run may require `gate.tests`;
- even so, the evaluation will be `UNVERIFIED` if there is no valid evidence of a test execution.

The separation is deliberate:

```text
Capability = what the harness is declared able to do
Evidence   = what was observed to happen
Eval       = what Rapid OS can conclude from that evidence
```
