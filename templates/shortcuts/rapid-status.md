---
description: "Muestra el estado del run activo de Rapid OS: tareas, gates y último veredicto."
context-command: rapid status --json
allowed-commands: status
---
# Rapid OS: estado

{{context_step}}

Resume para la persona el estado del run activo a partir de la salida de `rapid status --json`:

- Modo, run y estado general.
- Tareas completadas frente al total y la lista de `run.tasks`: cada tarea con su estado (`status`), su título y los ids de evidencia que la respaldan (`evidence_ids`). Las casillas de `tasks.md` de la spec no son el avance: siguen en `[ ]` aunque la tarea esté hecha.
- Gates con su estado (`status`), cuáles esperan aprobación humana, y el último veredicto.

Si `session` es `null`, indica que no hay run activo; si existe `last_run`, resume también sus tareas y gates como los del último run. Sugiere `/rapid-feature` u otro `/rapid-<modo>` (en Codex: `$rapid-feature` o `$rapid-<modo>`). Si la salida trae `person_actions`, muéstralas tal cual con su explicación (`why`) y pídele a la persona que las ejecute en su propia terminal; no las ejecutes tú. Este comando es de solo lectura: no ejecutes nada más y no edites `.rapid-os/`.
