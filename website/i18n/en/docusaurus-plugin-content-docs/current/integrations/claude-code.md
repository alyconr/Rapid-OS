---
title: Anthropic Claude Code Integration
description: Govern interactive and terminal workflows in Claude Code with Rapid OS v3.
---

# Anthropic Claude Code Integration

Technical guide to governing interactive and terminal workflows in **Claude Code** with **Rapid OS v3**.

## 1. What Claude Code is and how it fits with Rapid OS

Claude Code is Anthropic's command-line development tool for working directly with codebases through editing, search, and command execution tools.

**How they fit together:** Claude Code is the external execution agent. Rapid OS provides the governance framework: it defines the spec in advance, controls architectural risk, and uses deterministic evidence to check that promised work was completed before accepting the task.

## 2. Configure Rapid OS

Rapid OS includes the `claude` profile:
```bash
rapid harness show claude
```

The profile declares `context.consume`, `repository.read`, and `workspace.current` as `supported`. Other capabilities remain `unknown` until explicitly configured for the local project.

## 3. Configure Claude Code

1. Sign in to Claude Code following its official instructions (`claude login`).
2. Grant permissions to run local tests and edit files according to your team's policies.
3. Make sure Claude Code reads `.rapid-os/standards/` to follow project architecture standards.

## Main workflow: shortcuts

The recommended way to work with Claude Code is through `/rapid-<mode>` shortcuts. The [shortcuts guide](../guides/shortcuts.md) covers all nine shortcuts, their workflow, human approval, and common errors.

### Install

```bash
rapid init --shortcuts                                # while initializing the project
rapid shortcuts install --harness claude              # in an initialized project
rapid shortcuts install --harness claude --hooks      # also install hooks (section 6)
```

This generates `.claude/skills/rapid-*/SKILL.md` (the nine shortcuts; see the [skills documentation](https://code.claude.com/docs/en/skills)). After updating Rapid OS, run `rapid shortcuts install` again.

### Start with `/rapid-init` (onboarding)

`/rapid-init` is the project entry point. It guides onboarding (`rapid setup next`), asks about each component's stack, architecture, services, and project documents, and reviews drafts with you before finishing. Then use `/rapid-feature` and the other modes. See [Your First Project](../getting-started/first-project.md).

To make shortcuts available across projects, install them in your user directory (`~/.claude/skills/`). The Rapid OS installer offers this at the end:

```bash
rapid shortcuts install --global --harness claude
```

Shortcuts and hooks run `rapid` from the agent's shell. If it is not on `PATH`, `rapid init` and `rapid doctor` report `RAPID1414` (a warning, not an error). See the [shortcuts guide](../guides/shortcuts.md).

### Invoke

Enter `/rapid-` in Claude Code and select a shortcut, or launch it directly:

```text
/rapid-feature add CSV export to the monthly report
```

- Claude Code is the only harness that runs `` !`rapid next --json` `` before sending the prompt. If it fails, the skill aborts, so `rapid` must be on `PATH`.
- `allowed-tools` pre-approves only `rapid next`, `start`, `check`, `task`, `finish`, and `status`; never `approve` or `abort`.
- `/rapid-approve` uses `disable-model-invocation` and does **not** approve; it gives you the command for your own terminal. Always approve there, not through Claude Code `!` mode (`RAPID1310`).

## Advanced mode (v3 commands)

The v3 commands (`rapid spec`, `rapid run`, `rapid evidence`, `rapid eval`, and others) remain available for CI, debugging, and auditing.

## 4. Governed workflow

1. **Create a spec and run:**
   ```bash
   rapid spec create --id spec-feature --title "New feature" --mode feature --task "T001: Implement feature" --status ready
   rapid context --manifest
   rapid run create --spec spec-feature --harness claude
   ```
2. **Verify and record the baseline:** Save the real test log as `base.log`, register `evidence_baseline.json`, and acknowledge the gate before activating the run:
   ```bash
   python -m unittest discover -s tests -t . > base.log 2>&1
   rapid evidence add --run <run-id> --input evidence_baseline.json
   rapid run gate <run-id> gate.baseline acknowledged
   ```
3. **Instruct Claude Code:** Ask it to read `.rapid-os/specs/spec-feature/spec.json` and `.rapid-os/runs/<run-id>/contract.json`, implement the required changes, and run the test suite.
4. **External execution:** Claude Code edits files and runs `python -m unittest`.
5. **Capture and ingest evidence:** Register changed files (`file_change`), passing tests with the log (`test_result`), workspace state, and final contract review. See the [manual walkthrough](../tutorials/first-governed-project.md#7-evidence-collection) for evidence formats.
   ```bash
   rapid run status <run-id> active
   rapid run task <run-id> T001 in_progress
   rapid evidence add --run <run-id> --input evidence_files.json
   rapid evidence add --run <run-id> --input evidence_tests.json
   rapid evidence add --run <run-id> --input evidence_workspace.json
   rapid evidence add --run <run-id> --input evidence_review.json
   rapid run gate <run-id> gate.tests acknowledged
   rapid run gate <run-id> gate.final-verification acknowledged
   rapid run task <run-id> T001 done
   rapid run status <run-id> finished
   ```
6. **Evaluate:**
   ```bash
   rapid eval run --run <run-id> --write --require-pass
   ```
