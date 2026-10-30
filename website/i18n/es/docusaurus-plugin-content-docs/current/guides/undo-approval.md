---
title: Deshacer una aprobación
description: Cómo volver atrás de una aprobación humana dada demasiado pronto, antes y después de rapid finish, sin editar el ledger y sin perder trabajo.
---

# Deshacer una aprobación

La decisión sobre un gate queda registrada como evidencia en el ledger del run, y el ledger solo se amplía: `rapid approve` no se puede repetir y nada edita `.rapid-os/` para retirar una aprobación. Por eso `rapid approve <gate>` sobre un gate ya decidido falla con `RAPID1332` y apunta aquí. Lo que debes hacer depende de una sola cosa: **¿ya se ejecutó `rapid finish`?**

| Dónde estás | Qué hacer |
| :--- | :--- |
| El gate está aprobado (o rechazado) y `rapid finish` **no** se ha ejecutado | [Caso A](#caso-a-antes-de-rapid-finish): `rapid abort` |
| `rapid finish` ya se ejecutó (el run está cerrado) | [Caso B](#caso-b-después-de-rapid-finish): `git revert`, reabrir la historia, run nuevo |

Por defecto Rapid OS no hace commit por ti. `rapid finish --merge` puede crear el commit e integrar el worktree aprobado despues de que escribas la frase de confirmacion; de lo contrario, el codigo queda en tu directorio de trabajo hasta que hagas commit.

## Caso A: antes de `rapid finish` {#caso-a-antes-de-rapid-finish}

El run sigue abierto, así que aún se puede cancelar. Tras aprobar el último gate humano, `rapid approve` imprime `Siguiente: rapid finish ...`: ese es el último punto desde el que puedes retroceder.

1. Cancela el run:

   ```bash
   rapid abort --reason "aprobado demasiado pronto"
   ```

   Termina el run como `cancelled` y limpia la sesión. Un worktree aislado se queda en disco.

2. Aparta el código si quieres conservarlo. Guarda en el stash todo lo que produjo el run, también los archivos nuevos, pero deja en paz la carpeta de Rapid OS:

   ```bash
   git stash push --include-untracked -m "run <run-id>: aprobado demasiado pronto" -- . ':(exclude).rapid-os'
   ```

   `git stash list` lo muestra y `git stash pop` lo recupera cuando quieras continuar desde ahí.

3. Empieza un run nuevo (`/rapid-feature` o `rapid start feature`). Un gate rechazado funciona igual: `rapid next` devuelve `blocked` con `rapid abort`, y el motivo que diste con `--reason` llega en `action.rejection`, así que el agente abre el run nuevo atendiéndolo.

:::warning Nunca `git clean`
No uses `git clean` para «empezar de cero». Borra los archivos sin seguimiento, entre ellos `.rapid-os/` (el ledger, las evidencias, tus decisiones del onboarding) y cualquier archivo que creó el run. Si solo quieres quitar el código de en medio, usa el `git stash` de arriba.
:::

## Caso B: después de `rapid finish` {#caso-b-después-de-rapid-finish}

Un run terminado está cerrado para siempre: `rapid abort` ya no aplica y su veredicto queda en el ledger como registro de lo ocurrido. El camino de vuelta es git y un run nuevo.

1. Revierte el commit (o los commits) que hiciste a partir de ese run:

   ```bash
   git revert <commit>
   ```

   Si aún no hiciste commit, descarta o aparta el directorio de trabajo (el comando de stash del caso A).

2. Reabre la historia si `rapid finish` la marcó en el brief del producto. Cambia solo esa línea (el archivo anterior va a `.rapid-os/backups/`):

   ```bash
   rapid setup story H002 --reopen
   ```

3. Empieza un run nuevo para la historia (`/rapid-feature H002`). `rapid next` te la vuelve a ofrecer porque otra vez está abierta.

## Véase también

- [`rapid approve`](../cli.md#rapid-approve) y [`rapid abort`](../cli.md#rapid-abort) en la referencia de la CLI.
- `RAPID1332` en la [referencia de diagnósticos](../troubleshooting/diagnostics.md).
- [Ciclo de gobernanza](../governance-loop.md): por qué las aprobaciones son evidencia y el ledger solo se amplía.
