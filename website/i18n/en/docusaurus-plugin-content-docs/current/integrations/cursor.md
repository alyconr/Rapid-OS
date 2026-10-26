---
title: Cursor IDE Integration
description: Integrate Cursor Composer and workspace rules with Rapid OS v3 governance.
---

# Cursor IDE Integration

Learn how to integrate **Cursor** (Composer and workspace rules) with the deterministic architecture of **Rapid OS v3**.

## 1. What Cursor is and how it fits with Rapid OS

Cursor is a VS Code-based editor optimized for multi-file AI assistance through Composer, contextual chat, and project rules.

**How they fit together:** Cursor provides the editor interface and AI-assisted editing capabilities. Rapid OS governs the technical change lifecycle so the model cannot make unauthorized modifications or close tasks without evidence of real test runs.

## 2. Configure Rapid OS

Rapid OS includes a built-in `cursor` profile:

```bash
rapid harness show cursor
```

It declares native support for consuming context and operating in the editor's current workspace.

## 3. Configure Cursor (`.cursorrules`)

To have Cursor's model follow Rapid OS rules automatically, add a `.cursorrules` file at the project root:

```markdown
# Rapid OS Governance Rules
1. Before starting a task, consult `.rapid-os/specs/` for the requirements.
2. Do not modify files outside the scope of the current execution contract.
3. After changing code, always run the unit tests in the terminal.
4. Do not consider a task complete until you generate and register evidence in Rapid OS.
```

## Main workflow: shortcuts

The recommended way to work with Cursor is to use `/rapid-<mode>` shortcuts. The [shortcuts guide](../guides/shortcuts.md) covers all nine shortcuts, their workflow, human approval, and common errors.

### Install

```bash
rapid init --shortcuts                                # while initializing the project
rapid shortcuts install --harness cursor              # in an initialized project
```

This generates `.cursor/skills/rapid-*/SKILL.md` (the nine shortcuts; see [Cursor skills documentation](https://cursor.com/docs/context/skills)). After updating Rapid OS, run `rapid shortcuts install` again. `.cursorrules` continues to provide project rules.

### Start with `/rapid-init` (onboarding)

`/rapid-init` is the project entry point. It guides onboarding (`rapid setup next`), asks about each component's stack, architecture, services, and project documents, and reviews drafts with you before finishing. Then use `/rapid-feature` and the other modes. See [Your First Project](../getting-started/first-project.md).

To make `/rapid-init` and the other shortcuts available across projects, install them in your user directory (`~/.cursor/skills/`). The Rapid OS installer offers this at the end:

```bash
rapid shortcuts install --global --harness cursor
```

Shortcuts and hooks run `rapid` from the agent's shell. If it is not on `PATH`, `rapid init` and `rapid doctor` report `RAPID1414` (a warning, not an error). See the [shortcuts guide](../guides/shortcuts.md).

### Invoke

In the Agent chat, type `/` and search for the shortcut:

```text
/rapid-feature add CSV export to the monthly report
```

- `/rapid-approve` uses `disable-model-invocation`, so it is included only when you invoke it. It does **not** approve anything; it gives you the command to run in your terminal (`RAPID1310` if an agent tries to run it).
- Cursor also reads `.agents/skills/` and `.claude/skills/`. If you use Cursor with Claude Code, Codex, or Antigravity, see [Combining harnesses](../guides/shortcuts.md#combining-harnesses) before adding `cursor` to the installation.

## Advanced mode (v3 commands)

The v3 commands (`rapid spec`, `rapid run`, `rapid evidence`, `rapid eval`, and others) remain available for CI, debugging, and auditing. The steps below retain the manual workflow.

## 4. Workflow in Cursor Composer

1. **Create a run:**
   ```bash
   rapid run create --spec <spec-id> --harness cursor
   ```
2. **Verify the baseline:** Run the initial tests and save the log as `base.log`. Register baseline evidence using `evidence_baseline.json`, acknowledge `gate.baseline`, then activate the run:
   ```bash
   python -m unittest discover -s tests -t . > base.log 2>&1
   rapid evidence add --run <run-id> --input evidence_baseline.json
   rapid run gate <run-id> gate.baseline acknowledged
   rapid run status <run-id> active
   rapid run task <run-id> T001 in_progress
   ```
3. **Provide context in Composer:** In Cursor Composer, reference the generated file: `@.rapid-os/runs/<run-id>/contract.json implement task T001 and run the tests.`
4. **Verify the tests:** Confirm that tests pass in Cursor's integrated terminal.
5. **Register evidence:** Use `rapid evidence add` to record changed-file, test, workspace, and final review evidence. See the [manual walkthrough](../tutorials/first-governed-project.md#7-evidence-collection) for the evidence schemas.
   ```bash
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

## 5. Common issues

- **Composer adds unwanted temporary files:** Make sure `.gitignore` excludes temporary files and that only necessary paths are included in `file_change` evidence.
