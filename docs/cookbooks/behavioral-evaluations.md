---
title: Evaluaciones de Comportamiento (Behavioral Evals)
description: Cookbook de evaluación determinista de contratos, compuertas y evidencias en RAPID OS.
---

# Evaluaciones de Comportamiento (Behavioral Evals)

El motor de **Evaluación de Comportamiento** (`BehavioralEvaluator`) de RAPID OS realiza auditorías offline y deterministas sobre la ejecución de un run. Evalúa el contrato (`ExecutionContract`), el estado del ciclo (`RunState`) y el conjunto de evidencias inmutables (`RunEvidence[]`) contra un conjunto de reglas canónicas (`BehavioralRuleset`).

---

## Product Truth: La naturaleza de la Evaluación

> **Principio de Verdad del Producto**:
> 1. RAPID OS **no** invoca modelos LLM para evaluar código ("LLM-as-a-judge"). La evaluación es **100% matemática, lógica y reproducible**.
> 2. Una declaración de estado (ej. `GateDisposition.ACKNOWLEDGED`) es una aserción del usuario; si no cuenta con evidencia observable respaldándola, el evaluador la marca como `UNVERIFIED`.
> 3. El veredicto `PASS` certifica que las reglas y compuertas exigidas por la política se satisfacen con las evidencias registradas. **No garantiza matemáticamente que el software esté libre de defectos**.

---

## 1. Los cuatro veredictos de Evaluación (`EvaluationVerdict`)

| Veredicto | Significado | Exigencia en CI (`--require-pass`) |
| :--- | :--- | :--- |
| **`pass`** | Todas las compuertas obligatorias y requerimientos cuentan con evidencias válidas que las satisfacen al 100%. | **Pasa** (Exit code `0`) |
| **`pass_with_waivers`** | Todas las compuertas se satisfacen, pero una o más compuertas permitidas fueron formalmente exentas con un waiver justificado. | **Pasa** (Exit code `0`) |
| **`unverified`** | Existen compuertas reconocidas en el estado que carecen del registro de evidencia observable correspondiente. | **Falla** (Exit code `1`, diagnóstico `RAPID1225`) |
| **`fail`** | Al menos una compuerta obligatoria fue rechazada, omitida, o una prueba falló según la evidencia registrada. | **Falla** (Exit code `1`, diagnóstico `RAPID1226`) |

---

## 2. Ejecución de la Evaluación (`rapid eval run`)

Por defecto, la evaluación se ejecuta en modo de solo lectura para inspeccionar el resultado en terminal:

```bash
# Evaluación en memoria (Read-only)
rapid eval run --run my-run-001

# Evaluación con formato JSON
rapid eval run --run my-run-001 --json
```

### Persistir el reporte de evaluación (`--write`)
Para registrar el reporte inmutable en `.rapid-os/evals/<run-id>/reports/eval_report_0001.json`:

```bash
rapid eval run --run my-run-001 --write
```

### Modo estricto para integración continua (`--require-pass`)
En flujos de CI/CD o hooks pre-merge, puedes exigir que el comando falle si el veredicto no es `pass` o `pass_with_waivers`:

```bash
rapid eval run --run my-run-001 --require-pass
```

---

## 3. Inspección y Repetición Semántica (Replay)

RAPID OS permite consultar el histórico de reportes de evaluación generados para un run:

```bash
# Listar reportes generados
rapid eval list --run my-run-001

# Inspeccionar el detalle de una revisión de reporte
rapid eval show --run my-run-001 --revision 1
```

### Protección contra manipulación manual
Cada vez que se carga un reporte (`rapid eval show` o `rapid validate`), RAPID OS ejecuta una **repetición semántica obligatoria** (*semantic replay*): vuelve a computar las aserciones sobre el contrato, el estado y las evidencias reales en disco. Si alguien alteró manualmente el archivo de reporte para cambiar un `FAIL` por `PASS`, el sistema detecta la discrepancia y emite el diagnóstico `RAPID1223`.

---

## 4. Estructura de un Reporte de Evaluación (`EvaluationReport`)

Un reporte generado contiene los siguientes bloques fundamentales:

```json
{
  "schema_version": 1,
  "run_id": "my-run-001",
  "revision": 1,
  "verdict": "pass",
  "ruleset_version": 1,
  "ruleset_digest": "3a4b5c6d...",
  "contract_digest": "e1f2a3b4...",
  "state_digest": "9f8e7d6c...",
  "evidence_set_digest": "4c3b2a1f...",
  "summary": {
    "total_assertions": 8,
    "satisfied": 8,
    "waived": 0,
    "unverified": 0,
    "failed": 0
  },
  "assertions": [
    {
      "id": "A001_contract_integrity",
      "category": "contract",
      "status": "satisfied",
      "target": "ExecutionContract",
      "reason": "Digest coincide y spec está en estado ready"
    },
    {
      "id": "A002_gate_implementation_tests",
      "category": "gate",
      "status": "satisfied",
      "target": "implementation_tests",
      "reason": "Evidencia E001 (test_result) acredita 42 tests exitosos"
    }
  ]
}
```
