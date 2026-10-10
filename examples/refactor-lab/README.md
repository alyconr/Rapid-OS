# Refactor Lab — Commission Calculation Decoupling

Acompaña al tutorial canónico [Refactor Engineering Lab](../../docs/tutorials/refactor-lab.md).

## Requisitos

- `starter/`: Cálculo de comisiones y formato de cadena fuertemente acoplados.
- `solution/`: Extracción de `CommissionCalculator` desacoplado, manteniendo la firma original de `CommissionReporter.calculate_and_format`.

## Ejecución de pruebas

```bash
python -m unittest discover examples/refactor-lab/starter/tests
python -m unittest discover examples/refactor-lab/solution/tests
```
