# Laboratorio 3: Refactor Engineering Lab

Refactoriza sin romper nada: separa el cálculo de comisiones del formato del informe sin cambiar la API pública. En tu agente escribes tres cosas; en la terminal solo preparas el ejemplo y apruebas.

## Con shortcuts

### 1. Prepara el proyecto de ejemplo

```bash
cp -r ~/.rapid-os/examples/refactor-lab/starter commission-app && cd commission-app
git init -b main && git add . && git commit -m "starter"
```

En Windows PowerShell, la copia es `Copy-Item -Recurse $HOME\.rapid-os\examples\refactor-lab\starter commission-app`. Si instalaste Rapid OS con `pip`, el ejemplo está en [`examples/refactor-lab/starter`](https://github.com/alyconr/Rapid-OS/tree/main/examples/refactor-lab/starter).

### 2. Configura el proyecto

Abre tu agente en la carpeta y escribe `/rapid-init` (en Codex, `$rapid-init`). Detecta Python y propone `python -m unittest discover` como comando de tests: acéptalo. Los documentos del proyecto puedes omitirlos en este laboratorio.

### 3. Pide el trabajo

```text
/rapid-refactor extraer un CommissionCalculator puro sin cambiar la firma pública de CommissionReporter
```

Rapid OS guarda cuántos tests pasan antes del cambio (baseline). Si después del refactor pasan menos, el run se bloquea y el agente te muestra la diferencia.

### 4. Aprueba en tu terminal

Cuando el agente termina, se detiene y te da el comando exacto. Ejecútalo en **otra terminal**, fuera del agente, por ejemplo:

```bash
rapid approve gate.final-verification
```

Vuelve al agente y escribe `/rapid-next` para cerrar el run.

**Resultado:** `CommissionCalculator` existe, `CommissionReporter` conserva su firma, pasan los mismos tests que antes y el run termina con veredicto `pass`.

¿No tienes los shortcuts? Una sola vez: `rapid shortcuts install --global --harness claude`, o dentro de la carpeta `rapid init --shortcuts`. Detalle en la [guía de shortcuts](../guides/shortcuts.md).

---

## Detalles del laboratorio

### Estado inicial

```text
commission-app/
├── commission.py
└── tests/
    ├── __init__.py
    └── test_commission.py
```

En la versión inicial (`starter`):
```python
class CommissionReporter:
    @staticmethod
    def calculate_and_format(sales_amount: float, rate_percent: float) -> str:
        # Cálculo y string formatting acoplados monolíticamente
        commission = sales_amount * (rate_percent / 100.0)
        return f"[COMMISSION-REPORT] Sales: ${sales_amount:.2f} | Rate: {rate_percent:.1f}% | Due: ${commission:.2f}"
```

### Requisitos

1. **Separación de responsabilidades:** Crear la clase `CommissionCalculator` con método estático `calculate(sales_amount, rate_percent) -> float`.
2. **Preservación de API pública:** Mantener `CommissionReporter.calculate_and_format` delegando en el nuevo calculador.
3. **Validaciones idénticas:** Rechazar valores negativos con `ValueError`.
4. **Verificación doble:** Demostrar que las pruebas previas pasan sin modificación alguna sobre la interfaz pública.

---

## Modo avanzado

No lo necesitas para hacer el laboratorio. El mismo tipo de trabajo hecho a mano con los comandos v3 (spec, run, evidencia y evaluación), para CI o auditoría, está en el [recorrido manual (Bajo el capó)](first-governed-project.md) y en el [ciclo de gobernanza v3](../governance-loop.md).
