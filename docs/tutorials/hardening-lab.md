---
title: Lab 4 - Hardening and Security Engineering
description: Harden user registration by validating and bounding input with the Rapid OS workflow.
---

# Lab 4: Hardening and Security Engineering

Harden user registration by validating and bounding input to `register_user`. You will enter three things in your agent; in the terminal, you only prepare the example and approve the result.

## With shortcuts

### 1. Prepare the example project

```bash
cp -r ~/.rapid-os/examples/hardening-lab/starter user-profiles && cd user-profiles
git init -b main && git add . && git commit -m "starter"
```

In Windows PowerShell, use `Copy-Item -Recurse $HOME\.rapid-os\examples\hardening-lab\starter user-profiles`. If you installed Rapid OS with `pip`, the example is in [`examples/hardening-lab/starter`](https://github.com/alyconr/Rapid-OS/tree/main/examples/hardening-lab/starter).

### 2. Set up the project

Open your agent in the folder and enter `/rapid-init` (`$rapid-init` in Codex). It detects Python and suggests `python -m unittest discover` as the test command; accept it. You can skip the project documents for this lab. When asked for an archetype, choose **Corporate** (`corporate`), which includes stricter security rules.

### 3. Request the work

```text
/rapid-hardening validate and bound register_user inputs
```

The agent works in an isolated copy of the repository (`rapid start --resume --worktree` creates `../<repo>-<run-id>` on branch `rapid/<run-id>`), so your `main` branch does not change before review. In addition to final verification, the agent requests a review (`gate.review`), which you can approve or waive.

### 4. Approve in your terminal

When the agent finishes, it stops and gives you the exact command. Run it in **another terminal**, outside the agent, for example:

```bash
rapid approve gate.final-verification
```

Return to the agent and enter `/rapid-next` to close the run.

The run's code remains in `../<repo>-<run-id>` on `rapid/<run-id>`. Commit in that worktree before merging the branch into your project, then remove the worktree. `rapid finish` prints the exact paths and commands when uncommitted changes remain. Do not use `git worktree remove` with the **--force** option; it deletes uncommitted work.

**Result:** `register_user` rejects usernames, emails, and bios outside the limits, with tests for each; the run ends with a `pass` verdict (or `pass_with_waivers` if you waived the review).

No shortcuts yet? Install them once with `rapid shortcuts install --global --harness claude`, or run `rapid init --shortcuts` inside the folder. Replace `claude` with your agent. See the [shortcuts guide](../guides/shortcuts.md).

## Lab details

### Starting state

```text
user-profiles/
├── profile_mgr.py
└── tests/
    ├── __init__.py
    └── test_profile_mgr.py
```

In the starter version, `UserProfileManager.register_user(username, email, bio)` stores any string without validation.

### Requirements

1. **Username:** Match the regular expression `^[a-zA-Z0-9_-]{3,32}$`.
2. **Email:** Apply strict validation with a standard email format.
3. **Bio:** Limit length to 200 characters and explicitly reject null characters (`\x00`).
4. **Exceptions:** Raise `ValidationError` (derived from `ValueError`) for any boundary violation.

## Advanced mode

You do not need this for the lab. The same kind of work done manually with v3 commands (spec, run, evidence, and evaluation), for CI or auditing, is covered in the [manual walkthrough](first-governed-project.md) and the [v3 governance loop](../governance-loop.md).
