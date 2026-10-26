# Laboratorio 2: Bugfix Engineering Lab

Corrige un bug real: un descuento del 10% sobre $100 devuelve un total negativo. En tu agente escribes tres cosas; en la terminal solo preparas el ejemplo y apruebas.

## Con shortcuts

### 1. Prepara el proyecto de ejemplo

```bash
cp -r ~/.rapid-os/examples/bugfix-lab/starter pricer-app && cd pricer-app
git init -b main && git add . && git commit -m "starter"
```

En Windows PowerShell, la copia es `Copy-Item -Recurse $HOME\.rapid-os\examples\bugfix-lab\starter pricer-app`. Si instalaste Rapid OS con `pip`, el ejemplo está en [`examples/bugfix-lab/starter`](https://github.com/alyconr/Rapid-OS/tree/main/examples/bugfix-lab/starter).

El ejemplo trae un test en rojo (`test_regression_expected_discount` en `tests/test_pricer.py`). Bórralo antes de empezar: la baseline debe quedar en verde, y el agente escribirá su propio test que reproduce el bug.

### 2. Configura el proyecto

Abre tu agente en la carpeta y escribe `/rapid-init` (en Codex, `$rapid-init`). Detecta Python y propone `python -m unittest discover` como comando de tests: acéptalo. Los documentos del proyecto puedes omitirlos en este laboratorio.

### 3. Pide el trabajo

```text
/rapid-bugfix el descuento del 10% devuelve un total negativo
```

Primero el agente reproduce el bug con un test que falla (Rapid OS registra ese rojo como evidencia esperada), después corrige la fórmula y comprueba que el mismo test pasa.

### 4. Aprueba en tu terminal

Cuando el agente termina, se detiene y te da el comando exacto. Ejecútalo en **otra terminal**, fuera del agente, por ejemplo:

```bash
rapid approve gate.final-verification
```

Vuelve al agente y escribe `/rapid-next` para cerrar el run.

**Resultado:** El descuento se calcula bien, el test que reproducía el bug queda en verde y el run termina con veredicto `pass`.

¿No tienes los shortcuts? Una sola vez: `rapid shortcuts install --global --harness claude`, o dentro de la carpeta `rapid init --shortcuts`. Detalle en la [guía de shortcuts](../guides/shortcuts.md).

---

## Detalles del laboratorio

### Estado inicial

```text
pricer-app/
├── pricer.py
└── tests/
    ├── __init__.py
    └── test_pricer.py
```

En la versión inicial (`starter`):
```python
discount_amount = subtotal * discount_percent # ERROR: falta dividir entre 100.0
```
Un descuento del 10% en $100 resulta en `-$900.00`.

### Requisitos

1. **Fórmula:** Corregir el cálculo a `subtotal * (discount_percent / 100.0)`.
2. **Límites:** Validar que `discount_percent` esté en el rango `[0.0, 100.0]`; de lo contrario, lanzar `ValueError`.
3. **Regresión:** Mantener el soporte para carritos con múltiples productos y cantidades.
4. **Verificación:** Probar baseline con el comportamiento defectuoso antes de aplicar el parche.

---

## Modo avanzado

No lo necesitas para hacer el laboratorio. El mismo tipo de trabajo hecho a mano con los comandos v3 (spec, run, evidencia y evaluación), para CI o auditoría, está en el [recorrido manual (Bajo el capó)](first-governed-project.md) y en el [ciclo de gobernanza v3](../governance-loop.md).
