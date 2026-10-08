# Rapid OS v3 Governance Loop

Rapid OS v3 governs AI-assisted software engineering through a deterministic, offline, 8-step governance loop. Every artifact is content-addressed with SHA-256 digests and free of wall-clock timestamps, random UUIDs, or host-specific absolute paths.

---

## 1. End-to-End Pipeline

```text
Repository
    ↓  rapid scan [--write]
ProjectModel (.rapid-os/project.json)
    ↓  rapid spec create / revise / status ready
SpecRecord + SpecRevision (.rapid-os/specs/<spec-id>/)
    ↓  rapid context compile --spec <spec-id>
CompiledContext + ContextManifest
    ↓  rapid policy show / init
ExecutionPolicy (.rapid-os/policy.json)
    ↓  rapid run create --spec <spec-id> --harness <harness-id>
ExecutionContract + RunRecord + RunState (.rapid-os/runs/<run-id>/)
    ↓  rapid harness resolve --run <run-id> [--locked] [--require-compatible]
CapabilityResolution (.rapid-os/harnesses/ & .rapid-os/capabilities.lock)
    ↓  External Coding Harness Execution + rapid run gate / status / task
Updated RunState Ledger (states/0001.json .. 000N.json)
    ↓  rapid evidence add --run <run-id> --input <evidence.json>
RunEvidence + Copied Artifacts (.rapid-os/evidence/<run-id>/)
    ↓  rapid eval run --run <run-id> [--write] [--require-pass]
EvaluationReport (.rapid-os/evals/<run-id>/reports/000N.json)
    ↓  rapid validate [--strict]
Cross-Phase Integrity Verification
```

---

## 2. Cross-Module Digest & Provenance Chain

Each layer binds cryptographically (via canonical SHA-256 digests) to its upstream inputs:

1. **`SpecRevision.content_digest` → `ExecutionContract.spec_content_digest`**: Ensures a Run cannot silently drift if a Spec is later revised or tampered with (`RAPID1003`).
2. **`CompiledContext.manifest.content_digest` → `ExecutionContract.context_digest`**: Locks the exact compiled Markdown and `ContextManifest` snapshot (`context.md` and `context-manifest.json`) used when the Run was created (`RAPID1004`).
3. **`ProjectModel` → `ExecutionContract.project_model_digest`**: Captures the exact repository intelligence snapshot at contract creation.
4. **`ExecutionPolicy` → `ExecutionContract.policy_digest`**: Binds the policy rules that produced the `ExecutionClass`, `RiskLevel`, `WorkspaceRequirement`, and `GateRequirement` set.
5. **`ExecutionContract.contract_digest` → `RunRecord` & `RunState`**: Every append-only state transition (`states/0001.json` .. `000N.json`) pins `contract_digest` and is re-verified sequentially from revision `1` (`RAPID1012`).
6. **`ExecutionContract.harness` → `HarnessProfile` → `CapabilityResolution`**: Evaluates whether the selected harness declares support for all capabilities derived from the contract (`RAPID1100–RAPID1112`).
7. **`RunState.content_digest` → `RunEvidence.state_digest`**: Every evidence record (`E001` .. `E00N`) pins the exact `run_id`, `contract_digest`, `state_revision`, and historical `state_digest` at which the observation occurred, along with SHA-256 digests and byte sizes of all copied files in `artifacts/E00N/` (`RAPID1202–RAPID1205`).
8. **`RunEvidence[]` → `evidence_set_digest` → `EvaluationReport`**: Every persisted `EvaluationReport` pins `contract_digest`, `state_revision`, `state_digest`, `evidence_set_digest`, `ruleset_digest`, and `extra_capability_ids`, and undergoes mandatory semantic replay via `BehavioralEvaluator` whenever loaded or validated (`RAPID1223`).

---

## 3. Declarations vs. Capabilities vs. Evidence vs. Verdicts

Rapid OS v3 enforces a strict separation between four concepts that are frequently conflated in AI tooling:

| Concept | Layer | Meaning |
| :--- | :--- | :--- |
| **`GateDisposition.ACKNOWLEDGED`** | Phase 4 (`RunState`) | A human or workflow **declared** that a gate was satisfied. Does **not** prove work was verified. |
| **`GateDisposition.WAIVED`** | Phase 4 (`RunState`) & Phase 6 (`EvaluationReport`) | An explicitly permitted policy exception with a recorded non-empty reason (forbidden at `CRITICAL` risk). |
| **`CompatibilityStatus.COMPATIBLE`** | Phase 5 (`CapabilityResolution`) | The selected `HarnessProfile` **declares** `supported` for all required capabilities. Does **not** prove the harness exercised them at runtime. |
| **`AssertionOutcome.UNVERIFIED` / `EvaluationVerdict.UNVERIFIED`** | Phase 6 (`EvaluationReport`) | A required lifecycle state, task (`DONE`), gate (`ACKNOWLEDGED`), or observable capability lacks qualifying `RunEvidence`. Causes `rapid eval run --require-pass` to fail with `RAPID1225` (exit `1`). |
| **`EvaluationVerdict.PASS`** | Phase 6 (`EvaluationReport`) | All required assertions are satisfied by verified `RunEvidence` under `BehavioralRuleset` v1. |
| **`EvaluationVerdict.PASS_WITH_WAIVERS`** | Phase 6 (`EvaluationReport`) | All non-waived required assertions pass and at least one required gate was validly `WAIVED`. Satisfies `--require-pass` (exit `0`). |
| **`EvaluationVerdict.FAIL`** | Phase 6 (`EvaluationReport`) | At least one required assertion failed (e.g., failed run lifecycle, non-zero test exit code, failed test count `> 0`, or rejected review). Causes `rapid eval run --require-pass` to fail with `RAPID1226` (exit `1`). |

---

## 4. Explicit Product Boundaries

### What Rapid OS v3 Does
- Scans repositories deterministically for languages, frameworks, package managers, databases, testing frameworks, Docker, monorepo layouts, and deploy hints with traceable `Evidence`.
- Compiles task-specific, budgeted context (`CompiledContext`) with conflict detection and provenance (`ContextManifest`).
- Manages multi-spec authoring lifecycles (`draft`, `ready`, `archived`) and immutable revisions (`0001`, `0002`, ...).
- Classifies execution risk (`low`, `medium`, `high`, `critical`) and scope (`spike`, `bounded`, `architectural`) and generates immutable `ExecutionContract` records.
- Tracks append-only `RunState` transitions (`prepared`, `active`, `blocked`, `finished`, `failed`, `cancelled`) with strict pre/post-execution gate and task phase boundaries.
- Resolves declared harness capabilities (`HarnessProfile`, `.rapid-os/capabilities.lock`) against contract-derived requirements.
- Ingests immutable `RunEvidence` records (`E001`, ...), copies supporting artifacts into `.rapid-os/evidence/<run-id>/artifacts/`, and verifies SHA-256 digests and byte sizes.
- Evaluates runs deterministically offline (`BehavioralEvaluator` → `EvaluationReport`) with mandatory semantic replay verification.

### What Rapid OS v3 Does NOT Do
- Does **not** launch or orchestrate autonomous coding agents or call LLM APIs.
- Does **not** use LLM-as-a-judge (all evaluations are 100% deterministic ruleset checks).
- Does **not** execute arbitrary shell commands or run your project's test suite during runs or evaluations.
- Does **not** automatically create or manage Git branches or worktrees for runs.
- Does **not** provide cryptographic hardware/remote attestation of external evidence producers (authenticity is local digest, size, sequence, and contract/state binding verification).
- Does **not** claim that `EvaluationVerdict.PASS` is a mathematical proof of zero software bugs or complete requirement coverage beyond the recorded evidence rules.
