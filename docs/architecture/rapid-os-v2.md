# Rapid OS v2 Architecture Migration

## Summary

Issue #6 started the Rapid OS v2 migration with extraction, not a rewrite. Issue #7 added the first formal adapter boundary for generated agent context files while keeping the same CLI commands, project config, and generated file outputs. Issue #8 adds first-class Codex support as an opt-in adapter.

`rapid.py` remains the compatibility entrypoint because the existing install scripts and user aliases execute it directly. It now delegates to the package CLI and re-exports compatibility constants/functions for existing import users.

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

Supported adapters after issue #8:

- Cursor: `.cursorrules`
- Claude Code: `CLAUDE.md`
- Google Antigravity: `.agent/rules/constitution.md`
- VS Code / Copilot: `INSTRUCTIONS.md`
- Codex: `AGENTS.md`

Codex support is project-scoped and opt-in. Selecting `codex` writes `AGENTS.md` at the project root with the composed Rapid OS context. Rapid OS does not generate `AGENTS.override.md`, global Codex configuration, or nested Codex instruction files in this migration step.

## Scope Artifact Workflow

Issue #10 upgrades `rapid scope` from a minimal one-file prompt helper into a structured spec generator. The command remains interactive and keeps `SPECS.md` as the primary artifact, while also writing `TASKS.md` and `ACCEPTANCE.md`.

The scope workflow collects initiative details, mode, business objective, problem statement, scope boundaries, actors, main flow, edge cases, business rules, technical constraints, affected modules, data impact, acceptance criteria, testing strategy, and implementation tasks. Supported modes are `new feature`, `refactor`, `bugfix`, and `legacy hardening`.

Scope rendering is deterministic and local. Rapid OS does not infer tasks or acceptance criteria with AI in this workflow. Blank fields are rendered as `_Not specified._`, and comma- or semicolon-separated answers become Markdown lists or checklists. Existing `SPECS.md`, `TASKS.md`, and `ACCEPTANCE.md` files are backed up before being overwritten.

## Validation and Diagnostics

Issue #11 adds validation as an additive diagnostics layer. The validation service returns `Diagnostic` entries with `info`, `warning`, and `error` levels plus stable diagnostic codes. The domain module does not print, exit, or write files; the CLI owns rendering and process exit behavior.

New commands:

- `rapid validate` checks templates, project standards, config/tool ids, adapter render contracts, stack/topology consistency, and the assembled project context before generation. It supports `--json` and `--strict`.
- `rapid doctor` reports resolved paths, template health, optional Node/npx availability, and project checks when the current directory already contains `.rapid-os/`. It supports `--json`.
- `rapid inspect-context` composes the final context using the same context assembly path as generation, then prints included sections, selected tools, and a preview. It supports `--json` and `--summary`.

Exit codes are intentionally simple: `0` means no validation errors, `1` means validation errors were found, and `--strict` makes warnings fail with `1` too. `inspect-context` does not render agent-specific previews in this migration step.

## Compatibility Guarantees

- Existing commands remain available: `init`, `skill`, `mcp`, `scope`, `deploy`, `vision`, `refine`, `guide`, the current `prompt` command, and the additive diagnostics commands `validate`, `doctor`, and `inspect-context`.
- Existing aliases that call `python rapid.py` continue to work.
- Existing import users can still read common compatibility constants from `rapid.py`, including `SCRIPT_DIR`, `TEMPLATES_DIR`, `CURRENT_DIR`, `PROJECT_RAPID_DIR`, and `CONFIG_FILE`.
- Existing import users can still call `generate_cursor_rules`, `generate_claude_config`, `generate_antigravity_config`, and `generate_vscode_instructions`; those helpers now delegate to adapters.
- Generated files remain in their current locations: `.cursorrules`, `CLAUDE.md`, `.agent/rules/constitution.md`, `INSTRUCTIONS.md`, `AGENTS.md`, `claude_desktop_config.json`, `SPECS.md`, `TASKS.md`, `ACCEPTANCE.md`, `DEPLOY.md`, and `references/VISION_CONTEXT.md`.
- Project config remains `.rapid-os/config.json`.
- Missing project config still defaults to Cursor, Claude, Antigravity, and VS Code only; Codex must be explicitly selected or added to `tools`.
- Template discovery still prefers a source checkout `templates/` directory and falls back to `~/.rapid-os/templates`.

## Intentionally Unchanged

This migration does not redesign MCP generation, change install scripts, generate global Codex config, add agent-specific context previews, or add `AGENTS.override.md`.

Some command workflows still live in `rapid_os.cli.main` because moving them wholesale into new abstractions would be a larger behavior-changing rewrite. The priority here is to isolate reusable logic first, then migrate command domains incrementally.

## Remaining Migration Work

Future Codex work can add Codex-specific skill placement, deeper Codex configuration, or nested instruction-file support. Future scope work can add non-interactive flags or richer templates. Future diagnostics work can add richer machine-readable categories, more formal stack/topology metadata, and agent-specific dry-run previews. Those additions should remain behind the existing boundaries and be introduced in separate PRs.

Command flows can be split further by domain once the adapter boundary is stable.
