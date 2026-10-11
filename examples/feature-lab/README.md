# Feature Lab — In-Memory Booking Availability

Acompaña al tutorial canónico [Feature Engineering Lab](../../docs/tutorials/feature-lab.md).

## Requisitos

- `starter/`: Sistema de reservas sin detección de conflictos de horario.
- `solution/`: Validación estricta que lanza `SlotAlreadyBookedError` ante intentos de reserva duplicada para el mismo horario.

## Ejecución de pruebas

```bash
python -m unittest discover examples/feature-lab/starter/tests
python -m unittest discover examples/feature-lab/solution/tests
```
