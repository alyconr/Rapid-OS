---
title: Arquitectura de orquestación
description: "Cómo la capa porcelain (rapid start, next, check, finish…) conduce un run sobre el motor de gobernanza v3 (plumbing): Conductor, NextAction, session.json, productores de evidencia, ruleset v2 y defensas de rapid approve."
---

# Arquitectura de orquestación

Rapid OS tiene dos capas. El **plumbing** (`rapid spec`, `rapid run`, `rapid evidence`, `rapid eval`…) es el motor de gobernanza v3: registros inmutables, contratos, evidencia y evaluación. El **porcelain** (`rapid start`, `rapid next`, `rapid check`, `rapid task`, `rapid attach`, `rapid finish`, `rapid approve`, `rapid status`, `rapid abort`) es la capa de intención que conduce un run *usando* el plumbing. Los [shortcuts](../guides/shortcuts.md) son archivos que enseñan a un agente a seguir ese bucle; el [modo avanzado](../governance-loop.md) usa el plumbing directamente.

Esta página describe cómo encajan las piezas. Los límites de lo que se ejecuta están en [límites del producto](../concepts/product-boundaries.md).

---

## 1. Porcelain sobre plumbing

```text
  Persona / agente                     ¿quién decide?
        │  /rapid-<modo> <objetivo>
        ▼
  Shortcuts y hooks (por harness)      enseñan el bucle y vigilan al agente
        │  rapid next / start / check / task / attach / finish
        ▼
  PORCELAIN  rapid_os/orchestration/   Conductor (puro) + lifecycle (E/S)
        │  llama a los registries, nunca a funciones de la CLI
        ▼
  PLUMBING   rapid_os/adapters/        SpecRegistry · RunRegistry · EvidenceRegistry · EvalRegistry
             rapid_os/domain/          contratos, RunState, RunEvidence, BehavioralEvaluator
        ▼
  .rapid-os/   specs/ runs/ evidence/ evals/   ledger append-only (+ session.json y scratch/)
```

- El porcelain **no crea otro modelo de datos**: cada acción termina en registros del plumbing (specs, runs, estados, evidencia, reportes) con los mismos digests.
- El ledger es append-only: ningún verbo reescribe archivos bajo `.rapid-os/runs`, `evidence` o `evals`.
- Un gate humano nunca se reconoce automáticamente (ver [sección 8](#8-rapid-approve-capas-de-defensa-y-su-límite)).

---

## 2. El bucle

```text
        ┌────────────────────────────────────────────────────────────┐
        │                                                            │
        ▼                                                            │
  rapid next --json ──► action.kind                                  │
        │                                                            │
        ├─ author_spec ──► redactar la spec ──► rapid start <modo> --spec-file -
        ├─ run_baseline / activate / verify ──► ejecutar action.command
        ├─ implement_task ──► implementar ──► rapid check -- <tests> ──► action.after (rapid task done)
        │                                                            │
        ├─ await_human_approval ──► SE DETIENE: una persona ejecuta rapid approve <gate> ──┐
        ├─ blocked ──► explicar el motivo (p. ej. rapid abort tras un rechazo)             │
        └─ finish ──► rapid finish ──► veredicto (PASS / PASS_WITH_WAIVERS / FAIL / UNVERIFIED)
                                                                     ▲                      │
                                                                     └──────────────────────┘
```

`rapid next` nunca muta el estado: calcula la siguiente acción y se puede repetir. `rapid check` ejecuta un comando y registra evidencia; `rapid finish` registra los cambios, reconoce los gates de máquina que ya cumplen las reglas y evalúa el run.

---

## 3. El Conductor: una función pura con el evaluador como oráculo

`next_action(contract, state, evidence, playbook, *, evaluator, test_command)` (en `rapid_os/orchestration/conductor.py`) **no hace E/S**: recibe el contrato, el `RunState`, la evidencia y el playbook del modo, y devuelve un `NextAction`. La E/S (leer el ledger, escribir evidencia, ejecutar `rapid check`) vive en `lifecycle.py`.

El Conductor no reimplementa las reglas de gobernanza: **pregunta al `BehavioralEvaluator`**. Evalúa el run en memoria (`evaluator.evaluate(...)`) y lee las aserciones (`UNVERIFIED`, `FAIL`, `PASS`) para decidir qué falta.

`gate_satisfied(contract, state, evidence, gate_id, *, evaluator)` formaliza esa idea: reconoce *hipotéticamente* el gate (en una copia del estado) y vuelve a evaluar. Si la aserción del gate pasa a `PASS`, la evidencia ya lo respalda y reconocerlo es seguro; si no, falta evidencia. Así `rapid start` y `rapid finish` solo reconocen gates de máquina cuando la evidencia los justifica, y nunca un gate humano.

Orden de las reglas (la primera que aplica gana):

| # | Condición | Acción |
| :--- | :--- | :--- |
| 1 | El run es terminal | `done` (con el resultado) |
| 2 | El run está `blocked` | `blocked` |
| 3 | Una revisión humana fue rechazada (`changes_requested`) | `blocked` con el comando `rapid abort`: el gate queda en `FAIL` en ese run |
| 4 | `prepared` con `gate.baseline` pendiente | `run_baseline` (o `activate` si ya se cumple) |
| 5 | `active` con tareas sin terminar | `implement_task` (reglas del modo: `bugfix` pide `rapid check --expect fail` sobre `T001`; `research` cierra tareas con `--no-check`) |
| 6 | Todas las tareas terminales | `refactor`: `blocked` si bajan los tests pasados respecto a la baseline; una aserción en `FAIL` → `blocked` |
| 7 | Tarea o gate de máquina sin verificar, o la capability `tests.execute` sin observar | `verify` |
| 8 | Gates humanos pendientes | `await_human_approval` |
| 9 | Todo resuelto | `finish` |

Los playbooks (`templates/modes/<modo>.json`) aportan la plantilla de spec y los textos de cada acción; las reglas específicas de cada modo están en las [guías de modo](../guides/modes/index.md).

---

## 4. El esquema de `NextAction`

`rapid next --json` (y `rapid start --json`, `rapid finish --json`) devuelven:

```json
{
  "schema_version": 1,
  "run_id": "booking-availability-r1-run-001",
  "mode": "feature",
  "action": {
    "kind": "implement_task",
    "task_id": "T001",
    "instructions": "Implementa solo la tarea indicada. Corre los tests con rapid check.",
    "command": ["rapid", "task", "start", "T001"],
    "after": ["rapid", "task", "done", "T001"]
  },
  "awaiting_human": ["gate.final-verification"],
  "missing": ["task.T001.evidence", "gate.gate.tests.evidence"],
  "progress": {"tasks_done": 0, "tasks_total": 1},
  "outcome": null
}
```

| Campo | Significado |
| :--- | :--- |
| `action.kind` | `author_spec`, `run_baseline`, `activate`, `implement_task`, `verify`, `await_human_approval`, `finish`, `done` o `blocked` |
| `action.command` | Comando exacto a ejecutar (como lista argv) o `null` |
| `action.after` | Comando a ejecutar cuando el agente termina el trabajo de la acción (p. ej. `rapid task done`) o `null` |
| `action.task_id`, `action.gate_ids` | Tarea o gates a los que se refiere la acción (opcionales) |
| `action.spec_template` | Plantilla de spec del modo, en `author_spec` (opcional) |
| `action.workspace_path` | Worktree aislado del run, si lo tiene (opcional) |
| `awaiting_human` | Gates humanos pendientes |
| `missing` | Aserciones del evaluador aún sin cumplir |
| `outcome` | Veredicto o resultado, solo cuando `kind` es `done` |

Los campos opcionales se omiten cuando no se usan, así que la salida de un modo sin worktree no cambia.

---

## 5. `.rapid-os/session.json`

El porcelain recuerda el run activo en `.rapid-os/session.json` (`rapid init` lo añade a `.gitignore` si existe). No forma parte del ledger y no tiene digest:

| Campo | Significado |
| :--- | :--- |
| `schema_version`, `active_run_id`, `mode`, `harness` | Run activo, modo y harness elegidos |
| `start_head` | `HEAD` de git al iniciar; `rapid finish` registra los cambios contra él |
| `start_untracked` (opcional) | Archivos sin seguimiento que ya existían al iniciar; `rapid finish` no se los atribuye al run |
| `workspace_path` (opcional) | Worktree aislado creado con `rapid start --worktree` |

`rapid abort` borra el archivo; `rapid validate` lo comprueba contra el `RunRegistry` (`RAPID1304`, `RAPID1305`). Junto a él, `.rapid-os/scratch/` guarda los logs de `rapid check` y el estado de los hooks; ambos son desechables.

---

## 6. Productores de evidencia del porcelain

Cada verbo que registra evidencia lo hace con un productor identificable:

| Productor | Quién lo escribe | Evidencia |
| :--- | :--- | :--- |
| `rapid:check` | `rapid check`, `rapid task done`, baseline de `rapid start` | `test_result` o `command_result`, con el log como artefacto |
| `rapid:start` | `rapid start` | `workspace` (`current` o `isolated`) |
| `rapid:finish` | `rapid finish` | `file_change` con los archivos modificados por el run, sin `.rapid-os/` ni artefactos de herramientas (`__pycache__`, `*.pyc`, `.pytest_cache`...); sin cambios reales no se registra |
| `rapid:attach` | `rapid attach` | `artifact` con el archivo adjunto, ligado a una tarea |
| `user` | `rapid approve` | `review` con el resultado y el revisor |
| `harness:<id>` | un harness externo, vía `rapid evidence add` | cualquiera; ver el ruleset v2 |

---

## 7. Ruleset v2

El evaluador aplica por defecto el ruleset v2 (`rapid eval run --ruleset {1,2}`):

- **`gate.architecture`:** en `feature`, `bugfix` y `refactor`, si existe `architecture.json`, el contrato añade este gate de máquina (`architecture_check`, posterior a la ejecución, obligatorio, no dispensable). `rapid next` propone `rapid check --gate gate.architecture -- rapid arch check` y las violaciones son `RAPID1420`. Ver [Arquitectura por stack](../concepts/architecture.md#el-gate-gatearchitecture).
- **`expectation: "fail"`:** `rapid check --expect fail --task <id>` registra un fallo esperado. Genera la aserción `reproduction.<tarea>` en `PASS` si el comando falló de verdad (y en `FAIL` si no), y esa evidencia **no** cuenta como fallo de la tarea ni sirve de evidencia de `gate.baseline` o `gate.tests`. Solo se admite ligada a una tarea (`RAPID1320`).
- **`harness:*` no cierra gates humanos:** la evidencia de revisión producida por un `harness:<id>` queda `UNVERIFIED` para los gates de revisión humana. Solo una revisión de `rapid approve` (productor `user`) puede respaldarlos.

---

## 8. `rapid approve`: capas de defensa y su límite

Aprobar un gate humano exige estas comprobaciones, de la más barata a la más fuerte:

1. **TTY:** sin terminal interactiva falla con `RAPID1310` (un EOF durante la confirmación se trata igual).
2. **Marcador de sesión:** `CLAUDE_CODE_CHILD_SESSION=1` rechaza la ejecución.
3. **Ascendencia:** si algún proceso ancestro es el binario de Claude Code (`claude`/`claude.exe`), falla con `RAPID1310` aunque haya TTY y no queden variables.
4. **Confirmación textual:** hay que teclear `aprobar <gate-id>` (`dispensar <gate-id>` para `--waive`).
5. **Hooks de Claude Code (opcionales):** `PreToolUse` deniega al agente `rapid approve`, `rapid abort`, `rapid run gate`, `rapid evidence add` y la edición de `.rapid-os/`, y deniega quitar las variables de sesión.
6. **Evidencia:** la aprobación queda como `review` con productor `user`; el evaluador no acepta la de un `harness:*` (ruleset v2).

**Límite conocido.** Son defensas de mejor esfuerzo, no una garantía criptográfica. La detección por ascendencia no ve a un proceso que se desacopla de su padre (doble fork, `setsid`, `nohup … &`), a un `claude.exe` renombrado ni a un pid reutilizado; un TTY se puede emular; el análisis de comandos de los hooks no detecta uno construido en tiempo de ejecución; y la identidad del revisor es la que se declara. La regla de fondo no cambia: **una persona aprueba, en su propia terminal.**

---

## 9. Dónde está cada pieza

| Pieza | Módulo |
| :--- | :--- |
| Conductor, `NextAction` | `rapid_os/orchestration/conductor.py`, `actions.py` |
| Verbos del porcelain (E/S) | `rapid_os/orchestration/lifecycle.py`, `check.py`, `session.py`, `workspace.py` |
| Playbooks | `templates/modes/*.json`, `rapid_os/orchestration/playbooks.py` |
| Hooks | `rapid_os/orchestration/hooks.py` (decisión pura), `hook_runtime.py`, `rapid_os/adapters/claude_hooks.py` |
| Shortcuts | `templates/shortcuts/*.md`, `rapid_os/adapters/shortcut_installer.py`, `rapid_os/adapters/agents/` |
| Ascendencia de procesos | `rapid_os/core/ancestry.py` |
| Motor de gobernanza | [Arquitectura v3](./rapid-os-v3.md) |
