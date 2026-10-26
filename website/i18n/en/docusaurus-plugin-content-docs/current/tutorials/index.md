---
title: Rapid OS Hands-on Labs
description: Small, dependency-free Python projects for practicing each Rapid OS engineering mode.
---

# Rapid OS Hands-on Labs

Each lab is a small example project (Python, no dependencies) paired with an engineering mode. Every lab follows the same four steps:

1. **Prepare the example:** copy the `starter` folder and make a commit.
2. Run **`/rapid-init`** in your agent and accept its proposals.
3. Run **`/rapid-<mode>`** with the lab goal; the agent does the work.
4. Run **`rapid approve`** in your terminal when prompted, then use `/rapid-next` to close the run.

You do not need to learn any other commands. If you do not have shortcuts yet, install them once with `rapid shortcuts install --global --harness claude` (replace `claude` with your agent). See the [shortcuts guide](../guides/shortcuts.md).

## Choose a lab

| Lab | Shortcut | What you will practice |
|---|---|---|
| [1. Feature](feature-lab.md) | `/rapid-feature` | Add a feature with acceptance criteria and tests. Start here. |
| [2. Bugfix](bugfix-lab.md) | `/rapid-bugfix` | Reproduce a bug with a failing test before fixing it. |
| [3. Refactor](refactor-lab.md) | `/rapid-refactor` | Change structure without reducing the passing test count. |
| [4. Hardening](hardening-lab.md) | `/rapid-hardening` | Improve security in an isolated repository copy with human review. |
| [5. Research](research-lab.md) | `/rapid-research` | Run a spike comparing options and record the findings. |

Examples are in [`examples/`](https://github.com/alyconr/Rapid-OS/tree/main/examples) (also installed at `~/.rapid-os/examples/`). Each contains `starter/` (the starting point) and `solution/` (a reference solution).

## What Rapid OS does and what your agent does

- **Your agent** edits code, runs tests, and drafts the spec.
- **Rapid OS** sets the run rules (tasks, gates, required tests), records evidence of what ran, and returns a verdict. It never approves for you: you approve human gates in your terminal.

## Advanced mode

The labs do not use the v3 commands. To do the work manually (for CI, auditing, or to understand what Rapid OS records at each step), follow the [manual walkthrough](first-governed-project.md), in the **How it works** section.

If anything fails, see [Troubleshooting the labs](../troubleshooting/tutorials.md).
