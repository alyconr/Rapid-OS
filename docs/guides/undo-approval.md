---
title: Undo an approval
description: How to back out of a human approval you gave too soon, before and after rapid finish, without editing the ledger and without losing work.
---

# Undo an approval

A gate decision is recorded as evidence in the run's ledger, and the ledger is append-only: `rapid approve` cannot be repeated, and nothing edits `.rapid-os/` to take an approval back. That is why `rapid approve <gate>` on a gate that is already decided fails with `RAPID1332` and points here. What you do instead depends on one thing: **has `rapid finish` run?**

| You are here | What to do |
| :--- | :--- |
| The gate is approved (or rejected), `rapid finish` has **not** run | [Case A](#case-a-before-rapid-finish): `rapid abort` |
| `rapid finish` already ran (the run is closed) | [Case B](#case-b-after-rapid-finish): `git revert`, reopen the story, new run |

Rapid OS never commits for you (`rapid finish` ends with "Rapid OS no hace commit: revisa los cambios y haz commit tú"), so until you commit, the code is only in your working tree.

## Case A: before `rapid finish` {#case-a-before-rapid-finish}

The run is still open, so it can still be cancelled. After approving the last human gate, `rapid approve` prints `Siguiente: rapid finish ...`: that is the last point where you can back out.

1. Cancel the run:

   ```bash
   rapid abort --reason "approved too soon"
   ```

   It ends the run as `aborted` and clears the session. An isolated worktree stays on disk.

2. Set the code aside if you want to keep it. Stash everything the run produced, including new files, but leave Rapid OS's own folder alone:

   ```bash
   git stash push --include-untracked -m "run <run-id>: approved too soon" -- . ':(exclude).rapid-os'
   ```

   `git stash list` shows it and `git stash pop` brings it back whenever you want to continue from it.

3. Start a new run (`/rapid-feature` or `rapid start feature`). A rejected gate works the same way: `rapid next` returns `blocked` with `rapid abort`, and the rejection text you gave with `--reason` is in `action.rejection`, so the agent opens the new run addressing it.

:::warning Never `git clean`
Do not use `git clean` to "start from scratch". It deletes untracked files, which includes `.rapid-os/` (the ledger, the evidence, your onboarding decisions) and any file the run created. If you only want the code out of the way, use the `git stash` command above.
:::

## Case B: after `rapid finish` {#case-b-after-rapid-finish}

A finished run is closed for good: `rapid abort` no longer applies and its verdict stays in the ledger as the record of what happened. The way back is through git and a new run.

1. Revert the commit(s) you made from that run:

   ```bash
   git revert <commit>
   ```

   If you did not commit yet, discard or stash the working tree instead (see the stash command in Case A).

2. Reopen the story if `rapid finish` ticked it in the product brief. This changes only that one line (the previous file goes to `.rapid-os/backups/`):

   ```bash
   rapid setup story H002 --reopen
   ```

3. Start a new run for the story (`/rapid-feature H002`). `rapid next` offers it again because it is open again.

## See also

- [`rapid approve`](../cli.md#rapid-approve) and [`rapid abort`](../cli.md#rapid-abort) in the CLI reference.
- `RAPID1332` in the [diagnostics reference](../troubleshooting/diagnostics.md).
- [Governance loop](../governance-loop.md): why approvals are evidence and the ledger is append-only.
