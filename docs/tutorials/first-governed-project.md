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
├── README.md
└── tests/
    ├── __init__.py
    └── test_app.py
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

En la raíz del proyecto:

```bash
rapid init
```

Esto crea la estructura `.rapid-os/` con sus estándares y configuración base.

### Paso 2: Escanear el proyecto

```bash
rapid scan --write
```

El scanner detecta el lenguaje (Python) y los directorios de pruebas (`tests/`), persistiendo el Project Model.

### Paso 3: Crear la Especificación

```bash
rapid spec create \
  --id spec-task-priority \
  --title "Añadir soporte de prioridades a TaskTracker" \
  --mode feature \
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

Para una especificación en modo `feature` sin flags críticos, la política determina una clasificación `standard` con nivel de riesgo `low` o `medium`.

### Paso 6: Crear el Run de Ejecución

```bash
rapid run create --spec spec-task-priority --harness codex
```

Esto genera un identificador de run (ej. `spec-task-priority-r1-run-001`), calcula el digest SHA-256 del contrato y escribe el snapshot inicial `RunState s1`.

### Paso 7: Resolver Capabilities del Harness

```bash
rapid harness show codex
```

Observa que RAPID OS reporta las capacidades soportadas (`context.consume`, `repository.read`, `workspace.current`) y aquellas que dependen de tu entorno local (`tests.execute`, `repository.write`).

---

## 6. External Execution

> **Nota de límite de responsabilidades:** RAPID OS **no** edita el código. La implementación la realiza el desarrollador o su coding harness externo (Claude Code, Cursor, Codex, Antigravity, etc.).

Modifica externamente `app.py` y `tests/test_app.py` para cumplir los requerimientos:

```python
# app.py
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

Ejecuta las pruebas en tu terminal:

```bash
python -m unittest discover -s tests -t .
```

---

## 7. Evidence Collection

Actualiza el estado del Run para reflejar el progreso del trabajo externo:

### 1. Iniciar la tarea y pasar el run a activo

```bash
rapid run status spec-task-priority-r1-run-001 active
rapid run task spec-task-priority-r1-run-001 T001 in_progress
```

### 2. Registrar evidencia de cambios en el código (`file_change`)

Prepara el archivo de evidencia `evidence_file_change.json`:

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

### 3. Registrar evidencia de pruebas aprobadas (`test_result`)

Prepara `evidence_test_result.json`:

```json
{
  "kind": "test_result",
  "producer": "harness:codex",
  "summary": "Ejecución exitosa de suite de pruebas unitarias",
  "task_ids": ["T001"],
  "gate_ids": ["gate.final-verification"],
  "capability_ids": ["tests.execute"],
  "payload": {
    "suite": "tests/test_app.py",
    "exit_code": 0,
    "passed": 4,
    "failed": 0,
    "skipped": 0
  }
}
```

Ingiérelo:

```bash
rapid evidence add --run spec-task-priority-r1-run-001 --input evidence_test_result.json
```

### 4. Reconocer gates y marcar tarea como completada

```bash
rapid run gate spec-task-priority-r1-run-001 gate.final-verification acknowledged
rapid run task spec-task-priority-r1-run-001 T001 done
rapid run status spec-task-priority-r1-run-001 finished
```

---

## 8. Evaluation

Ejecuta el evaluador conductual determinista:

```bash
rapid eval run --run spec-task-priority-r1-run-001 --write --require-pass
```

El evaluador inspecciona las transiciones de estado, verifica que los gates requeridos estén satisfechos por la evidencia vinculada y emite el veredicto:

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
- **Error `RAPID1226` (Evaluation Fail):** Un gate requerido quedó en estado `pending` o la evidencia asociada contiene un `exit_code != 0`.

---

## 11. Assessment Criteria

- [x] Repositorio inicializado y escaneado.
- [x] Spec en estado `ready` y Context compilado.
- [x] Run creado y vinculado al harness `codex`.
- [x] Código y pruebas implementados externamente.
- [x] Evidencias `E001` y `E002` registradas con hashes válidos.
- [x] Veredicto `pass` emitido por `rapid eval run`.
- [x] `rapid validate` finaliza con código de salida 0.
