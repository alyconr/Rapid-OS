---
title: Harness Profiles and Capabilities
description: Configure coding harness profiles, resolve capability compatibility, and create locks in Rapid OS.
---

# Harness Profiles and Capabilities

Editors and assistants such as Cursor, Claude Code, GitHub Copilot, Codex, and Antigravity expose different tools. Rapid OS does not assume they can perform the same actions. The **Harness Capability Registry** declares, versions, and audits capabilities each harness says it supports.

## What a capability represents

A declared capability such as `repository.write` or `shell.execute` represents support declared by the harness. Rapid OS does not invoke the harness or control operating-system processes and permissions. A declaration does not prove execution or correctness.

## Canonical capabilities

The canonical catalog contains: `context.consume`, `git.inspect`, `git.modify`, `mcp.invoke`, `repository.read`, `repository.write`, `shell.execute`, `subagents.delegate`, `tests.execute`, `workspace.current`, and `workspace.isolated`.

## Built-in profiles

```bash
rapid harness list
rapid harness show codex
rapid harness show claude
rapid harness show cursor
rapid harness show antigravity
```

## Create or customize a local profile

Initialize a profile at `.rapid-os/harnesses/<id>.json`:

```bash
rapid harness init my-internal-agent
```

A version 1 `HarnessProfile` contains `schema_version`, `id`, and a list of capability declarations, each with `capability_id`, `status`, and `reason`. The only valid statuses are `supported`, `unsupported`, and `unknown`. Use `reason` to explain operational restrictions; `conditional` is not a valid status.

## Lock and resolve capabilities

`rapid harness lock` computes canonical SHA-256 digests for active profiles and records them in `.rapid-os/capabilities.lock` for consistent CI and local use.

```bash
rapid harness resolve --run feature-payment-r1-run-001
rapid harness resolve --run feature-payment-r1-run-001 --locked
rapid harness resolve --run feature-payment-r1-run-001 --require-compatible
```

Resolution is `compatible` when every required capability is supported; `incompatible` when a required capability is unsupported; and `unresolved` when any is unknown or undeclared. With `--require-compatible`, incompatible returns exit 1 and `RAPID1110`; unresolved also returns exit 1.

Require an additional capability at resolution time with `--require`, for example:

```bash
rapid harness resolve --run feature-payment-r1-run-001 --require "shell.execute" --require-compatible
```
