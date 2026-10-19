---
description: "Implementa una funcionalidad con un run gobernado de Rapid OS (modo feature)."
argument-hint: "[objetivo de la funcionalidad]"
mode: feature
context-command: rapid next --json
allowed-commands: next start check task finish status
---
# Rapid OS: modo feature

{{context_step}}

Conduces un run gobernado de Rapid OS en modo `feature`. El objetivo es lo que la persona escribió al invocar este comando. Sigue este bucle:

1. Ejecuta `rapid next --json`.
2. Si `action.kind` es `author_spec`, decide la historia y redacta la spec:
   - Si el argumento es un id de historia (por ejemplo `H002`) y existe `action.seed`, úsalo: el texto está en `seed.stories`.
   - Si no hay argumentos y existe `action.seed`, propón la historia que conviene empezar entre `seed.stories` (son todas las historias sin marcar del brief, en orden). Si no es la primera, explica en una frase por qué (por ejemplo, por dependencias). Pide confirmación a la persona antes de redactar la spec. Si `seed.confirmed` es `false`, avisa que el brief sigue como supuesto: lo redactó el agente y nadie lo confirmó.
   - Con la historia elegida, lee `seed.source` y, si no son `null`, `seed.business_doc` y `seed.data_model_doc`. Copia a `business_rules` de la spec las reglas de negocio relevantes citando el documento (por ejemplo, «Según docs/BUSINESS_RULES.md: ...»). Añade a `tags` el valor `story:<id>` para que `rapid finish` te diga qué historia marcar.
   - Con argumentos que no son un id, o sin `seed`, redacta la spec desde los argumentos del usuario siguiendo `action.spec_template`. Si no hay argumentos suficientes, pregunta antes de redactar.
   - Pasa la spec por stdin a `rapid start feature --spec-file -`. No marques la historia en el brief: lo hace la persona cuando el run termina.
3. Si `action.command` existe, ejecútalo. Si `action.kind` es `implement_task`, implementa solo esa tarea y ejecuta `action.after`. Corre los tests siempre con `rapid check -- <comando>`.
4. Repite hasta que `action.kind` sea `done` o `await_human_approval`. Pide aprobación solo cuando action.kind sea await_human_approval; ignora awaiting_human en cualquier otra acción (esa lista incluye desde el inicio del run los gates humanos del contrato, aunque queden tareas abiertas). En `await_human_approval`, resume la evidencia y da el comando exacto con el id de `action.gate_ids` (el mismo que lista `awaiting_human`, campo de la salida de `rapid next --json`, no de `action`), por ejemplo `rapid approve gate.final-verification`; dile a la persona que lo ejecute en otra terminal, fuera del agente. No sugieras ejecutarlo desde esta sesión (ni con el prefijo de exclamación ni de ninguna otra forma) y usa siempre el id exacto del gate.
5. Nunca ejecutes `rapid approve`, `rapid abort`, `rapid run gate` ni `rapid evidence add`, y nunca edites `.rapid-os/`. Si `action.command` es `rapid abort` (revisión rechazada), explica la razón a la persona y espera su decisión.
