---
title: What is Rapid OS?
description: The purpose, scope, users, and mental model of Rapid OS v3.
---

# What is Rapid OS?

Rapid OS is an **engineering governance layer for AI-assisted development**. Installed as a CLI, it maintains versionable artifacts in the repository so coding harness work has context, scope, rules, traceability, and verifiable evidence.

## Purpose

Rapid OS helps ensure that an AI-assisted task can answer these questions verifiably:

1. What do we know about the repository?
2. What should be built?
3. What context does the agent need for this task?
4. What risk level and controls apply?
5. Has the harness declared the required capabilities?
6. What actually happened during execution?
7. What evidence shows that the task and its gates were satisfied?
8. Does the project remain internally consistent?

## Who it is for

Rapid OS is designed for:

- Developers using Codex, Claude, Cursor, VS Code, or other coding harnesses.
- Teams standardizing how context is provided to AI agents.
- Architects separating human decisions from automated inferences.
- Teams with quality, security, review, or migration controls.
- Organizations needing traceability between specifications, execution, and evidence.

## Mental model

Rapid OS is a **control layer**, not the builder:

```text
User / team defines intent and constraints
        ↓
Rapid OS produces context, contracts, gates, and records
        ↓
External coding harness implements or modifies software
        ↓
Rapid OS ingests evidence and evaluates deterministic rules
        ↓
Governed result
```

## What it does

Rapid OS can detect languages, frameworks, databases, testing tools, Docker, monorepos, and deployment signals; maintain immutable specification revisions; compile task-specific context; classify risk and require gates; model harness capabilities; maintain an append-only run ledger; copy and verify evidence artifacts with SHA-256; produce reproducible deterministic evaluations; validate integrity across specifications, runs, evidence, and evaluations; and guide governed runs with `rapid start`, `rapid next`, `rapid check`, `rapid task`, `rapid attach`, and `rapid finish`. It can also generate `/rapid-<mode>` shortcuts for supported harnesses.

## What it does not do

Rapid OS does not invoke LLMs or coding agents automatically. Its plumbing commands operate on files and records rather than executing repository code. The porcelain runs only the configured `test_command` or an explicitly supplied `rapid check -- <command>` (without a shell), plus read-only Git commands to record run changes. It does not independently approve human gates, create branches or worktrees except when explicitly requested with `rapid start --worktree`, or guarantee that a `PASS` means there are no bugs or perfect security.

Human approvals are performed by a person in their terminal using `rapid approve`; an acknowledged gate is not evidence, and a declared capability is not proof it was used. Drafts remain assumptions until explicitly confirmed.

## Compatibility

Rapid OS v3 retains legacy v2 workflows, including `rapid init`, `rapid scope`, `rapid skill`, `rapid mcp`, `rapid vision`, `rapid deploy`, `rapid refine`, `rapid inspect-context`, `rapid validate`, and `rapid doctor`, while adding the v3 governance loop.
