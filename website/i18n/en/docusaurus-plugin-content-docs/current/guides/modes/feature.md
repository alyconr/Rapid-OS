---
title: Feature Mode
description: End-to-end workflow for developing new capabilities with Rapid OS.
---

# Feature Mode

**Feature** mode is designed to implement new capabilities while preserving existing contracts and architectural design.

## With the `/rapid-feature` shortcut

```text
/rapid-feature add CSV export to the monthly report
```

In Codex, use `$rapid-feature ...`. The shortcut guides the full run; see the [shortcuts guide](../shortcuts.md) for installation and invocation by harness.

The playbook (`templates/modes/feature.json` and Conductor rules) works as follows:

- `rapid next` provides the spec template (`action.spec_template`: title, business goal, scope, acceptance criteria, and atomic tasks `T001...`), which the agent fills from your goal.
- The default risk is medium: the baseline is verified and recorded at startup (`gate.baseline`), tasks are checked with `rapid check`, and the run includes `gate.tests` and human `gate.final-verification`.
- **Architecture:** If `.rapid-os/standards/architecture.json` exists (created during onboarding for the selected stack), the contract includes the required, non-waivable machine gate `gate.architecture`; `rapid next` proposes `rapid check --gate gate.architecture -- rapid arch check`. A layer or public-contract violation returns `RAPID1420`, and `rapid finish` will not return `PASS` until corrected. See [Stack Architecture](../../concepts/architecture.md#the-gate-gatearchitecture).
- The loop is: implement each task → `rapid check -- <test_command>` → `rapid finish`. You give final approval in your terminal.

### In a new project (no code or tests)

Rapid OS observes run changes with Git, so the project must be a repository; onboarding creates one if needed (`rapid start` without a repository returns `RAPID1416`). If the repository has no source code (outside `docs/` and hidden directories) and no tests, there is no baseline to capture and the test command would fail before work begins. In this case, `rapid start feature`:

- Adds `T001: Minimal scaffold with a passing test` as the first task. Your tasks become `T002...` in the text and contract, and `rapid start` explains this in `notes` (for example, `T001→T002`). Always use IDs returned by `rapid next`.
- Creates the contract **without `gate.baseline`**, with optional field `baseline_waived: "empty_repository"`; the run starts active.
- Closes the scaffold task with a passing `rapid check`; from then on, tests belong to your project.

`rapid status` and `rapid finish` show `No baseline: new project`. A repository with code but no tests retains a baseline: add a passing test in a task, or use Research mode. `bugfix`, `refactor`, and `hardening` do not start in an empty repository (`RAPID1413`: there is no code to fix, refactor, or harden; use `/rapid-feature`).

### The first feature can come from the brief

If you onboarded with `/rapid-init` (or `rapid setup`), the brief (`docs/PRODUCT_BRIEF.md`) has a stories section using `- [ ] H001: ...`. With no active run, `rapid next` adds an optional `seed` field to the `author_spec` action with **all** unchecked stories in order, plus business rules and data-model documents if they exist (see [`rapid next`](../../cli.md#rapid-next)).

```text
/rapid-feature       # no arguments: suggests a story and waits for confirmation
/rapid-feature H002  # uses the specified story
```

- Without arguments, the agent suggests an unchecked story and briefly explains why if it is not the first one (for example, dependencies). It drafts the spec only after you confirm.
- The spec copies relevant rules from `docs/BUSINESS_RULES.md` into `business_rules`, cites the document, and is tagged `story:<id>`.
- If the brief is still an unconfirmed draft (`seed.confirmed` is `false`), the agent warns that it is making assumptions.
- For a brief story, the agent adds a tag such as `story:H002`. When `rapid finish` returns PASS, it marks that story complete in `docs/PRODUCT_BRIEF.md`: changes only `- [ ] H002:` to `- [x] H002:`, saves a copy in `.rapid-os/backups/`, and leaves the brief's `source` and `status` unchanged. With another verdict, it says the story will be marked when the run passes; with `rapid finish --no-tick`, it only suggests marking `H002` complete. One run covers one story.

The rest of this guide describes the workflow with v3 commands (**Advanced Mode**), useful for CI, debugging, and auditing.

## Advanced workflow

The complete process is: scan and write project intelligence; create a ready feature spec; compile context; create a run and resolve harness compatibility; implement within scope; register test and Git evidence; verify evidence; and evaluate with `rapid eval run --write --require-pass`.

For example, create a spec with `rapid spec create --mode feature`, compile with `rapid context --spec <id> --harness codex --mode feature --manifest`, and create the run with `rapid run create --spec <id> --harness codex --classification bounded --risk medium`. Then use `rapid harness resolve --run <run-id> --require-compatible` before external execution.

After tests pass, register valid `test_result` and `git_result` evidence using `rapid evidence add`. Verify the evidence sequence with `rapid evidence verify --run <run-id>`, then evaluate the completed run:

```bash
rapid eval run --run <run-id> --write --require-pass
```

If all gates and rules are satisfied, the `PASS` report is stored immutably in `.rapid-os/evals/`.
