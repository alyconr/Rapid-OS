# Rapid OS v3.0.0 Release Notes

**Release Version**: `3.0.0`  
**Artifact Schema Version**: `1` (`BehavioralRuleset` version `1`)  
**Python Requirement**: Python `>=3.10` (Standard Library Only)

---

## 1. Overview

**Rapid OS v3.0.0** evolves Rapid OS from a static context template generator (v1/v2) into a **Contract-Driven Engineering OS for AI Coding Harnesses**.

While preserving full backward compatibility with all Rapid OS v2 commands (`rapid init`, `rapid scope`, `rapid skill`, `rapid mcp`, `rapid vision`, `rapid deploy`, `rapid refine`, `rapid inspect-context`, `rapid validate`, `rapid doctor`), Rapid OS v3 introduces an end-to-end, deterministic, offline governance loop across six architectural phases.

---

## 2. What's Included in v3.0.0

### Phase 0 — Hardening Foundation
- Strict path containment (`ensure_path_within_root`, `resolve_child_path`, `safe_rmtree_child`) preventing symlink escapes and path traversal.
- Atomic UTF-8 file writes (`safe_write_text`, `safe_copy_file`) with `.bak` backup protection where appropriate and append-only immutability for v3 registries.
- Safe subprocess boundary (`shell=False` enforced for optional `npx skills` integration; zero subprocess calls across v3 governance registries and evaluators).

### Phase 1 — Project Intelligence (`rapid scan`)
- Canonical `ProjectModel`, `ProjectFact`, `Evidence`, `Confidence`, and `SourceType` in `rapid_os.domain.project`.
- Deterministic repository detectors (`rapid_os.domain.scanner`) with secret-safe `.env` key inspection (`read_env_keys()` never reads secret values).
- Optional `.rapid-os/project.json` snapshot persistence (`rapid scan --write`) and `RAPID600–RAPID604` validation.

### Phase 2 — Context Compiler (`rapid context`)
- Task-aware `ContextCompiler`, `ContextResolver`, `ContextSourceLoader`, and `ContextManifest` (`rapid_os.domain.context`).
- Deterministic 14-tier source precedence hierarchy, character budget enforcement (`--max-chars`) with non-truncation guarantee for required sources, and structural conflict detection across selected fragments.
- `RAPID700–RAPID705` diagnostics and read-only CLI (`rapid context [compile] --mode ... --harness ... --spec ... --manifest --json`).

### Phase 3 — Spec Registry (`rapid spec`)
- Multi-spec authoring registry under `.rapid-os/specs/<spec-id>/` with `SpecRecord` (`spec.json`) and immutable `SpecRevision` directories (`revisions/0001/`, `0002/`, ...).
- Lifecycle management (`draft`, `ready`, `archived`), SHA-256 artifact digest verification (`requirements.md`, `tasks.md`, `acceptance.md`), legacy export (`rapid spec export-legacy`), and `RAPID800–RAPID809` validation.

### Phase 4 — Execution Policy Engine & Run Contract (`rapid policy` & `rapid run`)
- Deterministic `ExecutionPolicy` (`.rapid-os/policy.json` or default) and `ExecutionPolicyEvaluator` producing `PolicyDecision` (`ExecutionClass`, `RiskLevel`, `WorkspaceRequirement`, `GateRequirement`).
- Immutable `ExecutionContract` (`contract.json`), `context.md`, `context-manifest.json`, and append-only `RunState` ledger (`states/0001.json` .. `000N.json`) under `.rapid-os/runs/<run-id>/`.
- Strict pre-execution and post-execution phase boundary enforcement and `RAPID1000–RAPID1014` validation.

### Phase 5 — Harness Capability Registry (`rapid harness`)
- Canonical 11-capability catalog (`CANONICAL_CAPABILITY_DEFINITIONS`) across 8 categories.
- Conservative built-in `HarnessProfile` definitions (`codex`, `claude`, `cursor`, `vscode`, `antigravity`) and full-replacement project overrides in `.rapid-os/harnesses/<id>.json`.
- Deterministic `CapabilityRequirementResolver`, `CapabilityResolver` (`compatible`, `incompatible`, `unresolved`), `.rapid-os/capabilities.lock`, and `RAPID1100–RAPID1112` validation.

### Phase 6 — Evidence Engine & Behavioral Evals (`rapid evidence` & `rapid eval`)
- Append-only `EvidenceRegistry` under `.rapid-os/evidence/<run-id>/` storing immutable `RunEvidence` records (`records/E001.json`, ...) and SHA-256/size-verified copied files (`artifacts/E001/`, ...).
- Deterministic offline `BehavioralEvaluator` and append-only `EvalRegistry` under `.rapid-os/evals/<run-id>/reports/` with mandatory semantic replay verification (`RAPID1223`).
- Strict separation between gate declarations (`ACKNOWLEDGED`), waivers (`WAIVED`), missing proof (`UNVERIFIED`), and verified evidence (`PASS`, `PASS_WITH_WAIVERS`, `FAIL`), backed by `RAPID1200–RAPID1229` diagnostics.

### Release Hardening & Packaging
- PEP 517/518 packaging via `pyproject.toml` and `MANIFEST.in` with `rapid` console script entrypoint (`rapid_os.cli.main:main`) and bundled package templates (`importlib.resources` fallback when installed as a wheel outside a repo checkout).
- Global `rapid --version` (`Rapid OS 3.0.0`), updated `rapid guide`, comprehensive `--help` descriptions, hardened `install.sh` and `install.ps1`, and end-to-end governance/tampering/wheel test suites.

---

## 3. CLI Summary

```text
rapid --version
rapid --help
rapid guide
rapid init
rapid scan
rapid spec       (create | list | show | revise | status | export-legacy)
rapid context    ([compile] --mode ... --spec ... --harness ... --manifest --json)
rapid policy     (show | init)
rapid run        (create | list | show | status | task | gate)
rapid harness    (list | show | init | lock | resolve)
rapid evidence   (list | show | add | verify)
rapid eval       (run | list | show)
rapid validate   ([--strict] [--json])
rapid doctor     ([--json])
rapid inspect-context
rapid scope
rapid skill
rapid mcp
rapid vision
rapid deploy
rapid refine
rapid prompt
```

---

## 4. Compatibility & Upgrade Notes

- **Zero Breaking Changes to v2 Workflows**: Existing projects using `.rapid-os/config.json`, `.rapid-os/standards/`, `SPECS.md`, `TASKS.md`, `ACCEPTANCE.md`, and `python rapid.py` continue to work without modification.
- **No Network or External Runtime Dependencies**: Rapid OS v3.0.0 uses only the Python 3.10+ standard library.
- **Independent Schema Versioning**: Package version is `3.0.0`, while all v3 JSON schemas remain at `schema_version = 1`.
