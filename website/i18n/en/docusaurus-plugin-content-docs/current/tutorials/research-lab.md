---
title: Lab 5 - Research and Spike Engineering
description: Compare JSON and SQLite for storing preferences and record the findings with Rapid OS.
---

# Lab 5: Research and Spike Engineering

Run a spike: compare JSON and SQLite for storing preferences, then record what you learned. You will enter three things in your agent; in the terminal, you only prepare the example and approve the result.

## With shortcuts

### 1. Prepare the example project

```bash
cp -r ~/.rapid-os/examples/research-lab/starter storage-spike && cd storage-spike
git init -b main && git add . && git commit -m "starter"
```

In Windows PowerShell, use `Copy-Item -Recurse $HOME\.rapid-os\examples\research-lab\starter storage-spike`. If you installed Rapid OS with `pip`, the example is in [`examples/research-lab/starter`](https://github.com/alyconr/Rapid-OS/tree/main/examples/research-lab/starter).

### 2. Set up the project

Open your agent in the folder and enter `/rapid-init` (`$rapid-init` in Codex). It detects Python and suggests `python -m unittest discover` as the test command; accept it. You can skip the project documents for this lab.

### 3. Request the work

```text
/rapid-research compare JSON and SQLite for storing preferences
```

A spike does not require a baseline or tests: the agent tries both options and records each finding as run evidence (`rapid attach <path> --label "..."`).

### 4. Approve in your terminal

When the agent finishes, it stops and gives you the exact command. Run it in **another terminal**, outside the agent, for example:

```bash
rapid approve gate.final-verification
```

Return to the agent and enter `/rapid-next` to close the run.

**Result:** A comparison based on measured data is recorded in the run, which ends with a `pass` verdict.

No shortcuts yet? Install them once with `rapid shortcuts install --global --harness claude`, or run `rapid init --shortcuts` inside the folder. Replace `claude` with your agent. See the [shortcuts guide](../guides/shortcuts.md).

## Lab details

### Starting state

```text
storage-spike/
├── experiment.py
└── tests/
    ├── __init__.py
    └── test_experiment.py
```

In the starter version, `StorageExperiment` contains only a method signature, with no executable logic.

### Requirements

1. **JSON implementation:** Write and read 50 structured records using `json.dump` / `json.loads`.
2. **SQLite implementation:** Create a relational table, insert the same 50 records, and query them with `sqlite3`.
3. **Deterministic metrics:** Count verified records and measure the resulting file size in bytes.
4. **No dependencies:** Do not add external ORM packages or benchmarking frameworks.

## Advanced mode

You do not need this for the lab. The same kind of work done manually with v3 commands (spec, run, evidence, and evaluation), for CI or auditing, is covered in the [manual walkthrough](first-governed-project.md) and the [v3 governance loop](../governance-loop.md).
