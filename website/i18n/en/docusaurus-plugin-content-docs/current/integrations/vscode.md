---
title: Visual Studio Code Integration
description: Govern Visual Studio Code and GitHub Copilot workflows with Rapid OS v3.
---

# Visual Studio Code Integration

Technical guide to governing development environments in **Visual Studio Code** and GitHub Copilot with **Rapid OS v3**.

## 1. What VS Code is and how it fits with Rapid OS

Visual Studio Code is a widely used code editor with integrated terminals, debugging panels, and AI extensions such as GitHub Copilot Chat.

**How they fit together:** Developers work in VS Code, using its integrated terminal to run `rapid` commands and Copilot Chat to help write code. Rapid OS gives each change a traceable contract and verifiable test evidence.

## 2. Configure Rapid OS

Rapid OS includes a built-in `vscode` profile:

```bash
rapid harness show vscode
```

Canonical declarations:
- `context.consume`: `supported`
- `repository.read`: `supported`
- `workspace.current`: `supported`
- Execution and write capabilities: configurable based on locally installed extensions.

## 3. Configure VS Code

1. Open the repository in VS Code.
2. Open the integrated terminal (`Ctrl+\`` or `Cmd+\``).
3. Make sure the Python virtual environment is selected in the status bar.

## Main workflow: shortcuts

The recommended way to work with VS Code and Copilot is through `/rapid-<mode>` shortcuts. The [shortcuts guide](../guides/shortcuts.md) covers all nine shortcuts, their workflow, human approval, and common errors.

### Install

```bash
rapid init --shortcuts                                # while initializing the project
rapid shortcuts install --harness vscode              # in an initialized project
```

This generates `.github/prompts/rapid-*.prompt.md` (the nine shortcuts as prompt files; see the [prompt files documentation](https://code.visualstudio.com/docs/copilot/customization/prompt-files)). After updating Rapid OS, run `rapid shortcuts install` again.

### Start with `/rapid-init` (onboarding)

`/rapid-init` is the project entry point. It guides onboarding (`rapid setup next`), asks about each component's stack, architecture, services, and project documents, and reviews drafts with you before finishing. Then use `/rapid-feature` and the other modes. See [Your First Project](../getting-started/first-project.md).

VS Code does not support `--global`: there is no documented user directory for prompt files used this way. Therefore `rapid shortcuts install --global --harness vscode` returns `RAPID1413` and writes nothing. Install `/rapid-init` in each project with `rapid shortcuts install --harness vscode`.

Shortcuts and hooks run `rapid` from the agent's shell. If it is not on `PATH`, `rapid init` and `rapid doctor` report `RAPID1414` (a warning, not an error). See the [shortcuts guide](../guides/shortcuts.md).

### Invoke

In the Chat view, type `/` followed by the shortcut name (or use **Chat: Run Prompt**):

```text
/rapid-feature add CSV export to the monthly report
```

- `/rapid-approve` does **not** approve anything; it gives you the command to run in the integrated terminal. `rapid approve` requires your interactive terminal and returns `RAPID1310` if an agent launches it.
- VS Code also reads skills from `.claude/skills/` and `.agents/skills/`. If you use VS Code with Claude Code, Codex, or Antigravity, see [Combining harnesses](../guides/shortcuts.md#combining-harnesses) before adding `vscode` to the installation.

## Advanced mode (v3 commands)

The v3 commands (`rapid spec`, `rapid run`, `rapid evidence`, `rapid eval`, and others) remain available for CI, debugging, and auditing.

## 4. Workflow in VS Code

1. **Create a run** in the integrated terminal:
   ```bash
   rapid run create --spec <spec-id> --harness vscode
   ```
2. **Verify the baseline:** Run the initial tests and save the log as `base.log`. Register baseline evidence with `evidence_baseline.json`, acknowledge `gate.baseline`, then activate the run:
   ```bash
   python -m unittest discover -s tests -t . > base.log 2>&1
   rapid evidence add --run <run-id> --input evidence_baseline.json
   rapid run gate <run-id> gate.baseline acknowledged
   rapid run status <run-id> active
   rapid run task <run-id> T001 in_progress
   ```
3. **Use Copilot Chat:** In Copilot Chat, use `#file:.rapid-os/runs/<run-id>/contract.json` to focus the model on the task goals and constraints.
4. **Run the tests:** Use the terminal or VS Code's testing panel.
5. **Register evidence:** Use the Rapid OS CLI in the terminal to record changed files, test results with a log, the current workspace, and final contract review. See the [manual walkthrough](../tutorials/first-governed-project.md#7-evidence-collection) for details and schemas.
   ```bash
   rapid evidence add --run <run-id> --input evidence_files.json
   rapid evidence add --run <run-id> --input evidence_test_result.json
   rapid evidence add --run <run-id> --input evidence_workspace.json
   rapid evidence add --run <run-id> --input evidence_review.json
   rapid run gate <run-id> gate.tests acknowledged
   rapid run gate <run-id> gate.final-verification acknowledged
   rapid run task <run-id> T001 done
   rapid run status <run-id> finished
   ```
6. **Final evaluation:**
   ```bash
   rapid eval run --run <run-id> --write --require-pass
   ```
