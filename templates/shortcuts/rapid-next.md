---
description: "Continúa el run activo de Rapid OS con la siguiente acción determinista."
context-command: rapid next --json
allowed-commands: next start check task finish status
---
# Rapid OS: siguiente acción

{{context_step}}

Continúa el run activo de Rapid OS. Sigue este bucle:

1. Ejecuta `rapid next --json`.
2. Si `action.kind` es `author_spec`, no hay run activo: pide a la persona el modo (`feature`, `bugfix`, `refactor`, `hardening` o `research`) y el objetivo, o sugiere el comando `/rapid-<modo>`.
3. Si `action.command` existe, ejecútalo. Si `action.kind` es `implement_task`, implementa solo esa tarea y ejecuta `action.after`. Corre los tests siempre con `rapid check -- <comando>`.
4. Repite hasta que `action.kind` sea `done` o `await_human_approval`. En `await_human_approval`, resume la evidencia y pide a la persona que ejecute `rapid approve <gate>` en SU terminal.
5. Nunca ejecutes `rapid approve`, `rapid run gate` ni `rapid evidence add`, y nunca edites `.rapid-os/`.
