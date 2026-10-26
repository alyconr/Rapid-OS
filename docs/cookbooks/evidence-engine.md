---
title: Evidence Ingestion and Verification
description: Cookbook of evidence formats (EvidenceKind), JSON authoring documents, and integrity verification in RAPID OS.
---

# Evidence Ingestion and Verification

The RAPID OS **Evidence Engine** guarantees that any claim about how the work was executed (tests run, reviews approved, files edited, commands executed) is backed by immutable, sequential records that are mathematically bound to the contract and active state of the run.

---

## CLI Interface Contract

Evidence is recorded in RAPID OS with the `rapid evidence add` subcommand:

```bash
rapid evidence add --run <run-id> --input <path-to-json-file> [--json]
```

> **Product Truth**: `rapid evidence add` does **not** accept direct flags such as `--kind`, `--producer`, or `--summary`. The authoring metadata, the task/gate references, and the payload specific to each evidence type are declared **inside the input JSON document** passed to `--input`.

Complementary Evidence Engine commands:
```bash
# List records E001..E00N and the run's consolidated digest
rapid evidence list --run <run-id> [--json]

# Inspect the detail and bindings of a specific piece of evidence
rapid evidence show --run <run-id> <evidence-id> [--json]

# Verify the ordinal sequence, artifact integrity, and hashes
rapid evidence verify --run <run-id> [--json]
```

---

## Authoring JSON Document Structure (`Authoring JSON`)

The JSON file passed through `--input` must have the following canonical structure:

```jsonc
{
  "kind": "<EvidenceKind>",
  "producer": "<producer-identifier>",
  "summary": "<descriptive-summary-of-the-record>",
  "payload": {
    /* Strictly required fields according to the kind */
  },
  "task_ids": ["T1"],
  "gate_ids": ["gate.tests"],
  "capability_ids": ["tests.execute"],
  "artifacts": ["reports/summary.txt"]
}
```

### Authoring document fields:

| Field | Required | Description | Constraints |
| :--- | :--- | :--- | :--- |
| `kind` | **Yes** | Canonical evidence type | One of the 9 values of [`EvidenceKind`](#the-9-evidence-types-evidencekind). |
| `producer` | **Yes** | Identifier of the system or tool that produced the evidence | Portable alphanumeric. If it includes a colon prefix (`:`), it must match the contract's harness (e.g. `harness:codex`) or an allowed format. |
| `summary` | **Yes** | Concise summary of the evidence | Non-empty portable text. |
| `payload` | **Yes** | Dictionary of type-specific data | Must contain **only and strictly** the fields required by the type. Unexpected fields cause immediate rejection (`RAPID1206`). |
| `task_ids` | No | List of linked task identifiers | Must exist in the run's `ExecutionContract`. |
| `gate_ids` | No | List of linked quality gates | Must match the canonical catalog IDs present in the contract (`gate.tests`, `gate.baseline`, `gate.review`, etc.). |
| `capability_ids` | No | Accredited harness capabilities | Must belong to the canonical capability catalog. |
| `artifacts` | No | Source files to copy and verify with SHA-256 | Existing POSIX relative paths. Required if `kind == "artifact"`. |

---

## The 9 Evidence Types (`EvidenceKind`)

Below are the complete, valid JSON documents for each of the 9 supported types, ready to use with `rapid evidence add --run <run-id> --input <file>`.

### 1. `test_result` (Automated Test Results)
Records the quantitative result of a test suite.

**Required `payload` fields**: `suite`, `exit_code`, `passed`, `failed`, `skipped`.

**File `test-evidence.json`**:
```json
{
  "kind": "test_result",
  "producer": "pytest",
  "summary": "Unit test suite 100% passing",
  "gate_ids": ["gate.tests"],
  "capability_ids": ["tests.execute"],
  "payload": {
    "suite": "unit-tests",
    "exit_code": 0,
    "passed": 42,
    "failed": 0,
    "skipped": 1
  }
}
```

**Execution**:
```bash
rapid evidence add --run feature-auth-r1-run-001 --input test-evidence.json
```

---

### 2. `command_result` (Command or Tool Result)
Records the output and return code of terminal commands, linters, or system tools.

**Required `payload` fields**: `label`, `exit_code`.

**File `command-evidence.json`**:
```json
{
  "kind": "command_result",
  "producer": "ruff",
  "summary": "Static code check with Ruff",
  "capability_ids": ["shell.execute"],
  "payload": {
    "label": "ruff check .",
    "exit_code": 0
  }
}
```

**Execution**:
```bash
rapid evidence add --run feature-auth-r1-run-001 --input command-evidence.json
```

---

### 3. `file_change` (Repository File Changes)
Records the relative paths of the files touched during implementation.

**Required `payload` fields**: `paths` (non-empty list of POSIX relative paths).

**What counts when `rapid finish` records it** (`producer: rapid:finish`): the tracked files that changed since the `HEAD` at the start of the run (`git diff --name-only`) plus the new untracked files that did not exist at the start, excluding `.rapid-os/` and **excluding the artifacts that tools generate**: any path with an exact segment `__pycache__`, `.pytest_cache`, `.mypy_cache`, `.ruff_cache`, `.tox`, `.nox`, `node_modules`, `.venv`, or `venv`, and the files `*.pyc`, `*.pyo`, `.coverage`, and `.coverage.*`. Whole segments are compared (`my__pycache__notes.md` does count) and they are ignored even if the project has no `.gitignore`. If no change remains after filtering, `rapid finish` does not record `file_change` and the `repository.write` capability is left without evidence: the verdict is not `pass`. Running the tests leaving `__pycache__` behind does not mean having written to the project.

**File `file-change-evidence.json`**:
```json
{
  "kind": "file_change",
  "producer": "git-inspector",
  "summary": "Files implemented in the authentication service",
  "capability_ids": ["repository.write"],
  "payload": {
    "paths": [
      "src/auth/service.py",
      "tests/unit/test_auth.py"
    ]
  }
}
```

**Execution**:
```bash
rapid evidence add --run feature-auth-r1-run-001 --input file-change-evidence.json
```

---

### 4. `git_result` (Git Repository Operations)
Records version control operations.

**Required `payload` fields**: `operation` (strictly `"inspect"` or `"modify"`).

**File `git-evidence.json`**:
```json
{
  "kind": "git_result",
  "producer": "git-cli",
  "summary": "Status inspection and clean working tree diff",
  "capability_ids": ["git.inspect"],
  "payload": {
    "operation": "inspect"
  }
}
```

**Execution**:
```bash
rapid evidence add --run feature-auth-r1-run-001 --input git-evidence.json
```

---

### 5. `workspace` (Workspace Mode and Isolation)
Accredits compliance with the workspace requirement or the `gate.workspace-isolation` gate.

**Required `payload` fields**: `mode` (strictly `"current"` or `"isolated"`).

> **Governance Rule**: To formally satisfy the `gate.workspace-isolation` governance gate (`rule.gate.workspace_isolation.v1`), the evaluator strictly requires `workspace` evidence with `mode: "isolated"` and the `workspace.isolated` capability. Evidence with `mode: "current"` accredits execution in the current working environment, but it does not demonstrate the isolation required by runs with elevated classification or risk.

**File `workspace-evidence.json`**:
```json
{
  "kind": "workspace",
  "producer": "workspace-manager",
  "summary": "Execution environment verified on an isolated working branch",
  "gate_ids": ["gate.workspace-isolation"],
  "capability_ids": ["workspace.isolated"],
  "payload": {
    "mode": "isolated"
  }
}
```

**Execution**:
```bash
rapid evidence add --run feature-auth-r1-run-001 --input workspace-evidence.json
```

---

### 6. `review` (Formal Peer or Security Reviews)
Records the formal approval of gates such as `gate.review`, `gate.security-review`, or `gate.manual-approval`.

**Required `payload` fields**:
- `review_type`: strictly `"peer"`, `"security"`, `"migration"`, `"manual"`, or `"final"`.
- `outcome`: strictly `"approved"`, `"changes_requested"`, or `"rejected"`.
- `reviewer`: portable reviewer identifier (no slashes `/`).

**File `review-evidence.json`**:
```json
{
  "kind": "review",
  "producer": "github-pr",
  "summary": "Technical approval from peer review",
  "gate_ids": ["gate.review"],
  "payload": {
    "review_type": "peer",
    "outcome": "approved",
    "reviewer": "lead-architect"
  }
}
```

**Execution**:
```bash
rapid evidence add --run feature-auth-r1-run-001 --input review-evidence.json
```

---

### 7. `tool_invocation` (Tool or Analyzer Invocation)
Records the execution of type checkers, linters, or development tools.

**Required `payload` fields**:
- `tool_id`: tool identifier (no slashes `/`).
- `outcome`: strictly `"success"` or `"failure"`.

**File `tool-evidence.json`**:
```json
{
  "kind": "tool_invocation",
  "producer": "typecheck-runner",
  "summary": "Static type analysis executed successfully",
  "payload": {
    "tool_id": "mypy",
    "outcome": "success"
  }
}
```

**Execution**:
```bash
rapid evidence add --run feature-auth-r1-run-001 --input tool-evidence.json
```

---

### 8. `delegation` (Delegation of Subtasks or External Services)
Records the handoff or delegation to a service or subagent.

**Required `payload` fields**:
- `target`: identifier of the delegate (no slashes `/`).
- `outcome`: strictly `"success"` or `"failure"`.

**File `delegation-evidence.json`**:
```json
{
  "kind": "delegation",
  "producer": "orchestrator",
  "summary": "Delegation of asset compilation to the frontend pipeline",
  "capability_ids": ["subagents.delegate"],
  "payload": {
    "target": "frontend-build-worker",
    "outcome": "success"
  }
}
```

**Execution**:
```bash
rapid evidence add --run feature-auth-r1-run-001 --input delegation-evidence.json
```

---

### 9. `artifact` (Hash-Verified Attachments)
Lets you attach project files (coverage reports, logs, binaries) that are physically copied to `.rapid-os/evidence/<run-id>/artifacts/<evidence-id>/` and protected by a SHA-256 digest.

**Required `payload` fields**: `label`.  
**Additional field required in the authoring document**: `artifacts` (list of relative paths to existing files).

**File `artifact-evidence.json`**:
```json
{
  "kind": "artifact",
  "producer": "coverage-agent",
  "summary": "Consolidated code coverage report",
  "artifacts": [
    "reports/coverage.json"
  ],
  "payload": {
    "label": "coverage-report"
  }
}
```

**Execution**:
```bash
rapid evidence add --run feature-auth-r1-run-001 --input artifact-evidence.json
```

---

## Artifact Management and Behavior (`Artifacts`)

When an authoring document includes the `"artifacts"` array:
1. **Safe Copy**: RAPID OS reads the source file (e.g. `reports/coverage.json`), verifies that it is not a symbolic link, and copies it to `.rapid-os/evidence/<run-id>/artifacts/<evidence-id>/reports/coverage.json`.
2. **Digest and Size Calculation**: It deterministically computes the SHA-256 hash and the size in bytes (`size_bytes`), recording them in the `RunEvidence` record.
3. **Immutable Integrity**: If the file copied into `.rapid-os/evidence/` is later altered or deleted, `rapid evidence verify` detects the tampering and emits the diagnostic `RAPID1205` (`EvidenceArtifactIntegrityError`).

> **Product Truth about Authenticity**: The SHA-256 hash calculation verifies the **local physical integrity** of the copied file against the immutable record. It is not an external cryptographic attestation and does not guarantee the truthfulness or reliability of the producer that generated the content.

---

## Integrity Verification (`rapid evidence verify`)

To check the continuity of the sequence and the mathematical consistency of all the evidence in a run:

```bash
rapid evidence verify --run feature-auth-r1-run-001
```

This command verifies:
- **Continuous sequence**: There are no gaps in the numbering (`E001`, `E002`, `E003` with no omissions).
- **State and Contract Binding**: The `contract_digest` and `state_digest` digests of each piece of evidence match exactly the run's contract and active state.
- **Artifact Integrity**: Each file in the artifacts folder matches, byte for byte and by SHA-256 hash, its declaration in the JSON record.
- **Set Hash (`evidence_set_digest`)**: Computes the global canonical digest of the ordered set of evidence, which is an input to the behavioral evaluation with `rapid eval run`.
