# Laboratorio 3: Bugfix Engineering Lab

Aprende a gobernar la corrección de defectos con RAPID OS garantizando la captura de baseline, pruebas de reproducción y prevención de regresiones.

---

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

1. Ejecuta el test que demuestra el defecto en el estado inicial:

```bash
python -m unittest discover -s tests -t .
```

2. Registra la evidencia de baseline:
```json
{
  "kind": "test_result",
  "producer": "harness:claude",
  "summary": "Captura de baseline reproduciendo defecto de cálculo de descuento",
  "task_ids": ["T001"],
  "gate_ids": ["gate.baseline"],
  "capability_ids": ["tests.execute"],
  "payload": {
    "suite": "tests/test_pricer.py",
    "exit_code": 0,
    "passed": 2,
    "failed": 0,
    "skipped": 0
  }
}
```

Ingiérela:

```bash
rapid run status spec-order-discount-fix-r1-run-001 active
rapid run task spec-order-discount-fix-r1-run-001 T001 in_progress
rapid evidence add --run spec-order-discount-fix-r1-run-001 --input evidence_baseline.json
rapid run gate spec-order-discount-fix-r1-run-001 gate.baseline acknowledged
```

3. Aplica externamente la corrección en `pricer.py`:

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
```bash
rapid evidence add --run spec-order-discount-fix-r1-run-001 --input evidence_file_change.json
```

2. Registra el resultado de las nuevas pruebas unitarias:
```json
{
  "kind": "test_result",
  "producer": "harness:claude",
  "summary": "Suite de regresión aprobada tras corrección de escala",
  "task_ids": ["T001"],
  "gate_ids": ["gate.tests", "gate.final-verification"],
  "capability_ids": ["tests.execute"],
  "payload": {
    "suite": "tests/test_pricer.py",
    "exit_code": 0,
    "passed": 4,
    "failed": 0,
    "skipped": 0
  }
}
```

```bash
rapid evidence add --run spec-order-discount-fix-r1-run-001 --input evidence_regression.json
rapid run gate spec-order-discount-fix-r1-run-001 gate.tests acknowledged
rapid run gate spec-order-discount-fix-r1-run-001 gate.final-verification acknowledged
rapid run task spec-order-discount-fix-r1-run-001 T001 done
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

