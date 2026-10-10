# Bugfix Lab — Order Pricing Discount Bug

Acompaña al tutorial canónico [Bugfix Engineering Lab](../../docs/tutorials/bugfix-lab.md).

## Requisitos

- `starter/`: Cálculo de descuento erróneo sin normalización de porcentaje.
- `solution/`: Fórmula corregida `subtotal * (discount_percent / 100.0)` con tests de regresión.

## Ejecución de pruebas

```bash
python -m unittest discover examples/bugfix-lab/starter/tests
python -m unittest discover examples/bugfix-lab/solution/tests
```
