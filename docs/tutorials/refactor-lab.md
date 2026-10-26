---
title: Lab 3 - Refactor Engineering
description: Refactor commission calculation without changing the public API using the Rapid OS workflow.
---

# Lab 3: Refactor Engineering

Refactor without breaking anything: separate commission calculation from report formatting without changing the public API. You will enter three things in your agent; in the terminal, you only prepare the example and approve the result.

## With shortcuts

### 1. Prepare the example project

```bash
cp -r ~/.rapid-os/examples/refactor-lab/starter commission-app && cd commission-app
git init -b main && git add . && git commit -m "starter"
```

In Windows PowerShell, use `Copy-Item -Recurse $HOME\.rapid-os\examples\refactor-lab\starter commission-app`. If you installed Rapid OS with `pip`, the example is in [`examples/refactor-lab/starter`](https://github.com/alyconr/Rapid-OS/tree/main/examples/refactor-lab/starter).

### 2. Set up the project

Open your agent in the folder and enter `/rapid-init` (`$rapid-init` in Codex). It detects Python and suggests `python -m unittest discover` as the test command; accept it. You can skip the project documents for this lab.

### 3. Request the work

```text
/rapid-refactor extract a pure CommissionCalculator without changing CommissionReporter's public signature
```

Rapid OS records how many tests pass before the change (the baseline). If fewer pass after the refactor, the run is blocked and the agent shows you the difference.

### 4. Approve in your terminal

When the agent finishes, it stops and gives you the exact command. Run it in **another terminal**, outside the agent, for example:

```bash
rapid approve gate.final-verification
```

Return to the agent and enter `/rapid-next` to close the run.

**Result:** `CommissionCalculator` exists, `CommissionReporter` retains its signature, the same tests still pass, and the run ends with a `pass` verdict.

No shortcuts yet? Install them once with `rapid shortcuts install --global --harness claude`, or run `rapid init --shortcuts` inside the folder. Replace `claude` with your agent. See the [shortcuts guide](../guides/shortcuts.md).

## Lab details

### Starting state

```text
commission-app/
├── commission.py
└── tests/
    ├── __init__.py
    └── test_commission.py
```

The starter version couples calculation and string formatting in one method:
```python
class CommissionReporter:
    @staticmethod
    def calculate_and_format(sales_amount: float, rate_percent: float) -> str:
        # Calculation and string formatting are tightly coupled
        commission = sales_amount * (rate_percent / 100.0)
        return f"[COMMISSION-REPORT] Sales: ${sales_amount:.2f} | Rate: {rate_percent:.1f}% | Due: ${commission:.2f}"
```

### Requirements

1. **Separate responsibilities:** Create a `CommissionCalculator` class with a static `calculate(sales_amount, rate_percent) -> float` method.
2. **Preserve the public API:** Keep `CommissionReporter.calculate_and_format` and delegate to the new calculator.
3. **Keep validation consistent:** Reject negative values with `ValueError`.
4. **Verify twice:** Show that the existing tests pass without any change to the public interface.

## Advanced mode

You do not need this for the lab. The same kind of work done manually with v3 commands (spec, run, evidence, and evaluation), for CI or auditing, is covered in the [manual walkthrough](first-governed-project.md) and the [v3 governance loop](../governance-loop.md).
