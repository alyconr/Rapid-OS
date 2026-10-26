---
title: Orchestration Architecture
description: How the porcelain layer drives a run through the v3 governance engine.
---

# Orchestration Architecture

Rapid OS has two layers. **Plumbing** (`rapid spec`, `rapid run`, `rapid evidence`, `rapid eval`, and related commands) is the v3 governance engine: immutable records, contracts, evidence, and evaluation. **Porcelain** (`rapid start`, `rapid next`, `rapid check`, `rapid task`, `rapid attach`, `rapid finish`, `rapid approve`, `rapid status`, `rapid abort`) expresses user intent and drives a run through that engine. [Shortcuts](../guides/shortcuts.md) teach a harness the loop; the [advanced mode](../governance-loop.md) uses plumbing directly.

The porcelain does not create a separate data model. Each action ends in the same plumbing registries and digests. The ledger is append-only; no command rewrites records under `.rapid-os/runs`, `evidence`, or `evals`. Human gates are never acknowledged automatically.

## The loop

`rapid next --json` computes the next action without changing state and can be repeated. Actions include authoring a spec, running a baseline, activating, implementing a task, verifying, awaiting human approval, and finishing. `rapid check` runs a command and records evidence; `rapid finish` records changes, acknowledges eligible machine gates, and evaluates the run.

## The Conductor

`next_action(contract, state, evidence, playbook, *, evaluator, test_command)` in `rapid_os/orchestration/conductor.py` is pure: it receives the contract, run state, evidence, and mode playbook, and returns a `NextAction`. I/O belongs to `lifecycle.py`. The Conductor asks `BehavioralEvaluator` which assertions remain unsatisfied; it does not reimplement governance rules.

`gate_satisfied(...)` hypothetically acknowledges a gate in a copy of state and evaluates again. If its assertion passes, evidence supports acknowledgment. This allows machine gates to be acknowledged only when justified, never human gates.

Rule order: terminal run → `done`; blocked run → `blocked`; rejected human review → `blocked` with `rapid abort`; pending baseline → `run_baseline`; unfinished tasks → `implement_task`; terminal tasks with failing assertions → `blocked`; missing machine evidence or unobserved `tests.execute` → `verify`; pending human gates → `await_human_approval`; otherwise → `finish`. Mode playbooks define the task details; see [mode guides](../guides/modes/index.md).

## `NextAction` schema

`rapid next --json` (also `rapid start --json` and `rapid finish --json`) returns `schema_version`, `run_id`, `mode`, an `action` (`kind`, instructions, command, and follow-up), pending human gates, missing assertions, progress, and an outcome when done. Optional fields are omitted when unused.

## Session and evidence

`.rapid-os/session.json` records the active run, mode, harness, starting Git HEAD, pre-existing untracked paths, and optional isolated worktree. It is not part of the ledger and has no digest. `rapid abort` removes it; `rapid validate` checks it against the RunRegistry. `.rapid-os/scratch/` stores disposable check logs and hook state.

Evidence producers include `rapid:check` (test or command results), `rapid:start` (workspace), `rapid:finish` (changed files, excluding `.rapid-os/` and tool artifacts), `rapid:attach` (artifact), `user` (`rapid approve` review), and `harness:<id>` (external evidence).

## Ruleset v2

- `gate.architecture` is added for `feature`, `bugfix`, and `refactor` when `architecture.json` exists. It requires `rapid arch check` evidence and cannot be waived.
- `rapid check --expect fail --task <id>` records an expected failure as a reproduction assertion. It is not a task failure and cannot satisfy baseline or test gates.
- Evidence from `harness:*` cannot satisfy human review gates. Only `rapid approve` evidence from producer `user` can do so.

## Human approval defenses and limits

`rapid approve` requires an interactive TTY, rejects the Claude Code child-session marker and Claude Code process ancestry, and requires typing `approve <gate-id>` (or `waive <gate-id>`). Optional Claude Code hooks deny sensitive commands and edits under `.rapid-os/`. Approval is recorded as a `user` review.

These are best-effort defenses, not cryptographic identity proof. Detached or renamed processes, emulated TTYs, dynamically constructed commands, and declared reviewer identities limit detection. A person must approve in their own terminal.

## Where the pieces live

- Conductor and `NextAction`: `rapid_os/orchestration/conductor.py`, `actions.py`
- Porcelain lifecycle and I/O: `lifecycle.py`, `check.py`, `session.py`, `workspace.py`
- Playbooks: `templates/modes/*.json`, `playbooks.py`
- Hooks: `hooks.py`, `hook_runtime.py`, `rapid_os/adapters/claude_hooks.py`
- Shortcuts: `templates/shortcuts/*.md`, `shortcut_installer.py`, `rapid_os/adapters/agents/`
- Process ancestry: `rapid_os/core/ancestry.py`
- Governance engine: [Architecture v3](./rapid-os-v3.md)
