# Manual Walkthrough: The Governance Loop by Hand (Under the Hood)

> **Advanced mode.** You do not need this lab to use Rapid OS: it does by hand, with the v3 commands (`rapid scan`, `rapid spec`, `rapid run`, `rapid evidence`, `rapid eval`…), what the agent does for you with the shortcuts. It is meant for integrators, CI, and auditing. If you are just starting out, go to the [labs](index.md), beginning with [Feature](feature-lab.md) (`/rapid-feature`).

Learn how to run the complete RAPID OS v3 Governance Loop on a real Python project with an external assistant or coding harness.

---

## 1. Overview

- **Name:** Task Tracker CLI Governance.
- **Problem:** A Python project without governance risks unvalidated changes introduced by AI assistants. A new task-priority feature must be implemented under a verifiable contract.
- **Goal:** Walk through the entire governance cycle, from `rapid init` to evidence evaluation and final integrity validation.
- **Difficulty level:** Advanced.
- **Prerequisites:** Basic use of the terminal and Python commands.
- **Dependencies:** Python 3.10+ (standard library only).
- **Reference files:** [`examples/first-governed-project/`](https://github.com/alyconr/Rapid-OS/tree/main/examples/first-governed-project).

---

## 2. Learning Outcomes

By completing this lab, you will know how to:
1. Initialize RAPID OS in an existing repository.
2. Scan project facts with `rapid scan --write`.
3. Create a declarative specification (`rapid spec create`).
4. Compile a reproducible Context Bundle (`rapid context --manifest`).
5. Inspect and resolve the execution policy (`rapid policy show`).
6. Generate an immutable `ExecutionContract` and an initial `RunState` (`rapid run create`).
7. Resolve the capability profile of your coding harness (`rapid harness show`).
8. Run the implementation externally with your preferred tool or harness.
9. Update tasks and gates in the versioned state (`rapid run task` and `rapid run gate`).
10. Record deterministic evidence tied to state revisions (`rapid evidence add`).
11. Evaluate the Run's compliance (`rapid eval run`).
12. Validate the holistic integrity of the project (`rapid validate`).

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

### Step 1: Initialize RAPID OS

At the project root, initialize Rapid OS without prompts (`--yes`) with a Python stack and register the test command:

```bash
rapid init --stack python-ai --yes
rapid setup set test-command "python -m unittest discover -s tests -t ."
```

This creates the `.rapid-os/` structure with its standards and base configuration. Everything else (topology, archetype) takes the stack's default values.

### Step 2: Scan the project

```bash
rapid scan --write
```

The scanner detects the language (Python) and the test directories (`tests/`), persisting the Project Model.

### Step 3: Create the Specification

Create the specification with its implementation task (`--task`). The id is derived from the title (`task-priority`) and the default mode is `feature`. Then mark it as ready:

```bash
rapid spec create --title "Task priority" --task "T001: Implementar soporte de prioridades en TaskTracker"
rapid spec status task-priority ready
```

### Step 4: Compile the Context Bundle

Generate the deterministic context bundle to feed the coding harness:

```bash
rapid context --manifest
```

### Step 5: Inspect the Execution Policy

```bash
rapid policy show
```

For a specification in `feature` mode, the policy engine resolves the `bounded` classification (the canonical classes are `spike`, `bounded`, and `architectural`) with a `medium` risk level. This policy requires the following mandatory gates:
- `gate.baseline` (phase `pre_execution`): prior verification of the repository's test health before starting changes.
- `gate.tests` (phase `post_execution`): verification with a passing test suite and an attached log artifact.
- `gate.architecture` (phase `post_execution`): this project was initialized with a backend stack (`python-ai`), so it starts as a modular monolith and its contract verifies the rule with `rapid arch check`.
- `gate.final-verification` (phase `post_execution`): final formal review of contract compliance with an approved verdict.

### Step 6: Create the Execution Run

```bash
rapid run create --spec task-priority --harness codex
```

This generates a deterministic run identifier (for example `task-priority-r1-run-001`), computes the SHA-256 digest of the contract, and writes the initial `RunState s1` snapshot in `prepared` state.

### Step 7: Resolve the Harness Capabilities

```bash
rapid harness show codex
```

Note that RAPID OS reports the supported capabilities (`context.consume`, `repository.read`, `workspace.current`) and those that depend on your local environment (`tests.execute`, `repository.write`).

---

## 6. External Execution

> **Responsibility boundary note:** RAPID OS does **not** edit the code. The implementation is carried out by the developer or their external coding harness (Claude Code, Cursor, Codex, Antigravity, etc.).

### Step 1: Run and Capture the Baseline

Before modifying the code and activating the run, run the existing test suite and capture the authentic output in an artifact file `base.log`:

```bash
python -m unittest discover -s tests -t . > base.log 2>&1
```

### Step 2: External Implementation of Code and Tests

Externally modify `app.py` and `tests/test_app.py` to meet the requirements:

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

Run the updated suite, capturing the output log in `tests.log`:

```bash
python -m unittest discover -s tests -t . > tests.log 2>&1
```

---

## 7. Evidence Collection

Update the Run's state by ingesting the evidence required by the `BehavioralEvaluator`:

### 1. Record Baseline Evidence and Acknowledge `gate.baseline`

The evaluator requires `gate.baseline` to have test or command evidence with `exit_code: 0`, zero failures, and at least one physical artifact (`base.log`). In addition, `pre_execution` phase gates must be acknowledged before the run is activated.

Prepare `evidence_baseline.json`:

```json
{
  "kind": "test_result",
  "producer": "harness:codex",
  "summary": "Verificación exitosa de baseline previo a modificaciones",
  "task_ids": ["T001"],
  "gate_ids": ["gate.baseline"],
  "capability_ids": ["tests.execute"],
  "payload": {
    "suite": "tests/test_app.py",
    "exit_code": 0,
    "passed": 2,
    "failed": 0,
    "skipped": 0
  },
  "artifacts": ["base.log"]
}
```

Ingest the evidence and acknowledge the gate:

```bash
rapid evidence add --run task-priority-r1-run-001 --input evidence_baseline.json
rapid run gate task-priority-r1-run-001 gate.baseline acknowledged
```

### 2. Activate the Run and start the task

Once the pre-execution gate is satisfied, move the run to the `active` state and mark the task as in progress:

```bash
rapid run status task-priority-r1-run-001 active
rapid run task task-priority-r1-run-001 T001 in_progress
```

### 3. Record Code Change Evidence (`file_change`)

The evaluator requires the `repository.write` capability to be demonstrated through `file_change` evidence tied to the tasks in the contract's scope.

Prepare `evidence_file_change.json`:

```json
{
  "kind": "file_change",
  "producer": "harness:codex",
  "summary": "Implementación de prioridad en app.py y tests",
  "task_ids": ["T001"],
  "gate_ids": [],
  "capability_ids": ["repository.write"],
  "payload": {
    "paths": ["app.py", "tests/test_app.py"]
  }
}
```

Ingest it into RAPID OS:

```bash
rapid evidence add --run task-priority-r1-run-001 --input evidence_file_change.json
```

### 4. Record Passing Test Evidence (`test_result`)

The evaluator requires `gate.tests` to contain `test_result` evidence with `exit_code: 0`, `failed: 0`, and at least one registered log artifact (`tests.log`).

Prepare `evidence_test_result.json`:

```json
{
  "kind": "test_result",
  "producer": "harness:codex",
  "summary": "Ejecución exitosa de suite de pruebas unitarias",
  "task_ids": ["T001"],
  "gate_ids": ["gate.tests"],
  "capability_ids": ["tests.execute"],
  "payload": {
    "suite": "tests/test_app.py",
    "exit_code": 0,
    "passed": 4,
    "failed": 0,
    "skipped": 0
  },
  "artifacts": ["tests.log"]
}
```

Ingest it:

```bash
rapid evidence add --run task-priority-r1-run-001 --input evidence_test_result.json
```

### 4 bis. Record Architecture Evidence (`command_result`)

The evaluator requires `gate.architecture` to contain `command_result` evidence with `exit_code: 0` and a log artifact (`arch.log`). The checker only judges code inside `app/modules/` (the rule's modules folder): this project has no modules yet, so there is nothing to violate.

Capture the checker's output:

```bash
rapid arch check > arch.log 2>&1
```

Prepare `evidence_architecture.json`:

```json
{
  "kind": "command_result",
  "producer": "harness:codex",
  "summary": "rapid arch check sin violaciones",
  "task_ids": ["T001"],
  "gate_ids": ["gate.architecture"],
  "capability_ids": ["shell.execute"],
  "payload": {
    "label": "rapid arch check",
    "exit_code": 0
  },
  "artifacts": ["arch.log"]
}
```

Ingest it:

```bash
rapid evidence add --run task-priority-r1-run-001 --input evidence_architecture.json
```

### 5. Record Workspace Evidence (`workspace`)

The evaluator requires validating the derived `workspace.current` capability through `workspace` evidence with payload `mode: "current"`.

Prepare `evidence_workspace.json`:

```json
{
  "kind": "workspace",
  "producer": "harness:codex",
  "summary": "Verificación de espacio de trabajo actual",
  "task_ids": ["T001"],
  "gate_ids": [],
  "capability_ids": ["workspace.current"],
  "payload": {
    "mode": "current"
  }
}
```

Ingest it:

```bash
rapid evidence add --run task-priority-r1-run-001 --input evidence_workspace.json
```

### 6. Record Final Review Evidence (`review`)

The evaluator requires the contractual gate `gate.final-verification` to have `review` evidence with `review_type: "final"` and `outcome: "approved"`.

Prepare `evidence_review.json`:

```json
{
  "kind": "review",
  "producer": "user",
  "summary": "Revisión final contractual de cumplimiento",
  "task_ids": ["T001"],
  "gate_ids": ["gate.final-verification"],
  "payload": {
    "review_type": "final",
    "outcome": "approved",
    "reviewer": "quality-lead"
  }
}
```

Ingest it:

```bash
rapid evidence add --run task-priority-r1-run-001 --input evidence_review.json
```

### 7. Mark the Task Done, Acknowledge Gates, and Finish the Run

With all the evidence recorded and verifiable, complete the task, acknowledge the post-execution gates, and transition the run to `finished`:

```bash
rapid run task task-priority-r1-run-001 T001 done
rapid run gate task-priority-r1-run-001 gate.tests acknowledged
rapid run gate task-priority-r1-run-001 gate.architecture acknowledged
rapid run gate task-priority-r1-run-001 gate.final-verification acknowledged
rapid run status task-priority-r1-run-001 finished
```

---

## 8. Evaluation

Run the deterministic behavioral evaluator: first save the report (`--write`) and then require the successful verdict (`--require-pass`, which exits with an error if the verdict is not `pass`):

```bash
rapid eval run --run task-priority-r1-run-001 --write
rapid eval run --run task-priority-r1-run-001 --require-pass
```

The evaluator inspects the state transitions, verifies that the required gates (`gate.baseline`, `gate.tests`, `gate.architecture`, `gate.final-verification`) and the observed capabilities are satisfied by the linked evidence, and emits the verdict:

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

## 10. Troubleshooting & Common Errors

- **Error `RAPID1203` (Evidence Binding Mismatch):** The run state advanced before the evidence was recorded. The `rapid evidence add` command automatically resolves the current state revision if you omit or synchronize `state_revision`.
- **Error `RAPID1225` / `RAPID1226` (Evaluation Unverified / Fail):** A required gate was not acknowledged, does not contain valid evidence, or the associated evidence contains an `exit_code != 0`. Remember that `gate.baseline` must be acknowledged before the run is activated.

---

## 11. Assessment Criteria

- [x] Repository initialized and scanned.
- [x] Spec in `ready` state and Context compiled.
- [x] Run created and linked to the `codex` harness.
- [x] Baseline evidence captured and `gate.baseline` acknowledged before `active`.
- [x] Code and tests implemented externally with log artifacts.
- [x] `file_change`, `test_result`, `workspace`, and `review` evidence recorded.
- [x] Gates `gate.tests`, `gate.architecture`, and `gate.final-verification` acknowledged.
- [x] `pass` verdict emitted by `rapid eval run --require-pass`.
- [x] `rapid validate` finishes with exit code 0.
