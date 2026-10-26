---
title: Lab 1 - Feature Engineering
description: Add availability validation to a booking system using the Rapid OS feature workflow.
---

# Lab 1: Feature Engineering

Add a feature to a booking system: reject bookings that overlap in the same time slot. You will enter three things in your agent; in the terminal, you only prepare the example and approve the result.

## With shortcuts

### 1. Prepare the example project

```bash
cp -r ~/.rapid-os/examples/feature-lab/starter booking-app && cd booking-app
git init -b main && git add . && git commit -m "starter"
```

In Windows PowerShell, copy it with `Copy-Item -Recurse $HOME\.rapid-os\examples\feature-lab\starter booking-app`. If you installed Rapid OS with `pip`, the example is in [`examples/feature-lab/starter`](https://github.com/alyconr/Rapid-OS/tree/main/examples/feature-lab/starter).

### 2. Set up the project

Open your agent in the folder and enter `/rapid-init` (`$rapid-init` in Codex). It detects Python and suggests `python -m unittest discover` as the test command; accept it. You can skip the project documents for this lab.

### 3. Request the work

```text
/rapid-feature add availability checks: reject bookings that overlap in the same time slot
```

The agent drafts the spec, checks that the example tests pass before changing anything (the baseline), implements the validation with tests, and runs them with `rapid check`.

### 4. Approve in your terminal

When the agent finishes, it stops and gives you the exact command. Run it in **another terminal**, outside the agent, for example:

```bash
rapid approve gate.final-verification
```

Return to the agent and enter `/rapid-next` to close the run.

**Result:** Booking an occupied time slot raises an error, the test suite passes, and the run ends with a `pass` verdict.

No shortcuts yet? Install them once with `rapid shortcuts install --global --harness claude`, or run `rapid init --shortcuts` inside the folder. Replace `claude` with your agent. See the [shortcuts guide](../guides/shortcuts.md).

## Lab details

### Starting state

```text
booking-app/
├── booking.py
└── tests/
    ├── __init__.py
    └── test_booking.py
```

In the starter version, `BookingSystem.create_booking(user_id, slot)` saves any booking without checking whether the time slot is already occupied.

### Requirements

1. **Detect collisions:** Raise `SlotAlreadyBookedError` if the requested time slot is already registered.
2. **Normalize input:** Strip whitespace from `user_id` and `slot`.
3. **Handle edge cases:** Reject empty strings or strings containing only whitespace.
4. **Preserve valid bookings:** Valid bookings must continue to be saved normally.

## Advanced mode

You do not need this for the lab. The same kind of work done manually with v3 commands (spec, run, evidence, and evaluation), for CI or auditing, is covered in the [manual walkthrough](first-governed-project.md) and the [v3 governance loop](../governance-loop.md).
