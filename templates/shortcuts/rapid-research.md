---
description: "Investiga un tema con un run gobernado de Rapid OS (modo research)."
argument-hint: "[pregunta o tema]"
mode: research
context-command: rapid next --json
allowed-commands: next start check task finish status
---
# Rapid OS: modo research

{{context_step}}

Conduces un run gobernado de Rapid OS en modo `research`. El objetivo es lo que la persona escribió al invocar este comando. Sigue este bucle:

1. Ejecuta `rapid next --json`.
2. Si `action.kind` es `author_spec`: obtén la plantilla de este modo con `rapid start research --json` (en `action.spec_template`; `rapid next` sin run activo solo conoce la del modo feature), redacta la spec desde los argumentos del usuario siguiendo esa plantilla y pásala por stdin a `rapid start research --spec-file -`. Si no hay argumentos suficientes, pregunta antes de redactar.
3. Si `action.command` existe, ejecútalo. Si `action.kind` es `implement_task`, implementa solo esa tarea y ejecuta `action.after`. Corre los tests siempre con `rapid check -- <comando>`.
4. Repite hasta que `action.kind` sea `done` o `await_human_approval`. Pide aprobación solo cuando action.kind sea await_human_approval; ignora awaiting_human en cualquier otra acción (esa lista incluye desde el inicio del run los gates humanos del contrato, aunque queden tareas abiertas). En `await_human_approval`, resume la evidencia y da el comando exacto con el id de `action.gate_ids` (el mismo que lista `awaiting_human`, campo de la salida de `rapid next --json`, no de `action`), por ejemplo `rapid approve gate.final-verification`; dile a la persona que lo ejecute en otra terminal, fuera del agente. No sugieras ejecutarlo desde esta sesión (ni con el prefijo de exclamación ni de ninguna otra forma) y usa siempre el id exacto del gate.
5. Nunca ejecutes `rapid approve`, `rapid abort`, `rapid run gate` ni `rapid evidence add`, y nunca edites `.rapid-os/`. Si `action.command` es `rapid abort` (revisión rechazada), explica la razón a la persona y espera su decisión: `action.rejection` trae `reviewer` y `reason`, el texto que la persona escribió al rechazar (puede ser `null` si el rechazo es anterior); léeselo tal cual. Cuando la persona haya abortado y abras el run nuevo, redacta la spec para atender ese motivo y cítalo en `business_rules` y en los criterios de aceptación, en vez de repetir el mismo enfoque.
6. `rapid finish` no hace commit y tú tampoco lo hagas por ella ni afirmes que Rapid OS lo hace: al terminar, dile a la persona que revise los cambios y haga el commit ella. Después de `finish`, `rapid next` ofrece la siguiente historia sin marcar del brief (`author_spec` con `seed`).
