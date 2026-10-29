---
title: Modo Refactor
description: Guía de refactorización arquitectónica sin regresiones funcionales ni cambios de comportamiento.
---

# Modo Refactor

El modo **Refactor** gobierna cambios en la estructura interna del código (simplificación, desacoplamiento, rendimiento, eliminación de deuda técnica) garantizando que los contratos externos y el comportamiento observable se mantengan idénticos.

---

## Con el shortcut `/rapid-refactor`

```text
/rapid-refactor separar el cálculo de comisiones del formato de salida
```

(En Codex: `$rapid-refactor …`.) El shortcut conduce el run completo; la instalación y la invocación por harness están en la [guía de shortcuts](../shortcuts.md).

Qué hace su playbook (`templates/modes/refactor.json` y las reglas del Conductor):

- La baseline es obligatoria (`gate.baseline`): es la referencia de no regresión.
- **Arquitectura:** si el proyecto tiene `.rapid-os/standards/architecture.json` (lo escribe el onboarding con el stack elegido), el contrato incluye el gate de máquina `gate.architecture` (obligatorio, no dispensable) y `rapid next` propone `rapid check --gate gate.architecture -- rapid arch check --new-only`. Una violación de capas o de contrato público es `RAPID1420` y `rapid finish` no da `PASS` hasta que se corrija el código. Solo cuentan las violaciones que el run añade: las que el proyecto ya tenía cuando el run empezó son deuda, se informan y no bloquean, y **un refactor es donde esa deuda se paga**: en este modo, un archivo que el run toca y que aún tiene una violación antigua cuenta como fallo, así que no se puede tocar un archivo y dejarlo violando. Cuando `api/` (o la capa de entrada del stack) importa `infrastructure/`, el mensaje dice dónde va la composición para ese stack (en `python-fastapi`, `app/main.py` o el `public.py` del módulo). Detalle en [Arquitectura por stack](../../concepts/architecture.md#el-gate-gatearchitecture).
- Cuando todas las tareas terminan, si el último `test_result` tiene menos tests pasados que la baseline, `rapid next` devuelve `blocked` con la diferencia: un refactor no puede reducir los tests que pasan. La comparación nunca se omite en silencio: desde que el run está activo, un refactor cuyo `gate.baseline` no tiene una ejecución de tests **con conteo** (la baseline se grabó como comando suelto, o la salida no tenía un resumen que Rapid OS pueda leer) queda `blocked` con la instrucción de repetirla (`rapid check --gate gate.baseline -- <comando de test>`), y la comprobación de cobertura perdida también se aplica a mitad de run. Un check ligado a la baseline o a una tarea cuenta como ejecución de tests cuando su salida tiene resumen, sea cual sea su argv. Si la baseline y la última ejecución de tests usaron comandos distintos, `rapid next` y `rapid finish` avisan de que sus conteos no son comparables. Antes de aprobar, `rapid approve` y `rapid finish`, el código debe ser el que vio el último check de `gate.tests` (`RAPID1423`), así que no se puede borrar un test después del último check.
- Es una regla del Conductor (`rapid_os/orchestration/conductor.py`), no del evaluador.

El resto de esta guía describe el mismo ciclo con comandos v3 (**Modo avanzado**), útil para CI, depuración y auditoría.

---

## Reglas de oro del Refactor en RAPID OS

1. **Invarianza de comportamiento**: Si los tests funcionales existentes requieren modificaciones de aserción para pasar, no es un refactor puro; es un cambio funcional encubierto.
2. **Baseline obligatorio**: Debe existir una foto verificada del estado de las pruebas antes de modificar la primera línea de código.
3. **Paridad de suite**: La misma suite de pruebas debe ejecutarse antes y después con 0 fallos.

---

## Flujo paso a paso

```mermaid
flowchart LR
    Scan["rapid scan --write"] --> Spec["rapid spec create --mode refactor"]
    Spec --> Run["rapid run create --risk medium"]
    Run --> Base["1. Registrar Baseline"]
    Base --> Exec["2. Refactorizar código"]
    Exec --> Verify["3. Verificar Paridad"]
    Verify --> Eval["4. rapid eval run --require-pass"]
```

---

## 1. Especificación del Refactor

Registra los límites exactos de la reestructuración:

```bash
rapid spec create \
  --title "Desacoplar capa de persistencia en pagos" \
  --mode refactor \
  --objective "Extraer repositorio abstracto para aislar la base de datos de la lógica de dominio" \
  --scope "Módulo payments/ y adapters/db/" \
  --acceptance "0 cambios en firmas públicas de servicios y suite de 150 tests pasando al 100%" \
  --task "1. Definir PaymentRepositoryProtocol" \
  --task "2. Implementar PostgresPaymentRepository" \
  --task "3. Inyectar dependencia en PaymentService" \
  --status ready
```

---

## 2. Iniciar el Run y registrar el Baseline

Crea el run en RAPID OS:

```bash
rapid run create \
  --spec desacoplar-capa-de-persistencia-en-pagos \
  --harness codex \
  --classification bounded \
  --risk medium
```

### Captura de Evidencia Baseline
Ejecuta la suite completa sobre el código original y añade la evidencia:

```json
{
  "kind": "test_result",
  "producer": "pytest-baseline",
  "summary": "Baseline de 150 tests aprobados en código original",
  "gate_ids": ["baseline_check"],
  "payload": {
    "suite": "all-tests-baseline",
    "exit_code": 0,
    "passed": 150,
    "failed": 0,
    "skipped": 0
  }
}
```

```bash
rapid evidence add \
  --run desacoplar-capa-de-persistencia-en-pagos-r1-run-001 \
  --input baseline-evidence.json
```

Acredita la compuerta de baseline en el estado del run:

```bash
rapid run gate \
  desacoplar-capa-de-persistencia-en-pagos-r1-run-001 \
  baseline_check \
  acknowledged \
  --reason "Baseline ejecutado y verificado en 150 tests verdes"
```

---

## 3. Ejecución del Refactor en el Harness

Entrega las instrucciones a tu agente o asistente de código asegurando que no toque los archivos de pruebas de contrato existentes.

---

## 4. Captura de Evidencia Posterior y Diff

### Evidencia de paridad de pruebas
```json
{
  "kind": "test_result",
  "producer": "pytest-post-refactor",
  "summary": "150 tests aprobados post-refactor con cero fallos",
  "gate_ids": ["implementation_tests"],
  "payload": {
    "suite": "all-tests-post-refactor",
    "exit_code": 0,
    "passed": 150,
    "failed": 0,
    "skipped": 0
  }
}
```

```bash
rapid evidence add \
  --run desacoplar-capa-de-persistencia-en-pagos-r1-run-001 \
  --input post-evidence.json
```

### Evidencia de cambios de archivos (`file_change`)
```json
{
  "kind": "file_change",
  "producer": "git-inspector",
  "summary": "Reestructuración confinada al módulo payments sin tocar tests",
  "payload": {
    "paths": [
      "payments/service.py",
      "payments/repositories.py"
    ]
  }
}
```

```bash
rapid evidence add \
  --run desacoplar-capa-de-persistencia-en-pagos-r1-run-001 \
  --input files-evidence.json
```

---

## 5. Evaluación de Comportamiento

```bash
rapid eval run \
  --run desacoplar-capa-de-persistencia-en-pagos-r1-run-001 \
  --write \
  --require-pass
```

El motor de evaluación confirmará que la compuerta de baseline y las pruebas de implementación están verificadas con evidencia matemática idónea.

