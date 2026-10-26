---
title: Shortcuts by Harness
description: Install and use /rapid-<mode> commands in supported coding harnesses, including human approval and troubleshooting.
---

# Shortcuts by Harness

**Shortcuts** are the primary Rapid OS workflow. Start with `/rapid-init`: your agent guides project onboarding with `rapid setup` (stack, topology, archetype, agents, test command, and documents). Then use a mode-specific command such as `/rapid-feature` to complete work inside a governed run. You describe the goal; the shortcut guides the agent through `rapid next` → `rapid start` → `rapid check` → `rapid finish` and pauses when a human decision is needed.

The v3 commands (`rapid spec`, `rapid run`, `rapid evidence`, `rapid eval`, and others) remain available as **Advanced Mode** for CI, debugging, and auditing. See the [CLI reference](/cli) and the manual workflow in each [mode guide](/guides/modes/).

Install shortcuts once for all your projects (the installer offers this at the end; replace `claude` with your harness):

```bash
rapid shortcuts install --global --harness claude
```

In VS Code, or if you prefer to version shortcuts with the repository, install them in the project with `rapid init --shortcuts`. Then use your agent:

```text
/rapid-init billing API for small businesses, in Python   # in Codex: $rapid-init
/rapid-feature add CSV export to the monthly report
```

:::note `rapid` must be on PATH
Shortcuts and hooks invoke `rapid` from the agent's shell. If it cannot be resolved, `rapid init` and `rapid doctor` report `RAPID1414` (this is a warning, not an error). Install using the installer or `pipx install git+https://github.com/alyconr/Rapid-OS.git`.
:::

## Installation

```bash
rapid init --shortcuts
rapid shortcuts install
rapid shortcuts install --harness claude --harness codex
rapid shortcuts install --harness claude --hooks
rapid shortcuts install --harness claude --dry-run
rapid shortcuts install --harness claude --only rapid-init
rapid shortcuts install --global --harness claude
rapid shortcuts list
rapid shortcuts remove --harness codex
```

Without `--harness`, supported harnesses listed under `tools` in `.rapid-os/config.json` are used. In a project without that file, provide `--harness` (`RAPID1312`). Generated files contain a marker; `remove` deletes only marked files. Installation is idempotent and backs up changed files. Hooks are not installed unless requested with `--hooks`.

### User-wide installation (`--global`)

`rapid shortcuts install --global --harness <id> [--only rapid-init]` writes shortcuts to the harness's documented user skills folder, making them available across projects. It requires `--harness`, does not read a project configuration, and does not support `--hooks`. `vscode` is not supported globally (`RAPID1413`) because its documentation does not specify a stable user-level path.

| Harness | User directory |
| --- | --- |
| `claude` | `~/.claude/skills/<name>/SKILL.md` |
| `codex` | `~/.agents/skills/<name>/SKILL.md` |
| `cursor` | `~/.cursor/skills/<name>/SKILL.md` |
| `antigravity` | `~/.gemini/config/skills/<name>/SKILL.md` |
| `vscode` | Not supported globally |

After upgrading Rapid OS, run `rapid shortcuts list` to find outdated shortcuts, then `rapid shortcuts install` to update them. Consider versioning project shortcuts so the team shares the same workflow.

## Harness locations and invocation

| Harness | Generated location | Invocation |
| --- | --- | --- |
| Claude Code | `.claude/skills/<name>/SKILL.md` | `/rapid-init`, `/rapid-feature ...` |
| Codex | `.agents/skills/<name>/SKILL.md` | `$rapid-init`, `$rapid-feature ...`, or select from `/skills` |
| Antigravity | `.agents/skills/<name>/SKILL.md` | `/rapid-feature ...` |
| Cursor | `.cursor/skills/<name>/SKILL.md` | `/rapid-feature ...` in Agent chat |
| VS Code / Copilot | `.github/prompts/<name>.prompt.md` | `/rapid-feature ...` in chat |

Claude Code alone runs the `rapid next --json` context command before sending the prompt and supports Rapid OS hooks. Other harnesses are instructed to run the command themselves. For the mode-specific shortcuts and their arguments, see the [engineering modes guide](/guides/modes/).
