# Laboratorios prácticos de RAPID OS

Cada laboratorio es un proyecto de ejemplo pequeño (Python, sin dependencias) y un modo de ingeniería. Todos se hacen igual, en cuatro pasos:

1. **Prepara el ejemplo**: copias la carpeta `starter` y haces un commit.
2. **`/rapid-init`** en tu agente: acepta lo que propone.
3. **`/rapid-<modo>`** con el objetivo del laboratorio: el agente hace el trabajo.
4. **`rapid approve`** en tu terminal cuando el agente te lo pida, y `/rapid-next` para cerrar.

No necesitas aprender ningún otro comando. Si aún no tienes los shortcuts, una sola vez: `rapid shortcuts install --global --harness claude` (cambia `claude` por tu agente). Detalle en la [guía de shortcuts](../guides/shortcuts.md).

---

## Elige un laboratorio

| Laboratorio | Shortcut | Qué practicas |
|---|---|---|
| [1. Feature](feature-lab.md) | `/rapid-feature` | Añadir una funcionalidad con criterios de aceptación y tests. Empieza aquí. |
| [2. Bugfix](bugfix-lab.md) | `/rapid-bugfix` | Reproducir el bug con un test en rojo antes de corregirlo. |
| [3. Refactor](refactor-lab.md) | `/rapid-refactor` | Cambiar la estructura sin que bajen los tests que pasan. |
| [4. Hardening](hardening-lab.md) | `/rapid-hardening` | Endurecer seguridad en una copia aislada del repositorio, con revisión humana. |
| [5. Research](research-lab.md) | `/rapid-research` | Un spike que compara opciones y deja los hallazgos registrados. |

Los ejemplos están en [`examples/`](https://github.com/alyconr/Rapid-OS/tree/main/examples) (con el instalador, en `~/.rapid-os/examples/`). Cada uno trae `starter/` (el punto de partida) y `solution/` (una solución de referencia).

---

## Qué hace Rapid OS y qué hace tu agente

- **Tu agente** edita el código, ejecuta los tests y redacta la spec.
- **Rapid OS** fija las reglas del run (tareas, gates, tests obligatorios), registra la evidencia de lo que se ejecutó y da un veredicto. Nunca aprueba por ti: los gates humanos los apruebas tú en tu terminal.

---

## Modo avanzado

Los laboratorios no usan los comandos v3. Si necesitas hacer el trabajo a mano (para CI, auditoría o para entender qué registra Rapid OS en cada paso), sigue el [recorrido manual (Bajo el capó)](first-governed-project.md), en la sección **Cómo funciona**.

Si algo falla, revisa la [guía de problemas en los laboratorios](../troubleshooting/tutorials.md).
