# Rapid OS v2 Architecture (Historical Reference)

> **Historical Architecture Document**: This document describes the **Rapid OS v2** architecture baseline (`v2.0.0`), which remains backward-compatible inside Rapid OS v3. For the current **Rapid OS v3 (`v3.0.0`)** architecture—including Project Intelligence, Context Compiler, Spec Registry, Execution Policy & Runs, Harness Capability Registry, and Evidence Engine & Behavioral Evals—see [rapid-os-v3.md](rapid-os-v3.md).

## Summary

Rapid OS v2 established the modular package baseline. It keeps the legacy CLI commands, project config, generated file outputs, and `rapid.py` compatibility entrypoint while moving reusable behavior behind package, domain, adapter, scanner, validation, MCP, and testing boundaries.

`rapid.py` remains the compatibility entrypoint alongside the `rapid` console script (`rapid_os.cli.main:main`). It delegates to the package CLI and re-exports compatibility constants/functions for existing import users.

## Completed v2 Scope

- Core package refactor without a big-bang rewrite.
- Agent adapter architecture for generated context files.
- First-class, opt-in Codex support through `AGENTS.md`.
- Structured scope/spec generation through `SPECS.md`, `TASKS.md`, and `ACCEPTANCE.md`.
- Validation and diagnostics commands for local project health.
- Project scanner for safer, reviewable `rapid init` suggestions.
- MCP abstraction layer with a Claude Desktop renderer.
- Automated unittest and CLI smoke-check workflow in GitHub Actions.

## Package Responsibilities

- `rapid_os.cli` owns argparse setup, command dispatch, and the current command workflows.
- `rapid_os.core.paths` resolves runtime paths, including source-local templates before installed templates.
- `rapid_os.core.config` loads, inspects, and saves `.rapid-os/config.json` with explicit configuration state classification (`missing`, `valid`, `invalid_json`, `invalid_schema`, `io_error`) while preserving default fallback behavior for normal missing configs.
- `rapid_os.core.filesystem` contains reusable filesystem helpers including path containment (`ensure_path_within_root`, `resolve_child_path`, `safe_rmtree_child`), timestamped backups, atomic UTF-8 file writes (`safe_write_text`, `safe_copy_file`, `safe_append_text`), and `npx` detection.
- `rapid_os.core.process` provides safe subprocess execution (`run_command`, `run_npx_skills_add`, `resolve_npx_executable`, `is_npx_available`) with `shell=False` enforced and explicit Windows `npx.cmd` resolution.
- `rapid_os.core.identifiers` validates local slug identifiers (`validate_identifier`) separately from remote package references (`validate_remote_package_reference`).
- `rapid_os.core.context` composes standards and visual context in the existing priority order.
- `rapid_os.core.output` contains shared CLI output helpers.
- `rapid_os.domain.agents` is now a compatibility facade for the existing generation helpers.
- `rapid_os.domain.scope` renders and writes structured spec-driven development artifacts for `rapid scope`.
- `rapid_os.domain.validation` returns pure diagnostics for templates, project standards, config/tool references, stack/topology consistency, and composed context inspection.
- `rapid_os.domain.project` defines the canonical v3 Phase 1 Project Intelligence Model (`Confidence`, `SourceType`, `Evidence`, `ProjectFact`, `ProjectModel`, and `normalize_facts`). See [rapid-os-v3.md](rapid-os-v3.md) for the v3 architecture.
- `rapid_os.domain.scanner` detects project characteristics (`build_project_model`, `scan_project`), keeps `ProjectScan` as a zero-duplicate-state compatibility facade over `ProjectModel`, returns reviewable init suggestions without printing, prompting, writing files, or mutating project choices, and inspects `.env` / `.env.*` variable names via `read_env_keys()` without reading secret values.
- `rapid_os.adapters.project_snapshot` persists and reads optional `.rapid-os/project.json` snapshots via `safe_write_text(..., backup=True)` when explicitly requested (`rapid scan --write`).
- `rapid_os.domain.mcp` models MCP servers (including `package` and `version`), generation plans, and non-blocking warnings independently from output formats.
- `rapid_os.adapters.mcp` renders MCP models into concrete output formats, currently the existing Claude Desktop JSON shape and editor-specific MCP destinations.
- `rapid_os.adapters.agents` owns the agent adapter contract, default registry, and implementations for Cursor, Claude, Antigravity, VS Code, and Codex.

The package modules avoid command execution on import. Console UTF-8 setup happens when the CLI entrypoint runs, so importing reusable helpers remains lightweight for tests and future integrations.

## Agent Adapter Architecture

Agent-specific project context generation now flows through `AgentAdapter` implementations. Each adapter declares:

- A stable tool id matching `.rapid-os/config.json`, such as `cursor` or `claude`.
- Generated output files through `AgentOutput`.
- Rendering behavior for the context payload.
- Activation and placement behavior through the base `activate()` flow, including parent directory creation, backup creation, UTF-8 writes, and the existing success messages.
- Optional metadata for user-facing or future orchestration needs.

The default registry preserves the previous generation order for existing agents: Cursor, Claude, Antigravity, then VS Code. Codex is registered after those adapters. Unknown tool ids remain ignored during context generation, which keeps research tool config entries such as `context7` and `firecrawl` compatible with the existing project config shape.

Supported adapters in v2:

- Cursor: `.cursorrules`
- Claude Code: `CLAUDE.md`
- Google Antigravity: `.agent/rules/constitution.md`
- VS Code / Copilot: `INSTRUCTIONS.md`
- Codex: `AGENTS.md`

Codex support is project-scoped and opt-in. Selecting `codex` writes `AGENTS.md` at the project root with the composed Rapid OS context. Rapid OS v2 does not generate `AGENTS.override.md`, global Codex configuration, or nested Codex instruction files.

## Scope Artifact Workflow

`rapid scope` is a structured spec generator. The command remains interactive and keeps `SPECS.md` as the primary artifact, while also writing `TASKS.md` and `ACCEPTANCE.md`.

The scope workflow collects initiative details, mode, business objective, problem statement, scope boundaries, actors, main flow, edge cases, business rules, technical constraints, affected modules, data impact, acceptance criteria, testing strategy, and implementation tasks. Supported modes are `new feature`, `refactor`, `bugfix`, and `legacy hardening`.

Scope rendering is deterministic and local. Rapid OS does not infer tasks or acceptance criteria with AI in this workflow. Blank fields are rendered as `_Not specified._`, and comma- or semicolon-separated answers become Markdown lists or checklists. Existing `SPECS.md`, `TASKS.md`, and `ACCEPTANCE.md` files are backed up before being overwritten.

## Validation and Diagnostics

Validation is an additive diagnostics layer. The validation service returns `Diagnostic` entries with `info`, `warning`, and `error` levels plus stable diagnostic codes. The domain module does not print, exit, or write files; the CLI owns rendering and process exit behavior.

New commands:

- `rapid validate` checks templates, project standards, config/tool ids, adapter render contracts, stack/topology consistency, and the assembled project context before generation. It supports `--json` and `--strict`.
- `rapid doctor` reports resolved paths, template health, optional Node/npx availability, and project checks when the current directory already contains `.rapid-os/`. It supports `--json`.
- `rapid inspect-context` composes the final context using the same context assembly path as generation, then prints included sections, selected tools, and a preview. It supports `--json` and `--summary`.

Exit codes are intentionally simple: `0` means no validation errors, `1` means validation errors were found, and `--strict` makes warnings fail with `1` too. `inspect-context` does not render agent-specific previews in v2.

## Project Scanner

The bounded project scanner supports safer initialization. It detects probable language, framework, package manager, Docker presence, testing framework, monorepo signals, database hints, and deployment provider hints from local project files. It does not perform network calls, install dependencies, write files, or update `.rapid-os/config.json`.

`rapid init` runs the scanner by default before stack/topology selection. The CLI prints a compact summary and suggested init choices, then asks for confirmation. Suggestions are applied only after the user accepts them. If the user rejects suggestions, if evidence is mixed, or if no confident suggestion exists, `rapid init` falls back to the existing manual menus.

The scanner suggests stack and topology in v2. `rapid init --no-scan` preserves the manual initialization flow, and `rapid init --stack <name>` remains authoritative over scanner stack suggestions.

## MCP Abstraction

The MCP workflow now uses a reusable model and renderer boundary. `rapid_os.domain.mcp` builds a structured `McpConfig` from topology content, selected tools, current project paths, and existing MCP templates. It supports the current server ids: `filesystem`, `postgres`, `supabase`, `context7`, and `firecrawl`.

Rendering is handled outside the domain model. `rapid_os.adapters.mcp` now resolves editor-specific MCP targets and renders editor-specific config formats: Codex TOML with `mcp_servers`, Claude/Cursor JSON with `mcpServers`, VS Code JSON with `servers`, and a conservative Antigravity JSON shape. The CLI remains the facade responsible for reading project files, printing warnings, creating backups, and writing the rendered output.

Unresolved placeholders, missing key hints, and unpinned package/image references (`MCP012`, `MCP013`) are warnings, not hard failures. This preserves the current editable starter-config behavior while making the generation plan reusable and auditable for future MCP destinations.

## Hardening Foundation (v2)

The v2 foundation includes shared security, correctness, and reproducibility primitives:

- `rapid_os.core.process`: Safe subprocess execution (`run_command`, `run_npx_skills_add`, `resolve_npx_executable`, `is_npx_available`) that rejects `shell=True`, passes user arguments as literal list items, and resolves `npx.cmd` on Windows vs `npx` on POSIX.
- `rapid_os.core.identifiers`: Dedicated validation for local slug identifiers (`validate_identifier`) versus remote package references (`validate_remote_package_reference`), preventing path traversal or option injection while preserving `owner/package`, `@scope/pkg`, and `pkg@version` inputs.
- `rapid_os.core.filesystem`: Path containment helpers (`ensure_path_within_root`, `resolve_child_path`, `safe_rmtree_child`) and atomic UTF-8 write primitives (`safe_write_text`, `safe_copy_file`, `safe_append_text`) with optional `.bak` backups and parent creation.
- `rapid_os.core.config`: Explicit configuration state classification (`missing`, `valid`, `invalid_json`, `invalid_schema`, `io_error`) via `inspect_project_config_file()` and `ProjectConfigError`, surfaced in `rapid validate`, `rapid doctor`, and `rapid inspect-context`.
- `rapid_os.domain.scanner`: Secret-safe `.env` / `.env.*` inspection via `read_env_keys(path)` that extracts only variable names and never stores, matches, or exposes secret values.
- `rapid_os.domain.mcp`: Explicit `package` and `version` metadata on `McpServer` plus non-blocking reproducibility warnings (`MCP012` for unpinned `npx` packages, `MCP013` for unpinned Docker images).

## Branch Governance

- `main` is the active primary branch and authoritative baseline for Rapid OS v2 and future work.
- `develop` (`origin/develop` at `fbe2e12`) is 29 commits behind `main` (`0` ahead) and is considered obsolete historical branch state. All feature and hardening branches must branch from and target `main`.

## Compatibility Guarantees

- Existing commands remain available: `init`, `skill`, `mcp`, `scope`, `deploy`, `vision`, `refine`, `guide`, the current `prompt` command, and the additive diagnostics commands `validate`, `doctor`, and `inspect-context`.
- Existing aliases that call `python rapid.py` continue to work.
- Existing import users can still read common compatibility constants from `rapid.py`, including `SCRIPT_DIR`, `TEMPLATES_DIR`, `CURRENT_DIR`, `PROJECT_RAPID_DIR`, and `CONFIG_FILE`.
- Existing import users can still call `generate_cursor_rules`, `generate_claude_config`, `generate_antigravity_config`, and `generate_vscode_instructions`; those helpers now delegate to adapters.
- Generated files remain in their current locations for agent instructions and docs: `.cursorrules`, `CLAUDE.md`, `.agent/rules/constitution.md`, `INSTRUCTIONS.md`, `AGENTS.md`, `SPECS.md`, `TASKS.md`, `ACCEPTANCE.md`, `DEPLOY.md`, and `references/VISION_CONTEXT.md`. MCP outputs are editor-specific.
- Project config remains `.rapid-os/config.json`.
- Scanner results are not stored in project config.
- Missing project config still defaults to Cursor, Claude, Antigravity, and VS Code only; Codex must be explicitly selected or added to `tools`.
- `rapid mcp` now writes the editor-specific MCP file selected by CLI flags or interactive choice instead of a single shared output path.
- Template discovery still prefers a source checkout `templates/` directory and falls back to `~/.rapid-os/templates`.

## Intentionally Unchanged

Rapid OS v2 does not redesign MCP UX, validation commands, install scripts, generate global Codex config, add agent-specific context previews, or add `AGENTS.override.md`.

Some command workflows still live in `rapid_os.cli.main` because moving them wholesale into new abstractions would be a larger behavior-changing rewrite. The v2 baseline intentionally keeps those flows stable while isolating reusable logic behind package and domain boundaries.

## Potential v2.1 Enhancements

The items below are optional post-v2 improvements, not unfinished v2 requirements. Future Codex work can add Codex-specific skill placement, deeper Codex configuration, or nested instruction-file support. Future scope work can add non-interactive flags or richer templates. Future diagnostics work can add richer machine-readable categories, more formal stack/topology metadata, and agent-specific dry-run previews. Future scanner work can add a standalone scan command, persisted scan metadata, deeper monorepo targeting, or richer framework mappings. Those additions should remain behind the existing boundaries and be introduced in separate PRs.

Command flows can be split further by domain in future v2.1+ work if that can be done without changing user-facing behavior.
