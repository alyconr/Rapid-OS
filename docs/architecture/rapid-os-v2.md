# Rapid OS v2 Architecture Migration

## Summary

Issue #6 starts the Rapid OS v2 migration with extraction, not a rewrite. The CLI keeps the same command names and file outputs, while reusable logic moves out of the historical `rapid.py` monolith into a small package structure that can be tested independently.

`rapid.py` remains the compatibility entrypoint because the existing install scripts and user aliases execute it directly. It now delegates to the package CLI and re-exports compatibility constants/functions for existing import users.

## Package Responsibilities

- `rapid_os.cli` owns argparse setup, command dispatch, and the current command workflows.
- `rapid_os.core.paths` resolves runtime paths, including source-local templates before installed templates.
- `rapid_os.core.config` loads and saves `.rapid-os/config.json` with the same defaults and fallback behavior.
- `rapid_os.core.filesystem` contains reusable filesystem/process helpers such as timestamped backups and `npx` detection.
- `rapid_os.core.context` composes standards and visual context in the existing priority order.
- `rapid_os.core.output` contains shared CLI output helpers.
- `rapid_os.domain.agents` writes generated context files for Cursor, Claude, Antigravity, and VS Code.
- `rapid_os.adapters` is intentionally empty in this PR and reserved for future first-class adapter work.

The package modules avoid command execution on import. Console UTF-8 setup happens when the CLI entrypoint runs, so importing reusable helpers remains lightweight for tests and future integrations.

## Compatibility Guarantees

- Existing commands remain available: `init`, `skill`, `mcp`, `scope`, `deploy`, `vision`, `refine`, `guide`, and the current `prompt` command.
- Existing aliases that call `python rapid.py` continue to work.
- Existing import users can still read common compatibility constants from `rapid.py`, including `SCRIPT_DIR`, `TEMPLATES_DIR`, `CURRENT_DIR`, `PROJECT_RAPID_DIR`, and `CONFIG_FILE`.
- Generated files remain in their current locations: `.cursorrules`, `CLAUDE.md`, `.agent/rules/constitution.md`, `INSTRUCTIONS.md`, `claude_desktop_config.json`, `SPECS.md`, `DEPLOY.md`, and `references/VISION_CONTEXT.md`.
- Project config remains `.rapid-os/config.json`.
- Template discovery still prefers a source checkout `templates/` directory and falls back to `~/.rapid-os/templates`.

## Intentionally Unchanged

This PR does not introduce first-class Codex support, redesign MCP generation, redesign scope/spec workflows, add validation commands, change install scripts, or create a full agent adapter system.

Some command workflows still live in `rapid_os.cli.main` because moving them wholesale into new abstractions would be a larger behavior-changing rewrite. The priority here is to isolate reusable logic first, then migrate command domains incrementally.

## Remaining Migration Work

The next PR should introduce an explicit agent adapter interface and move Cursor, Claude, Antigravity, VS Code, and future Codex behavior behind it. After that, command flows can be split further by domain once the adapter boundary is stable.
