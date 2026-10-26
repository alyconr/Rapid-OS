# Anthropic Claude Code Integration

Technical guide for governing interactive and terminal workflows with **Claude Code** using **RAPID OS v3**.

---

## 1. What Claude Code is and how it fits with RAPID OS

Claude Code is Anthropic's command-line development tool, designed to operate directly on codebases through editing, search, and command-execution tools.

**How it fits with RAPID OS:**
Claude Code acts as the external executing agent. RAPID OS acts as the governance framework: it defines the specification up front, controls architectural risk, and uses deterministic evidence to check that everything promised was delivered before a task is accepted.

---

## 2. Configuration in RAPID OS

RAPID OS includes the `claude` profile identifier:

```bash
rapid harness show claude
```

Declarative profile:
- `context.consume`: `supported`
- `repository.read`: `supported`
- `workspace.current`: `supported`
- Other capabilities: marked `unknown` until the local environment configures them explicitly in the project.

---

## 3. Configuration in Claude Code

1. Sign in to Claude Code following the official guides (`claude login`).
2. Grant permissions to run local tests and edit files according to your team's policies.
3. Make sure Claude Code reads the `.rapid-os/standards/` folder so it aligns with the project's architectural standards.

---

## Main workflow: shortcuts

The recommended way to work with Claude Code is through the `/rapid-<mode>` shortcuts. The 9 shortcuts, the loop they follow, human approval, and common errors are covered in the [shortcuts guide](../guides/shortcuts.md).

### Install

```bash
rapid init --shortcuts                                # when initializing the project
rapid shortcuts install --harness claude              # in an already initialized project
rapid shortcuts install --harness claude --hooks      # also install the hooks (section 6)
```

This generates `.claude/skills/rapid-*/SKILL.md` (the 9 shortcuts; [skills documentation](https://code.claude.com/docs/en/skills)). After updating Rapid OS, run `rapid shortcuts install` again.

### First step: `/rapid-init` (onboarding)

A project's entry point is `/rapid-init`: it drives the onboarding (`rapid setup next`), asks you for the stack of each component, the architecture, the services, and the documents, and reviews the drafts with you before closing. After that you use `/rapid-feature` and the other modes. See [First project](../getting-started/first-project.md).

To have `/rapid-init` and the other shortcuts in all your projects without installing them in each one, install them in your user folder (`~/.claude/skills/`); the Rapid OS installer asks you about this when it finishes:

```bash
rapid shortcuts install --global --harness claude
```

Shortcuts and hooks run `rapid` from the agent's shell: if it is not on the `PATH`, `rapid init` and `rapid doctor` warn with `RAPID1414` (a warning, not an error). See the [shortcuts guide](../guides/shortcuts.md).

### Invocation

Type `/rapid-` in Claude Code and pick a shortcut, or launch it directly:

```text
/rapid-feature add CSV export to the monthly report
```

- Claude Code is the only harness that runs the `` !`rapid next --json` `` line before sending the prompt; if that command fails, the skill is aborted, so `rapid` must be on the `PATH`.
- `allowed-tools` pre-approves only `rapid next`, `start`, `check`, `task`, `finish`, and `status`; never `approve` or `abort`.
- `/rapid-approve` carries `disable-model-invocation` and **does not approve**: it gives you the command to run in your terminal. Always approve in your own terminal, not with Claude Code's `!` mode (`RAPID1310`).

---

## Advanced mode (v3 commands)

The v3 commands (`rapid spec`, `rapid run`, `rapid evidence`, `rapid eval`…) remain available for CI, debugging, and auditing, and you do not need to use them by hand day to day. Sections 4 and 5 keep the full manual workflow.

## 4. Governed Workflow

1. **Create the Spec and Run in RAPID OS:**
```bash
rapid spec create --id spec-feature --title "New feature" --mode feature --task "T001: Implement feature" --status ready
rapid context --manifest
rapid run create --spec spec-feature --harness claude
```

2. **Verify and Record the Baseline:**
Run the baseline test suite, saving the authentic log as an artifact (`base.log`), record the baseline evidence (following the structure of [`evidence_baseline.json`](../tutorials/first-governed-project.md#1-record-baseline-evidence-and-acknowledge-gatebaseline)), and acknowledge the gate before activating the run:
```bash
python -m unittest discover -s tests -t . > base.log 2>&1
rapid evidence add --run <run-id> --input evidence_baseline.json
rapid run gate <run-id> gate.baseline acknowledged
```

3. **Instruct Claude Code:**
Ask Claude Code in the terminal:
> *"Read the specification in `.rapid-os/specs/spec-feature/spec.json` and the contract in `.rapid-os/runs/<run-id>/contract.json`. Implement the necessary changes and run the test suite."*

4. **External Execution:**
Claude Code edits the files and runs `python -m unittest`.

5. **Evidence Capture and Ingestion:**
The developer, or Claude Code itself, invokes the RAPID OS CLI to record progress (see the canonical structure of each file in the [Under the hood lab](../tutorials/first-governed-project.md#7-evidence-collection)):
- [`evidence_files.json`](../tutorials/first-governed-project.md#3-record-code-change-evidence-file_change): file modification evidence (`file_change`).
- [`evidence_tests.json`](../tutorials/first-governed-project.md#4-record-passing-test-evidence-test_result): passing test results with their attached log file (`test_result`).
- [`evidence_workspace.json`](../tutorials/first-governed-project.md#5-record-workspace-evidence-workspace): current workspace verification (`workspace`).
- [`evidence_review.json`](../tutorials/first-governed-project.md#6-record-final-review-evidence-review): approved contractual review (`review`).

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

6. **Evaluation:**
```bash
rapid eval run --run <run-id> --write --require-pass
```

---

## 5. Common Problems

- **Claude Code edits without running tests:** The evaluation will flag `fail` or `unverified` if no evidence with a valid `test_result` is provided.
- **Non-canonical paths:** Paths in evidence payloads must be relative POSIX paths (e.g. `src/app.py`, not absolute paths with `C:\`).

---

## 6. Claude Code hooks (optional loop enforcement)

> Hooks reinforce the main shortcuts workflow; they are not part of advanced mode.

Claude Code hooks run a command at points in the agent's lifecycle ([official documentation](https://code.claude.com/docs/en/hooks)). Rapid OS provides two, `rapid hook stop` and `rapid hook pre-tool`, so the agent does not stop in the middle of a run, does not launch commands reserved for the person, and does not edit `.rapid-os/`.

> Hooks are run by Claude Code, not by Rapid OS: Rapid OS still does not invoke agents. They only respond with a blocked stop or a denied tool.

### Install

```bash
rapid shortcuts install --harness claude --hooks
rapid shortcuts install --harness claude --hooks --dry-run --json   # see what would change
rapid shortcuts remove --harness claude --hooks                      # removes only its own entries
```

This merges a `Stop` group and a `PreToolUse` group (matcher `Bash|PowerShell|Write|Edit|MultiEdit|NotebookEdit`) into the project's `.claude/settings.json`; the command is `rapid` with the arguments `hook stop` / `hook pre-tool` (Claude Code's *exec* form: no shell, identical on Linux, macOS, and Windows). It does not touch other keys or the user's hooks, makes a `.bak` copy, and is idempotent. `rapid init --shortcuts` does **not** install hooks: you must ask for them with `--hooks` (in `rapid init` or in `rapid shortcuts install`).

`rapid` must be on the `PATH` of the machine where Claude Code runs (for example with `pipx install git+https://github.com/alyconr/Rapid-OS.git`). If it cannot be resolved, Claude Code treats it as a non-blocking error and the enforcement stops acting; `rapid doctor` warns about it with `RAPID1339`.

### What `Stop` does

It blocks the stop with the reason (`instructions` plus the exact command) while `rapid next` proposes `run_baseline`, `activate`, `implement_task`, `verify`, or `finish`. It does not block on `author_spec`, `await_human_approval`, `blocked` (not even when `rapid abort` is proposed after a `--reject`), `done`, or when there is no session.

Loop guard: at most `hooks.max_stop_blocks` consecutive blocks (3 by default) per session and action; configurable in `.rapid-os/config.json`:

```json
{ "hooks": { "max_stop_blocks": 3 } }
```

Claude Code also applies its own cap on consecutive continuations.

### What `PreToolUse` does

| Agent action | Result |
| :--- | :--- |
| `rapid approve …`, `rapid run gate …`, `rapid run status …`, `rapid evidence add …`, `rapid spec status …`, `rapid abort` | Denied. For `approve`, the reason gives the exact command the person must type in their terminal. |
| `rapid status`, `next`, `check`, `task`, `attach`, `finish`, `start` | Allowed. |
| `Write`, `Edit`, `MultiEdit`, `NotebookEdit` on `.rapid-os/` | Denied. |
| Shell commands that write to `.rapid-os/` (`>`, `>>`, `tee`, `cp`, `mv`, `rm`, `sed -i`, `find -delete`, …) | Denied. |
| Removing or redefining `CLAUDE_CODE_CHILD_SESSION` or `CLAUDECODE` (`env -u`, `env --unset`, `env -i`, `unset`, `VAR=` or `VAR=0` prefixes, `export`, `Remove-Item Env:`, `$env:VAR = …`) | Denied, with a reason that points to `rapid next`: those variables are what make `rapid approve` refuse to run inside an agent session. |
| `rapid approve --help` (or `-h`) | Allowed: it only prints the help. |

The hook also detects `python -m rapid_os …`, `python rapid.py …`, absolute paths to the executable, environment prefixes (`VAR=1 rapid …`), `sudo`/`env`/`timeout`, commands that run a string (`bash -c`, `bash -xc`, `script -qec`, `su -c`, `eval`), and `find … -exec`, as well as chained or nested commands (`;`, `&&`, `||`, `|`, `$(…)`, backticks). `script` deserves a separate mention: it gives the command a terminal, so together with `env -u CLAUDE_CODE_CHILD_SESSION` it would allow bypassing `rapid approve`'s TTY check; that is why it is analyzed the same way as `bash -c` and removing those variables is denied.

> **Defense in depth in `rapid approve`.** Hooks are not the only barrier: `rapid approve` refuses (`RAPID1310`) when there is no TTY, when `CLAUDE_CODE_CHILD_SESSION` is `1`, and also when any ancestor process is the `claude` binary (the parent process chain is walked using the standard library). Ancestry detection is best-effort: a process that detaches from its parent (double fork, `setsid`, `nohup … &`) is reparented to `init` and no longer has `claude` as an ancestor; together with a renamed `claude.exe` and a reused pid from a dead parent, this is a known limit. The rule remains that a person approves in their own terminal. If ancestry cannot be read, the command is not refused for that reason and `rapid doctor` warns about it (`RAPID1319`). A person approving in their own terminal is unaffected.
>
> **Command detection is best-effort.** It analyzes the command line the hook sees; it cannot prevent a determined agent from building the command at runtime or from writing to `.rapid-os/` with a programming language. Hooks reinforce the loop; they do not replace the rule that a person approves in their terminal (`rapid approve` requires a TTY and fails with `RAPID1310`).

### Worktrees and errors

- Project resolution walks up from the payload's `cwd` to the first `.rapid-os/`. If the `cwd` is the worktree created by `rapid start --worktree`, the main repository's ledger is used (the one stored as `workspace_path` in `session.json`).
- No project: no output and exit 0.
- Any internal error, a stdin that is not JSON, or a corrupt `.rapid-os/`: no output, exit 0, and a line in `.rapid-os/scratch/hooks.log`. A hook must never break the agent.
