# Laboratorio 4: Refactor Engineering Lab

Aprende a gobernar refactorizaciones complejas con RAPID OS desacoplando lógica de negocio sin alterar contratos públicos ni romper compatibilidad.

---

## 1. Overview

- **Nombre:** Desacoplamiento de Lógica de Comisiones.
- **Problema:** Un módulo de reportes combina cálculo financiero y formateo de texto en un único método monolítico, impidiendo reutilización y pruebas puras de dominio.
- **Objetivo:** Refactorizar extrayendo un `CommissionCalculator` puro manteniendo la firma pública de `CommissionReporter` intacta.
- **Nivel de dificultad:** Avanzado.
- **Conocimientos previos:** Modos de ingeniería y principios de diseño modular.
- **Dependencias:** Python 3.10+ (biblioteca estándar).
- **Archivos de referencia:** [`examples/refactor-lab/`](https://github.com/alyconr/Rapid-OS/tree/main/examples/refactor-lab).

---

## 2. Learning Outcomes

1. Clasificar operaciones de reestructuración interna bajo el modo `refactor`.
2. Demostrar paridad funcional comparando pruebas antes y después de la modificación.
3. Gobernar revisiones de código mediante evidencias de tipo `review`.
4. Garantizar que la suite previa y posterior mantenga una tasa de aprobación del 100%.

---

## 3. Initial State

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

---

## 4. Engineering Requirements

1. **Separación de responsabilidades:** Crear la clase `CommissionCalculator` con método estático `calculate(sales_amount, rate_percent) -> float`.
2. **Preservación de API pública:** Mantener `CommissionReporter.calculate_and_format` delegando en el nuevo calculador.
3. **Validaciones idénticas:** Rechazar valores negativos con `ValueError`.
4. **Verificación doble:** Demostrar que las pruebas previas pasan sin modificación alguna sobre la interfaz pública.

---

## 5. Guided Procedure

### Paso 1: Crear la Spec en Modo Refactor

```bash
rapid spec create \
  --id spec-commission-decoupling \
  --title "Extracción de CommissionCalculator de la capa de reporte" \
  --mode refactor \
  --status ready
```

### Paso 2: Crear el Run

```bash
rapid context --manifest
rapid run create --spec spec-commission-decoupling --harness vscode
```

---

## 6. External Execution

Implementa la solución desacoplada:

```python
class CommissionCalculator:
    """Pure domain logic for commission calculation."""
    @staticmethod
    def calculate(sales_amount: float, rate_percent: float) -> float:
        if sales_amount < 0 or rate_percent < 0:
            raise ValueError("Sales amount and rate must be non-negative.")
        return round(sales_amount * (rate_percent / 100.0), 2)

class CommissionReporter:
    """Presentation layer preserving backwards-compatible public API."""
    @staticmethod
    def calculate_and_format(sales_amount: float, rate_percent: float) -> str:
        commission = CommissionCalculator.calculate(sales_amount, rate_percent)
        return f"[COMMISSION-REPORT] Sales: ${sales_amount:.2f} | Rate: {rate_percent:.1f}% | Due: ${commission:.2f}"
```

---

## 7. Evidence Collection

1. Actualizar estado e ingerir evidencia de cambios en el código (`file_change`).
2. Ingerir evidencia de revisión técnica (`review`):

```json
{
  "kind": "review",
  "producer": "harness:vscode",
  "summary": "Revisión arquitectónica confirmando preservación de API pública",
  "task_ids": ["T001"],
  "gate_ids": [],
  "capability_ids": [],
  "payload": {
    "review_type": "peer",
    "outcome": "approved",
    "reviewer": "tech-lead"
  }
}
```

```bash
rapid evidence add --run spec-commission-decoupling-r1-run-001 --input evidence_review.json
```

3. Ingerir evidencia de pruebas de no-regresión (`test_result`):

```json
{
  "kind": "test_result",
  "producer": "harness:vscode",
  "summary": "Pruebas de compatibilidad y nuevo calculador de comisiones aprobadas",
  "task_ids": ["T001"],
  "gate_ids": ["gate.tests", "gate.final-verification"],
  "capability_ids": ["tests.execute"],
  "payload": {
    "suite": "tests/test_commission.py",
    "exit_code": 0,
    "passed": 3,
    "failed": 0,
    "skipped": 0
  }
}
```

```bash
rapid evidence add --run spec-commission-decoupling-r1-run-001 --input evidence_tests.json
rapid run gate spec-commission-decoupling-r1-run-001 gate.tests acknowledged
rapid run gate spec-commission-decoupling-r1-run-001 gate.final-verification acknowledged
rapid run task spec-commission-decoupling-r1-run-001 T001 done
rapid run status spec-commission-decoupling-r1-run-001 finished
```

---

## 8. Evaluation

```bash
rapid eval run --run spec-commission-decoupling-r1-run-001 --write --require-pass
```

---

## 9. Validation

```bash
rapid validate
```

---

## 10. Assessment

- [x] Lógica desacoplada en `CommissionCalculator`.
- [x] API pública previa 100% retrocompatible.
- [x] Evidencia de `review` aprobada por revisor humano/técnico.
- [x] Veredicto `pass` obtenido.

