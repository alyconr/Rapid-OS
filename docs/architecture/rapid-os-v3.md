# Rapid OS v3 Architecture

## Roadmap Overview

Rapid OS v3 evolves Rapid OS from a static context template generator into a deterministic, provenance-backed engineering intelligence platform for AI coding harnesses.

```text
Phase 0  Hardening Foundation (COMPLETE)
Phase 1  Project Intelligence (COMPLETE)
Phase 2  Context Compiler (COMPLETE)
Phase 3  Spec Registry v3 (CURRENT)
Phase 4  Execution Policy Engine (PLANNED)
Phase 5  Harness Capability Registry (PLANNED)
Phase 6  Evidence Engine & Evals (PLANNED)
```

> Only Phase 0, Phase 1, Phase 2, and Phase 3 are implemented in the repository today. Phases 4–6 are documented strictly as planned architecture targets.

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


