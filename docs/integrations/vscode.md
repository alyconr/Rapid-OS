# Visual Studio Code Integration

Technical guide to governing development environments in **Visual Studio Code** and GitHub Copilot with **RAPID OS v3**.

---

## 1. What it is and how it fits with RAPID OS

Visual Studio Code is the widely adopted standard code editor, offering integrated terminals, debugging panels, and AI extensions such as GitHub Copilot Chat.

**Fit with RAPID OS:**
The developer works in VS Code, using the integrated terminal to run `rapid` commands and Copilot Chat to assist with writing code. RAPID OS guarantees that every change has a traceable contract and verifiable test evidence.

---

## 2. Configuration in RAPID OS

RAPID OS includes the built-in `vscode` profile:

```bash
rapid harness show vscode
```

Canonical output:
- `context.consume`: `supported`
- `repository.read`: `supported`
- `workspace.current`: `supported`
- Execution and write capabilities: configurable depending on the local extensions installed.

---

## 3. Configuration in VS Code

1. Open the repository in VS Code.
2. Open the integrated terminal (`Ctrl+\`` or `Cmd+\``).
3. Make sure the Python virtual environment is selected in the status bar.

---

## Main workflow: shortcuts

The recommended way to work with VS Code and Copilot is with the `/rapid-<mode>` shortcuts. The 9 shortcuts, the loop they follow, human approval, and common errors are in the [shortcuts guide](../guides/shortcuts.md).

### Install

```bash
rapid init --shortcuts                                # when initializing the project
rapid shortcuts install --harness vscode              # in an already initialized project
```

It generates `.github/prompts/rapid-*.prompt.md` (the 9 shortcuts as *prompt files*; [documentation](https://code.visualstudio.com/docs/copilot/customization/prompt-files)). After updating Rapid OS, run `rapid shortcuts install` again.

### First step: `/rapid-init` (onboarding)

The entry point of a project is `/rapid-init`: it drives the onboarding (`rapid setup next`), asks you for the stack of each component, the architecture, the services, and the documents, and reviews the drafts with you before closing. After that you use `/rapid-feature` and the other modes. See [First project](../getting-started/first-project.md).

`--global` does not exist for VS Code: there is no documented user folder for *prompt files* for this use, so `rapid shortcuts install --global --harness vscode` fails with `RAPID1413` and writes nothing. Install `/rapid-init` in each project with `rapid shortcuts install --harness vscode`.

The shortcuts and hooks run `rapid` from the agent's shell: if it is not on the `PATH`, `rapid init` and `rapid doctor` warn with `RAPID1414` (a warning, not an error). See the [shortcuts guide](../guides/shortcuts.md).

### Invoke

In the Chat view, type `/` followed by the name (or use the **Chat: Run Prompt** command):

```text
/rapid-feature añadir exportación CSV al informe mensual
```

- `/rapid-approve` **does not approve**: it gives you the command to run in the integrated terminal. `rapid approve` requires an interactive terminal of your own and fails with `RAPID1310` if an agent launches it.
- VS Code also reads skills from `.claude/skills/` and `.agents/skills/`. If you use VS Code together with Claude Code, Codex, or Antigravity, see [how to combine harnesses](../guides/shortcuts.md#if-you-combine-harnesses) before adding `vscode` to the installation.

---

## Advanced mode (v3 commands)

The v3 commands (`rapid spec`, `rapid run`, `rapid evidence`, `rapid eval`…) remain available for CI, debugging, and auditing, and you do not need to run them by hand in day-to-day work either. Section 4 keeps the complete manual workflow.

## 4. Workflow in VS Code

1. **Run creation:**
In the integrated terminal:
```bash
rapid run create --spec <spec-id> --harness vscode
```

2. **Verify the Baseline:**
Run the initial tests, saving the authentic log as an artifact (`base.log`), record the baseline evidence (as in [`evidence_baseline.json`](../tutorials/first-governed-project.md#1-record-baseline-evidence-and-acknowledge-gatebaseline)), and acknowledge `gate.baseline` before activating the run:
```bash
python -m unittest discover -s tests -t . > base.log 2>&1
rapid evidence add --run <run-id> --input evidence_baseline.json
rapid run gate <run-id> gate.baseline acknowledged
rapid run status <run-id> active
rapid run task <run-id> T001 in_progress
```

3. **Assistance with Copilot Chat:**
In Copilot Chat, use `#file:.rapid-os/runs/<run-id>/contract.json` to focus the model on the task's objectives and constraints.

4. **Running Tests:**
Run the test suite from the terminal or through VS Code's testing panel.

5. **Recording Evidence:**
Use the RAPID OS CLI in the terminal to record progress (see details and schemas in the [Under the Hood lab](../tutorials/first-governed-project.md#7-evidence-collection)):
- [`evidence_files.json`](../tutorials/first-governed-project.md#3-record-code-change-evidence-file_change): file modification (`file_change`).
- [`evidence_test_result.json`](../tutorials/first-governed-project.md#4-record-passing-test-evidence-test_result): test result with a log artifact (`test_result`).
- [`evidence_workspace.json`](../tutorials/first-governed-project.md#5-record-workspace-evidence-workspace): current workspace (`workspace.current`).
- [`evidence_review.json`](../tutorials/first-governed-project.md#6-record-final-review-evidence-review): approved final contractual review (`review`).

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

6. **Final Evaluation:**
```bash
rapid eval run --run <run-id> --write --require-pass
```
