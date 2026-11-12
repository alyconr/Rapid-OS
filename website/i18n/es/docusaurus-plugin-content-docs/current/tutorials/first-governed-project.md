# Recorrido manual: el bucle de gobernanza a mano (Bajo el capó)

> **Modo avanzado.** No necesitas este laboratorio para usar Rapid OS: escribe en una terminal, uno a uno, los comandos de uso diario (`rapid start`, `rapid next`, `rapid check`, `rapid task`, `rapid approve`, `rapid finish`) que el agente ejecuta por ti con los shortcuts. Es para integradores, CI y auditoría. Si estás empezando, ve a los [laboratorios](index.md), empezando por [Feature](feature-lab.md) (`/rapid-feature`).

Aprende a ejecutar el bucle de gobernanza completo de RAPID OS sobre un proyecto Python real, viendo qué registra cada paso y por qué un veredicto solo llega a `pass` con tests reales y una aprobación humana real.

---

## 1. Overview

- **Nombre:** Task Tracker CLI Governance.
- **Problema:** Un proyecto Python sin gobernanza arriesga cambios no validados introducidos por asistentes de IA. Se requiere implementar una nueva funcionalidad de prioridad de tareas bajo un contrato verificable.
- **Objetivo:** Recorrer todo el ciclo de gobernanza, desde `rapid init` hasta el informe de evaluación y la validación final de integridad, solo con los comandos de uso diario.
- **Nivel de dificultad:** Avanzado.
- **Conocimientos previos:** Uso básico de terminal, git y comandos de Python.
- **Dependencias:** Python 3.10+ (exclusivamente biblioteca estándar) y git.
- **Archivos de referencia:** [`examples/first-governed-project/`](https://github.com/alyconr/Rapid-OS/tree/main/examples/first-governed-project).

---

## 2. Learning Outcomes

Al completar este laboratorio, sabrás cómo:
1. Inicializar RAPID OS en un repositorio git existente.
2. Abrir un run gobernado desde un archivo de spec (`rapid start feature --spec-file`), que además registra la baseline.
3. Pedir a Rapid OS el siguiente paso determinista (`rapid next`).
4. Trabajar en una tarea y cerrarla con sus tests (`rapid task start`, `rapid task done`).
5. Satisfacer los gates de máquina con checks que ejecuta el propio Rapid OS (`rapid check`).
6. Aprobar el gate humano desde tu propia terminal (`rapid approve`).
7. Terminar el run y obtener su informe de evaluación (`rapid finish`, `rapid eval run --require-pass`).
8. Validar la integridad holística del proyecto (`rapid validate`).
9. Distinguir los comandos de plomería (`rapid evidence add`, `rapid run gate`), que nunca satisfacen un gate de tests ni uno humano.

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

1. **Nueva funcionalidad:** Permitir especificar la prioridad de la tarea (`low`, `medium`, `high`), con `medium` por defecto.
2. **Validación:** Rechazar prioridades desconocidas con `ValueError`.
3. **Filtrado:** `list_tasks(priority=None)` debe permitir filtrar por prioridad cuando se indique una.
4. **Preservación:** No romper las pruebas unitarias existentes.

---

## 5. Guided Procedure

### Paso 1: Poner el starter bajo git

Rapid OS observa los cambios de un run con git, así que el proyecto parte de un commit:

```bash
git init
git add .
git commit -m "Starter task tracker"
```

### Paso 2: Inicializar RAPID OS

En la raíz del proyecto, inicializa Rapid OS sin preguntas (`--yes`) con un stack Python:

```bash
rapid init --stack python-ai --yes
```

Esto crea la estructura `.rapid-os/` con sus estándares y configuración base. Detecta la carpeta `tests/` y registra `python -m unittest discover` como `test_command` del proyecto: el comando en el que Rapid OS confía para ejecutar los tests.

### Paso 3: Escribir la spec

La spec dice qué debe lograr el run y qué tareas tiene. Guárdala como `spec.json`:

```json
{
  "title": "Task priority",
  "business_objective": "Tasks carry a priority so the most urgent work can be listed first.",
  "acceptance_criteria": [
    "add_task accepts the priorities low, medium and high, and medium by default",
    "add_task rejects an unknown priority with ValueError",
    "list_tasks(priority) returns only the tasks of that priority"
  ],
  "implementation_tasks": ["T001: Implementar soporte de prioridades en TaskTracker"]
}
```

### Paso 4: Iniciar el run

```bash
rapid start feature --spec-file spec.json
```

`rapid start` guarda la spec (id `task-priority`), resuelve la política de ejecución y crea el run `task-priority-r1-run-001` con su `ExecutionContract` inmutable. Para una spec `feature` sobre un stack de backend, el contrato exige estos gates:

- `gate.baseline` (fase `pre_execution`): la suite de tests pasa antes de cambiar nada. `rapid start` ejecuta él mismo `test_command` y registra el resultado como evidencia `test_result` producida por `rapid:check`; con la baseline satisfecha, activa el run.
- `gate.tests` (fase `post_execution`): la suite de tests pasa sobre el código final.
- `gate.architecture` (fase `post_execution`): este proyecto se inicializó con un stack de backend (`python-ai`), así que parte como monolito modular y la regla se verifica con `rapid arch check`.
- `gate.final-verification` (fase `post_execution`): una persona aprueba el resultado, en su propia terminal.

### Paso 5: Pedir el siguiente paso

```bash
rapid next
```

Rapid OS responde con la siguiente acción determinista y su comando exacto: `implement_task -> rapid task start T001`. Siempre que dudes de qué sigue, `rapid next` te lo dice.

---

## 6. External Execution

> **Nota de límite de responsabilidad:** RAPID OS **no** edita el código. La implementación la hace el desarrollador o su coding harness externo (Claude Code, Cursor, Codex, Antigravity, etc.).

### Paso 1: Empezar la tarea

```bash
rapid task start T001
```

### Paso 2: Implementar el código y sus tests

Modifica `app.py` y `tests/test_app.py` para cumplir los requisitos:

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

### Paso 3: Cerrar la tarea con sus tests

```bash
rapid task done T001
```

`rapid task done` ejecuta `test_command` antes de cerrar la tarea. Si un test falla, la tarea sigue abierta y el comando sale con el fallo.

---

## 7. Evidence Collection

Toda la evidencia de este recorrido la escribe el propio Rapid OS mientras ejecuta algo. Nunca escribes evidencia a mano.

### 1. Verificar los gates de máquina

Pide el siguiente paso:

```bash
rapid next
```

Responde `verify -> rapid check --gate gate.tests`. Ejecuta el comando que da:

```bash
rapid check --gate gate.tests
```

Sin comando, `rapid check` ejecuta él mismo el `test_command` del proyecto (`python -m unittest discover`): no lo escribes ni lo citas. Lo ejecuta sin shell, guarda su salida como log en `.rapid-os/scratch/checks/`, lee el resumen de tests (`Ran 4 tests ... OK`) y registra evidencia `test_result` producida por `rapid:check` con los conteos, `counted: true` y la huella (`tree`) del árbol de trabajo que verificó.

Después, el gate de arquitectura. `rapid next` lo propone con `--new-only` (solo fallan las violaciones que añade el run); este proyecto aún no tiene módulos, así que el checker sin opciones también pasa:

```bash
rapid next
rapid check --gate gate.architecture -- rapid arch check
```

### 2. Qué no cuenta como ejecución de tests

Un gate de tests (`gate.tests`, `gate.baseline`) solo lo satisface un check que ejecutó Rapid OS con el `test_command` del proyecto (o con otro comando que una persona aceptó en su terminal), con al menos un test ejecutado y el árbol de trabajo registrado. Por eso:

- `rapid check --gate gate.tests -- python -c "print('4 passed in 0.1s')"` imprime un resumen, pero no es `test_command`: se registra como un check normal sin `gate.tests`, `rapid check` sale con 1 y `RAPID1440`, y `rapid next` sigue pidiendo `rapid check --gate gate.tests`. Aceptar otro comando es decisión de la persona (`--accept-test-command`, ver la [referencia de la CLI](../cli.md#check--verification-rapid-check)).
- Si el código cambia después del último check, `rapid next`, `rapid approve` y `rapid finish` piden un check nuevo y nombran los archivos (`RAPID1423`).

### 3. Aprobar el gate humano

`rapid next` responde ahora `await_human_approval -> rapid approve gate.final-verification`. Revisa el diff y ejecuta, **en tu propia terminal** (no desde dentro de un agente):

```bash
rapid approve gate.final-verification
```

Rapid OS te muestra lo que apruebas (criterios de aceptación, tareas y el resultado de `gate.tests` y `gate.architecture`) y pregunta `¿Apruebas gate.final-verification? [s/N]`: responde `s`. Registra una evidencia `review` escrita por `rapid approve`, con tu nombre y la huella del árbol de trabajo que aprobaste. Un agente no puede hacerlo: dentro de una sesión de agente, bajo un proceso de agente o sin TTY se rechaza (`RAPID1310`).

---

## 8. Evaluation

Termina el run:

```bash
rapid finish
```

`rapid finish` registra los archivos cambiados (`file_change`, producido por `rapid:finish`), reconoce los gates de máquina cuya evidencia los satisface, comprueba que el código sigue siendo el que verificaron los tests y el que aprobaste (si no, se niega con `RAPID1423` o `RAPID1433` y nombra los archivos) y escribe el informe de evaluación con el veredicto.

Vuelve a leer el informe y exige el veredicto exitoso (`--require-pass` sale con error si el veredicto no es `pass`):

```bash
rapid eval run --run task-priority-r1-run-001 --require-pass
```

El evaluador (ruleset 3) revisa el ciclo de vida del run, las tareas, los gates requeridos (`gate.baseline`, `gate.tests`, `gate.architecture`, `gate.final-verification`) y las capacidades observadas, y emite el veredicto:

```json
{
  "verdict": "pass",
  "run_id": "task-priority-r1-run-001"
}
```

---

## 9. Validation

Valida la integridad criptográfica de todo el repositorio:

```bash
rapid validate
```

---

## 10. Referencia: los comandos de plomería

Los comandos de uso diario se apoyan en comandos de más bajo nivel que siguen disponibles para integradores y CI: `rapid scan`, `rapid spec`, `rapid context`, `rapid policy show`, `rapid run create`, `rapid run task`, `rapid run gate`, `rapid evidence add` y `rapid eval run`. Dos de ellos escriben en el registro y tienen límites que importan:

- **`rapid evidence add` no satisface gates de tests ni humanos.** Registra evidencia producida fuera de Rapid OS (`harness:<id>`, `ci:<nombre>`, `external:<nombre>`). Los productores `rapid:*` y la evidencia `review` de producer `user` están reservados a los comandos que los observan (`rapid check`, `rapid start`, `rapid finish`, `rapid attach`, `rapid approve`): `evidence add` los rechaza con `RAPID1430`. Un `test_result` escrito a mano nunca satisface `gate.tests` ni `gate.baseline`: el gate queda `unverified`.
- **`rapid run gate` no cambia gates humanos.** `rapid run gate <run> gate.final-verification acknowledged` se rechaza con `RAPID1431`; un gate humano solo se mueve con `rapid approve <gate>` en la terminal de la persona. Reconocer un gate de tests con `rapid run gate` sin un check de `rapid check` deja su aserción en `unverified`.

Por ejemplo, los dos se rechazan:

```text
rapid evidence add --run task-priority-r1-run-001 --input review_a_mano.json   # producer "user", kind "review" -> RAPID1430
rapid run gate task-priority-r1-run-001 gate.final-verification acknowledged   # gate humano -> RAPID1431
```

La lista completa de comandos está en la [referencia de la CLI](../cli.md) y en el [bucle de gobernanza v3](../governance-loop.md).

---

## 11. Troubleshooting & Common Errors

- **`RAPID1432` (gate de tests no verificable):** la evidencia vinculada a `gate.tests` o `gate.baseline` no era una ejecución de tests de la que Rapid OS pueda responder (sin resumen de tests y sin ser `test_command`, cero tests ejecutados, sin árbol registrado, o escrita con `rapid evidence add`). Ejecuta el comando que da `rapid next`.
- **`RAPID1423` / `RAPID1434` (código no verificado):** el código cambió después del último check de tests, o ese check no registró qué árbol verificó. Vuelve a ejecutar el check de tests.
- **`RAPID1433` (el código cambió después de la aprobación):** vuelve a ejecutar el check de tests y aprueba de nuevo con `rapid approve <gate>`.
- **`RAPID1435` (otro comando de tests que el de la baseline):** repite el check con el comando de la baseline; solo la persona puede aceptar la diferencia, en su terminal, con `rapid finish --accept-test-command "MOTIVO"`.
- **Error `RAPID1225` / `RAPID1226` (Evaluation Unverified / Fail):** un gate requerido no está satisfecho por evidencia válida, o la evidencia asociada tiene `exit_code != 0` o tests fallidos. `rapid next` nombra lo que falta.

---

## 12. Assessment Criteria

- [x] Repositorio bajo git y RAPID OS inicializado.
- [x] Run iniciado desde `spec.json`, con la baseline registrada por `rapid start`.
- [x] Tarea `T001` implementada y cerrada con `rapid task done`.
- [x] `gate.tests` y `gate.architecture` verificados con `rapid check`.
- [x] `gate.final-verification` aprobado con `rapid approve` en la terminal de una persona.
- [x] Run terminado con `rapid finish` y veredicto `pass` confirmado por `rapid eval run --require-pass`.
- [x] `rapid validate` finaliza con código de salida 0.
- [x] Ninguna evidencia escrita a mano: sin `rapid evidence add` ni `rapid run gate`.
