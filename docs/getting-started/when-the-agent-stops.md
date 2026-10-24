---
title: Cuando el agente se detiene
description: Qué hacer cuando el agente para y te pide algo; aprobar, rechazar, ver en qué va el trabajo, cancelarlo y leer el resultado.
---

# Cuando el agente se detiene

Mientras trabaja, el agente no te pide nada. Se detiene solo en tres casos: **necesita tu aprobación**, **algo bloquea el trabajo** o **terminó**. En los tres te dice qué pasó y qué hacer. Esta página resume las respuestas posibles.

## Te pide aprobar

Es lo más común: el trabajo está hecho y los tests pasaron, pero la última palabra es tuya. El agente te resume lo que hizo y te da un comando. Ejecútalo en **otra terminal**, fuera del agente:

```bash
rapid approve gate.final-verification
```

Después vuelve al agente y escribe `/rapid-next` para cerrar.

| Si quieres… | En tu terminal |
| :--- | :--- |
| Aprobar | `rapid approve <gate>` (el agente te da el nombre exacto) |
| Ver qué falta aprobar | `rapid approve` (sin nada más) |
| Rechazar y explicar por qué | `rapid approve <gate> --reject --reason "<motivo>"` |
| Dispensar una revisión opcional | `rapid approve <gate> --waive --reason "<motivo>"` |

¿Por qué en tu terminal y no en el agente? Porque la aprobación es la garantía de que una persona revisó el trabajo. Rapid OS rechaza `rapid approve` cuando detecta que lo lanza el agente, y ningún shortcut aprueba por ti. Si no recuerdas qué aprobar, escribe `/rapid-approve` en el agente: te muestra los pendientes y el comando, pero no aprueba.

Si rechazas, el trabajo no se da por bueno. El agente te explica la situación y espera tu decisión; normalmente se cancela y se empieza de nuevo con lo que aprendiste.

## Algo bloquea el trabajo

El agente te dice la causa. Las más frecuentes:

- **Tus tests ya fallaban antes de empezar.** Rapid OS comprueba la suite al inicio (la *baseline*) para no culpar al agente de un rojo que ya existía. Arregla esos tests y escribe `/rapid-next`.
- **En un refactor pasan menos tests que antes.** El agente te muestra cuáles; pídele que lo corrija.
- **Ya hay un trabajo en curso.** Solo hay uno activo a la vez: termínalo con `/rapid-next` o cancélalo.

## Ver en qué va o cancelar

| Si quieres… | Dónde | Qué escribes |
| :--- | :--- | :--- |
| Ver tareas, aprobaciones pendientes y estado | En el agente | `/rapid-status` |
| Que el agente siga donde se quedó | En el agente | `/rapid-next` |
| Cancelar el trabajo en curso | En tu terminal | `rapid abort --reason "<motivo>"` |

Cancelar no borra tu código: marca el trabajo como cancelado y libera el sitio para empezar otro.

## Terminó

Al cerrar, el agente te muestra el veredicto:

| Veredicto | Qué significa |
| :--- | :--- |
| `pass` | Todo lo exigido tiene evidencia: los tests se ejecutaron y pasaron, y aprobaste. |
| `pass_with_waivers` | Igual que `pass`, pero dispensaste alguna revisión opcional. |
| `unverified` | Falta evidencia de algo (por ejemplo, un test que nunca se ejecutó). |
| `fail` | Algo exigido falló, o rechazaste la aprobación. |

`pass` no significa "sin bugs": significa que lo que se pidió quedó demostrado con evidencia que Rapid OS ejecutó y registró. Si el trabajo venía de una historia del brief (`H001`…), con `pass` queda marcada como hecha.

Si algo no cuadra, revisa los [problemas frecuentes](../troubleshooting/tutorials.md) o el [catálogo de diagnósticos](../troubleshooting/diagnostics.md) (los códigos `RAPIDxxxx` que aparecen en los mensajes).
