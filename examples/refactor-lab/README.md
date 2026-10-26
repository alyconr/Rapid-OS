# Refactor Lab — Commission Calculation Decoupling

Accompanies the canonical tutorial [Refactor Engineering Lab](../../docs/tutorials/refactor-lab.md).

## Requirements

- `starter/`: Commission calculation and string formatting tightly coupled.
- `solution/`: Extraction of a decoupled `CommissionCalculator`, keeping the original signature of `CommissionReporter.calculate_and_format`.

## Running the tests

```bash
python -m unittest discover examples/refactor-lab/starter/tests
python -m unittest discover examples/refactor-lab/solution/tests
```
