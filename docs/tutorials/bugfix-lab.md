---
title: Lab 2 - Bugfix Engineering
description: Reproduce and fix a percentage discount bug using the Rapid OS bugfix workflow.
---

# Lab 2: Bugfix Engineering

Fix a real bug: a 10% discount on $100 returns a negative total. You will enter three things in your agent; in the terminal, you only prepare the example and approve the result.

## With shortcuts

### 1. Prepare the example project

```bash
cp -r ~/.rapid-os/examples/bugfix-lab/starter pricer-app && cd pricer-app
git init -b main && git add . && git commit -m "starter"
```

In Windows PowerShell, copy it with `Copy-Item -Recurse $HOME\.rapid-os\examples\bugfix-lab\starter pricer-app`. If you installed Rapid OS with `pip`, the example is in [`examples/bugfix-lab/starter`](https://github.com/alyconr/Rapid-OS/tree/main/examples/bugfix-lab/starter).

The example includes a failing test (`test_regression_expected_discount` in `tests/test_pricer.py`). Delete it before starting: the baseline must pass, and the agent will write its own test to reproduce the bug.

### 2. Set up the project

Open your agent in the folder and enter `/rapid-init` (`$rapid-init` in Codex). It detects Python and suggests `python -m unittest discover` as the test command; accept it. You can skip the project documents for this lab.

### 3. Request the work

```text
/rapid-bugfix the 10% discount returns a negative total
```

First, the agent reproduces the bug with a failing test (Rapid OS records that failure as expected evidence). It then fixes the formula and checks that the same test passes.

### 4. Approve in your terminal

When the agent finishes, it stops and gives you the exact command. Run it in **another terminal**, outside the agent, for example:

```bash
rapid approve gate.final-verification
```

Return to the agent and enter `/rapid-next` to close the run.

**Result:** The discount is calculated correctly, the regression test passes, and the run ends with a `pass` verdict.

No shortcuts yet? Install them once with `rapid shortcuts install --global --harness claude`, or run `rapid init --shortcuts` inside the folder. Replace `claude` with your agent. See the [shortcuts guide](../guides/shortcuts.md).

## Lab details

### Starting state

```text
pricer-app/
├── pricer.py
└── tests/
    ├── __init__.py
    └── test_pricer.py
```

The starter version contains this bug:
```python
discount_amount = subtotal * discount_percent # ERROR: must divide by 100.0
```
A 10% discount on $100 results in `-$900.00`.

### Requirements

1. **Formula:** Calculate the discount as `subtotal * (discount_percent / 100.0)`.
2. **Limits:** Validate that `discount_percent` is in the `[0.0, 100.0]` range; otherwise, raise `ValueError`.
3. **Regression:** Preserve support for carts with multiple products and quantities.
4. **Verification:** Check the baseline with the defective behavior before applying the fix.

## Advanced mode

You do not need this for the lab. The same kind of work done manually with v3 commands (spec, run, evidence, and evaluation), for CI or auditing, is covered in the [manual walkthrough](first-governed-project.md) and the [v3 governance loop](../governance-loop.md).
