# Rapid OS v3 Architecture

## Roadmap Overview

Rapid OS v3 evolves Rapid OS from a static context template generator into a deterministic, provenance-backed engineering intelligence platform for AI coding harnesses.

```text
Phase 0  Hardening Foundation (COMPLETE)
Phase 1  Project Intelligence (CURRENT)
Phase 2  Context Compiler (PLANNED)
Phase 3  Spec Registry v3 (PLANNED)
Phase 4  Execution Policy Engine (PLANNED)
Phase 5  Harness Capability Registry (PLANNED)
Phase 6  Evidence Engine & Evals (PLANNED)
```

> Only Phase 0 and Phase 1 are implemented in the repository today. Phases 2–6 are documented strictly as planned architecture targets.

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
- `Evidence` entries are deduplicated and sorted by `(path, reason, source_type, detector)`.
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

- `rapid scan`: Runs local detectors and prints a human-readable summary of detected categories, values, confidence levels, and init suggestions without writing any files.
- `rapid scan --verbose`: Includes per-fact detector IDs and evidence paths/reasons in the human-readable output.
- `rapid scan --json`: Emits only the serialized `ProjectModel` JSON to `stdout` (no banners or decorative text) for machine consumption.
- `rapid scan --write`: Persists the canonical `ProjectModel` snapshot to `.rapid-os/project.json` with atomic write and `.bak` backup protection.
- `rapid scan --json --write`: Writes `.rapid-os/project.json` and emits the exact same JSON document to `stdout`.
