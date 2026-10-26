---
title: Verify the Installation
description: Official commands for checking that Rapid OS is installed and working correctly.
---

# Verify the Installation

After installing Rapid OS, run these commands to confirm that the CLI responds and your environment is ready to govern projects.

## 1. Product version (`rapid --version`)

Check the installed version:

```bash
rapid --version
```

**Expected output:**
```text
Rapid OS 3.1.1
```

If the command does not respond or says the command was not found, see the [troubleshooting guide](../troubleshooting/installation.md).

## 2. General help (`rapid --help`)

Confirm that the argument parser and main subcommands are available:

```bash
rapid --help
```

**Expected output:** A list describing Rapid OS and the available commands (`init`, `scan`, `context`, `spec`, `policy`, `run`, `harness`, `evidence`, `eval`, `validate`, `doctor`, `guide`, and others).

## 3. Workflow overview (`rapid guide`)

Rapid OS includes a read-only interactive guide to the governance loop's eight steps:

```bash
rapid guide
```

**Expected output:** A visual terminal summary of the v3 governance loop that identifies which commands are **read-only** and which **write state**.

## 4. Environment diagnostics (`rapid doctor`)

Inspect the environment configuration, template locations, and available tools:

```bash
rapid doctor
```

**Expected output:**
```text
==> Rapid OS Doctor

Configuration:
  Project config: .rapid-os/config.json (Not found - run 'rapid init')
  Rapid home:     /home/<user>/.rapid-os

Environment:
  Node.js:        Available (v20.x.x)  # or Not installed (optional)
  npx:            Available            # or Not installed (optional)
  Python:         3.12.x

Templates:
  Bundled:        Available (stacks, archetypes, topologies)

Status: OK (Warnings: 0, Errors: 0)
```

:::note A missing project config is normal here
If you run `rapid doctor` outside a project initialized with Rapid OS, it is normal to see `Project config: .rapid-os/config.json (Not found - run 'rapid init')`. This only means the current directory does not have active governance yet.
:::

## 5. Installed shortcuts (`rapid shortcuts list`)

Inside a project where you ran `rapid init --shortcuts` (or `rapid shortcuts install`), check the status of each generated file:

```bash
rapid shortcuts list
```

**Expected output:** Your harness shortcuts should have the `installed` status. If one is `outdated` after a Rapid OS update, run `rapid shortcuts install`; if it is `missing`, install it. Use `--json` to get the same status for scripts. If you selected Cursor or VS Code alongside Claude, Codex, or Antigravity, you may see `WARNING RAPID1321`: this is only a warning about overlapping directories (see [Combining harnesses](../guides/shortcuts.md#if-you-combine-harnesses)).

## 6. Diagnostics inside a project (`rapid doctor`)

After initializing a project, `rapid doctor` also checks the porcelain layer. These warnings can be expected and do not indicate an installation failure:

- **`RAPID1319`**: The process tree could not be read, so `rapid approve` cannot check whether an agent launched it. Approval still requires an interactive terminal.
- **`RAPID1414`**: Shortcuts or hooks are installed, but `rapid` is not on the PATH used by the agent's shell. This is a warning (exit 0), not an error. Install Rapid OS with the installer or `pipx install git+https://github.com/alyconr/Rapid-OS.git`, then launch the agent from a terminal where `rapid --version` works. Global `/rapid-init` is checked the same way: the skill runs `rapid` from that shell.
- **`RAPID1339`**: Claude Code hooks are installed, but Claude Code cannot resolve `rapid` on its PATH. Install Rapid OS where Claude Code can find it (for example, with `pipx install git+https://github.com/alyconr/Rapid-OS.git`) or add its scripts directory to PATH. This warning does not appear if you do not use hooks.

## All set

If the commands succeeded, your installation is working and reproducible. Continue to [Getting Started](../getting-started.md) or the tutorial [Your First Governed Project](../getting-started/first-project.md).
