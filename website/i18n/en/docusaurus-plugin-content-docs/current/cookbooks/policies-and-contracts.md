---
title: Execution Policies and Contracts
description: Configure .rapid-os/policy.json and understand execution contracts in Rapid OS.
---

# Execution Policies and Contracts

In Rapid OS, changes are governed by an **ExecutionContract**, evaluated deterministically by `ExecutionPolicyEvaluator` against `.rapid-os/policy.json`.

## Inspect or initialize policy

```bash
rapid policy show
rapid policy show --json
rapid policy init
```

The default policy is built in. `rapid policy init` creates a project policy; if the file already exists, it aborts with `RAPID1005` to avoid accidental overwrite.

## Policy schema

Version 1 policy fields include `minimum_classification` (`spike`, `bounded`, or `architectural`), `minimum_risk` (`low`, `medium`, `high`, or `critical`), architectural tags and path prefixes, high and critical risk tags, `workspace_by_risk`, `waivable_gate_ids`, and `extra_required_gate_ids`. Workspace rules use `current_allowed` or `isolated_required`; path prefixes are relative POSIX paths. Waivable gates are limited to canonical gate IDs.

## Canonical gates

| Gate | Phase | Evidence |
| --- | --- | --- |
| `gate.workspace-isolation` | Pre-execution | `workspace` |
| `gate.baseline` | Pre-execution | Passing `test_result` or `command_result` |
| `gate.manual-approval` | Pre-execution | `review` or `delegation` |
| `gate.tests` | Post-execution | Passing `test_result` |
| `gate.architecture` | Post-execution | Successful `rapid arch check` command result, when configured for supported modes; not waivable |
| `gate.review` | Post-execution | Approved `review` |
| `gate.security-review` | Post-execution | `review` or `command_result` |
| `gate.migration-review` | Post-execution | Specialized `review` |
| `gate.final-verification` | Post-execution | Complete run evaluation |

## Contract lifecycle

`rapid run create --spec <spec-id> --harness <harness-id>` resolves the immutable spec and digest, evaluates its paths and tags against policy, emits a `PolicyDecision`, creates the immutable contract, and initializes `RunState` revision 1 in `prepared` state.

```bash
rapid run status my-run-001 active --reason "Implementation started"
rapid run task my-run-001 T1 done --reason "Endpoints implemented and tested"
rapid run gate my-run-001 gate.baseline acknowledged --reason "Baseline passed"
rapid run status my-run-001 finished --reason "Tasks complete and tests pass"
```

## Justified waivers

A human may waive a gate only when its ID appears in `waivable_gate_ids` (the default examples are `gate.review` and `gate.tests`):

```bash
rapid run gate my-run-001 gate.review waived --reason "Emergency production hotfix, incident #992"
```

Attempting to waive a gate not permitted by policy is rejected with `RAPID1013`. Evaluation reports the waiver and returns `pass_with_waivers` when all other requirements pass.
