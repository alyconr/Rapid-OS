# First Governed Project — Task Tracker

This example project accompanies the canonical tutorial [First Governed Project](../../docs/tutorials/first-governed-project.md).

## Structure

- `starter/`: Basic task tracking application without priority support.
- `solution/`: Application with priority support (`low`, `medium`, `high`) and filtering.

## Running the tests

```bash
# Starter
python -m unittest discover examples/first-governed-project/starter/tests

# Solution
python -m unittest discover examples/first-governed-project/solution/tests
```
