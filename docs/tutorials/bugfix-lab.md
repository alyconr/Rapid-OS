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

## Modo avanzado

No lo necesitas para hacer el laboratorio. Es el mismo recorrido con los comandos v3, para entender qué registra cada paso y para CI y auditoría.

<details>
<summary>Ver el laboratorio con comandos v3</summary>

## 1. Overview

- **Nombre:** Corrección de Defecto en Cálculo de Descuentos.
- **Problema:** En el cálculo de facturación, la tasa de descuento no se divide entre 100, provocando totales erróneos y montos negativos.
- **Objetivo:** Ejecutar un flujo de modo `bugfix` con captura obligatoria de `gate.baseline` y suite de regresión aprobada.
- **Nivel de dificultad:** Intermedio.
- **Conocimientos previos:** Modos de ingeniería de RAPID OS.
- **Dependencias:** Python 3.10+ (biblioteca estándar).
- **Archivos de referencia:** [`examples/bugfix-lab/`](https://github.com/alyconr/Rapid-OS/tree/main/examples/bugfix-lab).

---

## 2. Learning Outcomes

1. Comprender por qué los modos `bugfix` exigen la compuerta `gate.baseline`.
2. Registrar evidencia de falla previa para documentar la existencia genuina del defecto.
3. Crear pruebas unitarias que aíslen el caso defectuoso.
4. Aplicar la corrección externamente y verificar la eliminación de la regresión.
5. Ingerir evidencia combinada de baseline y suite de pruebas final.

---

## 3. Initial State

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

---

## 4. Engineering Requirements

1. **Fórmula:** Corregir el cálculo a `subtotal * (discount_percent / 100.0)`.
2. **Límites:** Validar que `discount_percent` esté en el rango `[0.0, 100.0]`; de lo contrario, lanzar `ValueError`.
3. **Regresión:** Mantener el soporte para carritos con múltiples productos y cantidades.
4. **Verificación:** Probar baseline con el comportamiento defectuoso antes de aplicar el parche.

---

## 5. Guided Procedure

### Paso 1: Crear la Spec en Modo Bugfix

```bash
rapid spec create \
  --id spec-order-discount-fix \
  --title "Corrección de escala porcentual en OrderPricer" \
  --mode bugfix \
  --status ready
```

### Paso 2: Crear el Run y Detectar Gates

```bash
rapid context --manifest
rapid run create --spec spec-order-discount-fix --harness claude
```

Observa que la política asigna obligatoriamente:
- `gate.baseline`: Demostrar la reproducción del error antes del arreglo.
- `gate.tests`: Demostrar la aprobación de la suite completa.
- `gate.final-verification`: Verificación final.

---

## 6. External Execution & Baseline Capture

1. Ejecuta el test que caracteriza el comportamiento actual antes de modificar el código y captura el log:

```bash
python -m unittest tests/test_pricer.py > base.log 2>&1
```

2. Prepara la evidencia canónica de baseline (`evidence_baseline.json`) adjuntando el log generado:

```json
{
  "kind": "test_result",
  "producer": "harness:claude",
  "summary": "Captura de baseline previo con suite ejecutada y artifact adjunto",
  "task_ids": ["T001"],
  "gate_ids": ["gate.baseline"],
  "capability_ids": ["tests.execute"],
  "payload": {
    "suite": "tests/test_pricer.py",
    "exit_code": 0,
    "passed": 2,
    "failed": 0,
    "skipped": 0
  },
  "artifacts": ["base.log"]
}
```

3. Registra la evidencia y reconoce la compuerta `gate.baseline` mientras el Run se encuentra en estado `prepared`:

> **Product Truth (Lifecycle & Gate Phases)**:  
> Las compuertas de fase `PRE_EXECUTION` (como `gate.baseline` y `gate.workspace-isolation`) **deben** ser reconocidas mientras el Run está en estado `prepared`. Intentar transicionar el Run a `active` con una compuerta `PRE_EXECUTION` pendiente dispara `RAPID1014` (Precondition failed).

```bash
# Ingesta de evidencia en estado prepared
rapid evidence add --run spec-order-discount-fix-r1-run-001 --input evidence_baseline.json

# Reconocimiento de la compuerta PRE_EXECUTION
rapid run gate spec-order-discount-fix-r1-run-001 gate.baseline acknowledged

# Con las compuertas PRE_EXECUTION satisfechas, transicionar a active
rapid run status spec-order-discount-fix-r1-run-001 active
rapid run task spec-order-discount-fix-r1-run-001 T001 in_progress
```

4. Aplica externamente la corrección en `pricer.py`:

```python
class OrderPricer:
    @staticmethod
    def calculate_total(items: list[dict[str, float]], discount_percent: float = 0.0) -> float:
        if discount_percent < 0 or discount_percent > 100:
            raise ValueError("Discount must be between 0 and 100.")
        subtotal = sum(item["price"] * item.get("qty", 1) for item in items)
        discount_amount = subtotal * (discount_percent / 100.0)
        total = subtotal - discount_amount
        return round(total, 2)
```

---

## 7. Evidence Collection

1. Registra el cambio de archivos:

```json
{
  "kind": "file_change",
  "producer": "harness:claude",
  "summary": "Corrección de fórmula de descuento y adición de tests de regresión",
  "task_ids": ["T001"],
  "gate_ids": [],
  "capability_ids": ["repository.write"],
  "payload": {
    "paths": ["pricer.py", "tests/test_pricer.py"]
  }
}
```

```bash
rapid evidence add --run spec-order-discount-fix-r1-run-001 --input evidence_file_change.json
```

2. Ejecuta externamente la suite completa de pruebas unitarias y genera el log auténtico:

```bash
python -m unittest tests/test_pricer.py > tests.log 2>&1
```

3. Prepara la evidencia del resultado de pruebas (`evidence_regression.json`):

```json
{
  "kind": "test_result",
  "producer": "harness:claude",
  "summary": "Suite de regresión aprobada tras corrección de escala",
  "task_ids": ["T001"],
  "gate_ids": ["gate.tests"],
  "capability_ids": ["tests.execute"],
  "payload": {
    "suite": "tests/test_pricer.py",
    "exit_code": 0,
    "passed": 4,
    "failed": 0,
    "skipped": 0
  },
  "artifacts": ["tests.log"]
}
```

```bash
rapid evidence add --run spec-order-discount-fix-r1-run-001 --input evidence_regression.json
```

4. Registra la evidencia de verificación contractual final (`evidence_final.json`):

```json
{
  "kind": "review",
  "producer": "user",
  "summary": "Revisión final de código y verificación de ausencia de regresiones",
  "task_ids": ["T001"],
  "gate_ids": ["gate.final-verification"],
  "payload": {
    "review_type": "final",
    "outcome": "approved",
    "reviewer": "quality-engineer"
  }
}
```

```bash
rapid evidence add --run spec-order-discount-fix-r1-run-001 --input evidence_final.json
```

5. Registra la evidencia del espacio de trabajo (`evidence_workspace.json`):

```json
{
  "kind": "workspace",
  "producer": "harness:claude",
  "summary": "Verificación del espacio de trabajo local actual",
  "capability_ids": ["workspace.current"],
  "payload": {
    "mode": "current"
  }
}
```

```bash
rapid evidence add --run spec-order-discount-fix-r1-run-001 --input evidence_workspace.json
```

6. Completa la tarea, reconoce las compuertas `POST_EXECUTION` y finaliza el Run:

> **Product Truth (Post-Execution Order)**:  
> Las compuertas de fase `POST_EXECUTION` (`gate.tests`, `gate.final-verification`) exigen que las tareas del contrato hayan concluido (`T001 -> done`). Reconocerlas antes dispara `RAPID1014`.

```bash
# Marcar la tarea como completada
rapid run task spec-order-discount-fix-r1-run-001 T001 done

# Reconocer las compuertas POST_EXECUTION
rapid run gate spec-order-discount-fix-r1-run-001 gate.tests acknowledged
rapid run gate spec-order-discount-fix-r1-run-001 gate.final-verification acknowledged

# Transicionar el Run a su estado final
rapid run status spec-order-discount-fix-r1-run-001 finished
```

---

## 8. Evaluation

```bash
rapid eval run --run spec-order-discount-fix-r1-run-001 --write --require-pass
```

---

## 9. Validation

```bash
rapid validate
```

---

## 10. Assessment

- [x] Evidencia de baseline `E001` documentando el comportamiento original.
- [x] Corrección matemática implementada.
- [x] Evidencia de regresión aprobada sin errores.
- [x] Veredicto `pass` verificado deterministamente.

</details>
