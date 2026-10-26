---
title: Use Cases
description: Practical scenarios where Rapid OS provides context, governance, and evidence.
---

# Use Cases

Rapid OS is useful when the goal is not only to "generate code," but to show **what was requested, under which constraints the work ran, and what evidence exists for the result**.

## 1. Implement a feature with controlled context

A team needs to add a feature without letting the agent improvise architecture or business rules.

With shortcuts, use `/rapid-feature <goal>`; the agent drafts the spec, creates the run, and stops at human gates.

Advanced workflow (v3 commands):

```bash
rapid scan --write
rapid spec create --title "New feature" --mode feature --status ready
rapid context --spec new-feature --harness codex --manifest
rapid run create --spec new-feature --harness codex
```

Rapid OS pins a spec, compiles context with provenance, and creates an execution contract before the harness changes code.

## 2. Refactor a legacy system

With shortcuts, use `/rapid-refactor <scope>`; the run is blocked if the passing test baseline decreases.

In a legacy system, `rapid init` and `rapid scan` help distinguish:

- signals detected in the repository;
- rules confirmed by the team;
- standards the agent must follow;
- the explicit scope of the refactor.

This reduces the chance that the agent copies outdated patterns just because they exist in the current code.

## 3. High-risk changes

Use `/rapid-hardening <area>` for work in an isolated worktree (`rapid start --worktree`), `/rapid-bugfix <description>` to fix a defect, or `/rapid-research <question>` for investigation without mandatory tests.

A schema migration, authentication, infrastructure, or security change can raise risk to `high` or `critical`. Rapid OS may require an isolated workspace, a baseline, manual review, tests, security review, migration review, and final verification. The run cannot bypass the contract's preconditions.

## 4. Teams using multiple coding harnesses

Run `rapid shortcuts install --harness <id>` to generate the same `/rapid-*` shortcuts in each harness directory; see [Combining harnesses](./shortcuts.md#if-you-combine-harnesses).

Rapid OS models profiles for `codex`, `claude`, `cursor`, `vscode`, `antigravity`, and custom harnesses. This lets you answer: **Does this harness declare support for every capability required by this run?** The resolution can be `compatible`, `incompatible`, or `unresolved`.

## 5. Evidence for CI or review processes

This is the advanced-mode path: CI uses v3 commands, not shortcuts.

After an external tool runs tests or reviews, its results can be recorded as evidence:

```bash
rapid evidence add --run checkout-r1-run-001 --input test-evidence.json
rapid evidence verify --run checkout-r1-run-001
rapid eval run --run checkout-r1-run-001 --require-pass
```

Rapid OS validates bindings, sequence, digests, sizes, and semantic rules before returning a verdict.

## 6. Reusable context engineering

Legacy workflows remain useful for generating agent rules, maintaining project standards, preparing MCP for editors, installing skills, recording visual references, generating deployment guides, and creating structured prompts.

## When Rapid OS is not needed

Rapid OS may be excessive for very small exploratory tasks that need no traceability, policy, or evidence. It provides the most value when an organization needs **consistency, control, repeatability, and auditing**.
