# Laboratorio 1: Primer Proyecto Gobernado

Aprende a ejecutar el Governance Loop completo de RAPID OS v3 sobre un proyecto Python real con un asistente o coding harness externo.

---

## 1. Overview

- **Nombre:** Task Tracker CLI Governance.
- **Problema:** Un proyecto Python sin gobernanza arriesga cambios no validados introducidos por asistentes de IA. Se requiere implementar una nueva funcionalidad de prioridad de tareas bajo un contrato verificable.
- **Objetivo:** Recorrer todo el ciclo de gobernanza desde `rapid init` hasta la evaluación de evidencia y validación final de integridad.
- **Nivel de dificultad:** Principiante.
- **Conocimientos previos:** Uso básico de terminal y comandos de Python.
- **Dependencias:** Python 3.10+ (exclusivamente biblioteca estándar).
- **Archivos de referencia:** [`examples/first-governed-project/`](https://github.com/alyconr/Rapid-OS/tree/main/examples/first-governed-project).

---

## 2. Learning Outcomes

Al completar este laboratorio, sabrás cómo:
1. Inicializar RAPID OS en un repositorio existente.
2. Escanear facts del proyecto mediante `rapid scan --write`.
3. Crear una especificación declarativa (`rapid spec create`).
4. Compilar un Context Bundle reproducible (`rapid context --manifest`).
5. Inspeccionar y resolver la política de ejecución (`rapid policy show`).
6. Generar un `ExecutionContract` inmutable y un `RunState` inicial (`rapid run create`).
7. Resolver el perfil de capacidades de tu coding harness (`rapid harness show`).
8. Ejecutar la implementación externamente con tu herramienta o harness preferido.
9. Actualizar tareas y gates en el estado versionado (`rapid run task` y `rapid run gate`).
10. Registrar evidencia determinista vinculada a revisiones de estado (`rapid evidence add`).
11. Evaluar el cumplimiento del Run (`rapid eval run --write --require-pass`).
12. Validar la integridad holística del proyecto (`rapid validate`).

---

## 3. Initial State

La aplicación inicial es un gestor de tareas en memoria:

```text
task-tracker/
├── app.py
└── tests/
    ├── __init__.py
    └── test_app.py
```

Estado inicial de `app.py`:

```python
# app.py
"""Minimal Task Tracker application."""

class TaskTracker:
    def __init__(self):
        self.tasks: list[dict[str, object]] = []

    def add_task(self, title: str) -> dict[str, object]:
        if not title or not title.strip():
            raise ValueError("Task title cannot be empty.")
        task = {
            "id": len(self.tasks) + 1,
            "title": title.strip(),
            "status": "pending",
        }
        self.tasks.append(task)
        return task

    def list_tasks(self) -> list[dict[str, object]]:
        return list(self.tasks)
```

Estado inicial de `tests/test_app.py`:

```python
# tests/test_app.py
import unittest
from app import TaskTracker

class TestTaskTracker(unittest.TestCase):
    def setUp(self):
        self.tracker = TaskTracker()

    def test_add_and_list_tasks(self):
        task = self.tracker.add_task("Initial task")
        self.assertEqual(task["id"], 1)
        self.assertEqual(task["title"], "Initial task")
        self.assertEqual(task["status"], "pending")
        self.assertEqual(len(self.tracker.list_tasks()), 1)

    def test_reject_empty_task(self):
        with self.assertRaises(ValueError):
            self.tracker.add_task("")

if __name__ == "__main__":
    unittest.main()
```

Inicialización del paquete de pruebas `tests/__init__.py`:

```python
# tests/__init__.py
"""Test package initialization."""
```

En este estado inicial, `TaskTracker.add_task(title)` solo acepta el título de la tarea y le asigna el estado `pending`.

---

## 4. Engineering Requirements

1. **Nueva funcionalidad:** Permitir especificar la prioridad de la tarea (`low`, `medium`, `high`), por defecto `medium`.
2. **Validación:** Rechazar prioridades desconocidas con `ValueError`.
3. **Filtrado:** `list_tasks(priority=None)` debe permitir filtrar por prioridad cuando se indique.
4. **Preservación:** No romper pruebas unitarias existentes.

---

## 5. Guided Procedure

### Paso 1: Inicializar RAPID OS

En la raíz del proyecto, inicializa el entorno de gobernanza seleccionando el stack y arquetipo deseados:

```bash
rapid init --stack python-ai --archetype mvp --no-scan
```

Esto crea la estructura `.rapid-os/` con sus estándares y configuración base.

### Paso 2: Escanear el proyecto

```bash
rapid scan --write
```

El scanner detecta el lenguaje (Python) y los directorios de pruebas (`tests/`), persistiendo el Project Model.

### Paso 3: Crear la Especificación

Crea la especificación formal con su tarea de implementación declarada (`--task`):

```bash
rapid spec create \
  --id spec-task-priority \
  --title "Añadir soporte de prioridades a TaskTracker" \
  --mode feature \
  --task "T001: Implementar soporte de prioridades en TaskTracker" \
  --status ready
```

### Paso 4: Compilar el Context Bundle

Genera el paquete de contexto determinista para alimentar al coding harness:

```bash
rapid context --manifest
```

### Paso 5: Consultar la Política de Ejecución

```bash
rapid policy show
```

Para una especificación en modo `feature`, el motor de políticas resuelve la clasificación `bounded` (las clases canónicas son `spike`, `bounded` y `architectural`) con nivel de riesgo `medium`. Esta política requiere las siguientes compuertas obligatorias:
- `gate.baseline` (fase `pre_execution`): verificación previa de la salud de pruebas del repositorio antes de iniciar cambios.
- `gate.tests` (fase `post_execution`): verificación con suite de pruebas aprobada y artefacto de log adjunto.
- `gate.final-verification` (fase `post_execution`): revisión formal final de cumplimiento contractual con veredicto aprobado.

### Paso 6: Crear el Run de Ejecución

```bash
rapid run create --spec spec-task-priority --harness codex
```

Esto genera un identificador de run determinista (por ejemplo `spec-task-priority-r1-run-001`), calcula el digest SHA-256 del contrato y escribe el snapshot inicial `RunState s1` en estado `prepared`.

### Paso 7: Resolver Capabilities del Harness

```bash
rapid harness show codex
```

Observa que RAPID OS reporta las capacidades soportadas (`context.consume`, `repository.read`, `workspace.current`) y aquellas que dependen de tu entorno local (`tests.execute`, `repository.write`).

---

## 6. External Execution

> **Nota de límite de responsabilidades:** RAPID OS **no** edita el código. La implementación la realiza el desarrollador o su coding harness externo (Claude Code, Cursor, Codex, Antigravity, etc.).

### Paso 1: Ejecución y Captura del Baseline

Antes de modificar el código y activar el run, ejecuta la suite de pruebas existente y captura la salida auténtica en un archivo de artefacto `base.log`:

```bash
python -m unittest discover -s tests -t . > base.log 2>&1
```

### Paso 2: Implementación Externa de Código y Pruebas

Modifica externamente `app.py` y `tests/test_app.py` para cumplir los requerimientos:

```python
# app.py
"""Enhanced Task Tracker application with priority support."""

class TaskTracker:
    VALID_PRIORITIES = ("low", "medium", "high")

    def __init__(self):
        self.tasks: list[dict[str, object]] = []

    def add_task(self, title: str, priority: str = "medium") -> dict[str, object]:
        if not title or not title.strip():
            raise ValueError("Task title cannot be empty.")
        priority_normalized = priority.lower().strip()
        if priority_normalized not in self.VALID_PRIORITIES:
            raise ValueError(f"Invalid priority '{priority}': must be one of {self.VALID_PRIORITIES}.")
        task = {
            "id": len(self.tasks) + 1,
            "title": title.strip(),
            "priority": priority_normalized,
            "status": "pending",
        }
        self.tasks.append(task)
        return task

    def list_tasks(self, priority: str | None = None) -> list[dict[str, object]]:
        if priority is None:
            return list(self.tasks)
        p = priority.lower().strip()
        return [t for t in self.tasks if t["priority"] == p]
```

Actualiza la suite en `tests/test_app.py`:

```python
# tests/test_app.py
import unittest
from app import TaskTracker

class TestTaskTracker(unittest.TestCase):
    def setUp(self):
        self.tracker = TaskTracker()

    def test_add_and_list_tasks_default_priority(self):
        task = self.tracker.add_task("Initial task")
        self.assertEqual(task["id"], 1)
        self.assertEqual(task["title"], "Initial task")
        self.assertEqual(task["priority"], "medium")
        self.assertEqual(task["status"], "pending")
        self.assertEqual(len(self.tracker.list_tasks()), 1)

    def test_add_task_with_custom_priority(self):
        t1 = self.tracker.add_task("Urgent bug", priority="high")
        t2 = self.tracker.add_task("Clean backlog", priority="low")
        self.assertEqual(t1["priority"], "high")
        self.assertEqual(t2["priority"], "low")
        high_tasks = self.tracker.list_tasks(priority="high")
        self.assertEqual(len(high_tasks), 1)
        self.assertEqual(high_tasks[0]["title"], "Urgent bug")

    def test_reject_invalid_priority(self):
        with self.assertRaises(ValueError):
            self.tracker.add_task("Invalid", priority="critical")

    def test_reject_empty_task(self):
        with self.assertRaises(ValueError):
            self.tracker.add_task("")

if __name__ == "__main__":
    unittest.main()
```

Ejecuta la suite actualizada capturando el registro de salida en `tests.log`:

```bash
python -m unittest discover -s tests -t . > tests.log 2>&1
```

---

## 7. Evidence Collection

Actualiza el estado del Run ingiriendo la evidencia exigida por el `BehavioralEvaluator`:

### 1. Registrar evidencia de Baseline y Acreditar `gate.baseline`

El evaluador exige que `gate.baseline` cuente con evidencia de prueba o comando con `exit_code: 0`, cero fallos y al menos un artefacto físico (`base.log`). Además, las compuertas de fase `pre_execution` deben reconocerse obligatoriamente antes de activar el run.

Prepara `evidence_baseline.json`:

```json
{
  "kind": "test_result",
  "producer": "harness:codex",
  "summary": "Verificación exitosa de baseline previo a modificaciones",
  "task_ids": ["T001"],
  "gate_ids": ["gate.baseline"],
  "capability_ids": ["tests.execute"],
  "payload": {
    "suite": "tests/test_app.py",
    "exit_code": 0,
    "passed": 2,
    "failed": 0,
    "skipped": 0
  },
  "artifacts": ["base.log"]
}
```

Ingiere la evidencia y reconoce la compuerta:

```bash
rapid evidence add --run spec-task-priority-r1-run-001 --input evidence_baseline.json
rapid run gate spec-task-priority-r1-run-001 gate.baseline acknowledged
```

### 2. Activar el Run e iniciar la tarea

Una vez satisfecha la compuerta previa, pasa el run al estado `active` y marca la tarea en progreso:

```bash
rapid run status spec-task-priority-r1-run-001 active
rapid run task spec-task-priority-r1-run-001 T001 in_progress
```

### 3. Registrar evidencia de cambios en el código (`file_change`)

El evaluador exige constatar la capacidad `repository.write` mediante evidencia de tipo `file_change` asociada a las tareas en el alcance del contrato.

Prepara `evidence_file_change.json`:

```json
{
  "kind": "file_change",
  "producer": "harness:codex",
  "summary": "Implementación de prioridad en app.py y tests",
  "task_ids": ["T001"],
  "gate_ids": [],
  "capability_ids": ["repository.write"],
  "payload": {
    "paths": ["app.py", "tests/test_app.py"]
  }
}
```

Ingiérelo en RAPID OS:

```bash
rapid evidence add --run spec-task-priority-r1-run-001 --input evidence_file_change.json
```

### 4. Registrar evidencia de pruebas aprobadas (`test_result`)

El evaluador exige que `gate.tests` contenga evidencia `test_result` con `exit_code: 0`, `failed: 0` y al menos un artefacto de log registrado (`tests.log`).

Prepara `evidence_test_result.json`:

```json
{
  "kind": "test_result",
  "producer": "harness:codex",
  "summary": "Ejecución exitosa de suite de pruebas unitarias",
  "task_ids": ["T001"],
  "gate_ids": ["gate.tests"],
  "capability_ids": ["tests.execute"],
  "payload": {
    "suite": "tests/test_app.py",
    "exit_code": 0,
    "passed": 4,
    "failed": 0,
    "skipped": 0
  },
  "artifacts": ["tests.log"]
}
```

Ingiérelo:

```bash
rapid evidence add --run spec-task-priority-r1-run-001 --input evidence_test_result.json
```

### 5. Registrar evidencia de espacio de trabajo (`workspace`)

El evaluador exige validar la capacidad derivada `workspace.current` mediante una evidencia de tipo `workspace` con payload `mode: "current"`.

Prepara `evidence_workspace.json`:

```json
{
  "kind": "workspace",
  "producer": "harness:codex",
  "summary": "Verificación de espacio de trabajo actual",
  "task_ids": ["T001"],
  "gate_ids": [],
  "capability_ids": ["workspace.current"],
  "payload": {
    "mode": "current"
  }
}
```

Ingiérelo:

```bash
rapid evidence add --run spec-task-priority-r1-run-001 --input evidence_workspace.json
```

### 6. Registrar evidencia de revisión final (`review`)

El evaluador exige que la compuerta contractual `gate.final-verification` cuente con una evidencia de tipo `review` con `review_type: "final"` y `outcome: "approved"`.

Prepara `evidence_review.json`:

```json
{
  "kind": "review",
  "producer": "harness:codex",
  "summary": "Revisión final contractual de cumplimiento",
  "task_ids": ["T001"],
  "gate_ids": ["gate.final-verification"],
  "payload": {
    "review_type": "final",
    "outcome": "approved",
    "reviewer": "quality-lead"
  }
}
```

Ingiérelo:

```bash
rapid evidence add --run spec-task-priority-r1-run-001 --input evidence_review.json
```

### 7. Marcar tarea completada, reconocer compuertas y finalizar Run

Con toda la evidencia registrada y verificable, completa la tarea, reconoce las compuertas post-ejecución y transiciona el run a `finished`:

```bash
rapid run task spec-task-priority-r1-run-001 T001 done
rapid run gate spec-task-priority-r1-run-001 gate.tests acknowledged
rapid run gate spec-task-priority-r1-run-001 gate.final-verification acknowledged
rapid run status spec-task-priority-r1-run-001 finished
```

---

## 8. Evaluation

Ejecuta el evaluador conductual determinista exigiendo el veredicto exitoso (`--require-pass`):

```bash
rapid eval run --run spec-task-priority-r1-run-001 --write --require-pass
```

El evaluador inspecciona las transiciones de estado, verifica que los gates requeridos (`gate.baseline`, `gate.tests`, `gate.final-verification`) y las capacidades observadas estén satisfechos por la evidencia vinculada y emite el veredicto:

```json
{
  "verdict": "pass",
  "run_id": "spec-task-priority-r1-run-001"
}
```

---

## 9. Validation

Valida la integridad criptográfica de todo el repositorio:

```bash
rapid validate
```

---

## 10. Troubleshooting & Common Errors

- **Error `RAPID1203` (Evidence Binding Mismatch):** El estado del run avanzó antes de registrar la evidencia. El comando `rapid evidence add` resuelve automáticamente la revisión actual de estado si omites o sincronizas `state_revision`.
- **Error `RAPID1225` / `RAPID1226` (Evaluation Unverified / Fail):** Una compuerta requerida no fue reconocida, no contiene evidencias válidas o la evidencia asociada contiene un `exit_code != 0`. Recuerda que `gate.baseline` debe reconocerse antes de activar el run.

---

## 11. Assessment Criteria

- [x] Repositorio inicializado y escaneado.
- [x] Spec en estado `ready` y Context compilado.
- [x] Run creado y vinculado al harness `codex`.
- [x] Evidencia de baseline capturada y `gate.baseline` reconocido antes de `active`.
- [x] Código y pruebas implementados externamente con artefactos de log.
- [x] Evidencias `file_change`, `test_result`, `workspace` y `review` registradas.
- [x] Compuertas `gate.tests` y `gate.final-verification` reconocidas.
- [x] Veredicto `pass` emitido por `rapid eval run --require-pass`.
- [x] `rapid validate` finaliza con código de salida 0.
