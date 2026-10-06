# Rapid OS v3 Architecture

## Roadmap Overview

Rapid OS v3 evolves Rapid OS from a static context template generator into a deterministic, provenance-backed engineering intelligence platform for AI coding harnesses.

```text
Phase 0  Hardening Foundation (COMPLETE)
Phase 1  Project Intelligence (COMPLETE)
Phase 2  Context Compiler (COMPLETE)
Phase 3  Spec Registry v3 (COMPLETE)
Phase 4  Execution Policy Engine & Run Contract (CURRENT)
Phase 5  Harness Capability Registry (PLANNED)
Phase 6  Evidence Engine & Evals (PLANNED)
```

> Phases 0 through 4 are implemented in the repository today. Phases 5–6 are documented strictly as planned architecture targets.

---

## Phase 1: Project Intelligence Model

### Architectural Principle

Rapid OS v3 strictly separates four epistemic layers that must never be conflated:

1. **Raw Observation (`Evidence`)**: Verifiable local repository signals such as `package.json` dependency entries, `.env` variable key names, config files, or workflow files.
2. **Detected Fact (`ProjectFact`)**: A normalized, provenance-backed statement about the repository (`category="framework"`, `value="fastapi"`).
3. **Inference (`InitSuggestion` / `ScanSuggestions`)**: Heuristic recommendations derived from facts (for example, suggesting `stack = python-ai` or `topology = fullstack-separated`).
4. **User Decision (`.rapid-os/config.json` & `.rapid-os/standards/`)**: Explicit choices confirmed or configured by the developer.

### Pipeline

```text
Repository
    ↓
Detectors (rapid_os.domain.scanner)
    ↓
ProjectFact (raw facts with Evidence + SourceType + detector ID)
    ↓
normalize_facts() (consolidation, deduplication, confidence promotion, deterministic sort)
    ↓
ProjectModel (canonical, immutable, serializable v3 intelligence model)
    ↓
Validation (RAPID600–RAPID604) & Optional Snapshot (.rapid-os/project.json)
```

### Canonical Domain Entities (`rapid_os.domain.project`)

#### `Confidence`
Ordered enum (`LOW = "low"`, `MEDIUM = "medium"`, `HIGH = "high"`) representing certainty for a fact or suggestion. Always serialized as lowercase strings.

#### `SourceType`
Enum classifying how an observation was obtained:
- `file`
- `manifest`
- `config`
- `directory`
- `environment-key`
- `dependency`
- `workflow`

#### `Evidence`
Immutable record (`path`, `reason`, `source_type`, optional `detector`) proving why a fact was emitted:
- `path` is normalized to a relative POSIX path inside the project root (`package.json`, `apps/api/pyproject.toml`). Absolute host paths and `..` path traversal segments are rejected.
- `reason` is human-readable and never contains secret values from `.env` files.

#### `ProjectFact`
Immutable fact (`category`, `value`, `confidence`, `evidence`, `detector`):
- `detector` is a stable domain identifier (`language.python`, `framework.fastapi`, `database.postgres`, `testing.pytest`, `deploy.vercel`) decoupled from internal private function names.
- Performs no I/O, mutates no files, and contains no CLI presentation logic.

#### `normalize_facts`
Deterministic consolidation pass over emitted facts:
- Facts sharing `(category, value)` are merged into a single `ProjectFact`.
- `ProjectFact.detector` is resolved to the canonical detector identifier `canonical_detector_id(category, value)` independent of input order.
- `Evidence.detector` preserves the concrete detector/producer provenance for each observation.
- `Evidence` entries are deduplicated and sorted by `(path, reason, source_type, detector or "")`.
- The highest `Confidence` across merged detections is preserved.
- Distinct values within the same category (such as `nextjs` and `fastapi` in `framework` for a monorepo) are preserved as separate facts.
- Output facts are sorted deterministically by `(category, value)`.

#### `ProjectModel`
Canonical container (`schema_version = 1`, `root = "."`, `facts: tuple[ProjectFact, ...]`) with:
- Query helpers: `values(category)`, `has(category, value=None)`, `facts_for(category)`, `fact(category, value)`, `by_category()`, and `categories()`.
- Round-trip deterministic serialization: `to_dict()`, `to_json()`, `from_dict()`, and `from_json()`.

### Compatibility Facade (`ProjectScan`)

`ProjectScan` in `rapid_os.domain.scanner` wraps `ProjectModel` without duplicating state:
- `scan_project(root)` calls `build_project_model(root)` and returns `ProjectScan(model=model)`.
- `scan.detections` and `scan.facts` both return `model.facts`.
- `scan.to_model()` returns the underlying `ProjectModel`.
- `suggest_init_choices()` accepts either `ProjectModel` or `ProjectScan`, keeping `rapid init` compatible while operating directly on `ProjectFact` data.

### Optional Snapshot Persistence (`rapid_os.adapters.project_snapshot`)

- By default, scanning (`scan_project()`, `build_project_model()`, `rapid scan`, `rapid scan --json`, and `rapid init`) is **read-only** and does not write `.rapid-os/project.json`.
- When explicitly requested via `rapid scan --write` (or `write_project_snapshot()`), Rapid OS writes `.rapid-os/project.json` using `safe_write_text(..., backup=True)` and validates containment via `ensure_path_within_root()`.

### Snapshot Validation (`RAPID6xx` in `rapid_os.domain.validation`)

When `.rapid-os/project.json` is present, `rapid validate` and `rapid doctor` verify its integrity:
- `RAPID600` (`INFO`): Valid project intelligence snapshot loaded.
- `RAPID601` (`ERROR`): Invalid JSON in `.rapid-os/project.json`.
- `RAPID602` (`ERROR`): Unreadable `.rapid-os/project.json`.
- `RAPID603` (`ERROR`): Unsupported or invalid `schema_version`.
- `RAPID604` (`ERROR`): Corrupt structure or invalid `ProjectFact` / `Evidence` entry.

### CLI Surface (`rapid scan`)

- `rapid scan`: Runs local detectors and prints a human-readable summary of detected facts grouped by category (`value`, `confidence`, and `detector`) without writing any files or running `suggest_init_choices()`.
- `rapid scan --verbose`: Includes per-fact `Evidence` entries (`path`, `reason`, and `source_type`) in the human-readable output.
- `rapid scan --json`: Emits only the serialized `ProjectModel` JSON to `stdout` (no banners or decorative text) for machine consumption.
- `rapid scan --write`: Persists the canonical `ProjectModel` snapshot to `.rapid-os/project.json` with atomic write and `.bak` backup protection.
- `rapid scan --json --write`: Writes `.rapid-os/project.json` and emits the exact same JSON document to `stdout`.

---

## Phase 2: Context Compiler

### Architectural Principle

Whereas **Project Intelligence** answers *"What exists in the project?"*, the **Context Compiler** answers *"What does the agent actually need to know to execute this specific task?"*.

Instead of dumping all standards and raw scan facts indiscriminately, the Context Compiler resolves, ranks, budgets, and compiles task-relevant context with full provenance and explainability.

### Pipeline

```text
ProjectModel + Project Standards + Spec Registry / Task Intent (ContextRequest) + ContextPolicy
    ↓
ContextSourceLoader (rapid_os.adapters.context_sources)
    ↓
ContextResolver (selection, precedence, budget enforcement, conflict detection)
    ↓
ContextCompiler (deterministic Markdown rendering + ContextManifest generation)
    ↓
CompiledContext (schema_version = 1, content + manifest)
```

### Canonical Domain Entities (`rapid_os.domain.context`)

#### `ContextSourceKind` & Precedence Order
Explicit precedence hierarchy where user-confirmed constraints and rules always take priority over lower-level defaults and detected project facts:

1. `task_constraints`
2. `security`
3. `business`
4. `architecture`
5. `topology`
6. `tech_stack`
7. `coding_rules`
8. `spec`
9. `tasks`
10. `acceptance`
11. `design`
12. `reference`
13. `custom`
14. `project_intelligence`

#### `ContextPriority`
Ordered integer enum (`LOW = 10`, `MEDIUM = 50`, `HIGH = 80`, `CRITICAL = 100`).

#### `ContextMode`
Task execution modes (`feature`, `bugfix`, `refactor`, `hardening`, `research`, `general`), each defining mode-preferred source kinds and task-relevant `ProjectModel` fact filtering.

#### `ContextSource` & `ContextFragment`
Immutable, validated units of context with stable public identifiers (`task.constraints`, `standard.security`, `standard.business`, `standard.tech-stack`, `spec.<id>.requirements`, `spec.scope`, `project.intelligence`), portable POSIX paths, tags, selection reasons, and end-to-end portable `provenance` preserved through `ContextSource` → `ContextFragment` → `ManifestEntry` → `ContextManifest`.
- File-backed standards/specs record their relative POSIX path (e.g., `.rapid-os/standards/security.md`).
- Explicit task constraints (`ContextRequest.constraints`) are promoted to a first-class canonical source (`id="task.constraints"`, `kind=ContextSourceKind.TASK_CONSTRAINTS`, `priority=ContextPriority.CRITICAL`, `required=True`, `provenance="ContextRequest.constraints"`).
- Project Intelligence distinguishes snapshot provenance (`snapshot:.rapid-os/project.json`) from live scan provenance (`scan:live`), and fails explicitly with `RAPID704` if `.rapid-os/project.json` exists on disk but is corrupt or invalid (never silently falling back to a live scan).

#### `ContextRequest` & `ContextPolicy`
`ContextRequest` captures task intent (`mode`, `harness`, `objective`, `affected_paths`, `tags`, `max_chars`, `constraints`, `spec_id`, `spec_revision`). `ContextPolicy` (`DEFAULT_CONTEXT_POLICY`, `max_chars = 24000`) governs required kinds, mode preferences, priorities, and precedence order.

#### Budget Enforcement, Required Sources & Non-Truncation Guarantee
- Budget (`max_chars`) is enforced against the final compiled Markdown output (`len(compiled.content) <= max_chars`).
- Required fragments (including `task.constraints` and mode-required kinds such as `security` in `hardening` mode) are included first. If required fragments alone exceed `max_chars`, `ContextBudgetExceededError` is raised (`RAPID702`) without silently truncating rules.
- If a required source or mode-required kind is missing after resolution, `ContextCompiler.compile()` raises `ContextRequiredSourceMissingError` (`RAPID701`) and `rapid context` exits non-zero without emitting invalid compiled context to `stdout` (`ContextResolver.resolve()` retains `missing_required_kinds` on `ContextSelection` for low-level inspection).
- Optional fragments are evaluated in deterministic rank order (`-priority`, `-relevance_score`, `precedence_rank`, `source_id`, `fragment_id`). Any optional fragment that would exceed the remaining budget is skipped in its entirety with `reason="skipped: source exceeds remaining budget"`.

#### Conflict Detection (`ContextConflict`)
Detects structural contradictions across **effectively selected** fragments and `ProjectModel` facts (such as conflicting database declarations across `task.constraints`, `standard.business`, `standard.tech-stack`, and `project.intelligence`) and records the winning source according to `ContextPolicy` precedence. Sources skipped due to budget or relevance never participate in or win conflicts.

#### `ContextManifest` & `CompiledContext`
`CompiledContext` (`schema_version = 1`) bundles the deterministic compiled Markdown (`content`) with a machine-readable `ContextManifest` (`selected`, `skipped`, `conflicts`, `compiled_chars`, `max_chars`, `content_digest`), supporting full `to_dict()`, `to_json()`, `from_dict()`, and `from_json()` round-trip serialization (preserving `provenance` on every `ManifestEntry`).

### Context Validation Diagnostics (`RAPID7xx` in `rapid_os.domain.validation`)

- `RAPID700` (`INFO`): Context compiled successfully.
- `RAPID701` (`ERROR`): Required context source missing (`ContextRequiredSourceMissingError`).
- `RAPID702` (`ERROR`): Context budget exceeded by required sources (`ContextBudgetExceededError`).
- `RAPID703` (`WARNING`): Context conflict detected across selected sources.
- `RAPID704` (`ERROR`): Context source or `.rapid-os/project.json` snapshot unreadable or invalid.
- `RAPID705` (`ERROR`): Invalid `ContextRequest` or duplicate/invalid source identifiers.

### CLI Surface (`rapid context`)

- `rapid context` (or `rapid context compile`): Compiles and prints the task-relevant context in read-only mode (never writes files, never prompts, never makes network calls).
- `rapid context --mode <mode>`: Selects task mode (`feature`, `bugfix`, `refactor`, `hardening`, `research`, `general`).
- `rapid context --harness <harness>`: Selects target harness (`cursor`, `claude`, `codex`, `vscode`, `antigravity`).
- `rapid context --objective "..."`: Provides task objective for relevance scoring and task header rendering.
- `rapid context --spec <spec-id> [--spec-revision <n>]`: Injects a `ready` spec (current or pinned revision) from `.rapid-os/specs/<spec-id>/` into the Context Compiler and suppresses root singleton `SPECS.md` / `TASKS.md` / `ACCEPTANCE.md` files to prevent ambiguity.
- `rapid context --max-chars <n>`: Sets explicit character budget.
- `rapid context --manifest`: Prints human-readable manifest (`SELECTED`, `SKIPPED`, and `CONFLICTS`).
- `rapid context --json`: Emits pure `CompiledContext` JSON (`schema_version = 1`, `manifest`, `content`) to `stdout`.
- `rapid inspect-context` and `compose_project_context()` remain intact for v2 compatibility.

---

## Phase 3: Spec Registry v3

### Architectural Principle

Whereas legacy `rapid scope` overwrote three singleton root files (`SPECS.md`, `TASKS.md`, `ACCEPTANCE.md`) with no stable identity, concurrent spec support, revision history, or authoring lifecycle, the **Spec Registry** makes Spec-Driven Development (SDD) canonical, addressable, and immutable.

A **Spec** answers: *"What must be built and how will we know it is properly defined?"*.
It strictly separates **authoring state** (`draft`, `ready`, `archived`) from **execution state** (which belongs to Phase 4+).

### Pipeline & Filesystem Layout

```text
Scope / Spec Input
    ↓
Canonical Spec Model (SpecRecord + SpecRevision in rapid_os.domain.specs)
    ↓
SpecRegistry (.rapid-os/specs/<spec-id>/)
    ├── spec.json (schema_version = 1, id, status, current_revision)
    └── revisions/
        ├── 0001/
        │   ├── revision.json (schema_version = 1, structured fields + digests)
        │   ├── requirements.md
        │   ├── tasks.md
        │   └── acceptance.md
        └── 0002/
            └── ...
    ↓
Context Compiler (rapid context --spec <spec-id> [--spec-revision <n>])
```

- **No Duplicate Index**: Specs are discovered deterministically by scanning `.rapid-os/specs/*/spec.json` in lexical order.
- **Immutable Revisions, Historical Continuity & Atomic Commit Point**: Existing `revisions/<rev>/` directories (`format_revision_dir_name`: `0001`..`9999`, `10000`, ...) are never modified in place, and every historical revision `1..current_revision` must remain present and valid. Creating or revising a spec validates the model, writes `requirements.md`, `tasks.md`, `acceptance.md`, and `revision.json`, verifies revision completeness and SHA-256 digests, and updates `spec.json` (`current_revision`) **last**.

### Canonical Domain Entities (`rapid_os.domain.specs`)

#### `SPEC_SCHEMA_VERSION = 1` & `SPEC_REVISION_SCHEMA_VERSION = 1`
Independent schema versions governing `spec.json` and `revision.json`.

#### `SpecStatus`
Authoring lifecycle enum (`DRAFT = "draft"`, `READY = "ready"`, `ARCHIVED = "archived"`):
- Allowed transitions: `draft → ready`, `draft → archived`, `ready → draft`, `ready → archived`.
- `archived` is terminal in Phase 3.

#### `SpecMode`
Canonical authoring mode (`FEATURE = "feature"`, `BUGFIX = "bugfix"`, `REFACTOR = "refactor"`, `HARDENING = "hardening"`, `RESEARCH = "research"`), with compatibility mapping from legacy `rapid scope` modes (`new feature → feature`, `legacy hardening → hardening`).

#### `SpecRecord`
Immutable record (`schema_version`, `id`, `status`, `current_revision`) persisted in `.rapid-os/specs/<spec-id>/spec.json`. Contains no timestamps, no UUIDs, no host paths, and no execution state.

#### `SpecRevision`
Immutable structured revision (`schema_version`, `spec_id`, `revision`, `title`, `mode`, `business_objective`, `problem_statement`, `scope`, `out_of_scope`, `actors_users`, `main_flow`, `edge_cases`, `business_rules`, `technical_constraints`, `affected_paths`, `data_impact`, `acceptance_criteria`, `testing_strategy`, `implementation_tasks`, `tags`):
- Preserves exact user-authored ordering across all semantic tuple fields (`main_flow`, `implementation_tasks`, `acceptance_criteria`, etc.); only `tags` are normalized, deduplicated, and sorted lowercase.
- Strictly validates persisted `revision.json` keys against `CANONICAL_SPEC_REVISION_KEYS` (`RAPID803`), rejecting unknown or execution-state fields (`execution_status`, `run_id`, `agent`).
- Deterministically renders `requirements.md`, `tasks.md`, and `acceptance.md`, and computes `artifact_digests` (`requirements.md`, `tasks.md`, `acceptance.md`) plus `content_digest` (`<sha256-hex>`).
- Provides explicit compatibility converters `spec_revision_from_scope()` and `scope_spec_from_revision()` so legacy `ScopeSpec` acts strictly as an authoring DTO.

### Context Compiler Integration

When `ContextRequest.spec_id` is provided (`rapid context --spec <id>`):
- The target spec must have `status == SpecStatus.READY` (loading a `draft` or `archived` spec fails with `RAPID805`).
- `ContextSourceLoader` emits three canonical sources with portable repository-relative POSIX path provenance (`.rapid-os/specs/<id>/revisions/<rev>/<artifact>`):
  - `spec.<id>.requirements` (`ContextSourceKind.SPEC`, `HIGH` priority, `provenance=".rapid-os/specs/<id>/revisions/<rev>/requirements.md"`)
  - `spec.<id>.tasks` (`ContextSourceKind.TASKS`, `MEDIUM` priority, `provenance=".rapid-os/specs/<id>/revisions/<rev>/tasks.md"`)
  - `spec.<id>.acceptance` (`ContextSourceKind.ACCEPTANCE`, `MEDIUM` priority, `provenance=".rapid-os/specs/<id>/revisions/<rev>/acceptance.md"`)
- Root legacy singletons (`SPECS.md`, `TASKS.md`, `ACCEPTANCE.md`) are automatically excluded when `--spec` is active.
- Without `--spec`, `rapid context` preserves backward compatibility by reading root singletons if present and ignoring `.rapid-os/specs/` to avoid multi-spec ambiguity.

### Spec Registry Validation (`RAPID8xx` in `rapid_os.domain.validation`)

`validate_spec_registry(root)` is integrated into `rapid validate` and `rapid doctor`:
- `RAPID800` (`INFO`): Spec registry valid.
- `RAPID801` (`ERROR`): Invalid persisted `spec.json` record/schema (`InvalidSpecRecordError`: invalid JSON, unsupported `schema_version`, unknown fields, or invalid persisted record/status value).
- `RAPID802` (`ERROR`): Missing `revisions/` directory or missing required historical/current revision directory (`1..current_revision`, `CurrentRevisionMissingError`).
- `RAPID803` (`ERROR`): Invalid persisted `revision.json` manifest/schema (`InvalidRevisionManifestError`: invalid JSON, unsupported `schema_version`, unknown fields, or invalid revision fields).
- `RAPID804` (`ERROR`): Missing `requirements.md`, `tasks.md`, or `acceptance.md` artifact, or SHA-256 digest drift (`SpecArtifactDriftError`).
- `RAPID805` (`ERROR`): Invalid lifecycle transition or spec lifecycle prevents requested operation (`SpecLifecycleError`, e.g. `draft`/`archived` spec requested by operational context compilation).
- `RAPID806` (`ERROR`): Invalid `spec_id`, duplicate spec identity, or directory/record ID mismatch (`DuplicateSpecIdentityError`).
- `RAPID807` (`ERROR`): Referenced spec or revision not found (`SpecNotFoundError`).
- `RAPID808` (`ERROR`): Unsafe spec path, symlink escape, or unreadable spec entry (`UnsafeSpecPathError`).
- `RAPID809` (`WARNING`): Orphan or unreferenced revision entry inside `revisions/` (`revision > current_revision` or non-canonical entry).

### CLI Surface (`rapid spec`)

- `rapid spec create`: Creates a new spec (`--title`, `--id`, `--mode`, `--objective`, `--problem`, `--scope`, `--out-of-scope`, `--actor`, `--main-flow` / `--flow`, `--edge-case`, `--business-rule` / `--rule`, `--technical-constraint` / `--constraint`, `--affected-path`, `--data-impact`, `--acceptance`, `--testing`, `--task`, `--tag`, `--status {draft,ready}`, `--export-legacy`, `--json`). Interactive wizard when flags are omitted.
- `rapid spec list [--status {draft,ready,archived}] [--json]`: Lists specs in deterministic ID order without writing files.
- `rapid spec show <spec-id> [--revision <n>] [--json]`: Displays a spec and its current or pinned revision in read-only mode.
- `rapid spec revise <spec-id> [--json] [...]`: Creates immutable revision `current_revision + 1`, inheriting unspecified fields from `current_revision` and resetting status to `draft`.
- `rapid spec status <spec-id> <status> [--json]`: Transitions authoring status (`draft`, `ready`, `archived`).
- `rapid spec export-legacy <spec-id> [--revision <n>]`: Explicitly exports a spec revision to root `SPECS.md`, `TASKS.md`, and `ACCEPTANCE.md` with `.bak` backup protection.
- `rapid scope [--register] [--spec-id <id>] [--status {draft,ready}]`: Preserves legacy root file generation while optionally registering the spec in `.rapid-os/specs/`.

---

## Phase 4: Execution Policy Engine & Run Contract

### Architectural Principle

Phase 4 answers: *"Given an exact Spec revision and its compiled context, under what execution contract, risk classification, workspace requirement, and gates is work allowed to happen?"*

Rapid OS v3 strictly separates:
- **Spec**: *WHAT* must be built (authoring lifecycle in `.rapid-os/specs/`).
- **Context**: *WHAT* the agent needs to know (`CompiledContext`).
- **Policy**: *UNDER WHAT RULES* work may happen (`ExecutionPolicy` → `PolicyDecision`).
- **Run**: *ONE* concrete execution attempt pinned to an immutable `ExecutionContract` and append-only `RunState` snapshots in `.rapid-os/runs/<run-id>/`.
- **Evidence** (Phase 6, planned): *PROOF* of what actually happened.

Rapid OS does **not** act as an autonomous agent runtime: it never invokes external LLM CLIs, never runs shell commands, never creates git worktrees automatically, and never mutates application source code.

### Pipeline & Filesystem Layout

```text
ProjectModel + SpecRevision (status == ready) + CompiledContext + ExecutionPolicy
    ↓
ExecutionPolicyEvaluator (rapid_os.domain.policy)
    ↓
PolicyDecision (ExecutionClass, RiskLevel, RiskSignals, WorkspaceRequirement, GateRequirements, reasons)
    ↓
ExecutionContract (contract.json: immutable contract + SHA-256 digests)
    ↓
RunRegistry (.rapid-os/runs/<run-id>/)
    ├── run.json (schema_version = 1, id, spec_id, spec_revision, contract_digest, current_state_revision)
    ├── contract.json (schema_version = 1, immutable ExecutionContract)
    ├── context.md (immutable compiled context snapshot)
    ├── context-manifest.json (immutable ContextManifest snapshot)
    └── states/
        ├── 0001.json (initial RunState: status=prepared, tasks=pending, gates=pending)
        ├── 0002.json (append-only state transition)
        └── ...
```

- **No Duplicate Index**: Runs are discovered deterministically by scanning `.rapid-os/runs/*/run.json` in lexical order.
- **Deterministic Run IDs**: Default run IDs follow `<spec-id>-r<spec-revision>-run-<NNN>` (`001`..`999`, `1000`, ...) with no timestamps, random UUIDs, or host paths.
- **Immutable Contract & Append-Only State History**: `contract.json`, `context.md`, `context-manifest.json`, and existing `states/<NNNN>.json` files are never modified in place. Every transition writes `states/<next>.json` first, verifies its schema and invariants, and updates `run.json` (`current_state_revision`) **last**.

### Canonical Domain Entities (`rapid_os.domain.policy` & `rapid_os.domain.execution`)

#### `ExecutionClass`
Classification of execution scope (`SPIKE = "spike"`, `BOUNDED = "bounded"`, `ARCHITECTURAL = "architectural"`):
- `spike`: `SpecMode.RESEARCH` without architectural signals.
- `bounded`: `FEATURE`, `BUGFIX`, or `REFACTOR` without architectural signals.
- `architectural`: `SpecMode.HARDENING`, architectural tags/paths (`migration`, `schema`, `infra`, `deployment`, `security`, `auth`, `ci`, `architecture`), or non-empty `data_impact`.

#### `RiskLevel` & `RiskSignal`
Ordered risk enum (`LOW = 10`, `MEDIUM = 50`, `HIGH = 80`, `CRITICAL = 100`) paired with structured `RiskSignal` records (`id`, `level`, `reason`, `source`).
- Neither project policy nor CLI overrides (`--classification`, `--risk`) may downgrade the calculated `ExecutionClass` or `RiskLevel`; any downgrade attempt fails with `RAPID1006`.

#### `WorkspaceRequirement`
Declarative workspace rule (`CURRENT_ALLOWED = "current_allowed"`, `ISOLATED_REQUIRED = "isolated_required"`):
- `LOW` / `MEDIUM` default to `current_allowed`.
- `HIGH` / `CRITICAL` require `isolated_required`.

#### `GateKind`, `GatePhase`, & `GateRequirement`
Canonical execution gates evaluated across `PRE_EXECUTION` (`gate.workspace-isolation`, `gate.baseline`, `gate.manual-approval`) and `POST_EXECUTION` (`gate.tests`, `gate.review`, `gate.security-review`, `gate.migration-review`, `gate.final-verification`):
- Ordered deterministically by `CANONICAL_GATE_ORDER` without duplicates.
- At `CRITICAL` risk, no gate is waivable. Below `CRITICAL`, only gates listed in `policy.waivable_gate_ids` (`gate.review`, `gate.tests` by default) may be waived, and waiving always requires a non-empty `reason`.

#### `ExecutionPolicy` (`.rapid-os/policy.json`)
Optional project-level policy configuration (`EXECUTION_POLICY_SCHEMA_VERSION = 1`).
- If `.rapid-os/policy.json` does not exist, `DEFAULT_EXECUTION_POLICY` is used (`source="default"`).
- If `.rapid-os/policy.json` exists, it is validated strictly (`source=".rapid-os/policy.json"`); corrupt or invalid policy files fail explicitly with `RAPID1005` or `RAPID1006` without falling back to defaults.

#### `TaskContract` & `ExecutionContract`
`ExecutionContract` (`EXECUTION_CONTRACT_SCHEMA_VERSION = 1`) pins `spec_id`, `spec_revision`, `spec_content_digest`, `harness`, `policy_source`, `policy_digest`, `project_model_digest`, `context_digest`, `context_manifest_digest`, `decision`, `tasks` (`T001`, `T002`, ... derived deterministically from `SpecRevision.implementation_tasks`), `acceptance_criteria`, `affected_paths`, `technical_constraints`, and `contract_digest`.
- `contract_digest` is computed over the semantic contract payload (excluding `run_id` and `contract_digest`), so identical inputs produce identical `contract_digest` values across runs.

#### `RunStatus`, `TaskStatus`, `GateDisposition`, & `RunState`
`RunState` (`RUN_STATE_SCHEMA_VERSION = 1`) records the state revision (`1..current_state_revision`):
- Initial snapshot (`states/0001.json`) invariant: `revision = 1`, `status = prepared`, all tasks `pending` (empty reason), all gates `pending` (empty reason), and `change_kind = "run.prepared"` (`RAPID1012`).
- Sequential history verification (`s1 → s2 → ... → current`): every consecutive snapshot must advance `revision` by 1, mutate exactly one category (`run status`, `1 task`, or `1 gate`), match `change_kind`, and satisfy all phase boundary preconditions (`RAPID1012`).
- `RunStatus` transitions: `prepared → active | cancelled`, `active → blocked | finished | cancelled`, `blocked → active | cancelled`. `finished` and `cancelled` are terminal (`RAPID1009`).
- Phase boundaries (`RAPID1014`):
  - `PRE_EXECUTION` gates can only change while `status = prepared`.
  - Precondition for `prepared → active`: all required `PRE_EXECUTION` gates must be `acknowledged` or `waived`.
  - Tasks can only change while `status = active`.
  - `POST_EXECUTION` gates can only change while `status = active` and after all tasks are terminal (`done` or `skipped`).
  - Precondition for `active → finished`: all tasks must be `done` or `skipped` and all required `POST_EXECUTION` gates must be `acknowledged` or `waived`.
- `TaskStatus` transitions: `pending → in_progress | skipped`, `in_progress → done | blocked | skipped`, `blocked → in_progress | skipped`. `done` and `skipped` are terminal (`RAPID1010`).

### Execution Policy & Run Registry Validation (`RAPID1000–RAPID1019` in `rapid_os.domain.validation`)

`validate_execution_policy(rapid_dir, root)` and `validate_run_registry(rapid_dir, root)` are integrated into `rapid validate` and `rapid doctor`:
- `RAPID1000` (`INFO`): Execution policy and run registry valid.
- `RAPID1001` (`ERROR`): Invalid `run.json` record or schema (`InvalidRunRecordError`).
- `RAPID1002` (`ERROR`): Invalid `contract.json` or contract digest mismatch (`InvalidExecutionContractError`).
- `RAPID1003` (`ERROR`): Invalid spec binding (`InvalidSpecBindingError` — missing spec/revision, spec not `ready`, or `spec_content_digest` mismatch).
- `RAPID1004` (`ERROR`): Context snapshot or digest mismatch (`ContextSnapshotMismatchError`).
- `RAPID1005` (`ERROR`): Invalid execution policy schema (`InvalidExecutionPolicyError`).
- `RAPID1006` (`ERROR`): Policy violation or forbidden risk/classification downgrade (`PolicyViolationError`).
- `RAPID1007` (`ERROR`): Run identity error or referenced run not found (`DuplicateRunIdentityError`, `RunNotFoundError`).
- `RAPID1008` (`ERROR`): Unsafe run/policy path or symlink escape (`UnsafeRunPathError`).
- `RAPID1009` (`ERROR`): Invalid run status transition (`InvalidRunTransitionError`).
- `RAPID1010` (`ERROR`): Invalid task status transition (`InvalidTaskTransitionError`).
- `RAPID1011` (`ERROR` / `WARNING`): Run state history gap or missing `states/` directory (`ERROR`, `RunStateHistoryGapError`); unreferenced future state `revision > current_state_revision` or non-canonical entry in `states/` (`WARNING`).
- `RAPID1012` (`ERROR`): Invalid `RunState` schema, digest, contract alignment, initial state invariant, or semantic state transition history (`InvalidRunStateError`).
- `RAPID1013` (`ERROR`): Invalid gate disposition transition or invalid waiver (`InvalidGateTransitionError`).
- `RAPID1014` (`ERROR`): Run lifecycle or phase boundary precondition not satisfied (`ExecutionPreconditionError`).
- `RAPID1015–RAPID1019`: Reserved for future execution policy diagnostics.

### CLI Surface (`rapid policy` & `rapid run`)

- `rapid policy show [--json]`: Displays active execution policy (`default` or `.rapid-os/policy.json`) in read-only mode.
- `rapid policy init [--json]`: Writes default `.rapid-os/policy.json` (fails with `RAPID1005` if `.rapid-os/policy.json` already exists).
- `rapid run create --spec <spec-id> [--spec-revision <n>] [--id <run-id>] [--harness <harness>] [--classification <class>] [--risk <risk>] [--json]`: Evaluates policy, compiles context, and creates an immutable run contract and initial state `0001.json`.
- `rapid run list [--status <status>] [--json]`: Lists runs in deterministic ID order without mutating files.
- `rapid run show <run-id> [--state-revision <n>] [--json]`: Displays run record, contract, risk signals, tasks, gates, and current or historical state in read-only mode.
- `rapid run status <run-id> <status> [--reason "..."] [--json]`: Appends a new state revision transitioning run status after verifying gate/task preconditions.
- `rapid run task <run-id> <task-id> <status> [--reason "..."] [--json]`: Appends a new state revision transitioning a task (`T001`, ...).
- `rapid run gate <run-id> <gate-id> <disposition> [--reason "..."] [--json]`: Appends a new state revision acknowledging or waiving a gate.


