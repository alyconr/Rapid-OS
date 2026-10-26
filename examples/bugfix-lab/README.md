# Bugfix Lab — Order Pricing Discount Bug

Accompanies the canonical tutorial [Bugfix Engineering Lab](../../docs/tutorials/bugfix-lab.md).

## Requirements

- `starter/`: Wrong discount calculation without percentage normalization. It includes a characterization of the defect (`test_defect_characterization`) and a regression test that fails on purpose (`test_regression_expected_discount`), confirming that the bug really exists.
- `solution/`: Corrected formula `subtotal * (discount_percent / 100.0)` with the full regression suite green (`TestOrderPricerSolution`).

## Running the tests

```bash
# The starter fails with exit code 1 (failures=1 in test_regression_expected_discount)
python -m unittest discover -s examples/bugfix-lab/starter/tests -t examples/bugfix-lab/starter

# The solution passes 100% with exit code 0
python -m unittest discover -s examples/bugfix-lab/solution/tests -t examples/bugfix-lab/solution
```
