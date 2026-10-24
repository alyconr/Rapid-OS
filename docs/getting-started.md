---
title: Primeros pasos
description: Empieza en 3 pasos (instalar, /rapid-init, /rapid-feature), el mapa de la sección y, plegado, el recorrido avanzado con los comandos v3.
---

# Primeros pasos con Rapid OS

Rapid OS gobierna el trabajo de tu agente de código: cada cambio ocurre dentro de un **run** con spec, tareas, gates y evidencia verificable. Tú no tienes que aprender esos comandos: los ejecuta el agente a través de los **shortcuts** (`/rapid-…`). En tu terminal solo instalas y apruebas.

---

## 1. Empieza en 3 pasos

Necesitas Python 3.10+, Git y un agente de código: Claude Code, Codex, Cursor, Antigravity o VS Code (Copilot).

### Paso 1: instalar

Usa el instalador de tu sistema ([Linux](./installation/linux.md), [macOS](./installation/macos.md), [Windows](./installation/windows.md) o [WSL](./installation/wsl.md)). Al final pregunta para qué agentes instalar los shortcuts: escribe el tuyo (por ejemplo `claude`) y quedan disponibles en todos tus proyectos. Si te lo saltaste, una sola vez:

```bash
rapid shortcuts install --global --harness claude
```

:::note VS Code y versiones anteriores
VS Code no tiene carpeta de usuario para shortcuts: instálalos en cada proyecto con `rapid init --shortcuts`. Lo mismo si tu versión de Rapid OS aún no trae `/rapid-init` ni `--global` (lo verás en `rapid shortcuts install --help`).
:::

### Paso 2: describir el proyecto con `/rapid-init`

Abre tu agente en la carpeta del proyecto (nueva o con código) y escribe:

```text
/rapid-init una API en Python para validar nombres de usuario
```

El agente te propone, una decisión a la vez, el stack, el comando de tests y los documentos del proyecto (brief, reglas de negocio, modelo de datos, arquitectura). Para cada documento eliges: lo pegas, lo redacta el agente o lo omites. Lo que redacta queda como **borrador** hasta que tú digas que lo confirmas. En Codex se escribe `$rapid-init`.

### Paso 3: pedir el trabajo

```text
/rapid-feature añadir exportación CSV al informe mensual
```

El agente redacta la spec, implementa tarea por tarea y corre los tests. Cuando necesita a una persona se detiene y te da el comando exacto para **tu** terminal, por ejemplo:

```bash
rapid approve gate.final-verification
```

Después escribe `/rapid-next` en el agente y el run se cierra. Ningún shortcut aprueba por ti. Qué hacer en cada parada está en [Cuando el agente se detiene](./getting-started/when-the-agent-stops.md).

| Quieres… | Escribe en tu agente |
| :--- | :--- |
| Una funcionalidad nueva | `/rapid-feature <objetivo>` |
| Corregir un bug | `/rapid-bugfix <qué falla>` |
| Refactorizar sin romper tests | `/rapid-refactor <alcance>` |
| Endurecer seguridad | `/rapid-hardening <área>` |
| Investigar una opción | `/rapid-research <pregunta>` |
| Ver en qué va o seguir | `/rapid-status` · `/rapid-next` |
| Saber qué aprobar | `/rapid-approve` |

Carpetas y forma de invocarlos en cada agente: [guía de shortcuts](./guides/shortcuts.md).

---

## 2. Mapa de esta sección

Léela en este orden; cada página toma unos minutos.

| Página | Qué aprendes |
| :--- | :--- |
| [1. Tu primer proyecto](./getting-started/first-project.md) | De una carpeta vacía a tu primera funcionalidad aprobada. |
| [2. Un proyecto que ya existe](./getting-started/existing-project.md) | Usarlo en un repositorio con código, sin tocar tu código de negocio. |
| [3. Cuando el agente se detiene](./getting-started/when-the-agent-stops.md) | Aprobar, rechazar, ver en qué va, cancelar y leer el veredicto. |
| [4. Cómo se escribe la spec](./getting-started/first-spec.md) | Qué pide el agente para redactar la spec y cómo hacer un buen pedido. |
| [5. Qué sabe el agente de tu proyecto](./getting-started/first-context.md) | De dónde salen sus reglas, borradores frente a confirmados y cómo cambiarlos. |
| [6. Próximos pasos](./getting-started/next-steps.md) | Laboratorios, qué modo usar, trabajo en equipo y qué hacer si algo falla. |

Fuera de esta sección:

- [Guía de shortcuts](./guides/shortcuts.md): instalación por harness, el bucle y la aprobación humana.
- [Laboratorios](./tutorials/index.md): un laboratorio por modo, cada uno con su shortcut.
- [Referencia de CLI](./cli.md) y [diagnósticos](./troubleshooting/diagnostics.md).

---

## Modo avanzado

No lo necesitas para usar Rapid OS. Los comandos v3 (`rapid spec`, `rapid run`, `rapid evidence`, `rapid eval`…) hacen a mano lo que hace el agente con los shortcuts; sirven para CI, depuración y auditoría. Están en la sección **Cómo funciona**:

- [Ciclo de gobernanza v3](./governance-loop.md): qué registra cada paso y por qué.
- [Recorrido manual (Bajo el capó)](./tutorials/first-governed-project.md): un proyecto completo hecho a mano, de `rapid init` al veredicto.
