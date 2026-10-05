# Rapid OS v3 Architecture

## Roadmap Overview

Rapid OS v3 evolves Rapid OS from a static context template generator into a deterministic, provenance-backed engineering intelligence platform for AI coding harnesses.

```text
Phase 0  Hardening Foundation (COMPLETE)
Phase 1  Project Intelligence (COMPLETE)
Phase 2  Context Compiler (CURRENT)
Phase 3  Spec Registry v3 (PLANNED)
Phase 4  Execution Policy Engine (PLANNED)
Phase 5  Harness Capability Registry (PLANNED)
Phase 6  Evidence Engine & Evals (PLANNED)
```

> Only Phase 0, Phase 1, and Phase 2 are implemented in the repository today. Phases 3–6 are documented strictly as planned architecture targets.

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
ProjectModel + Project Standards + Task Intent (ContextRequest) + ContextPolicy
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
Immutable, validated units of context with stable public identifiers (`standard.security`, `standard.business`, `standard.tech-stack`, `spec.scope`, `project.intelligence`), portable POSIX paths, tags, and selection reasons.

#### `ContextRequest` & `ContextPolicy`
`ContextRequest` captures task intent (`mode`, `harness`, `objective`, `affected_paths`, `tags`, `max_chars`, `constraints`). `ContextPolicy` (`DEFAULT_CONTEXT_POLICY`, `max_chars = 24000`) governs required kinds, mode preferences, priorities, and precedence order.

#### Budget Enforcement & Non-Truncation Guarantee
- Budget (`max_chars`) is enforced against the final compiled Markdown output (`len(compiled.content) <= max_chars`).
- Required fragments are included first. If required fragments alone exceed `max_chars`, `ContextBudgetExceededError` is raised (`RAPID702`) without silently truncating rules.
- Optional fragments are evaluated in deterministic rank order (`-priority`, `-relevance_score`, `precedence_rank`, `source_id`, `fragment_id`). Any optional fragment that would exceed the remaining budget is skipped in its entirety with `reason="skipped: source exceeds remaining budget"`.

#### Conflict Detection (`ContextConflict`)
Detects structural contradictions across sources (such as conflicting database declarations between `standard.business` and `standard.tech-stack`, or between user-declared standards and `ProjectModel` facts) and records the winning source according to `ContextPolicy` precedence.

#### `ContextManifest` & `CompiledContext`
`CompiledContext` (`schema_version = 1`) bundles the deterministic compiled Markdown (`content`) with a machine-readable `ContextManifest` (`selected`, `skipped`, `conflicts`, `compiled_chars`, `max_chars`, `content_digest`), supporting full `to_dict()`, `to_json()`, `from_dict()`, and `from_json()` round-trip serialization.

### Context Validation Diagnostics (`RAPID7xx` in `rapid_os.domain.validation`)

- `RAPID700` (`INFO`): Context compiled successfully.
- `RAPID701` (`ERROR`): Required context source missing.
- `RAPID702` (`ERROR`): Context budget exceeded by required sources.
- `RAPID703` (`WARNING`): Context conflict detected across sources.
- `RAPID704` (`ERROR`): Context source unreadable.
- `RAPID705` (`ERROR`): Invalid `ContextRequest` or duplicate/invalid source identifiers.

### CLI Surface (`rapid context`)

- `rapid context` (or `rapid context compile`): Compiles and prints the task-relevant context in read-only mode (never writes files, never prompts, never makes network calls).
- `rapid context --mode <mode>`: Selects task mode (`feature`, `bugfix`, `refactor`, `hardening`, `research`, `general`).
- `rapid context --harness <harness>`: Selects target harness (`cursor`, `claude`, `codex`, `vscode`, `antigravity`).
- `rapid context --objective "..."`: Provides task objective for relevance scoring and task header rendering.
- `rapid context --max-chars <n>`: Sets explicit character budget.
- `rapid context --manifest`: Prints human-readable manifest (`SELECTED`, `SKIPPED`, and `CONFLICTS`).
- `rapid context --json`: Emits pure `CompiledContext` JSON (`schema_version = 1`, `manifest`, `content`) to `stdout`.
- `rapid inspect-context` and `compose_project_context()` remain intact for v2 compatibility.
