---
title: Google Antigravity Integration
description: Govern autonomous-agent and multi-agent workflows in Google Antigravity with Rapid OS v3.
---

# Google Antigravity Integration

Technical guide to governing autonomous-agent and multi-agent environments in **Google Antigravity** with **Rapid OS v3**.

## 1. What Antigravity is and how it fits with Rapid OS

Google Antigravity is an AI-assisted development environment designed for advanced pair programming and specialized subagents with access to shell tools, file editing, and MCP protocols.

**How they fit together:** Antigravity is a capable harness that can read, write, run commands, and delegate work to concurrent subagents. Rapid OS provides deterministic governance: immutable contracts, risk gates, and cryptographic verification of evidence produced by agents.

## 2. Configure Rapid OS

Rapid OS includes a built-in `antigravity` profile:

```bash
rapid harness show antigravity
```

Declared capabilities include `context.consume`, `repository.read`, and `workspace.current` as `supported`. `subagents.delegate` is available as a canonical governance capability.

## 3. Configure Antigravity

1. Configure your Antigravity workspace and required MCP servers.
2. Use project rules to instruct the primary agent to check Rapid OS contracts before declaring a task complete.
3. Allow the agent to run tests in controlled terminals.

## Main workflow: shortcuts

The recommended way to work with Antigravity is through `/rapid-<mode>` shortcuts. The [shortcuts guide](../guides/shortcuts.md) covers all nine shortcuts, their workflow, human approval, and common errors.

### Install

```bash
rapid init --shortcuts                                # while initializing the project
rapid shortcuts install --harness antigravity         # in an initialized project
```

This generates `.agents/skills/rapid-*/SKILL.md` (the nine shortcuts; see [Antigravity skills documentation](https://antigravity.google/docs/skills)). Codex uses the same directory, so selecting both writes the files only once. After updating Rapid OS, run `rapid shortcuts install` again.

### Start with `/rapid-init` (onboarding)

`/rapid-init` is the project entry point. It guides onboarding (`rapid setup next`), asks about component stacks, architecture, services, and project documents, and reviews drafts with you before finishing. Then use `/rapid-feature` and the other modes. See [Your First Project](../getting-started/first-project.md).

To make shortcuts available in all projects, install them in your user directory (`~/.gemini/config/skills/`). The Rapid OS installer offers this at the end:

```bash
rapid shortcuts install --global --harness antigravity
```

Shortcuts and hooks run `rapid` from the agent's shell. If it is not on `PATH`, `rapid init` and `rapid doctor` report `RAPID1414` (a warning, not an error). See the [shortcuts guide](../guides/shortcuts.md).

### Invoke

Invoke a shortcut with `/` in chat:

```text
/rapid-feature add CSV export to the monthly report
```

`/rapid-approve` does **not** approve. It shows pending gates and evidence and gives you the command for your terminal. If Antigravity delegates to subagents, the shortcut is still the same; the `rapid next` → `rapid check` → `rapid finish` loop and human approval in your terminal still apply.

## Advanced mode (v3 commands)

The v3 commands (`rapid spec`, `rapid run`, `rapid evidence`, `rapid eval`, and others) remain available for CI, debugging, and auditing. The steps below cover the manual workflow.

## 4. Govern complex tasks with subagents

For large tasks such as refactoring or hardening, Antigravity can invoke subagents:

1. **Create a run:**
   ```bash
   rapid run create --spec spec-complex-refactor --harness antigravity
   ```
2. **Verify the baseline:** Save the initial test log as `base.log`, register `evidence_baseline.json`, acknowledge `gate.baseline`, and activate the run:
   ```bash
   python -m unittest discover -s tests -t . > base.log 2>&1
   rapid evidence add --run <run-id> --input evidence_baseline.json
   rapid run gate <run-id> gate.baseline acknowledged
   rapid run status <run-id> active
   rapid run task <run-id> T001 in_progress
   ```
3. **Record delegation evidence:** If Antigravity delegates a subtask to a specialized agent, record canonical `delegation` evidence with capability `subagents.delegate` and the target and outcome.
4. **Record test evidence:** The agent runs tests in a temporary environment and captures the output as `test_result` evidence.
5. **Evaluate compliance:**
   ```bash
   rapid eval run --run <run-id> --write --require-pass
   ```

The evaluator deterministically checks that all required gates, tasks, and capabilities have been satisfied.
