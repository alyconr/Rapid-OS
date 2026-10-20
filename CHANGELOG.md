# Changelog

All notable changes to **Rapid OS** are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [Unreleased]

### Added
- Sidecar JSON por stack y topología (`templates/stacks/<id>.json`, `templates/topologies/<id>.json`) y módulo `rapid_os.domain.catalog` que los carga y valida (`RAPID1401`). `default_topology_for_stack` y la compatibilidad de `validate_stack_topology` leen ahora `compatible_topologies` y `default_topology`; el comportamiento de los 5 stacks existentes no cambia. Una plantilla sin sidecar es `RAPID1412` (aviso) y se trata como compatible con todas las topologías excepto `doc-site`.
- Stack `generic`: `rapid init` genera `tech-stack.md` con el lenguaje, gestor de paquetes, framework y testing detectados por el scanner y la regla de seguir las convenciones del repositorio. `infer_stack` lo reconoce por su línea de encabezado exacta (`# TECH STACK: GENERIC`).
- Bancos de preguntas como datos en `templates/setup/` (`docs/{brief,business,data-model,architecture}.json` y `stack-questions.json`), incluidos en sdist y wheel.

- `rapid setup next|show [--json]`: conductor de onboarding puro y de solo lectura (`rapid_os/domain/setup.py`, `rapid_os/orchestration/setup_conductor.py`, `rapid_os/adapters/setup_store.py`). Indica la siguiente decisión (stack, topología, arquetipo, agentes, comando de test, documentos, finish) y deriva el estado del disco en proyectos inicializados antes; nunca escribe, ni `.rapid-os/setup.json`. Códigos `RAPID1406` (estado inválido), `RAPID1413` (subcomando, clave o valor inválido) y, reservado, `RAPID1400` (INFO "Setup válido").

- Documentos del onboarding en el contexto con su procedencia: fuentes `doc.brief`, `doc.business`, `doc.data-model` y `doc.architecture` (solo cuentan con frontmatter `rapid-doc: <id>`), banner de supuestos para borradores sin confirmar, línea "pregunta, no inventes" para docs omitidos, y `doc.business` por encima de `standards/business.md` (`standard.business` pasa a omitido con la razón `superseded by doc.business`). Tipos de fuente aditivos `product` y `data_model`. `rapid validate` emite `RAPID1400`, `RAPID1403`, `RAPID1404`, `RAPID1406`, `RAPID1408` y `RAPID1410`. Página `docs/concepts/project-docs.md`.

- `rapid setup set|stack|doc|finish`: el harness completa el onboarding solo con comandos, y cada uno devuelve el siguiente `SetupAction` en `--json`. `set stack|topology|archetype|agents|test-command` registra la decisión (`RAPID1413` valor inválido, `RAPID1402` stack y topología incompatibles); `stack --custom --file -` guarda el `tech-stack.md` del harness con `Runtime`, `Framework` y `Testing` (`RAPID1409`); `doc <id> --source provided|drafted --file -` escribe `docs/<FILE>.md` con frontmatter (`rapid-doc`, `source`, `status`, `sha256`) y backup, valida secciones y tamaño solo para `drafted` (`RAPID1403`/`RAPID1404` son rechazo, `RAPID1405` un borrador sobre lo aportado por una persona sin `--replace`); `doc <id> --skip|--confirm|--reopen|--from-legacy`; `finish` (`RAPID1407` si quedan decisiones) aplica los estándares y la configuración, regenera los archivos de agente y es idempotente. `resolve_doc` de `business` incluye `legacy_source` cuando hay un `standards/business.md` con contenido y no existe `docs/BUSINESS_RULES.md`. Las escrituras viven en `rapid_os/orchestration/setup_apply.py`, sin `sys.exit`.
- `rapid init --business-file <ruta>` (importa las reglas de negocio como `provided`) y `rapid init --skip-docs`. Con `--yes` y sin ellos los documentos quedan `pending` y `init` termina con `Completa la documentación con /rapid-init o rapid setup next`.
- `RAPID1414` (WARNING): `rapid init` avisa, y `rapid doctor` reporta, que `rapid` no está en el `PATH` cuando hay shortcuts o hooks instalados. No cambia el exit code.

- `/rapid-init [descripción]` (`templates/shortcuts/rapid-init.md`): el agente conduce todo el onboarding con `rapid setup next --json` en bucle hasta `done`, propone con razones, redacta borradores que muestra completos, y solo ejecuta `--confirm` si la persona lo dice explícitamente. Es un shortcut de apoyo (no de modo); `rapid-init` encabeza `SHORTCUT_NAMES`.
- `rapid shortcuts install|list|remove --global --harness <id> [--only <shortcut>]`: instala en la carpeta de skills del usuario (`~/.claude/skills`, `~/.agents/skills`, `~/.cursor/skills`, `~/.gemini/config/skills`), con la documentación oficial citada en el código de cada adaptador. `vscode` no tiene ruta documentada: `--global` da `RAPID1413` y no escribe nada. `--only` limita el comando a un shortcut. `install.sh` e `install.ps1` ofrecen instalar `/rapid-init` global al terminar (solo con terminal interactiva, nunca por defecto).
- `rapid init` sugiere `/rapid-init` (`$rapid-init` en Codex) cuando quedan documentos pendientes.
- `rapid approve` con una tarea en curso imprime, tras `RAPID1014`, `<T> sigue en curso; espera a que el agente ejecute `rapid task done <T>`.` (mismo código y exit).
- Seed del brief: la acción `author_spec` de `rapid next` / `rapid start feature` (sin run ni spec) gana el campo opcional `seed` (`source`, `confirmed`, `stories[]` con todas las historias `- [ ] H001: ...` sin marcar y en orden, `business_doc`, `data_model_doc`), omitido si no hay brief administrado o no quedan historias. `/rapid-feature` propone la historia que conviene empezar y espera confirmación, copia las reglas relevantes de `docs/BUSINESS_RULES.md` a `business_rules` y etiqueta la spec con `story:<id>`; con un id (`H002`) usa esa historia.
- `rapid finish` (veredicto `pass` o `pass_with_waivers`) sugiere `Marca H002 como hecha en docs/PRODUCT_BRIEF.md` cuando la spec lleva el tag `story:H002`; nunca edita el brief (en `--json` la sugerencia va a stderr).
- Stack `python-api` (FastAPI, Pydantic v2, SQLAlchemy 2 async, Alembic, PostgreSQL, pytest + httpx; sin LangChain ni CrewAI), compatible con `fullstack-separated` (por defecto) y `fullstack-baas`. `infer_stack` lo reconoce por `TECH STACK: PYTHON API`. `python-ai` queda solo para «agentes de IA y pipelines de datos».
- Proyecto nuevo (sin código fuente fuera de `docs/` y carpetas ocultas, y sin tests): `rapid start feature` añade como primera tarea `T001: Scaffold mínimo con un test que pase` (las tareas escritas se renumeran para coincidir con los ids del contrato) y crea el contrato sin `gate.baseline`, con el campo opcional `baseline_waived: "empty_repository"` (omitido del contenido canónico y del digest de todos los demás contratos). `rapid start` avisa de la renumeración en el campo opcional `notes` de su salida (`T001→T002`; `Nota: ...` en texto) y `/rapid-feature` se la explica a la persona. `rapid status` y `rapid finish` muestran `Sin baseline: proyecto nuevo`. `bugfix`, `refactor` y `hardening` fallan en un repositorio nuevo con `RAPID1413` (`No hay código que arreglar|refactorizar|endurecer; usa /rapid-feature`). Un repo con código y sin tests conserva la baseline, y `run_baseline` sugiere crear un test que pase o usar `research`.

### Changed
- Los archivos de agente que Rapid OS regenera (`CLAUDE.md`, `AGENTS.md`, `.cursorrules`, `INSTRUCTIONS.md`, `.agent/rules/constitution.md`) ya no dejan `<archivo>.<timestamp>.bak` en la raíz: la copia anterior va a `.rapid-os/backups/`, solo si el contenido cambió, con las 5 más recientes por archivo. `rapid init` y `rapid setup finish` añaden `.rapid-os/backups/` al `.gitignore`.
- Los shortcuts de modo y `rapid-approve` piden aprobación solo cuando `action.kind` es `await_human_approval` (`awaiting_human` lista los gates humanos desde el inicio del run), dan el comando exacto con el id del gate para ejecutarlo en otra terminal y ya no sugieren el prefijo `!`.
- `rapid init` usa el mismo estado y la misma lógica de escritura que `rapid setup` (escribe `.rapid-os/setup.json`). La sección de negocio pasa a ser una por documento (brief, negocio, modelo de datos, arquitectura) con cuatro opciones: importar un archivo, escribirlo en la terminal, dejarlo para el agente u omitirlo; sin entrada adicional el documento queda pendiente. Se elimina el andamiaje `TODO` de `docs/` (`create_optional_docs_scaffold`, `SPECS.md`) y `rapid init` ya no escribe `standards/business.md` ni guarda plantillas de negocio. Corrige que, tras responder que sí a "¿Importar archivo?", una ruta vacía o un directorio daba `Is a directory`: ahora vuelve a preguntar.
- `main` pasa a la versión de desarrollo `3.2.0.dev0`. El release estable sigue siendo `v3.1.0` (rama `release/3.1`); los instaladores y la documentación de instalación siguen apuntando a ese tag.

### Fixed
- `rapid approve` en Windows con stdin redirigido a `NUL` (que reporta `isatty() == True`) ya falla con `RAPID1310` antes de tocar el ledger, en lugar de llegar a `RAPID1014`: `stdin_is_windows_nul()` distingue `NUL` de una consola con `GetConsoleMode`. La aprobación seguía rechazada; cambiaba solo el diagnóstico.
- `rapid finish` ve los cambios en un repositorio sin commits: con `start_head` nulo, `file_change` registra los archivos del índice y los no rastreados menos `start_untracked`, con el mismo filtro de artefactos (`observed_changes(cwd, start_head | None, start_untracked)`). Antes no había evidencia y el veredicto era `UNVERIFIED` en el camino carpeta vacía → feature.
- El harness de un run ya no sale `cursor` en un proyecto con `"tools": ["codex"]`: `detect_harness` usa el único harness soportado de `tools` (fuente `config_tools`); con varios mantiene el fallback `RAPID1300` y el aviso los lista. No se añade marcador de Codex: su documentación oficial solo describe variables propias (`CODEX_HOME`, `CODEX_API_KEY`) y `CODEX_THREAD_ID` aparece únicamente en una discusión de GitHub.
- Acentos perdidos en Windows PowerShell: `/rapid-init` indica escribir el documento en un archivo UTF-8 temporal y usar `--file`; `rapid setup doc --source drafted` rechaza un cuerpo con una letra, `?` y otra letra (`RAPID1415`) y con `provided` solo avisa.
- `rapid setup set` después de `finish` aplica el cambio enseguida y deja `finished=true`, sin reabrir el onboarding. La tarea de scaffold de un repositorio vacío sin `test_command` indica `rapid setup set test-command <cmd>`, y `RAPID1301` de `rapid task done` sugiere ese comando.
- `rapid finish` con veredicto PASS marca en `docs/PRODUCT_BRIEF.md` la historia que cita la spec con el tag `story:<ID>` (solo esa línea; backup en `.rapid-os/backups/`; `source`, `status` y borrador intactos). `rapid finish --no-tick` conserva la sugerencia. `/rapid-feature` pide el tag `story:<ID>`.
- La evidencia `file_change` (capability `repository.write`) ya no cuenta artefactos de herramientas: `rapid finish` ignora rutas con un segmento `__pycache__`, `.pytest_cache`, `.mypy_cache`, `.ruff_cache`, `.tox`, `.nox`, `node_modules`, `.venv` o `venv`, y archivos `*.pyc`, `*.pyo`, `.coverage` y `.coverage.*`, aunque el proyecto no tenga `.gitignore`. Antes, correr los tests dejaba `__pycache__` y una tarea sin cambios reales salía `pass`; ahora, sin cambios, no se registra `file_change` y el veredicto no es `pass`. `rapid init` y `rapid setup finish` añaden `__pycache__/`, `*.pyc` y `.pytest_cache/` a un `.gitignore` existente (nunca lo crean). La lógica de diff + untracked + filtros vive en una sola función (`observed_changes`), compartida con la lista de untracked del inicio del run.
- `rapid init` sugería `python -m unittest discover` como comando de test en repositorios JavaScript con una carpeta `tests/`. Ahora una sola función (`propose_test_command`) la usan `init` y `setup`: `npm test` si `package.json` tiene `scripts.test`, pytest si se detecta, y `unittest discover` solo en proyectos Python con carpeta de tests; si no, ninguna sugerencia.
- Corrección de comportamiento: `rapid init --yes` sin sugerencia del scanner ya no elige `web-modern` (Next.js) sino `generic`.

---

## [3.1.1] - 2026-10-19

### Fixed
- Stable installers now put a real `rapid` executable on `PATH` instead of a shell alias (`install.sh`) or a PowerShell profile function (`install.ps1`). Shortcuts and Claude Code hooks run `rapid` from the agent's non-interactive shell (Git Bash on Windows), which sees neither, and failed with `rapid: command not found`. `install.sh` installs into `~/.rapid-os/.venv` and links `~/.local/bin/rapid`; `install.ps1` installs into `$HOME\.rapid-os\.venv` and puts `rapid.exe` in `$HOME\.rapid-os\bin` on the user `PATH`. Both remove the alias or function left by earlier installers (with a `.rapid-os.bak` backup).
- Installation docs and troubleshooting explain that shortcuts and hooks need `rapid` on `PATH`.

---

## [3.1.0] - 2026-10-18

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
