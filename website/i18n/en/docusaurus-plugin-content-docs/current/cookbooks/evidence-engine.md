---
title: Evidence Ingestion and Verification
description: EvidenceKind formats, JSON authoring documents, and integrity verification in Rapid OS.
---

# Evidence Ingestion and Verification

The Rapid OS Evidence Engine records claims about work (tests, reviews, changed files, commands) in immutable, sequential records bound to the run contract and state.

## CLI

```bash
rapid evidence add --run <run-id> --input <path-to-json> [--json]
rapid evidence list --run <run-id> [--json]
rapid evidence show --run <run-id> <evidence-id> [--json]
rapid evidence verify --run <run-id> [--json]
```

`rapid evidence add` does not accept direct `--kind`, `--producer`, or `--summary` flags. Put metadata, task/gate references, and type-specific payload in the JSON authoring file.

## Authoring document

```json
{
  "kind": "test_result",
  "producer": "pytest",
  "summary": "Unit test suite passed",
  "payload": {"suite": "unit-tests", "exit_code": 0, "passed": 42, "failed": 0, "skipped": 1},
  "task_ids": ["T1"],
  "gate_ids": ["gate.tests"],
  "capability_ids": ["tests.execute"],
  "artifacts": ["reports/summary.txt"]
}
```

`kind`, `producer`, `summary`, and `payload` are required. Payload keys are strict for each kind; unknown keys are rejected (`RAPID1206`). Optional task and gate IDs must exist in the contract; capabilities must be canonical. Artifact paths are existing relative POSIX paths, required for `artifact` evidence. The CLI assigns evidence IDs and run bindings; do not author `id`, `schema_version`, or `run_id`.

## Evidence kinds

The nine canonical kinds are `test_result`, `command_result`, `file_change`, `artifact`, `review`, `workspace`, `delegation`, `risk_assessment`, and `decision`. Their payloads must contain exactly the fields defined by the corresponding schema. For example, test results include suite, exit code, passed, failed, and skipped counts; command results include label and exit code; file changes include paths; workspace evidence records the workspace mode; reviews include review type, outcome, and reviewer. Use the project cookbook examples as authoring templates and keep logs or other supporting files in `artifacts` when required by the gate.

## Verify integrity

After ingestion, inspect the records and verify their sequence, bindings, and artifact hashes:

```bash
rapid evidence list --run my-run-001
rapid evidence verify --run my-run-001
```

Evidence must be genuine and correspond to the current run state. Acknowledging a gate without evidence leaves it unverified; harness-produced evidence cannot satisfy human review gates under ruleset v2.
