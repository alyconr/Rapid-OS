# Rapid OS v2 Architecture Migration

## Summary

Issue #6 started the Rapid OS v2 migration with extraction, not a rewrite. Issue #7 adds the first formal adapter boundary for generated agent context files while keeping the same CLI commands, project config, and generated file outputs.

`rapid.py` remains the compatibility entrypoint because the existing install scripts and user aliases execute it directly. It now delegates to the package CLI and re-exports compatibility constants/functions for existing import users.

## Package Responsibilities

- `rapid_os.cli` owns argparse setup, command dispatch, and the current command workflows.
- `rapid_os.core.paths` resolves runtime paths, including source-local templates before installed templates.
- `rapid_os.core.config` loads and saves `.rapid-os/config.json` with the same defaults and fallback behavior.
- `rapid_os.core.filesystem` contains reusable filesystem/process helpers such as timestamped backups and `npx` detection.
- `rapid_os.core.context` composes standards and visual context in the existing priority order.
- `rapid_os.core.output` contains shared CLI output helpers.
- `rapid_os.domain.agents` is now a compatibility facade for the existing generation helpers.
- `rapid_os.adapters.agents` owns the agent adapter contract, default registry, and implementations for Cursor, Claude, Antigravity, and VS Code.

The package modules avoid command execution on import. Console UTF-8 setup happens when the CLI entrypoint runs, so importing reusable helpers remains lightweight for tests and future integrations.

## Agent Adapter Architecture

Agent-specific project context generation now flows through `AgentAdapter` implementations. Each adapter declares:

- A stable tool id matching `.rapid-os/config.json`, such as `cursor` or `claude`.
- Generated output files through `AgentOutput`.
- Rendering behavior for the context payload.
- Activation and placement behavior through the base `activate()` flow, including parent directory creation, backup creation, UTF-8 writes, and the existing success messages.
- Optional metadata for user-facing or future orchestration needs.

The default registry preserves the previous generation order: Cursor, Claude, Antigravity, then VS Code. Unknown tool ids remain ignored during context generation, which keeps research tool config entries such as `context7` and `firecrawl` compatible with the existing project config shape.

Supported adapters in issue #7:

- Cursor: `.cursorrules`
- Claude Code: `CLAUDE.md`
- Google Antigravity: `.agent/rules/constitution.md`
- VS Code / Copilot: `INSTRUCTIONS.md`

## Compatibility Guarantees

- Existing commands remain available: `init`, `skill`, `mcp`, `scope`, `deploy`, `vision`, `refine`, `guide`, and the current `prompt` command.
- Existing aliases that call `python rapid.py` continue to work.
- Existing import users can still read common compatibility constants from `rapid.py`, including `SCRIPT_DIR`, `TEMPLATES_DIR`, `CURRENT_DIR`, `PROJECT_RAPID_DIR`, and `CONFIG_FILE`.
- Existing import users can still call `generate_cursor_rules`, `generate_claude_config`, `generate_antigravity_config`, and `generate_vscode_instructions`; those helpers now delegate to adapters.
- Generated files remain in their current locations: `.cursorrules`, `CLAUDE.md`, `.agent/rules/constitution.md`, `INSTRUCTIONS.md`, `claude_desktop_config.json`, `SPECS.md`, `DEPLOY.md`, and `references/VISION_CONTEXT.md`.
- Project config remains `.rapid-os/config.json`.
- Template discovery still prefers a source checkout `templates/` directory and falls back to `~/.rapid-os/templates`.

## Intentionally Unchanged

This PR does not introduce first-class Codex support, redesign MCP generation, redesign scope/spec workflows, add validation commands, or change install scripts.

Some command workflows still live in `rapid_os.cli.main` because moving them wholesale into new abstractions would be a larger behavior-changing rewrite. The priority here is to isolate reusable logic first, then migrate command domains incrementally.

## Remaining Migration Work

Issue #8 should add first-class Codex support behind the same adapter contract. That work should define Codex output files, activation semantics, skill placement expectations, and any metadata needed by the CLI before adding `codex` to default project configuration.

After Codex is added, command flows can be split further by domain once the adapter boundary is stable.
