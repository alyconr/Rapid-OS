---
title: "Manual Walkthrough: The Governance Loop"
description: Run the complete Rapid OS governance loop manually on a Python project.
---

# Manual Walkthrough: The Governance Loop

> **Advanced mode.** This lab performs manually what shortcuts guide an agent to do. It is intended for integrators, CI, and audits. If you are new, start with the [labs index](index.md) and [Feature Lab](feature-lab.md).

Learn to run the full Rapid OS v3 Governance Loop on a Python project with an external assistant or coding harness.

## Overview

The sample Task Tracker CLI adds task priorities under a verifiable contract. Requirements: Python 3.10+, standard library only, basic terminal use. Reference project: [`examples/first-governed-project/`](https://github.com/alyconr/Rapid-OS/tree/main/examples/first-governed-project).

By the end, you will initialize and scan a repository, create a spec, compile context, inspect policy, create a run, resolve harness capabilities, implement externally, record state and evidence, evaluate the run, and validate integrity.

## Starting project

The starter contains `app.py`, `tests/__init__.py`, and `tests/test_app.py`. `TaskTracker.add_task(title)` stores pending tasks and rejects empty titles. The change will add `low`, `medium`, and `high` priorities (default `medium`), reject unknown priorities, support `list_tasks(priority=None)`, and preserve existing tests.

## Prepare the governed run

Initialize Rapid OS and configure the test command:

```bash
rapid init --stack python-ai --yes
rapid setup set test-command "python -m unittest discover -s tests -t ."
rapid scan --write
rapid spec create --title "Task priority" --task "T001: Add priority support to TaskTracker"
rapid spec status task-priority ready
rapid context --manifest
rapid policy show
rapid run create --spec task-priority --harness codex
rapid harness show codex
```

The run gets a deterministic ID such as `task-priority-r1-run-001`, a SHA-256 contract digest, and an initial `prepared` state. The policy requires baseline, tests, architecture (for this configured backend stack), and final verification gates. Capabilities describe harness declarations, not proof that actions occurred.

## Execute outside Rapid OS

Rapid OS does not edit code or run the harness for you. The developer or external coding harness makes the changes, runs tests, and captures logs.

Capture the baseline before implementation:

```bash
python -m unittest discover -s tests -t . > base.log 2>&1
```

Update `TaskTracker.add_task` to normalize and validate priority, include it in each task, and allow filtering in `list_tasks`. Add tests for the default, custom priorities, invalid priorities, and empty task titles. Capture the post-change run:

```bash
python -m unittest discover -s tests -t . > tests.log 2>&1
rapid arch check > arch.log 2>&1
```

## Record evidence and progress

Prepare authoring JSON files for baseline, file changes, passing tests, architecture check, workspace, and final review. Evidence input JSON uses `kind`, `producer`, `summary`, `payload`, and optional task/gate/capability IDs and artifacts. For test evidence, include suite, exit code, counts, and the corresponding log artifact; for file changes, include changed paths; for architecture, record the successful `rapid arch check` log. The final human review uses producer `user` and `review_type: "final"`.

Ingest each file with `rapid evidence add --run <run-id> --input <file>`. Acknowledge baseline before activation, then update task and run state. After implementation, mark the task done and acknowledge the required post-execution gates. Human approval must be performed by a person.

## Evaluate and validate

```bash
rapid eval run --run task-priority-r1-run-001 --write
rapid eval run --run task-priority-r1-run-001 --require-pass
rapid validate
```

The evaluator checks state transitions, required gates, observed capabilities, and linked evidence. `PASS` means the recorded requirements are satisfied; it is not a proof that software has no defects.

## Troubleshooting and assessment

`RAPID1203` indicates an evidence binding mismatch; add evidence against the current run state. `RAPID1225` or `RAPID1226` means a gate is unacknowledged, lacks valid evidence, or has a failing result. Baseline must be acknowledged before activation.

Completion criteria: initialized and scanned repository, ready spec and compiled context, run linked to the harness, baseline captured before activation, externally implemented code and tests with logs, required evidence and gates recorded, passing evaluation, and successful `rapid validate`.
