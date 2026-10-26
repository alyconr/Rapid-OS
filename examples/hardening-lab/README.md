# Hardening Lab — Boundary Validation & Input Hardening

Accompanies the canonical tutorial [Hardening Engineering Lab](../../docs/tutorials/hardening-lab.md).

## Requirements

- `starter/`: User profile registry without limits on length, format or sanitization.
- `solution/`: Defensive validation against arbitrary strings, invalid email formats and null bytes, raising `ValidationError`.

## Running the tests

```bash
python -m unittest discover examples/hardening-lab/starter/tests
python -m unittest discover examples/hardening-lab/solution/tests
```
