# Bugfix Lab — Order Pricing Discount Bug

Acompaña al tutorial canónico [Bugfix Engineering Lab](../../docs/tutorials/bugfix-lab.md).

## Requisitos

- `starter/`: Cálculo de descuento erróneo sin normalización de porcentaje. Incluye caracterización del defecto (`test_defect_characterization`) y prueba de regresión que falla deliberadamente (`test_regression_expected_discount`) comprobando la existencia real del bug.
- `solution/`: Fórmula corregida `subtotal * (discount_percent / 100.0)` con suite completa de regresión en verde (`TestOrderPricerSolution`).

## Ejecución de pruebas

```bash
# El starter falla con exit code 1 (failures=1 en test_regression_expected_discount)
python -m unittest discover -s examples/bugfix-lab/starter/tests -t examples/bugfix-lab/starter

# La solución pasa al 100% con exit code 0
python -m unittest discover -s examples/bugfix-lab/solution/tests -t examples/bugfix-lab/solution
```

