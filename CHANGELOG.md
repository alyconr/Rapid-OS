# Changelog

All notable changes to **Rapid OS** are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [3.0.0] - 2026-10-08

### Added
- **Phase 1 — Project Intelligence (`rapid scan`)**:
  - Canonical `ProjectModel`, `ProjectFact`, `Evidence`, `Confidence`, and `SourceType` domain entities (`rapid_os.domain.project`).
  - Deterministic local repository detectors (`rapid_os.domain.scanner`) for languages, frameworks, package managers, databases, testing frameworks, Docker, monorepos, and deployment targets.
  - Optional `.rapid-os/project.json` snapshot persistence (`rapid scan --write`) and `RAPID600–RAPID604` validation diagnostics.
- **Phase 2 — Context Compiler (`rapid context`)**:
  - Task-aware `ContextCompiler`, `ContextResolver`, `ContextSourceLoader`, `ContextManifest`, and `CompiledContext` (`rapid_os.domain.context`, `rapid_os.adapters.context_sources`).
  - 14-level source precedence hierarchy, character budget enforcement (`--max-chars`) with non-truncation guarantee for required sources, conflict detection across selected sources, and `RAPID700–RAPID705` diagnostics.
- **Phase 3 — Spec Registry (`rapid spec`)**:
  - Multi-spec registry in `.rapid-os/specs/<spec-id>/` with `SpecRecord` (`spec.json`), authoring lifecycle (`draft`, `ready`, `archived`), and immutable `SpecRevision` snapshots (`revisions/0001/`, ...) with SHA-256 artifact digests (`requirements.md`, `tasks.md`, `acceptance.md`).
  - CLI commands `rapid spec create|list|show|revise|status|export-legacy`, `rapid scope --register`, and `RAPID800–RAPID809` validation diagnostics.
- **Phase 4 — Execution Policy Engine & Run Contract (`rapid policy` & `rapid run`)**:
  - Deterministic `ExecutionPolicy` (`.rapid-os/policy.json`) and `ExecutionPolicyEvaluator` producing `PolicyDecision` (`ExecutionClass`, `RiskLevel`, `WorkspaceRequirement`, `GateRequirement`).
  - Immutable `ExecutionContract` (`contract.json`), compiled context snapshots, and append-only `RunState` ledger (`states/0001.json` .. `000N.json`) under `.rapid-os/runs/<run-id>/`.
  - CLI commands `rapid policy show|init` and `rapid run create|list|show|status|task|gate`, plus `RAPID1000–RAPID1014` validation diagnostics.
- **Phase 5 — Harness Capability Registry (`rapid harness`)**:
  - Canonical 11-capability catalog (`CANONICAL_CAPABILITY_DEFINITIONS`) across 8 categories, conservative built-in `HarnessProfile` definitions, and full-replacement project overrides in `.rapid-os/harnesses/<id>.json`.
  - `CapabilityRequirementResolver`, `CapabilityResolver` (`compatible`, `incompatible`, `unresolved`), `.rapid-os/capabilities.lock`, CLI commands `rapid harness list|show|init|lock|resolve`, and `RAPID1100–RAPID1112` diagnostics.
- **Phase 6 — Evidence Engine & Behavioral Evals (`rapid evidence` & `rapid eval`)**:
  - Append-only `EvidenceRegistry` under `.rapid-os/evidence/<run-id>/` storing immutable `RunEvidence` records (`records/E001.json`, ...) and SHA-256/size-verified copied artifacts (`artifacts/E001/`, ...).
  - Deterministic offline `BehavioralEvaluator` (`BehavioralRuleset` v1) and append-only `EvalRegistry` under `.rapid-os/evals/<run-id>/reports/` with mandatory semantic replay verification (`RAPID1223`).
  - CLI commands `rapid evidence list|show|add|verify` and `rapid eval run|list|show`, plus `RAPID1200–RAPID1229` diagnostics.
- **Packaging, Versioning & Release Readiness**:
  - PEP 517/518 `pyproject.toml` and `MANIFEST.in` providing the `rapid` console script entrypoint (`rapid_os.cli.main:main`) and bundled templates for wheel installations.
  - Global `rapid --version` flag outputting `Rapid OS 3.0.0`.
  - End-to-end governance loop, negative `UNVERIFIED` gate enforcement, cross-layer tampering defense-in-depth, CLI/docs Product Truth contract, and packaged template resolution test suite (`tests/test_v3_release_readiness.py`).

### Changed
- Updated `rapid guide` to present the 8-step Rapid OS v3 governance loop alongside read-only vs. state-writing command classifications.
- Enhanced `--help` descriptions across `rapid` and all v3 subcommands (`spec`, `policy`, `run`, `harness`, `evidence`, `eval`) to indicate read-only vs. write behavior.
- Improved `resolve_paths()` in `rapid_os.core.paths` to fall back to packaged `rapid_os.templates` resources when installed via wheel outside a repository checkout.
- Updated `install.sh` and `install.ps1` to pin stable installations to the `v3.0.0` tag (`git fetch --tags --force origin` and `git checkout --detach v3.0.0`) with `.git` repository verification and safe path quoting.

### Fixed
- Removed obsolete legacy harness constant/import in `rapid_os.domain.context` and `rapid_os.domain.execution` in favor of canonical `BUILTIN_HARNESS_IDS` and `validate_harness_id()`.
- Removed ghost CLI flags/commands (`--root`, `rapid update`, unsupported `rapid init` flags) from `docs/cli.md` so documentation matches the exact CLI parser.
- Clarified `RAPID1110`, `RAPID1209`, `RAPID1211`, `RAPID1225`, and `RAPID1226` diagnostic and CLI error messages with actionable remediation guidance.

### Security & Hardening
- Enforced strict path containment (`ensure_path_within_root`, `resolve_child_path`), symlink rejection, secret-value filtering in evidence payloads and `.env` scanning, atomic writes, crash-orphan detection (`RAPID1209` / `RAPID1211`), and mandatory semantic replay of persisted evaluation reports (`RAPID1223`).

### Documentation
- Added `docs/getting-started.md`, `docs/governance-loop.md`, `docs/release-v3.0.0.md`, `docs/release-checklist.md`, and `CHANGELOG.md`.
- Updated `README.md`, `docs/cli.md`, `docs/architecture/rapid-os-v3.md`, and marked `docs/architecture/rapid-os-v2.md` as historical reference.

---

## [2.0.0] - 2026-03-15

### Added
- Modular package architecture (`rapid_os.cli`, `rapid_os.core`, `rapid_os.domain`, `rapid_os.adapters`) with `rapid.py` compatibility entrypoint.
- Agent adapter registry supporting Cursor (`.cursorrules`), Claude Code (`CLAUDE.md`), Google Antigravity (`.agent/rules/constitution.md`), VS Code (`INSTRUCTIONS.md`), and Codex (`AGENTS.md`).
- Structured scope artifact workflow (`rapid scope` generating `SPECS.md`, `TASKS.md`, and `ACCEPTANCE.md`).
- Project validation and diagnostics (`rapid validate`, `rapid doctor`, `rapid inspect-context`).
- Initial project scanner for `rapid init` suggestions and structured multi-editor MCP configuration (`rapid mcp`).
