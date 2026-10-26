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
- **Fix:** This is only a warning. To avoid it, install one harness that covers both tools; see [Combining Harnesses](../guides/shortcuts.md#combining-harnesses).

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
