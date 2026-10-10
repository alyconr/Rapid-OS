# First Governed Project — Task Tracker

Este proyecto de ejemplo acompaña al tutorial canónico [Primer Proyecto Gobernado](../../docs/tutorials/first-governed-project.md).

## Estructura

- `starter/`: Aplicación básica de seguimiento de tareas sin soporte de prioridades.
- `solution/`: Aplicación con soporte de prioridades (`low`, `medium`, `high`) y filtrado.

## Ejecución de pruebas

```bash
# Starter
python -m unittest discover examples/first-governed-project/starter/tests

# Solution
python -m unittest discover examples/first-governed-project/solution/tests
```
