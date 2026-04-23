# Rapid OS v2 Architecture

## Summary

Rapid OS v2 is the current completed architecture baseline. It keeps the existing CLI commands, project config, generated file outputs, and `rapid.py` compatibility entrypoint while moving reusable behavior behind package, domain, adapter, scanner, validation, MCP, and testing boundaries.

`rapid.py` remains the compatibility entrypoint because the existing install scripts and user aliases execute it directly. It now delegates to the package CLI and re-exports compatibility constants/functions for existing import users.

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
- `rapid_os.core.config` loads and saves `.rapid-os/config.json` with the same defaults and fallback behavior.
- `rapid_os.core.filesystem` contains reusable filesystem/process helpers such as timestamped backups and `npx` detection.
- `rapid_os.core.context` composes standards and visual context in the existing priority order.
- `rapid_os.core.output` contains shared CLI output helpers.
- `rapid_os.domain.agents` is now a compatibility facade for the existing generation helpers.
- `rapid_os.domain.scope` renders and writes structured spec-driven development artifacts for `rapid scope`.
- `rapid_os.domain.validation` returns pure diagnostics for templates, project standards, config/tool references, stack/topology consistency, and composed context inspection.
- `rapid_os.domain.scanner` detects project characteristics and returns reviewable init suggestions without printing, prompting, writing files, or mutating project choices.
- `rapid_os.domain.mcp` models MCP servers, generation plans, and non-blocking warnings independently from output formats.
- `rapid_os.adapters.mcp` renders MCP models into concrete output formats, currently the existing Claude Desktop JSON shape.
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

Unresolved placeholders and missing key hints are warnings, not hard failures. This preserves the current editable starter-config behavior while making the generation plan reusable for future MCP destinations.

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
