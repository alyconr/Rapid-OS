---
title: Coding Harness Integrations
description: Technical and operational integration guides for Rapid OS v3 and popular AI coding environments.
---

# Coding Harness Integrations

These guides cover technical and operational integration between **Rapid OS v3** and popular AI-assisted coding environments and agents.

## 1. Core principle: declared capabilities versus actual capabilities

In Rapid OS, a harness profile (`HarnessProfile`) models the standard capabilities associated with a tool in a **declarative and conservative** way.

> **Product truth rule:** A built-in profile (`builtin:cursor`, `builtin:codex`, and others) does **not** grant a model magical permissions or guarantee that the local environment can perform an operation. A coding harness can only perform actions the developer has allowed in the terminal, sandbox, or local configuration.

## 2. Canonical capability matrix

Rapid OS evaluates exactly **11 canonical capability identifiers**:

| Canonical ID | Capability | Typical built-in status |
|---|---|---|
| `context.consume` | Harness can read and consume the Context Bundle | `supported` |
| `repository.read` | Read repository files and directories | `supported` |
| `workspace.current` | Operate in the active workspace | `supported` |
| `repository.write` | Modify files on disk | `unknown` (requires local permissions) |
| `shell.execute` | Run commands in the terminal or shell | `unknown` (subject to sandbox and approval) |
| `tests.execute` | Run automated test suites | `unknown` (depends on the local test runner) |
| `git.inspect` | Inspect branches, diffs, and Git status | `unknown` |
| `git.modify` | Create commits or branches, or modify Git state | `unknown` |
| `workspace.isolated` | Work in isolated branches or Git worktrees | `unknown` |
| `mcp.invoke` | Invoke tools through the MCP protocol | `unknown` |
| `subagents.delegate` | Delegate work to subagents | `unknown` |

## 3. Main workflow: shortcuts

The main workflow for any of these harnesses uses `/rapid-<mode>` shortcuts (`$rapid-<mode>` in Codex). Run `rapid init --shortcuts` or `rapid shortcuts install --harness <id>` to generate them for your tool. The agent guides the run (`rapid next` → `rapid start` → `rapid check` → `rapid finish`) and stops when a person needs to act. The v3 commands (`rapid spec`, `rapid run`, `rapid evidence`, `rapid eval`, and others) remain available in **Advanced Mode** for CI, debugging, and auditing. See the [shortcuts guide](../guides/shortcuts.md) for harness locations and invocation details.

## 4. Harness guides

Each guide starts with the main shortcut workflow and retains the advanced mode. Choose your tool:

1. [**OpenAI Codex / CLI**](codex.md): Headless execution workflows and governed scripts.
2. [**Anthropic Claude Code**](claude-code.md): Interactive CLI integration and terminal permissions.
3. [**Cursor IDE**](cursor.md): Composer integration, `.cursorrules` project rules, and context injection.
4. [**Visual Studio Code**](vscode.md): GitHub Copilot Chat, extensions, and integrated terminals.
5. [**Google Antigravity**](antigravity.md): Multi-agent orchestration, autonomous subagents, and advanced sandboxing.
