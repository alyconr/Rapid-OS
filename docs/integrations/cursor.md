# Cursor IDE Integration

Learn how to integrate **Cursor** (Composer and workspace rules) with the deterministic architecture of **RAPID OS v3**.

---

## 1. What Cursor is and how it fits with RAPID OS

Cursor is a code editor forked from VS Code and optimized for multi-file AI assistance through Composer, contextual chat, and project rules.

**How it fits with RAPID OS:**
Cursor provides the user interface and the assisted-editing capabilities in the editor, while RAPID OS governs the lifecycle of the technical change, preventing the model from making unauthorized modifications or closing tasks without evidence of real tests.

---

## 2. Configuration in RAPID OS

The `cursor` profile comes predefined in RAPID OS:

```bash
rapid harness show cursor
```

It declares native support for consuming context and operating in the editor's current workspace.

---

## 3. Configuration in Cursor (`.cursorrules`)

So that the model in Cursor automatically respects the RAPID OS rules, add a `.cursorrules` file at the root of your project:

```markdown
# RAPID OS Governance Rules
1. Before starting any task, consult `.rapid-os/specs/` to learn the requirements.
2. Do not modify files that are not part of the scope of the current execution contract.
3. After modifying code, always run the unit tests in the terminal.
4. Do not consider a task finished without generating and recording the evidence in RAPID OS.
```

---

## Main workflow: shortcuts

The recommended way to work with Cursor is through the `/rapid-<mode>` shortcuts. The 9 shortcuts, the loop they follow, human approval, and common errors are covered in the [shortcuts guide](../guides/shortcuts.md).

### Install

```bash
rapid init --shortcuts                                # when initializing the project
rapid shortcuts install --harness cursor              # in an already initialized project
```

This generates `.cursor/skills/rapid-*/SKILL.md` (the 9 shortcuts; [Cursor skills documentation](https://cursor.com/docs/context/skills)). After updating Rapid OS, run `rapid shortcuts install` again. `.cursorrules` continues to provide the project rules.

### First step: `/rapid-init` (onboarding)

A project's entry point is `/rapid-init`: it drives the onboarding (`rapid setup next`), asks you for the stack of each component, the architecture, the services, and the documents, and reviews the drafts with you before closing. After that you use `/rapid-feature` and the other modes. See [First project](../getting-started/first-project.md).

To have `/rapid-init` and the other shortcuts in all your projects without installing them in each one, install them in your user folder (`~/.cursor/skills/`); the Rapid OS installer asks you about this when it finishes:

```bash
rapid shortcuts install --global --harness cursor
```

Shortcuts and hooks run `rapid` from the agent's shell: if it is not on the `PATH`, `rapid init` and `rapid doctor` warn with `RAPID1414` (a warning, not an error). See the [shortcuts guide](../guides/shortcuts.md).

### Invocation

In the Agent chat, type `/` and search for the shortcut:

```text
/rapid-feature add CSV export to the monthly report
```

- `/rapid-approve` carries `disable-model-invocation`: it is only included if you invoke it yourself. It **does not approve**: it gives you the command to run in your terminal (`RAPID1310` if an agent tries it).
- Cursor also reads `.agents/skills/` and `.claude/skills/`. If you use Cursor together with Claude Code, Codex, or Antigravity, see [how to combine harnesses](../guides/shortcuts.md#if-you-combine-harnesses) before adding `cursor` to the installation.

---

## Advanced mode (v3 commands)

The v3 commands (`rapid spec`, `rapid run`, `rapid evidence`, `rapid eval`…) remain available for CI, debugging, and auditing, and you do not need to use them by hand day to day. Sections 4 and 5 keep the full manual workflow.

## 4. Workflow in Cursor Composer

1. **Create the Run:**
```bash
rapid run create --spec <spec-id> --harness cursor
```

2. **Verify the Baseline:**
Run the baseline tests, saving the authentic log as an artifact (`base.log`), record the baseline evidence (following [`evidence_baseline.json`](../tutorials/first-governed-project.md#1-record-baseline-evidence-and-acknowledge-gatebaseline)), and acknowledge `gate.baseline` before activating the run:
```bash
python -m unittest discover -s tests -t . > base.log 2>&1
rapid evidence add --run <run-id> --input evidence_baseline.json
rapid run gate <run-id> gate.baseline acknowledged
rapid run status <run-id> active
rapid run task <run-id> T001 in_progress
```

3. **Inject Context into Composer:**
In Cursor's Composer window, reference the generated file:
> `@.rapid-os/runs/<run-id>/contract.json implement task T001 and run the tests.`

4. **Verify Tests in the Terminal:**
Check that the tests pass in Cursor's integrated terminal.

5. **Record Evidence:**
Ingest the results with `rapid evidence add` (see the structures in the [Under the hood lab](../tutorials/first-governed-project.md#7-evidence-collection)):
- [`evidence_files.json`](../tutorials/first-governed-project.md#3-record-code-change-evidence-file_change): file modification evidence.
- [`evidence_tests.json`](../tutorials/first-governed-project.md#4-record-passing-test-evidence-test_result): test result with attached log.
- [`evidence_workspace.json`](../tutorials/first-governed-project.md#5-record-workspace-evidence-workspace): current workspace (`workspace.current`).
- [`evidence_review.json`](../tutorials/first-governed-project.md#6-record-final-review-evidence-review): approved contractual review.

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

---

## 5. Common Problems

- **Composer adds unwanted temporary files:** Make sure `.gitignore` excludes temporary files and that only the necessary paths appear in the `file_change` evidence.
