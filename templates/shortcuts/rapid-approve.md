---
description: "Muestra los gates humanos pendientes de Rapid OS y el comando exacto para aprobarlos en tu terminal."
argument-hint: "[gate]"
context-command: rapid status --json
disable-model-invocation: true
allowed-commands: status
---
# Rapid OS: aprobar gates

{{context_step}}

La aprobación de un gate humano la hace SOLO una persona, en su propia terminal. A partir de la salida de `rapid status --json`:

1. Lista los gates pendientes de aprobación humana (tipos `peer_review`, `security_review`, `migration_review`, `manual_approval` y `final_verification`; ids como `gate.peer-review`).
2. Para cada uno, resume la evidencia registrada que respalda la revisión.
3. Da el comando exacto con el id del gate, para que la persona lo ejecute en otra terminal, fuera del agente: `rapid approve <gate>` (o `rapid approve <gate> --reject --reason "<motivo>"` para rechazar). Si la persona indicó un gate como argumento, da solo ese comando. No sugieras ejecutarlo desde esta sesión (ni con el prefijo de exclamación ni de ninguna otra forma) y usa siempre el id exacto del gate.

Nunca ejecutes `rapid approve`, `rapid run gate` ni `rapid evidence add`, y nunca edites `.rapid-os/`. Si no hay gates pendientes, indícalo.
