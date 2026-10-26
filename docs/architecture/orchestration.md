---
title: Orchestration Architecture
description: "How the porcelain layer (rapid start, next, check, finish…) drives a run on top of the v3 governance engine (plumbing): Conductor, NextAction, session.json, evidence producers, ruleset v2, and the defenses of rapid approve."
---

# Orchestration Architecture

Rapid OS has two layers. The **plumbing** (`rapid spec`, `rapid run`, `rapid evidence`, `rapid eval`…) is the v3 governance engine: immutable records, contracts, evidence, and evaluation. The **porcelain** (`rapid start`, `rapid next`, `rapid check`, `rapid task`, `rapid attach`, `rapid finish`, `rapid approve`, `rapid status`, `rapid abort`) is the intent layer that drives a run *using* the plumbing. The [shortcuts](../guides/shortcuts.md) are files that teach an agent to follow that loop; the [advanced mode](../governance-loop.md) uses the plumbing directly.

This page describes how the pieces fit together. The limits of what gets executed are in [product boundaries](../concepts/product-boundaries.md).

---

## 1. Porcelain on top of plumbing

```text
  Person / agent                       who decides?
        │  /rapid-<mode> <goal>
        ▼
  Shortcuts and hooks (per harness)    teach the loop and watch the agent
        │  rapid next / start / check / task / attach / finish
        ▼
  PORCELAIN  rapid_os/orchestration/   Conductor (pure) + lifecycle (I/O)
        │  calls the registries, never CLI functions
        ▼
  PLUMBING   rapid_os/adapters/        SpecRegistry · RunRegistry · EvidenceRegistry · EvalRegistry
             rapid_os/domain/          contracts, RunState, RunEvidence, BehavioralEvaluator
        ▼
  .rapid-os/   specs/ runs/ evidence/ evals/   append-only ledger (+ session.json and scratch/)
```

- The porcelain **does not create another data model**: every action ends in plumbing records (specs, runs, states, evidence, reports) with the same digests.
- The ledger is append-only: no verb rewrites files under `.rapid-os/runs`, `evidence`, or `evals`.
- A human gate is never acknowledged automatically (see [section 8](#8-rapid-approve-layers-of-defense-and-their-limit)).

---

## 2. The loop

```text
        ┌────────────────────────────────────────────────────────────┐
        │                                                            │
        ▼                                                            │
  rapid next --json ──► action.kind                                  │
        │                                                            │
        ├─ author_spec ──► write the spec ──► rapid start <mode> --spec-file -
        ├─ run_baseline / activate / verify ──► run action.command
        ├─ implement_task ──► implement ──► rapid check -- <tests> ──► action.after (rapid task done)
        │                                                            │
        ├─ await_human_approval ──► STOPS: a person runs rapid approve <gate> ──┐
        ├─ blocked ──► explain the reason (e.g. rapid abort after a rejection)  │
        └─ finish ──► rapid finish ──► verdict (PASS / PASS_WITH_WAIVERS / FAIL / UNVERIFIED)
                                                                     ▲                      │
                                                                     └──────────────────────┘
```

`rapid next` never mutates state: it computes the next action and can be repeated. `rapid check` runs a command and records evidence; `rapid finish` records the changes, acknowledges the machine gates that already satisfy the rules, and evaluates the run.

---

## 3. The Conductor: a pure function with the evaluator as oracle

`next_action(contract, state, evidence, playbook, *, evaluator, test_command)` (in `rapid_os/orchestration/conductor.py`) **performs no I/O**: it receives the contract, the `RunState`, the evidence, and the mode playbook, and returns a `NextAction`. I/O (reading the ledger, writing evidence, running `rapid check`) lives in `lifecycle.py`.

The Conductor does not reimplement the governance rules: **it asks the `BehavioralEvaluator`**. It evaluates the run in memory (`evaluator.evaluate(...)`) and reads the assertions (`UNVERIFIED`, `FAIL`, `PASS`) to decide what is missing.

`gate_satisfied(contract, state, evidence, gate_id, *, evaluator)` formalizes that idea: it *hypothetically* acknowledges the gate (on a copy of the state) and evaluates again. If the gate's assertion becomes `PASS`, the evidence already backs it and acknowledging it is safe; if not, evidence is missing. This way `rapid start` and `rapid finish` only acknowledge machine gates when the evidence justifies it, and never a human gate.

Rule order (the first one that applies wins):

| # | Condition | Action |
| :--- | :--- | :--- |
| 1 | The run is terminal | `done` (with the outcome) |
| 2 | The run is `blocked` | `blocked` |
| 3 | A human review was rejected (`changes_requested`) | `blocked` with the `rapid abort` command: the gate stays `FAIL` in that run |
| 4 | `prepared` with a pending `gate.baseline` | `run_baseline` (or `activate` if it is already satisfied) |
| 5 | `active` with unfinished tasks | `implement_task` (mode rules: `bugfix` asks for `rapid check --expect fail` on `T001`; `research` closes tasks with `--no-check`) |
| 6 | All tasks terminal | `refactor`: `blocked` if passed tests drop relative to the baseline; an assertion in `FAIL` → `blocked` |
| 7 | Unverified task or machine gate, or the `tests.execute` capability unobserved | `verify` |
| 8 | Human gates pending | `await_human_approval` |
| 9 | Everything resolved | `finish` |

The playbooks (`templates/modes/<mode>.json`) provide the spec template and the text of each action; the rules specific to each mode are in the [mode guides](../guides/modes/index.md).

---

## 4. The `NextAction` schema

`rapid next --json` (and `rapid start --json`, `rapid finish --json`) return:

```json
{
  "schema_version": 1,
  "run_id": "booking-availability-r1-run-001",
  "mode": "feature",
  "action": {
    "kind": "implement_task",
    "task_id": "T001",
    "instructions": "Implementa solo la tarea indicada. Corre los tests con rapid check.",
    "command": ["rapid", "task", "start", "T001"],
    "after": ["rapid", "task", "done", "T001"]
  },
  "awaiting_human": ["gate.final-verification"],
  "missing": ["task.T001.evidence", "gate.gate.tests.evidence"],
  "progress": {"tasks_done": 0, "tasks_total": 1},
  "outcome": null
}
```

| Field | Meaning |
| :--- | :--- |
| `action.kind` | `author_spec`, `run_baseline`, `activate`, `implement_task`, `verify`, `await_human_approval`, `finish`, `done`, or `blocked` |
| `action.command` | Exact command to run (as an argv list) or `null` |
| `action.after` | Command to run when the agent finishes the action's work (e.g. `rapid task done`) or `null` |
| `action.task_id`, `action.gate_ids` | Task or gates the action refers to (optional) |
| `action.spec_template` | The mode's spec template, in `author_spec` (optional) |
| `action.workspace_path` | The run's isolated worktree, if it has one (optional) |
| `awaiting_human` | Pending human gates |
| `missing` | Evaluator assertions not yet satisfied |
| `outcome` | Verdict or result, only when `kind` is `done` |

Optional fields are omitted when unused, so the output of a mode without a worktree does not change.

---

## 5. `.rapid-os/session.json`

The porcelain remembers the active run in `.rapid-os/session.json` (`rapid init` adds it to `.gitignore` if one exists). It is not part of the ledger and has no digest:

| Field | Meaning |
| :--- | :--- |
| `schema_version`, `active_run_id`, `mode`, `harness` | Active run, chosen mode and harness |
| `start_head` | git `HEAD` at start; `rapid finish` records changes against it |
| `start_untracked` (optional) | Untracked files that already existed at start; `rapid finish` does not attribute them to the run |
| `workspace_path` (optional) | Isolated worktree created with `rapid start --worktree` |

`rapid abort` deletes the file; `rapid validate` checks it against the `RunRegistry` (`RAPID1304`, `RAPID1305`). Alongside it, `.rapid-os/scratch/` holds the `rapid check` logs and the hook state; both are disposable.

---

## 6. Porcelain evidence producers

Every verb that records evidence does so with an identifiable producer:

| Producer | Who writes it | Evidence |
| :--- | :--- | :--- |
| `rapid:check` | `rapid check`, `rapid task done`, the `rapid start` baseline | `test_result` or `command_result`, with the log as an artifact |
| `rapid:start` | `rapid start` | `workspace` (`current` or `isolated`) |
| `rapid:finish` | `rapid finish` | `file_change` with the files modified by the run, excluding `.rapid-os/` and tool artifacts (`__pycache__`, `*.pyc`, `.pytest_cache`...); with no real changes nothing is recorded |
| `rapid:attach` | `rapid attach` | `artifact` with the attached file, linked to a task |
| `user` | `rapid approve` | `review` with the result and the reviewer |
| `harness:<id>` | an external harness, via `rapid evidence add` | any; see ruleset v2 |

---

## 7. Ruleset v2

The evaluator applies ruleset v2 by default (`rapid eval run --ruleset {1,2}`):

- **`gate.architecture`:** in `feature`, `bugfix`, and `refactor`, if `architecture.json` exists, the contract adds this machine gate (`architecture_check`, post-execution, mandatory, non-waivable). `rapid next` proposes `rapid check --gate gate.architecture -- rapid arch check` and violations are `RAPID1420`. See [Architecture by stack](../concepts/architecture.md#the-gatearchitecture-gate).
- **`expectation: "fail"`:** `rapid check --expect fail --task <id>` records an expected failure. It produces the `reproduction.<task>` assertion as `PASS` if the command really failed (and `FAIL` if not), and that evidence does **not** count as a task failure nor serve as `gate.baseline` or `gate.tests` evidence. It is only accepted linked to a task (`RAPID1320`).
- **`harness:*` does not close human gates:** review evidence produced by a `harness:<id>` stays `UNVERIFIED` for human review gates. Only a `rapid approve` review (producer `user`) can back them.

---

## 8. `rapid approve`: layers of defense and their limit

Approving a human gate requires these checks, from cheapest to strongest:

1. **TTY:** without an interactive terminal it fails with `RAPID1310` (an EOF during confirmation is treated the same way).
2. **Session marker:** `CLAUDE_CODE_CHILD_SESSION=1` rejects the execution.
3. **Ancestry:** if any ancestor process is the Claude Code binary (`claude`/`claude.exe`), it fails with `RAPID1310` even when there is a TTY and no variables remain.
4. **Textual confirmation:** you must type `aprobar <gate-id>` (`dispensar <gate-id>` for `--waive`).
5. **Claude Code hooks (optional):** `PreToolUse` denies the agent `rapid approve`, `rapid abort`, `rapid run gate`, `rapid evidence add`, and editing `.rapid-os/`, and denies removing the session variables.
6. **Evidence:** the approval is stored as a `review` with producer `user`; the evaluator does not accept one from a `harness:*` (ruleset v2).

**Known limit.** These are best-effort defenses, not a cryptographic guarantee. Ancestry detection does not see a process that detaches from its parent (double fork, `setsid`, `nohup … &`), a renamed `claude.exe`, or a reused pid; a TTY can be emulated; the hooks' command analysis does not detect a command built at runtime; and the reviewer identity is whatever is declared. The underlying rule does not change: **a person approves, in their own terminal.**

---

## 9. Where each piece lives

| Piece | Module |
| :--- | :--- |
| Conductor, `NextAction` | `rapid_os/orchestration/conductor.py`, `actions.py` |
| Porcelain verbs (I/O) | `rapid_os/orchestration/lifecycle.py`, `check.py`, `session.py`, `workspace.py` |
| Playbooks | `templates/modes/*.json`, `rapid_os/orchestration/playbooks.py` |
| Hooks | `rapid_os/orchestration/hooks.py` (pure decision), `hook_runtime.py`, `rapid_os/adapters/claude_hooks.py` |
| Shortcuts | `templates/shortcuts/*.md`, `rapid_os/adapters/shortcut_installer.py`, `rapid_os/adapters/agents/` |
| Process ancestry | `rapid_os/core/ancestry.py` |
| Governance engine | [Architecture v3](./rapid-os-v3.md) |
