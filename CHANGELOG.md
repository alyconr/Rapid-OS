# Changelog

All notable changes to **Rapid OS** are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [Unreleased]

### Added
- Sidecar JSON por stack y topología (`templates/stacks/<id>.json`, `templates/topologies/<id>.json`) y módulo `rapid_os.domain.catalog` que los carga y valida (`RAPID1401`). `default_topology_for_stack` y la compatibilidad de `validate_stack_topology` leen ahora `compatible_topologies` y `default_topology`; el comportamiento de los 5 stacks existentes no cambia. Una plantilla sin sidecar es `RAPID1412` (aviso) y se trata como compatible con todas las topologías excepto `doc-site`.
- Stack `generic`: `rapid init` genera `tech-stack.md` con el lenguaje, gestor de paquetes, framework y testing detectados por el scanner y la regla de seguir las convenciones del repositorio. `infer_stack` lo reconoce por su línea de encabezado exacta (`# TECH STACK: GENERIC`).
- Bancos de preguntas como datos en `templates/setup/` (`docs/{brief,business,data-model,architecture}.json` y `stack-questions.json`), incluidos en sdist y wheel.

- `rapid setup next|show [--json]`: conductor de onboarding puro y de solo lectura (`rapid_os/domain/setup.py`, `rapid_os/orchestration/setup_conductor.py`, `rapid_os/adapters/setup_store.py`). Indica la siguiente decisión (stack, topología, arquetipo, agentes, comando de test, documentos, finish) y deriva el estado del disco en proyectos inicializados antes; nunca escribe, ni `.rapid-os/setup.json`. Códigos `RAPID1401` (subcomando faltante), `RAPID1406` y, reservado, `RAPID1400` (INFO "Setup válido").

### Fixed
- `rapid init` sugería `python -m unittest discover` como comando de test en repositorios JavaScript con una carpeta `tests/`. Ahora una sola función (`propose_test_command`) la usan `init` y `setup`: `npm test` si `package.json` tiene `scripts.test`, pytest si se detecta, y `unittest discover` solo en proyectos Python con carpeta de tests; si no, ninguna sugerencia.
- Corrección de comportamiento: `rapid init --yes` sin sugerencia del scanner ya no elige `web-modern` (Next.js) sino `generic`.

---

## [3.1.0] - 2026-10-16

### Added
- **Porcelain layer**: `rapid start`, `rapid next`, `rapid check`, `rapid task`, `rapid attach`, `rapid finish`, `rapid approve`, `rapid status` and `rapid abort` drive a governed run on top of the v3 plumbing. A pure Conductor (`next_action`) asks the `BehavioralEvaluator` what is missing and returns a `NextAction`; the active run lives in `.rapid-os/session.json`. Evidence producers: `rapid:check`, `rapid:start`, `rapid:finish`, `rapid:attach`.
- **Behavioral ruleset v2**: `rapid check --expect fail --task <id>` records an expected failure (`expectation: "fail"`) that produces a `reproduction.<task>` assertion and does not count as a failing task or gate evidence (`RAPID1320`); review evidence produced by a `harness:*` producer cannot close a human gate.
- **Five engineering modes** with playbooks in `templates/modes/`: `feature`, `bugfix` (baseline before the red test, `check --expect fail` on `T001`), `refactor` (blocked when passing tests drop below the baseline), `hardening` (isolated git worktree with `rapid start --worktree`) and `research` (`rapid attach`, no mandatory tests).
- **Shortcuts**: `rapid shortcuts install|list|remove` and `rapid init --shortcuts` generate eight `/rapid-<mode>` shortcuts (`rapid-feature`, `-bugfix`, `-refactor`, `-hardening`, `-research`, `-next`, `-status`, `-approve`) for Claude Code, Codex, Antigravity, Cursor and VS Code from `templates/shortcuts/`, idempotent and with `.bak` backups (`RAPID1311`–`RAPID1318`). A `RAPID1321` warning flags harness selections that leave the same shortcut in two folders one tool reads.
- **Claude Code hooks**: `rapid hook stop|pre-tool` keep the agent working until a person is needed and deny reserved commands (`rapid approve`, `rapid abort`, `rapid run gate`, `rapid evidence add`) and edits inside `.rapid-os/`; installed with `rapid shortcuts install --hooks` or `rapid init --hooks` (`RAPID1337`–`RAPID1339`).
- `rapid approve` without arguments lists pending human gates; `--waive` (waivable gates only) and `--reject` (review outcome `changes_requested`) with `--reason`; `--reviewer` defaults to `git config user.name` (`RAPID1330`–`RAPID1336`).
- `docs/architecture/orchestration.md` and `docs/guides/shortcuts.md`.

### Changed
- **`rapid approve` hardened**: it requires a TTY, refuses `CLAUDE_CODE_CHILD_SESSION=1` and, new, refuses when any ancestor process is Claude Code (`RAPID1310`; `RAPID1319` in `rapid doctor` when the ancestry cannot be read). The ancestry check is best-effort: a process that detaches from its parent (double fork, `setsid`, `nohup … &`), a renamed `claude.exe` or a reused pid escape it. The rule is unchanged: a person approves in their own terminal.
- **Shortcuts JSON contract**: in `rapid shortcuts install --json` and `list --json`, `warnings` is a list of homogeneous objects `{code, message, ...}` (`RAPID1315`, `RAPID1316`, `RAPID1321`); the loose text warnings of `install --json` became objects with the same text in `message`.
- Package version is `3.1.0`; the installers and the installation docs resolve the `v3.1.0` tag.
- `rapid finish` on a run that already ended exits `0` only when the stored verdict is `pass` or `pass_with_waivers` and records no new evidence; a run without a report exits `1` with `already ended (<outcome>)`.
- Product boundaries now state what is executed: the plumbing runs nothing; the porcelain runs only the `test_command` of `.rapid-os/config.json` or the argv given to `rapid check`, creates a worktree only with `rapid start --worktree`, and never invokes agents or approves human gates.
- Documentation presents the shortcuts as the main flow and the v3 commands as advanced mode; new "Shortcuts y orquestación" sidebar category and navbar entry; the unused `site/` Docusaurus template was removed.

### Fixed
- `rapid finish` text mode no longer fails with `AttributeError` and prints the report revision and verdict.
- Runs without a baseline gate (low-risk spikes) and isolated runs could never leave `prepared`.
- `rapid finish` no longer attributes to the run the untracked files that existed before `rapid start`.
- `rapid init --yes` without a scanner suggestion no longer picks the alphabetically first topology (`doc-site`) for every stack: the default topology is coherent with the stack (`doc-site` only with `docs-modern`, and `docs-modern` always with `doc-site`), so `rapid validate` no longer fails with `RAPID402`/`RAPID403`.
- `rapid init` (also with `--yes`) creates `.rapid-os/standards/security.md` from a minimal template when it does not exist, so `rapid start hardening` can create the run; the `RAPID1004` message now names the missing file and how to create it.
- `rapid start --spec-file` reuses a spec with the same identity and content when a previous start failed after creating it; with different content it exits with `RAPID1322` and suggests `rapid start <mode> --spec <id>` instead of an error without guidance.
- The `feature` playbook's `author_spec` instruction now says `rapid start <modo> --spec-file -` instead of `rapid spec create`.
- `rapid next` returns `blocked` with `rapid start --resume --worktree` when the contract requires an isolated workspace and the session has no worktree yet, like `rapid start`.
- `rapid start` and `rapid approve` report expected failures (a missing context source, a closed stdin) with a RAPID code instead of a traceback.

### Security & Hardening
- Defense in depth around human approval: TTY, session marker, process ancestry, typed confirmation, optional Claude Code hooks (including a guard against clearing the session variables) and `user`-only review evidence. These are best-effort controls, not cryptographic attestation.

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
