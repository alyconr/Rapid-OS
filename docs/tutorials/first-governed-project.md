# Manual Walkthrough: The Governance Loop by Hand (Under the Hood)

> **Advanced mode.** You do not need this lab to use Rapid OS: it types in a terminal, one by one, the daily commands (`rapid start`, `rapid next`, `rapid check`, `rapid task`, `rapid approve`, `rapid finish`) that the agent runs for you with the shortcuts. It is meant for integrators, CI, and auditing. If you are just starting out, go to the [labs](index.md), beginning with [Feature](feature-lab.md) (`/rapid-feature`).

Learn how to run the complete RAPID OS governance loop on a real Python project, seeing what each step records and why a verdict can only reach `pass` with real tests and a real human approval.

---

## 1. Overview

- **Name:** Task Tracker CLI Governance.
- **Problem:** A Python project without governance risks unvalidated changes introduced by AI assistants. A new task-priority feature must be implemented under a verifiable contract.
- **Goal:** Walk through the entire governance cycle, from `rapid init` to the evaluation report and the final integrity validation, using only the daily commands.
- **Difficulty level:** Advanced.
- **Prerequisites:** Basic use of the terminal, git, and Python commands.
- **Dependencies:** Python 3.10+ (standard library only) and git.
- **Reference files:** [`examples/first-governed-project/`](https://github.com/alyconr/Rapid-OS/tree/main/examples/first-governed-project).

---

## 2. Learning Outcomes

By completing this lab, you will know how to:
1. Initialize RAPID OS in an existing git repository.
2. Open a governed run from a spec file (`rapid start feature --spec-file`), which also records the baseline.
3. Ask Rapid OS for the next deterministic step (`rapid next`).
4. Work on a task and close it with its tests (`rapid task start`, `rapid task done`).
5. Satisfy the machine gates with checks Rapid OS runs itself (`rapid check`).
6. Approve the human gate from your own terminal (`rapid approve`).
7. Finish the run and get its evaluation report (`rapid finish`, `rapid eval run --require-pass`).
8. Validate the holistic integrity of the project (`rapid validate`).
9. Tell apart the plumbing commands (`rapid evidence add`, `rapid run gate`) that never satisfy a test or human gate.

---

## 3. Initial State

The initial application is an in-memory task manager:

```text
task-tracker/
├── app.py
└── tests/
    ├── __init__.py
    └── test_app.py
```

Initial state of `app.py`:

```python
# app.py
"""Minimal Task Tracker application."""

class TaskTracker:
    def __init__(self):
        self.tasks: list[dict[str, object]] = []

    def add_task(self, title: str) -> dict[str, object]:
        if not title or not title.strip():
            raise ValueError("Task title cannot be empty.")
        task = {
            "id": len(self.tasks) + 1,
            "title": title.strip(),
            "status": "pending",
        }
        self.tasks.append(task)
        return task

    def list_tasks(self) -> list[dict[str, object]]:
        return list(self.tasks)
```

Initial state of `tests/test_app.py`:

```python
# tests/test_app.py
import unittest
from app import TaskTracker

class TestTaskTracker(unittest.TestCase):
    def setUp(self):
        self.tracker = TaskTracker()

    def test_add_and_list_tasks(self):
        task = self.tracker.add_task("Initial task")
        self.assertEqual(task["id"], 1)
        self.assertEqual(task["title"], "Initial task")
        self.assertEqual(task["status"], "pending")
        self.assertEqual(len(self.tracker.list_tasks()), 1)

    def test_reject_empty_task(self):
        with self.assertRaises(ValueError):
            self.tracker.add_task("")

if __name__ == "__main__":
    unittest.main()
```

Initialization of the test package `tests/__init__.py`:

```python
# tests/__init__.py
"""Test package initialization."""
```

In this initial state, `TaskTracker.add_task(title)` only accepts the task title and assigns it the `pending` status.

---

## 4. Engineering Requirements

1. **New feature:** Allow specifying the task priority (`low`, `medium`, `high`), defaulting to `medium`.
2. **Validation:** Reject unknown priorities with `ValueError`.
3. **Filtering:** `list_tasks(priority=None)` must allow filtering by priority when one is given.
4. **Preservation:** Do not break existing unit tests.

---

## 5. Guided Procedure

### Step 1: Put the starter under git

Rapid OS observes the changes of a run with git, so the project starts from a commit:

```bash
git init
git add .
git commit -m "Starter task tracker"
```

### Step 2: Initialize RAPID OS

At the project root, initialize Rapid OS without prompts (`--yes`) with a Python stack:

```bash
rapid init --stack python-ai --yes
```

This creates the `.rapid-os/` structure with its standards and base configuration. It detects the `tests/` folder and records `python -m unittest discover` as the project's `test_command`: the command Rapid OS trusts to run the tests.

### Step 3: Write the spec

The spec says what the run must achieve and which tasks it has. Save it as `spec.json`:

```json
{
  "title": "Task priority",
  "business_objective": "Tasks carry a priority so the most urgent work can be listed first.",
  "acceptance_criteria": [
    "add_task accepts the priorities low, medium and high, and medium by default",
    "add_task rejects an unknown priority with ValueError",
    "list_tasks(priority) returns only the tasks of that priority"
  ],
  "implementation_tasks": ["T001: Implementar soporte de prioridades en TaskTracker"]
}
```

### Step 4: Start the run

```bash
rapid start feature --spec-file spec.json
```

`rapid start` stores the spec (id `task-priority`), resolves the execution policy, and creates the run `task-priority-r1-run-001` with its immutable `ExecutionContract`. For a `feature` spec on a backend stack the contract requires these gates:

- `gate.baseline` (phase `pre_execution`): the test suite passes before anything changes. `rapid start` runs `test_command` itself and records the result as `test_result` evidence produced by `rapid:check`; with the baseline satisfied it activates the run.
- `gate.tests` (phase `post_execution`): the test suite passes on the final code.
- `gate.architecture` (phase `post_execution`): this project was initialized with a backend stack (`python-ai`), so it starts as a modular monolith and the rule is verified with `rapid arch check`.
- `gate.final-verification` (phase `post_execution`): a person approves the result, in their own terminal.

### Step 5: Ask for the next step

```bash
rapid next
```

Rapid OS answers with the next deterministic action and its exact command: `implement_task -> rapid task start T001`. Whenever you are unsure what comes next, `rapid next` tells you.

---

## 6. External Execution

> **Responsibility boundary note:** RAPID OS does **not** edit the code. The implementation is carried out by the developer or their external coding harness (Claude Code, Cursor, Codex, Antigravity, etc.).

### Step 1: Start the task

```bash
rapid task start T001
```

### Step 2: Implement the code and its tests

Modify `app.py` and `tests/test_app.py` to meet the requirements:

```python
# app.py
"""Enhanced Task Tracker application with priority support."""

class TaskTracker:
    VALID_PRIORITIES = ("low", "medium", "high")

    def __init__(self):
        self.tasks: list[dict[str, object]] = []

    def add_task(self, title: str, priority: str = "medium") -> dict[str, object]:
        if not title or not title.strip():
            raise ValueError("Task title cannot be empty.")
        priority_normalized = priority.lower().strip()
        if priority_normalized not in self.VALID_PRIORITIES:
            raise ValueError(f"Invalid priority '{priority}': must be one of {self.VALID_PRIORITIES}.")
        task = {
            "id": len(self.tasks) + 1,
            "title": title.strip(),
            "priority": priority_normalized,
            "status": "pending",
        }
        self.tasks.append(task)
        return task

    def list_tasks(self, priority: str | None = None) -> list[dict[str, object]]:
        if priority is None:
            return list(self.tasks)
        p = priority.lower().strip()
        return [t for t in self.tasks if t["priority"] == p]
```

Update the suite in `tests/test_app.py`:

```python
# tests/test_app.py
import unittest
from app import TaskTracker

class TestTaskTracker(unittest.TestCase):
    def setUp(self):
        self.tracker = TaskTracker()

    def test_add_and_list_tasks_default_priority(self):
        task = self.tracker.add_task("Initial task")
        self.assertEqual(task["id"], 1)
        self.assertEqual(task["title"], "Initial task")
        self.assertEqual(task["priority"], "medium")
        self.assertEqual(task["status"], "pending")
        self.assertEqual(len(self.tracker.list_tasks()), 1)

    def test_add_task_with_custom_priority(self):
        t1 = self.tracker.add_task("Urgent bug", priority="high")
        t2 = self.tracker.add_task("Clean backlog", priority="low")
        self.assertEqual(t1["priority"], "high")
        self.assertEqual(t2["priority"], "low")
        high_tasks = self.tracker.list_tasks(priority="high")
        self.assertEqual(len(high_tasks), 1)
        self.assertEqual(high_tasks[0]["title"], "Urgent bug")

    def test_reject_invalid_priority(self):
        with self.assertRaises(ValueError):
            self.tracker.add_task("Invalid", priority="critical")

    def test_reject_empty_task(self):
        with self.assertRaises(ValueError):
            self.tracker.add_task("")

if __name__ == "__main__":
    unittest.main()
```

### Step 3: Close the task with its tests

```bash
rapid task done T001
```

`rapid task done` runs `test_command` before closing the task. If a test fails, the task stays open and the command exits with the failure.

---

## 7. Evidence Collection

Every piece of evidence in this walkthrough is written by Rapid OS itself while it runs something. You never write evidence by hand.

### 1. Verify the machine gates

Ask for the next step:

```bash
rapid next
```

It answers `verify -> rapid check --gate gate.tests -- python -m unittest discover`. Run the command it gives:

```bash
rapid check --gate gate.tests -- python -m unittest discover
```

`rapid check` runs the command without a shell, keeps its output as a log under `.rapid-os/scratch/checks/`, reads the test summary (`Ran 4 tests ... OK`), and records `test_result` evidence produced by `rapid:check` with the counts, `counted: true`, and the fingerprint (`tree`) of the working tree it verified.

Then the architecture gate. `rapid next` proposes it with `--new-only` (only violations the run adds fail); this project has no module yet, so the plain checker passes too:

```bash
rapid next
rapid check --gate gate.architecture -- rapid arch check
```

### 2. What does not count as a test run

A test gate (`gate.tests`, `gate.baseline`) is only satisfied by a check Rapid OS ran whose output had a test summary it could count (pytest, unittest, vitest, jest, `cargo test`, `go test -v`) or whose command is exactly `test_command`, with at least one test executed and the working tree recorded. So:

- `rapid check --kind test -- python -c "print('hello')"`, bound to `gate.tests`, passes as a command, but it is recorded as `command_result` and `rapid next` keeps asking for the real test command (`RAPID1432`).
- If the code changes after the last check, `rapid next`, `rapid approve`, and `rapid finish` ask for a new check and name the files (`RAPID1423`).

### 3. Approve the human gate

`rapid next` now answers `await_human_approval -> rapid approve gate.final-verification`. Review the diff and run, **in your own terminal** (not from inside an agent):

```bash
rapid approve gate.final-verification
```

Rapid OS asks you to type the phrase `aprobar gate.final-verification`. It records `review` evidence written by `rapid approve`, with your name and the fingerprint of the working tree you approved. An agent cannot do it: inside an agent session, under an agent process, or without a TTY, it is refused (`RAPID1310`).

---

## 8. Evaluation

Finish the run:

```bash
rapid finish
```

`rapid finish` records the changed files (`file_change`, produced by `rapid:finish`), acknowledges the machine gates whose evidence satisfies them, checks that the code is still the one the tests verified and you approved (otherwise it refuses with `RAPID1423` or `RAPID1433` and names the files), and writes the evaluation report with the verdict.

Read the report again and require the passing verdict (`--require-pass` exits with an error if the verdict is not `pass`):

```bash
rapid eval run --run task-priority-r1-run-001 --require-pass
```

The evaluator (ruleset 3) checks the run lifecycle, the tasks, the required gates (`gate.baseline`, `gate.tests`, `gate.architecture`, `gate.final-verification`), and the observed capabilities, and emits the verdict:

```json
{
  "verdict": "pass",
  "run_id": "task-priority-r1-run-001"
}
```

---

## 9. Validation

Validate the cryptographic integrity of the whole repository:

```bash
rapid validate
```

---

## 10. Reference: the plumbing commands

The daily commands above are built on lower-level commands that remain available for integrators and CI: `rapid scan`, `rapid spec`, `rapid context`, `rapid policy show`, `rapid run create`, `rapid run task`, `rapid run gate`, `rapid evidence add`, and `rapid eval run`. Two of them write to the ledger and have limits that matter:

- **`rapid evidence add` does not satisfy test or human gates.** It records evidence produced outside Rapid OS (`harness:<id>`, `ci:<name>`, `external:<name>`). The producers `rapid:*` and the `review` evidence of producer `user` are reserved for the commands that observe them (`rapid check`, `rapid start`, `rapid finish`, `rapid attach`, `rapid approve`): `evidence add` refuses them with `RAPID1430`. A hand-written `test_result` can never satisfy `gate.tests` or `gate.baseline`: the gate stays `unverified`.
- **`rapid run gate` does not change human gates.** `rapid run gate <run> gate.final-verification acknowledged` is refused with `RAPID1431`; a human gate only moves with `rapid approve <gate>` in the person's own terminal. Acknowledging a test gate with `rapid run gate` without a check from `rapid check` leaves its assertion `unverified`.

For example, both of these are refused:

```text
rapid evidence add --run task-priority-r1-run-001 --input review_by_hand.json   # producer "user", kind "review" -> RAPID1430
rapid run gate task-priority-r1-run-001 gate.final-verification acknowledged     # human gate -> RAPID1431
```

The full list of commands is in the [CLI reference](../cli.md) and the [v3 governance loop](../governance-loop.md).

---

## 11. Troubleshooting & Common Errors

- **`RAPID1432` (test gate not verifiable):** the evidence linked to `gate.tests` or `gate.baseline` was not a test run Rapid OS can vouch for (no test summary and not `test_command`, zero tests executed, no recorded tree, or written by `rapid evidence add`). Run the command `rapid next` gives.
- **`RAPID1423` / `RAPID1434` (code not verified):** the code changed after the last test check, or that check did not record which tree it verified. Run the test check again.
- **`RAPID1433` (code changed after the approval):** run the test check again and approve again with `rapid approve <gate>`.
- **`RAPID1435` (another test command than the baseline):** repeat the check with the baseline's command; only the person can accept the difference, in their terminal, with `rapid finish --accept-test-command "REASON"`.
- **Error `RAPID1225` / `RAPID1226` (Evaluation Unverified / Fail):** a required gate is not satisfied by valid evidence, or the associated evidence has `exit_code != 0` or failed tests. `rapid next` names what is missing.

---

## 12. Assessment Criteria

- [x] Repository under git and RAPID OS initialized.
- [x] Run started from `spec.json`, with the baseline recorded by `rapid start`.
- [x] Task `T001` implemented and closed with `rapid task done`.
- [x] `gate.tests` and `gate.architecture` verified with `rapid check`.
- [x] `gate.final-verification` approved with `rapid approve` in a person's terminal.
- [x] Run finished with `rapid finish` and `pass` verdict confirmed by `rapid eval run --require-pass`.
- [x] `rapid validate` finishes with exit code 0.
- [x] No evidence written by hand: no `rapid evidence add`, no `rapid run gate`.
