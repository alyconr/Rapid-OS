---
title: Getting Started
description: Start in three steps (install, /rapid-init, /rapid-feature), explore this section, and find the advanced v3 command walkthrough.
---

# Getting Started with Rapid OS

Rapid OS governs work by your coding agent: every change happens within a **run** with a spec, tasks, gates, and verifiable evidence. You do not need to learn those commands; the agent runs them through **shortcuts** (`/rapid-...`). In your terminal, you only install and approve.

## 1. Start in three steps

You need Python 3.10+, Git, and a coding agent: Claude Code, Codex, Cursor, Antigravity, or VS Code (Copilot).

### Step 1: Install

Use the installer for your system ([Linux](./installation/linux.md), [macOS](./installation/macos.md), [Windows](./installation/windows.md), or [WSL](./installation/wsl.md)). At the end, it asks which agents should receive shortcuts; enter yours (for example, `claude`) to make them available across projects. If you skipped that step, run this once:

```bash
rapid shortcuts install --global --harness claude
```

:::note VS Code and earlier versions
VS Code has no user directory for shortcuts, so install them in each project with `rapid init --shortcuts`. Do the same if your Rapid OS version does not yet include `/rapid-init` or `--global` (check `rapid shortcuts install --help`).
:::

### Step 2: Describe the project with `/rapid-init`

Open your agent in the project folder (new or existing) and enter:

```text
/rapid-init a Python API for validating usernames
```

The agent proposes the stack, test command, and project documents (brief, business rules, data model, and architecture), one decision at a time. For each document, you can provide it, have the agent draft it, or skip it. Agent-written content remains a **draft** until you confirm it. In Codex, enter `$rapid-init`.

### Step 3: Request the work

```text
/rapid-feature add CSV export to the monthly report
```

The agent drafts the spec, implements it task by task, and runs the tests. When a person needs to act, it stops and gives you the exact command for **your** terminal, for example:

```bash
rapid approve gate.final-verification
```

Then enter `/rapid-next` in the agent to close the run. No shortcut approves anything on your behalf. See [When the Agent Stops](./getting-started/when-the-agent-stops.md) for what to do at each pause.

| You want to... | Enter in your agent |
|---|---|
| Build a new feature | `/rapid-feature <goal>` |
| Fix a bug | `/rapid-bugfix <what is broken>` |
| Refactor without breaking tests | `/rapid-refactor <scope>` |
| Harden security | `/rapid-hardening <area>` |
| Investigate an option | `/rapid-research <question>` |
| Check progress or continue | `/rapid-status` · `/rapid-next` |
| See what needs approval | `/rapid-approve` |

See the [shortcuts guide](./guides/shortcuts.md) for shortcut locations and invocation in each agent.

## 2. Section map

Read these pages in order; each takes a few minutes.

| Page | What you will learn |
|---|---|
| [1. Your First Project](./getting-started/first-project.md) | Go from an empty folder to your first approved feature. |
| [2. An Existing Project](./getting-started/existing-project.md) | Use Rapid OS in a coded repository without changing business code during setup. |
| [3. When the Agent Stops](./getting-started/when-the-agent-stops.md) | Approve, reject, check progress, cancel, and read the verdict. |
| [4. Writing the Spec](./getting-started/first-spec.md) | What the agent asks to draft a spec and how to make a good request. |
| [5. What the Agent Knows About Your Project](./getting-started/first-context.md) | Where its rules come from, drafts versus confirmed content, and how to change them. |
| [6. Next Steps](./getting-started/next-steps.md) | Labs, choosing a mode, teamwork, and troubleshooting. |

Also see the [shortcuts guide](./guides/shortcuts.md), [hands-on labs](./tutorials/index.md), [CLI reference](./cli.md), and [diagnostics](./troubleshooting/diagnostics.md).

## Advanced mode

You do not need this to use Rapid OS. The v3 commands (`rapid spec`, `rapid run`, `rapid evidence`, `rapid eval`, and others) let you do manually what the agent does with shortcuts; they are useful for CI, debugging, and auditing. See **How It Works**:

- [v3 Governance Loop](./governance-loop.md): What each step records and why.
- [Manual Walkthrough](./tutorials/first-governed-project.md): A complete project done manually, from `rapid init` to the verdict.
