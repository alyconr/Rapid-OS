---
title: Troubleshooting Labs and Tutorials
description: Resolve common problems when running Rapid OS v3 hands-on labs.
---

# Troubleshooting Labs and Tutorials

## Shortcut workflow

Common errors when working with `/rapid-*`. See the complete [Shortcuts by Harness](../guides/shortcuts.md) guide and the [Diagnostics catalog](./diagnostics.md).

### `RAPID1301`: missing `test_command`

- **Cause:** `.rapid-os/config.json` has no `test_command` (or it is empty), so `rapid check` does not know which test command to run. This is a warning.
- **Fix:** Run `rapid init --test-command "python -m unittest discover"`, or set `"test_command": ["python", "-m", "unittest", "discover"]` (an argv list) in `.rapid-os/config.json`.

### `RAPID1307`: no active run

- **Cause:** `rapid check`, `task`, or `finish` ran without `.rapid-os/session.json` (no `rapid start`, or the run finished or was aborted).
- **Fix:** Start a run with a mode shortcut (`/rapid-feature <goal>`) or `rapid start <mode>`.

### `RAPID1308`: a run is already active

- **Cause:** You ran `rapid start` or a mode shortcut while `.rapid-os/session.json` contains a non-terminal run.
- **Fix:** Continue with `rapid next`, run `rapid start <mode> --resume`, or abort with `rapid abort`.

### `RAPID1310`: `rapid approve` is refused

- **Cause:** There is no interactive terminal, the session belongs to an agent (`CLAUDE_CODE_CHILD_SESSION=1`), or a parent process is Claude Code (for example, `!` mode).
- **Fix:** Run `rapid approve <gate>` yourself in your terminal (an editor's integrated terminal is fine). A shortcut never approves human gates.

### `RAPID1321`: overlapping harness directories

- **Cause:** You selected Cursor or VS Code together with Claude, Codex, or Antigravity, and the same `/rapid-*` shortcut is written to two directories that the tool reads.
- **Fix:** This is only a warning. To avoid it, install one harness that covers both tools; see [Combining Harnesses](../guides/shortcuts.md#if-you-combine-harnesses).

### `RAPID1415`: the spec lost its accents (`rapid start`, `rapid spec create`, `rapid spec revise`)

- **Cause:** the spec went through a Windows PowerShell 5.1 pipe (`$spec | rapid start feature --spec-file -`), which converts it to ASCII: `creación` arrives as `creaci?n` and the spec id would be `reserva-p-blica`. The message names the field and the word. Nothing was written: no spec, no revision, no run.
- **Fix:** write the spec to a temporary UTF-8 file outside `.rapid-os` and pass the path: `$spec | Set-Content -Encoding utf8 $env:TEMP\rapid-spec.json`, then `rapid start <mode> --spec-file $env:TEMP\rapid-spec.json`. Do not pipe it again. In bash or zsh, stdin with a heredoc is fine. See [Sending specs and documents from PowerShell](../installation/windows.md#text-from-powershell).

### `rapid check` on Windows: the log has no output and the tests are not counted

- **Cause:** in 3.2.0rc3 and earlier, `rapid check` decoded the command's output with the Windows code page (cp1252). The UTF-8 that Vitest prints (`✓`, `⎯`, `❯`) stopped the reader with `UnicodeDecodeError: 'charmap' codec can't decode byte 0x9d`: the log stayed without the output and the summary was not counted. `rapid task done` uses the same check.
- **Fix:** update Rapid OS; the output is now read as UTF-8 and `PYTHONUTF8=1` is no longer needed. Then run the check again: `rapid check -- <command>`.

### `RAPID1440`: the check did not count for `gate.tests`

- **Cause:** the check of `gate.tests` or `gate.baseline` ran another command than the configured `test_command` (a `python -c "print(...)"`, a script in `%TEMP%`, a hand-quoted copy of the command). Rapid OS recorded it as a normal check, without the gate: it cannot prove what ran.
- **Fix:** run `rapid check --gate gate.tests` without a command; Rapid OS runs the `test_command` itself, without a shell, so nothing has to be quoted in PowerShell. If another command really has to verify the gate, only the person can accept it, in their terminal: `rapid check --gate gate.tests --accept-test-command "<reason>" -- <command>` asks `[s/N]`.

### A refactor compares only the frontend tests with its baseline

- **Cause:** up to 3.2.0rc3, with a combined test command (backend and frontend) `rapid check` counted only the last summary of the output: `gate.tests` recorded `2 passed` (Angular) and not the 31 backend tests.
- **Fix:** update Rapid OS. `rapid check --gate gate.tests` runs each component of the combined command, adds the counts and keeps the breakdown (`components`). Take the baseline again if it was recorded before the update.

### `RAPID1441`: `rapid finish` gives no PASS because the run changed nothing

- **Cause:** the tree outside `.rapid-os/` is the one the run started from: the change was undone (a file returned to its previous version) after an earlier `rapid finish` had recorded `file_change`. A run that never made the change ends `UNVERIFIED` instead, with its reason. A feature, bugfix, refactor or hardening run does not end in PASS without the change it declares.
- **Fix:** make the change, run what `rapid next` gives (the test check), approve again and repeat `rapid finish`; or `rapid abort` if the run is not needed. `RAPID1442` is only a warning: the change touches no `affected_path` of the spec, so check that it is the right one.

### The security workflow is green but says "Nada que auditar"

- **Cause:** the dependencies job found no code of its language in the folder of the component (`backend/`, `frontend/`, or the root in a one-folder project): the folder does not exist yet or has no source files. Nothing was audited. In 3.2.0rc3 and earlier the job looked for the manifest and the lockfile only in the root, so with `fullstack-separated` it said "Sin dependencias declaradas todavía" or "Sin lockfile todavía" and passed while `backend/` and `frontend/` had them.
- **Fix:** nothing, while the repository is new. In an existing project, run `rapid doctor`: `RAPID1443` points to `rapid setup ci --regenerate`, which brings the workflow up to date (an edited workflow is not overwritten; the new one goes beside it as `.new`).

### semgrep blocks `pnpm-workspace.yaml` (or `.npmrc`, `.yarnrc.yml`, `pyproject.toml`, `Gemfile`)

- **Cause:** `p/owasp-top-ten` includes rules for the package manager configuration, such as `pnpm-missing-minimum-release-age`, `pnpm-trust-policy` and `pnpm-block-exotic-sub-dependencies`. A project scaffolded without those settings fails the semgrep job on its first push. Up to 3.2.0rc3 bandit ran after semgrep in the same job, so it did not run at all.
- **Fix:** add the settings of your package manager (table in [the security baseline](../concepts/security-baseline.md#package-manager-settings-that-semgrep-checks)); for pnpm, `minimumReleaseAge: 10080`, `trustPolicy: no-downgrade` and `blockExoticSubdeps: true` in `pnpm-workspace.yaml`. Then run `rapid setup ci --regenerate` so that each scanner has its own job.

### The dependencies job fails: "tiene código ... pero no tiene ..."

- **Cause:** the folder of the component has source files but no manifest or lockfile, for example `frontend tiene package.json pero ningún lockfile`. Without the lockfile the audit cannot know which versions are installed.
- **Fix:** install the dependencies in that folder and commit the lockfile (`pnpm-lock.yaml`, `package-lock.json`, `yarn.lock`, `uv.lock`, `Cargo.lock`, `Gemfile.lock`, `composer.lock`), or declare them (`pyproject.toml`, `requirements.txt`, `go.mod`).

## 1. Scanner and initialization issues

### `RAPID1001` (Project Model Error) or incomplete facts

- **Cause:** The scanner ran before recognized file extensions or test directories existed.
- **Fix:** Create at least one `.py` file and a `tests/` directory, then run `rapid scan --write` again.

## 2. Spec and context bundle issues

### `RAPID1010` (Spec Not Ready) when creating a run

- **Cause:** You tried to create an `ExecutionContract` linked to a spec in `draft` or `in_progress` state.
- **Fix:** A run can be created only from a `ready` spec:
  ```bash
  rapid spec update <spec-id> --status ready
  ```

## 3. Run states and task transitions

### `InvalidRunStateTransitionError`

- **Cause:** You tried to modify a task or gate while the run was `prepared` or `finished`.
- **Fix:** Set the run to `active` before modifying tasks:
  ```bash
  rapid run status <run-id> active
  ```

## 4. Evidence issues (`rapid evidence add`)

### `RAPID1203` (Evidence Binding Mismatch)

- **Cause:** `state_digest` or `state_revision` does not match the active run version.
- **Fix:** If authoring JSON manually, use the exact values from `rapid run show <run-id> --json`.

### `RAPID1206` (Invalid Evidence Payload)

- **Cause:** `payload` has extra or missing fields for the canonical schema of that `EvidenceKind`.
- **Fix:** See the schema table in the [Evidence Engine cookbook](../cookbooks/evidence-engine.md). For `test_result`, required fields are exactly `suite`, `exit_code`, `passed`, `failed`, and `skipped`.

## 5. Behavioral evaluation issues (`rapid eval run`)

### Verdict: `unverified`

- **Cause:** One or more required gates remain `pending` in `RunState`.
- **Fix:** Register the relevant evidence and acknowledge the gate:
  ```bash
  rapid run gate <run-id> <gate-id> acknowledged
  ```

### Verdict: `fail`

- **Cause:** Contradictory evidence was found (for example, `test_result` with a nonzero exit code or `file_change` touching paths outside the contract).
- **Fix:** Correct the code, rerun the suite, register new evidence with the correct result, and evaluate again.
