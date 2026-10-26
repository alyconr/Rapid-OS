---
title: Rapid OS v3 Governance Loop
description: The deterministic, offline, eight-step governance loop used by Rapid OS v3.
---

# Rapid OS v3 Governance Loop

Rapid OS v3 governs AI-assisted software engineering through a deterministic, offline, eight-step loop. Every artifact is content-addressed with SHA-256 digests and contains no wall-clock timestamps, random UUIDs, or host-specific absolute paths.

## 1. End-to-end pipeline

```text
Repository
    ↓ rapid scan [--write]
ProjectModel (.rapid-os/project.json)
    ↓ rapid spec create / revise / status ready
SpecRecord + SpecRevision (.rapid-os/specs/<spec-id>/)
    ↓ rapid context compile --spec <spec-id>
CompiledContext + ContextManifest
    ↓ rapid policy show / init
ExecutionPolicy (.rapid-os/policy.json)
    ↓ rapid run create --spec <spec-id> --harness <harness-id>
ExecutionContract + RunRecord + RunState (.rapid-os/runs/<run-id>/)
    ↓ rapid harness resolve --run <run-id> [--locked] [--require-compatible]
CapabilityResolution (.rapid-os/harnesses/ & .rapid-os/capabilities.lock)
    ↓ External Coding Harness Execution + rapid run gate / status / task
Updated RunState Ledger (states/0001.json .. 000N.json)
    ↓ rapid evidence add --run <run-id> --input <evidence.json>
RunEvidence + Copied Artifacts (.rapid-os/evidence/<run-id>/)
    ↓ rapid eval run --run <run-id> [--write] [--require-pass]
EvaluationReport (.rapid-os/evals/<run-id>/reports/000N.json)
    ↓ rapid validate [--strict]
Cross-phase integrity verification
```

## 2. Cross-module digest and provenance chain

Each layer is cryptographically bound to upstream inputs using canonical SHA-256 digests:

1. **`SpecRevision.content_digest` → `ExecutionContract.spec_content_digest`:** Prevents a run from silently drifting if its spec is later revised or tampered with (`RAPID1003`).
2. **`CompiledContext.manifest.content_digest` → `ExecutionContract.context_digest`:** Locks the exact compiled Markdown and `ContextManifest` snapshot (`context.md` and `context-manifest.json`) used to create the run (`RAPID1004`).
3. **`ProjectModel` → `ExecutionContract.project_model_digest`:** Captures the exact repository intelligence snapshot when the contract is created.
4. **`ExecutionPolicy` → `ExecutionContract.policy_digest`:** Binds the policy rules that produced the `ExecutionClass`, `RiskLevel`, `WorkspaceRequirement`, and `GateRequirement` set.
5. **`ExecutionContract.contract_digest` → `RunRecord` and `RunState`:** Every append-only state transition pins `contract_digest` and is re-verified sequentially from revision 1 (`RAPID1012`).
6. **`ExecutionContract.harness` → `HarnessProfile` → `CapabilityResolution`:** Checks whether the selected harness declares support for every capability derived from the contract (`RAPID1100–RAPID1112`).
7. **`RunState.content_digest` → `RunEvidence.state_digest`:** Each evidence record (`E001`...) pins the run ID, contract digest, state revision, and historical state digest for the observation, along with SHA-256 digests and byte sizes of copied files (`RAPID1202–RAPID1205`).
8. **`RunEvidence[]` → `evidence_set_digest` → `EvaluationReport`:** Every saved report pins the contract, state, evidence set, ruleset digest, and extra capability IDs. It must pass semantic replay through `BehavioralEvaluator` whenever loaded or validated (`RAPID1223`).

**Machine gate `gate.architecture`:** In `feature`, `bugfix`, and `refactor` runs, if `.rapid-os/standards/architecture.json` exists, the contract includes required, non-waivable `gate.architecture`. `rapid next` proposes `rapid check --gate gate.architecture -- rapid arch check`. A violation returns `RAPID1420`, and `rapid finish` will not return `PASS` until resolved. See [Architecture by Stack](./concepts/architecture.md).

## 3. Declarations, capabilities, evidence, and verdicts

Rapid OS v3 keeps separate four concepts often conflated in AI tools:

| Concept | Layer | Meaning |
|---|---|---|
| `GateDisposition.ACKNOWLEDGED` | Phase 4 (`RunState`) | A person or workflow **declared** a gate satisfied. This does **not** prove the work was verified. |
| `GateDisposition.WAIVED` | Phase 4 and Phase 6 | A policy-permitted exception with a recorded non-empty reason (forbidden at `CRITICAL` risk). |
| `CompatibilityStatus.COMPATIBLE` | Phase 5 | The selected profile **declares** support for all required capabilities. This does **not** prove the harness used them. |
| `AssertionOutcome.UNVERIFIED` / `EvaluationVerdict.UNVERIFIED` | Phase 6 | Required lifecycle state, completed task, acknowledged gate, or observable capability lacks qualifying evidence. `rapid eval run --require-pass` returns `RAPID1225` (exit 1). |
| `EvaluationVerdict.PASS` | Phase 6 | All required assertions are satisfied by verified evidence under `BehavioralRuleset` v1. |
| `EvaluationVerdict.PASS_WITH_WAIVERS` | Phase 6 | All non-waived assertions pass and at least one required gate was validly waived. Satisfies `--require-pass` (exit 0). |
| `EvaluationVerdict.FAIL` | Phase 6 | A required assertion failed (for example, failed lifecycle, nonzero test exit, failed tests, or rejected review). `--require-pass` returns `RAPID1226` (exit 1). |

## 4. Product boundaries

### What Rapid OS v3 does

- Deterministically scans repositories for languages, frameworks, package managers, databases, test frameworks, Docker, monorepo layouts, and deployment hints, with traceable evidence.
- Compiles task-specific, budgeted context with conflict detection and provenance.
- Manages multi-spec lifecycles (`draft`, `ready`, `archived`) and immutable revisions.
- Classifies risk and scope (`spike`, `bounded`, `architectural`) and generates immutable contracts.
- Tracks append-only run state with strict pre- and post-execution task and gate boundaries.
- Resolves declared harness capabilities against contract requirements.
- Ingests immutable run evidence, copies supporting artifacts, and checks SHA-256 digests and byte sizes.
- Evaluates runs deterministically and offline, with mandatory semantic replay verification.

### What Rapid OS v3 does not do

- Launch or orchestrate autonomous coding agents or call LLM APIs.
- Use an LLM as a judge; all evaluations use deterministic rules.
- Execute repository code through plumbing commands (`spec`, `run`, `evidence`, `eval`, and others). Porcelain runs only the configured `test_command` or argv passed to `rapid check`, plus read-only Git commands to record run changes.
- Create Git branches or worktrees except through `rapid start --worktree`; it never invokes agents or approves human gates.
- Provide hardware or remote cryptographic attestation for external evidence producers.
- Claim that `PASS` proves the software has no bugs or covers requirements beyond the recorded evidence rules.

## 5. Porcelain verbs and plumbing commands

Porcelain verbs drive the loop (see [Orchestration Architecture](./architecture/orchestration.md) and the [shortcuts guide](./guides/shortcuts.md)). Plumbing commands remain available for CI, debugging, and auditing (**advanced mode**).

| Porcelain verb | Plumbing commands it replaces |
|---|---|
| `rapid start <mode> --spec-file -` | `rapid spec create`, set spec ready, `rapid run create`, then baseline tests, evidence, gate acknowledgment, and activation. |
| `rapid next` | Manually inspect run and evaluation status to decide what is missing. |
| `rapid check -- <command>` | Run a command, save its log, and add `test_result` or `command_result` evidence (producer `rapid:check`). |
| `rapid task start\|done\|skip` | `rapid run task <run-id> <task-id> in_progress\|done\|skipped` (`done` also runs checks). |
| `rapid attach <path> --label <text>` | Add `artifact` evidence (producer `rapid:attach`). |
| `rapid finish` | Add file-change evidence, acknowledge machine gates satisfied by evidence, finish the run, and evaluate it. |
| `rapid approve <gate>` | Add review evidence (producer `user`) and acknowledge or waive the gate; only a person can run this. |
| `rapid status` | `rapid run show` / `rapid run status` and `rapid eval list`. |
| `rapid abort` | Set run status to `cancelled`. |
| `rapid shortcuts` / `rapid hook` | No plumbing command; these generate and enforce agent-side shortcut and Claude Code hook files. |
