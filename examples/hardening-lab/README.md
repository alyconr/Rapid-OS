# Hardening Lab — Boundary Validation & Input Hardening

Acompaña al tutorial canónico [Hardening Engineering Lab](../../docs/tutorials/hardening-lab.md).

## Requisitos

- `starter/`: Registro de perfiles de usuario sin límites de longitud, formato ni saneamiento.
- `solution/`: Validación defensiva contra cadenas arbitrarias, formatos de correo inválidos y bytes nulos, lanzando `ValidationError`.

## Ejecución de pruebas

```bash
python -m unittest discover examples/hardening-lab/starter/tests
python -m unittest discover examples/hardening-lab/solution/tests
```
