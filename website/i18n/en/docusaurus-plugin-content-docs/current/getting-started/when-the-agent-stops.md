---
title: When the Agent Stops
description: "What to do when the agent pauses to ask for something: approve, reject, check progress, cancel, and read the result."
---

# When the Agent Stops

While working, the agent does not ask you for anything. It stops only in three cases: **it needs your approval**, **something is blocking the work**, or **it is done**. In each case, it explains what happened and what to do. This page summarizes your options.

## It asks you to approve

This is the most common case: the work is done and the tests passed, but the final decision is yours. The agent summarizes its work and gives you a command. Run it in **another terminal**, outside the agent:

```bash
rapid approve gate.final-verification
```

Then return to the agent and enter `/rapid-next` to close the run.

| You want to... | In your terminal |
|---|---|
| Approve | `rapid approve <gate>` (the agent gives you the exact name) |
| See what still needs approval | `rapid approve` (with no arguments) |
| Reject and explain why | `rapid approve <gate> --reject --reason "<reason>"` |
| Waive an optional review | `rapid approve <gate> --waive --reason "<reason>"` |

**Why use your terminal instead of the agent?** Approval guarantees that a person reviewed the work. Rapid OS rejects `rapid approve` when it detects that an agent launched it, and no shortcut can approve for you. If you are not sure what needs approval, enter `/rapid-approve` in the agent. It shows pending gates and the command, but does not approve.

If you reject, the work is not accepted. The agent explains the situation and waits for your decision; usually, you cancel and start again with what you learned.

## Something is blocking the work

The agent tells you why. Common causes include:

- **Your tests already failed before work began.** Rapid OS checks the suite at the start (the *baseline*) so the agent is not blamed for an existing failure. Fix those tests and enter `/rapid-next`.
- **Fewer tests pass after a refactor.** The agent shows you which ones; ask it to fix the issue.
- **Another task is already in progress.** Only one run can be active at a time; finish it with `/rapid-next` or cancel it.

## Check progress or cancel

| You want to... | Where | What to enter |
|---|---|---|
| See tasks, pending approvals, and status | In the agent | `/rapid-status` |
| Have the agent continue where it stopped | In the agent | `/rapid-next` |
| Cancel the current task | In your terminal | `rapid abort --reason "<reason>"` |

Cancellation does not delete your code: it marks the run as cancelled and frees the slot for another task.

## It is done

When the run closes, the agent shows you the verdict:

| Verdict | Meaning |
|---|---|
| `pass` | Everything required has evidence: tests ran and passed, and you approved. |
| `pass_with_waivers` | Same as `pass`, but you waived an optional review. |
| `unverified` | Evidence is missing for something (for example, a test was never run). |
| `fail` | A requirement failed, or you rejected approval. |

`pass` does not mean "bug-free." It means the request was demonstrated with evidence that Rapid OS ran and recorded. If the work came from a brief story (`H001`...), `pass` marks it as complete.

If something seems wrong, see [Troubleshooting the Labs](../troubleshooting/tutorials.md) or the [diagnostics catalog](../troubleshooting/diagnostics.md) for `RAPIDxxxx` codes in messages.
