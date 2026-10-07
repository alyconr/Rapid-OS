# Rapid OS CLI Reference

Rapid OS provides a deterministic, standard-library-only command-line interface (`rapid` or `python rapid.py`) for project intelligence, task-aware context compilation, spec authoring, execution policy & runs, harness capability resolution, immutable run evidence ingestion, and deterministic behavioral evaluations.

## Global Options

- `--root <path>`: Target project root directory (defaults to current working directory).
- `--version`: Print the Rapid OS version and exit.
- `-h`, `--help`: Show command help and exit.

---

## Core Project & Legacy Workflow Commands

### `rapid init`
Initialize `.rapid-os/` standards, configuration, and AI harness rule files (`CLAUDE.md`, `AGENTS.md`, `.cursor/rules/`, `.github/copilot-instructions.md`).

```bash
rapid init
rapid init --stack python-ai --topology fullstack-separated --design minimal-saas --security high-compliance --ide cursor,claude,codex --no-interactive
```

### `rapid update`
Regenerate AI harness rule files from `.rapid-os/config.json` and `.rapid-os/standards/`.

```bash
rapid update
rapid update --ide cursor,claude --dry-run
```

### `rapid scan`
Scan the repository and emit normalized `ProjectFact` records (`ProjectModel`, `schema_version = 1`). Read-only unless `--write` is passed.

```bash
rapid scan
rapid scan --verbose
rapid scan --json
rapid scan --write
rapid scan --json --write
```

### `rapid validate` & `rapid doctor`
Validate `.rapid-os/` configuration, standards, project intelligence snapshot (`RAPID6xx`), spec registry (`RAPID8xx`), execution policy & run registry (`RAPID1000–RAPID1019`), harness capability registry & lock (`RAPID1100–RAPID1119`), evidence registry (`RAPID1200–RAPID1219`), and behavioral evaluation registry (`RAPID1220–RAPID1239`).

```bash
rapid validate
rapid validate --strict
rapid validate --json
rapid doctor
```

---

## Context Compiler (`rapid context`)

Compile task-relevant, budgeted context (`CompiledContext`, `schema_version = 1`) in read-only mode.

```bash
rapid context --mode feature --harness codex --objective "Implement billing webhook"
rapid context --spec billing-webhook --harness my-company-agent
rapid context --mode hardening --manifest
rapid context --mode general --json
```

Options:
- `--mode {feature,bugfix,refactor,hardening,research,general}`
- `--harness <harness-id>`: Any valid harness ID (`^[a-z0-9][a-z0-9-]{0,62}$`, e.g. `codex`, `claude`, `cursor`, `vscode`, `antigravity`, or custom IDs).
- `--objective <text>`
- `--spec <spec-id>` / `--spec-revision <n>`
- `--path <relative-path>` (repeatable)
- `--tag <tag>` (repeatable)
- `--constraint <constraint>` (repeatable)
- `--max-chars <n>`
- `--manifest`
- `--json`

---

## Spec Registry (`rapid spec`)

Manage immutable, multi-spec revisions in `.rapid-os/specs/<spec-id>/`.

```bash
rapid spec create --title "Checkout Flow" --mode feature --objective "Enable Stripe checkout" --scope "API" --acceptance "Webhook verified" --task "Add endpoint" --status ready
rapid spec list [--status {draft,ready,archived}] [--json]
rapid spec show <spec-id> [--revision <n>] [--json]
rapid spec revise <spec-id> --task "Add idempotency key" [--json]
rapid spec status <spec-id> {draft,ready,archived} [--json]
rapid spec export-legacy <spec-id> [--revision <n>]
```

---

## Execution Policy & Run Registry (`rapid policy` & `rapid run`)

Evaluate execution contracts (`ExecutionContract`, `schema_version = 1`) and track append-only run states in `.rapid-os/runs/<run-id>/`.

```bash
rapid policy show [--json]
rapid policy init [--json]

rapid run create --spec <spec-id> [--spec-revision <n>] [--id <run-id>] [--harness <harness-id>] [--classification {spike,bounded,architectural}] [--risk {low,medium,high,critical}] [--json]
rapid run list [--status {prepared,active,blocked,finished,failed,cancelled}] [--json]
rapid run show <run-id> [--state-revision <n>] [--json]
rapid run status <run-id> {active,blocked,finished,failed,cancelled} [--reason "..."] [--json]
rapid run task <run-id> <task-id> {in_progress,done,blocked,skipped} [--reason "..."] [--json]
rapid run gate <run-id> <gate-id> {acknowledged,waived} [--reason "..."] [--json]
```

---

## Harness Capability Registry (`rapid harness`)

Inspect declarative harness capability profiles (`HarnessProfile`, `schema_version = 1`), initialize project profile overrides in `.rapid-os/harnesses/<id>.json`, lock active profiles in `.rapid-os/capabilities.lock`, and resolve run contracts against harness capabilities (`CapabilityResolution`, `schema_version = 1`).

> **Product Truth**: A capability declaration states what a harness is expected to support; it does not execute the harness or prove that the capability was exercised at runtime.

### `rapid harness list`
List active harness profiles (`builtin:<id>` and `.rapid-os/harnesses/<id>.json` overrides) in deterministic `harness_id` order. Read-only.

```bash
rapid harness list
rapid harness list --json
```

### `rapid harness show <harness-id>`
Show a resolved harness profile, provenance (`source`), `content_digest`, and capability statuses (`supported`, `unsupported`, `unknown`). Read-only.

```bash
rapid harness show codex
rapid harness show codex --json
```

### `rapid harness init <harness-id>`
Copy a built-in harness profile to `.rapid-os/harnesses/<harness-id>.json` for project-specific customization. Never overwrites an existing file (`RAPID1102`). For custom harness IDs without a built-in profile, fails with `RAPID1103` and explains how to author `.rapid-os/harnesses/<harness-id>.json`.

```bash
rapid harness init codex
rapid harness init codex --json
```

### `rapid harness lock`
Write a deterministic `.rapid-os/capabilities.lock` snapshot (`schema_version = 1`) pinning all active harness profiles and their digests.

```bash
rapid harness lock
rapid harness lock --json
```

### `rapid harness resolve --run <run-id>`
Resolve an immutable run's `ExecutionContract` (`contract.harness`) against its active or locked harness profile in read-only mode (never modifies `.rapid-os/runs/<run-id>/`).

```bash
rapid harness resolve --run checkout-r1-run-001
rapid harness resolve --run checkout-r1-run-001 --locked
rapid harness resolve --run checkout-r1-run-001 --require mcp.invoke
rapid harness resolve --run checkout-r1-run-001 --require-compatible
rapid harness resolve --run checkout-r1-run-001 --json
```

Options:
- `--run <run-id>`: Required run identifier whose `ExecutionContract` is evaluated (`profile.id == contract.harness`; the harness is selected when creating the run via `rapid run create --harness <id>`).
- `--locked`: Resolve against the exact `HarnessProfile` snapshot stored in `.rapid-os/capabilities.lock` instead of live profiles on disk (`RAPID1111` if `.rapid-os/capabilities.lock` is missing or invalid).
- `--require <capability-id>`: Repeatable extra canonical capability requirement (`source="cli.require"`). Explicit extra requirements are additive only; they never remove, downgrade, or replace contract-derived requirements.
- `--require-compatible`: Gate mode — exits `0` only when `status == "compatible"`, and exits `1` with `RAPID1110` (`IncompatibleHarnessError`) when `status` is `incompatible` or `unresolved`. Without `--require-compatible`, resolution is informational and exits `0` for `compatible`, `incompatible`, and `unresolved`.
- `--json`: Emit pure `CapabilityResolution` JSON (`schema_version = 1`) on `stdout`.

### Requirement Derivation Rules (`CapabilityRequirementResolver`)
- **Always**:
  - `context.consume` (`source="contract.context"`)
  - `repository.read` (`source="contract.repository"`)
- **If `contract.tasks` is not empty**:
  - `repository.write` (`source="contract.tasks"`)
- **Workspace (`contract.workspace`)**:
  - `current_allowed` → `workspace.current` (`source="contract.workspace"`)
  - `isolated_required` → `workspace.isolated` (`source="contract.workspace"`)
- **Required `gate.tests`**:
  - `tests.execute` (`source="contract.gate.tests"`)
- **Human/governance gates**:
  - No technical harness capability derived
- **Explicit `--require <capability-id>`**:
  - `source="cli.require"` (additive only; never replaces contract-derived provenance)

### Harness Capability Diagnostics (`RAPID1100–RAPID1119`)
- `RAPID1100` (`INFO`): Harness capability registry / lock valid
- `RAPID1101` (`ERROR`): Invalid or unknown `capability_id` (`InvalidCapabilityIdError`)
- `RAPID1102` (`ERROR`): Invalid `HarnessProfile` schema/content/digest (`InvalidHarnessProfileError`)
- `RAPID1103` (`ERROR`): `HarnessProfile` not found (`HarnessProfileNotFoundError`)
- `RAPID1104` (`ERROR`): Invalid harness identity / filename-ID mismatch (`HarnessIdentityError`, `validate_harness_id()`)
- `RAPID1105` (`ERROR`): Unsafe profile/registry/lock path or symlink (`UnsafeHarnessPathError`)
- `RAPID1106` (`ERROR`): Invalid capability support declaration (`InvalidCapabilitySupportError`)
- `RAPID1107` (`ERROR`): Invalid `CapabilityRequirement` (`InvalidCapabilityRequirementError`)
- `RAPID1108` (`ERROR`): Invalid `CapabilityResolution` (`InvalidCapabilityResolutionError`)
- `RAPID1109` (`ERROR`): `CapabilityResolution` digest mismatch (`CapabilityResolutionDigestMismatchError`)
- `RAPID1110` (`ERROR`): Strict compatibility requirement not satisfied (`IncompatibleHarnessError`; applies to `incompatible` and `unresolved`)
- `RAPID1111` (`ERROR`): Invalid or missing `capabilities.lock` (`InvalidCapabilityLockError`)
- `RAPID1112` (`WARNING`): `capabilities.lock` stale relative to active profiles
- `RAPID1113–RAPID1119`: Reserved

---

## Evidence Engine (`rapid evidence`)

Ingest, inspect, and verify append-only, immutable execution evidence (`RunEvidence`, `schema_version = 1`: `id`, `run_id`, `contract_digest`, `state_revision`, `state_digest`, `kind`, `producer`, `summary`, `task_ids`, `gate_ids`, `capability_ids`, `payload`, `artifacts`, `content_digest` — no `recorded_at` field) and copied SHA-256-verified artifacts (`EvidenceArtifact`: `path`, `sha256`, `size_bytes`) under `.rapid-os/evidence/<run-id>/`.

> **Product Truth**: Evidence authenticity is local integrity verification (`content_digest`, artifact `sha256` and `size_bytes`, sequence continuity `E001..E00N`, and Run/Contract/`RunState` binding), not cryptographic external attestation. Adding evidence never mutates `.rapid-os/runs/<run-id>/`.

### `rapid evidence list --run <run-id>`
List recorded evidence items (`E001`, `E002`, ...) for a run in deterministic sequence order, along with `evidence_set_digest`. Read-only.

```bash
rapid evidence list --run checkout-r1-run-001
rapid evidence list --run checkout-r1-run-001 --json
```

### `rapid evidence show --run <run-id> <evidence-id>`
Show an individual `RunEvidence` record (`E001`), its `producer`, task/gate/capability bindings, structured payload (e.g. `command_result`: `{"label": "baseline", "exit_code": 0}`), and copied `EvidenceArtifact` entries (`path`, `sha256`, `size_bytes`). Read-only.

```bash
rapid evidence show --run checkout-r1-run-001 E001
rapid evidence show --run checkout-r1-run-001 E001 --json
```

### `rapid evidence add --run <run-id> --input <file>`
Ingest a new `RunEvidence` record from a JSON file, copy any referenced artifacts into `.rapid-os/evidence/<run-id>/artifacts/E00N/` with SHA-256 and byte-size verification, and commit `.rapid-os/evidence/<run-id>/records/E00N.json` last. Append-only (no `update` or `delete`). If a trailing crash-orphan directory `artifacts/E00N/` exists without `records/E00N.json`, `rapid evidence add` fails safely (`RAPID1211`) without advancing to `E00(N+1)`.

```bash
rapid evidence add --run checkout-r1-run-001 --input evidence.json
rapid evidence add --run checkout-r1-run-001 --input evidence.json --json
```

### `rapid evidence verify --run <run-id>`
Verify all `RunEvidence` records, sequence continuity (`E001..E00N`), Run/Contract/historical `RunState` bindings, and copied artifact SHA-256 digests and sizes. Read-only.

```bash
rapid evidence verify --run checkout-r1-run-001
rapid evidence verify --run checkout-r1-run-001 --json
```

### Evidence Diagnostics (`RAPID1200–RAPID1219`)
- `RAPID1200` (`INFO`): Evidence Registry valid
- `RAPID1201` (`ERROR`): Invalid evidence ID (`InvalidEvidenceIdError`)
- `RAPID1202` (`ERROR`): Invalid `RunEvidence` schema or `content_digest` (`InvalidRunEvidenceError`)
- `RAPID1203` (`ERROR`): Evidence Run / Contract / `RunState` / harness producer binding mismatch (`EvidenceBindingMismatchError`)
- `RAPID1204` (`ERROR`): Unsafe evidence path or symlink (`UnsafeEvidencePathError`)
- `RAPID1205` (`ERROR`): Evidence artifact missing, digest mismatch, or size mismatch (`EvidenceArtifactIntegrityError`)
- `RAPID1206` (`ERROR`): Invalid `EvidenceKind` or payload (`InvalidEvidencePayloadError`)
- `RAPID1207` (`ERROR`): Invalid task, gate, or capability reference (`InvalidEvidenceReferenceError`)
- `RAPID1208` (`ERROR`): Evidence sequence gap or duplicate identity (`EvidenceSequenceGapError`, including any missing historical record even if its `artifacts/E00K/` directory still exists)
- `RAPID1209` (`WARNING`): Trailing crash-orphan evidence artifact directory (`artifacts/E00N` without `records/E00N.json` at `max_record_ordinal + 1`; blocks `rapid evidence add`)
- `RAPID1210` (`ERROR`): Evidence not found (`EvidenceNotFoundError`)
- `RAPID1211` (`ERROR`): Append-only evidence overwrite violation (`EvidenceOverwriteError`)
- `RAPID1212–RAPID1219`: Reserved

---

## Behavioral Evals (`rapid eval`)

Run deterministic, offline behavioral evaluations (`BehavioralEvaluator` → `EvaluationReport`, `schema_version = 1`, `EvaluationVerdict`: `pass`, `pass_with_waivers`, `fail`, `unverified`) over an `ExecutionContract`, `RunState`, `RunEvidence[]`, `BehavioralRuleset` (`version = 1`), and `extra_capability_ids`, and inspect append-only evaluation reports under `.rapid-os/evals/<run-id>/reports/`.

> **Product Truth**: `GateDisposition.ACKNOWLEDGED` is a declaration, not proof (`UNVERIFIED` without qualifying evidence). `EvaluationVerdict.PASS` means the configured Phase 6 evidence rules are satisfied by the exact recorded evidence set; it does not mathematically prove the software has zero bugs or that requirements are complete. Every persisted `EvaluationReport` undergoes mandatory semantic replay via `BehavioralEvaluator` when loaded or validated (`RAPID1223` on any discrepancy).

### `rapid eval run --run <run-id>`
Evaluate a run's lifecycle, tasks, required gates, and required capabilities against its verified evidence set. Read-only unless `--write` is passed. Never modifies `.rapid-os/runs/<run-id>/` or `.rapid-os/harnesses/`.

```bash
rapid eval run --run checkout-r1-run-001
rapid eval run --run checkout-r1-run-001 --json
rapid eval run --run checkout-r1-run-001 --require mcp.invoke
rapid eval run --run checkout-r1-run-001 --write
rapid eval run --run checkout-r1-run-001 --require-pass
rapid eval run --run checkout-r1-run-001 --write --require-pass --json
```

Options:
- `--run <run-id>`: Required run identifier to evaluate.
- `--require <capability-id>`: Repeatable extra canonical capability requirement (`source="cli.require"`, additive only; persisted in `EvaluationReport.extra_capability_ids` and included in `report_digest`).
- `--write`: Persist the resulting `EvaluationReport` as the next append-only `.rapid-os/evals/<run-id>/reports/000N.json` file.
- `--require-pass`: Gate mode — exits `0` when `verdict` is `pass` or `pass_with_waivers`; exits `1` with `RAPID1225` (`EvaluationUnverifiedError`) when `verdict == "unverified"`, and exits `1` with `RAPID1226` (`EvaluationFailedError`) when `verdict == "fail"`. Without `--require-pass`, valid evaluations exit `0` regardless of verdict (`pass`, `pass_with_waivers`, `unverified`, `fail`).
- `--json`: Emit pure `EvaluationReport` JSON (`schema_version = 1`) on `stdout`.

### `rapid eval list --run <run-id>`
List persisted `EvaluationReport` snapshots (`0001.json`, `0002.json`, ...) for a run in deterministic sequence order. Read-only.

```bash
rapid eval list --run checkout-r1-run-001
rapid eval list --run checkout-r1-run-001 --json
```

### `rapid eval show --run <run-id> [--revision <n>]`
Show the latest (or pinned `--revision <n>`) persisted `EvaluationReport` for a run. Read-only.

```bash
rapid eval show --run checkout-r1-run-001
rapid eval show --run checkout-r1-run-001 --revision 1 --json
```

### Behavioral Eval Diagnostics (`RAPID1220–RAPID1239`)
- `RAPID1220` (`INFO`): Eval Registry valid
- `RAPID1221` (`ERROR`): Invalid `EvaluationReport` schema (`InvalidEvaluationReportError`)
- `RAPID1222` (`ERROR`): `EvaluationReport` digest mismatch (`EvaluationReportDigestMismatchError`)
- `RAPID1223` (`ERROR`): Evaluation Run / state / evidence binding or semantic replay mismatch (`EvaluationBindingMismatchError`)
- `RAPID1224` (`ERROR`): Unsafe eval path or symlink (`UnsafeEvaluationPathError`)
- `RAPID1225` (`ERROR`): Evaluation `UNVERIFIED` when `--require-pass` (`EvaluationUnverifiedError`)
- `RAPID1226` (`ERROR`): Evaluation `FAIL` when `--require-pass` (`EvaluationFailedError`)
- `RAPID1227` (`WARNING`): Stored `EvaluationReport` is stale relative to current `RunState`, `evidence_set_digest`, or `ruleset_digest`
- `RAPID1228` (`ERROR`): `EvaluationReport` not found (`EvaluationReportNotFoundError`)
- `RAPID1229` (`ERROR`): Append-only evaluation report overwrite violation (`EvaluationOverwriteError`)
- `RAPID1230–RAPID1239`: Reserved


