---
title: Modo Bugfix
description: Flujo de trabajo para reproducir, aislar y corregir defectos con tests de regresión verificados.
---

# Modo Bugfix

El modo **Bugfix** prioriza la reproducción verificable del error, la contención del alcance para evitar efectos secundarios y la adición obligatoria de una prueba de regresión antes de declarar resuelto el defecto.

---

## Con el shortcut `/rapid-bugfix`

```text
/rapid-bugfix el descuento del 10% devuelve un total negativo
```

(En Codex: `$rapid-bugfix …`.) El shortcut conduce el run completo; la instalación y la invocación por harness están en la [guía de shortcuts](../shortcuts.md).

Qué hace su playbook (`templates/modes/bugfix.json` y las reglas del Conductor):

- La baseline se toma en `rapid start`, **antes** de que exista el test de reproducción.
- La primera tarea (`T001`) es «Reproducir con un test en rojo». Mientras está en curso y no hay una aserción `reproduction.T001` en PASS, `rapid next` propone `rapid check --expect fail --task T001 -- <test_command>`, que registra el fallo esperado como evidencia.
- Con el fallo registrado, `T001` se cierra con `rapid task done T001 --no-check` (la suite está en rojo a propósito) y la corrección va en las tareas siguientes.

El resto de esta guía describe el mismo ciclo con comandos v3 (**Modo avanzado**), útil para CI, depuración y auditoría.

---

## Principios del modo Bugfix

1. **No hay fix sin prueba de regresión**: Todo defecto debe reproducirse primero mediante una prueba que falle.
2. **Alcance mínimo**: El parche debe limitarse estrictamente a corregir la causa raíz sin introducir refactorizaciones oportunistas.
3. **Evidencia de no-regresión**: Se debe registrar evidencia de que la suite general de pruebas sigue aprobando al 100%.

---

## Flujo paso a paso

```mermaid
flowchart TD
    Bug["1. Defecto reportado"] --> Spec["2. rapid spec create --mode bugfix"]
    Spec --> TestFail["3. Escribir test de regresión (rojo)"]
    TestFail --> EvFail["4. Guardar log de reproducción local"]
    EvFail --> Fix["5. Harness aplica la corrección"]
    Fix --> TestPass["6. Test de regresión y suite general pasan (verde)"]
    TestPass --> EvPass["7. Registrar evidencia de resolución (test_result)"]
    EvPass --> Eval["8. rapid eval run --require-pass"]
```

---

## 1. Registrar la especificación del Bugfix

```bash
rapid spec create \
  --title "Fix timeout en reconciliación de balance" \
  --mode bugfix \
  --objective "Corregir bloqueo por concurrencia en la consulta de saldos" \
  --scope "Servicio de reconciliación y queries SQL transaccionales" \
  --acceptance "Test de estrés concurrente pasa sin interbloqueos en <500ms" \
  --task "1. Reproducir el deadlock en test de integración" \
  --task "2. Aplicar SELECT ... FOR UPDATE SKIP LOCKED" \
  --task "3. Verificar ausencia de regresión en balance general" \
  --status ready
```

---

## 2. Compilar el contexto con foco en el defecto

```bash
rapid context \
  --spec fix-timeout-en-reconciliacion-de-balance \
  --harness codex \
  --mode bugfix \
  --path "services/reconciliation" \
  --path "tests/integration/test_reconciliation.py" \
  --manifest
```

---

## 3. Crear el Run y vincular la política

```bash
rapid run create \
  --spec fix-timeout-en-reconciliacion-de-balance \
  --harness codex \
  --classification bounded \
  --risk medium
```

---

## 4. Capturar Evidencia de Reproducción y Resolución

### Paso A: Evidencia del fallo inicial (Reproducción local)
Captura la traza y resultado del fallo como artefacto de reproducción local sin registrarlo todavía como `test_result` ligado a tareas o compuertas del run (ya que el evaluador actual clasificaría cualquier `test_result` con `exit_code != 0` o `failed > 0` como fallo irreversible del run):

```bash
# Ejecutar test de reproducción y almacenar el log rojo como artefacto local
pytest -k test_reconciliation_deadlock > reproduction.log 2>&1 || true
```

> **Nota de Gobernanza (Roadmap):** El PR 2.1 introducirá soporte formal de contratos con `expectation: fail` para pruebas de reproducción previa. Hasta entonces, conserva el log de falla como artefacto local de diagnóstico (`reproduction.log`) y no lo vincules como evidencia de compuertas ni tareas.

### Paso B: Evidencia de la corrección y no-regresión
Una vez aplicado el cambio en el código y aprobadas todas las pruebas:

```json
{
  "kind": "test_result",
  "producer": "pytest-full-suite",
  "summary": "Suite completa verde incluyendo nuevo test de regresión",
  "gate_ids": ["implementation_tests"],
  "payload": {
    "suite": "all-tests",
    "exit_code": 0,
    "passed": 48,
    "failed": 0,
    "skipped": 0
  }
}
```

```bash
rapid evidence add \
  --run fix-timeout-en-reconciliacion-de-balance-r1-run-001 \
  --input resolution-evidence.json
```

---

## 5. Evaluación final del Run

Ejecuta la evaluación final:

```bash
rapid eval run \
  --run fix-timeout-en-reconciliacion-de-balance-r1-run-001 \
  --write \
  --require-pass
```

El veredicto confirmará que las compuertas de pruebas (`implementation_tests`) fueron satisfechas con evidencia empírica.

