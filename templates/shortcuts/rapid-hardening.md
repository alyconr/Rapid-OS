---
description: "Endurece seguridad o robustez con un run gobernado de Rapid OS (modo hardening)."
argument-hint: "[área a endurecer]"
mode: hardening
context-command: rapid next --json
allowed-commands: next start check task finish status
---
# Rapid OS: modo hardening

{{context_step}}

Conduces un run gobernado de Rapid OS en modo `hardening`. El objetivo es lo que la persona escribió al invocar este comando. Sigue este bucle:

1. Ejecuta `rapid next --json`.
2. Si `action.kind` es `author_spec`: redacta la spec desde los argumentos del usuario siguiendo `action.spec_template` y pásala por stdin a `rapid start hardening --spec-file -`. Si no hay argumentos suficientes, pregunta antes de redactar.
3. Si `action.command` existe, ejecútalo. Si `action.kind` es `implement_task`, implementa solo esa tarea y ejecuta `action.after`. Corre los tests siempre con `rapid check -- <comando>`.
4. Repite hasta que `action.kind` sea `done` o `await_human_approval`. En `await_human_approval`, resume la evidencia y pide a la persona que ejecute `rapid approve <gate>` en SU terminal.
5. Nunca ejecutes `rapid approve`, `rapid run gate` ni `rapid evidence add`, y nunca edites `.rapid-os/`.
