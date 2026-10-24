---
title: Tu primer proyecto
description: De una carpeta vacía a tu primera funcionalidad aprobada con /rapid-init y /rapid-feature, y el mismo recorrido con los comandos v3 como modo avanzado.
---

# Tu primer proyecto

De una carpeta vacía a tu primera funcionalidad terminada y aprobada. Escribes tres cosas en tu agente y una en tu terminal.

- **Necesitas:** Rapid OS instalado (`rapid --version` responde) y un agente de código (Claude Code, Codex, Cursor, Antigravity o VS Code).
- **Tiempo:** unos 15 minutos.

---

## Camino principal: `/rapid-init`

### 1. Ten los shortcuts disponibles

Si al instalar Rapid OS respondiste con tu agente a la pregunta de los shortcuts, ya están. Si no, una sola vez:

```bash
rapid shortcuts install --global --harness claude
```

Cambia `claude` por `codex`, `cursor` o `antigravity`. En VS Code (o si prefieres los shortcuts dentro del repositorio) usa `rapid init --shortcuts` en la carpeta del proyecto.

### 2. Crea la carpeta y describe el proyecto

```bash
mkdir hello-rapid && cd hello-rapid
```

Abre tu agente en esa carpeta y escribe (en Codex, `$rapid-init`):

```text
/rapid-init una API en Python para validar nombres de usuario
```

### 3. Responde a sus propuestas

El agente te pregunta, una decisión a la vez: stack, topología, arquetipo (MVP o Corporate), comando de tests y los cuatro documentos del proyecto (brief, reglas de negocio, modelo de datos y arquitectura). Para cada decisión te recomienda una opción y una alternativa. Para cada documento eliges:

- **Pegarlo** si ya lo tienes.
- **Que lo redacte el agente**: te muestra el borrador completo antes de guardarlo.
- **Omitirlo**.

Lo que redacta el agente queda como **borrador**. Antes de cerrar te resume cada uno y te pregunta si lo confirmas: confirmado pasa a ser regla del proyecto; sin confirmar queda como supuesto que el agente puede cuestionar. Solo se confirma lo que tú digas explícitamente.

<details>
<summary>Qué ejecuta el agente por debajo</summary>

Los mismos comandos que puedes usar tú sin agente:

```bash
rapid setup next --json
rapid setup set stack python-fastapi
rapid setup set archetype mvp
rapid setup set test-command "python -m unittest discover"
rapid setup doc business --source drafted --file -   # el cuerpo por stdin; queda como borrador
rapid setup doc brief --skip
rapid setup review --done
rapid setup finish
```

Todos están en la [referencia de `rapid setup`](../cli.md#onboarding-rapid-setup).

</details>

### 4. Pide tu primera funcionalidad

```text
/rapid-feature añadir una función validate_username a app.py
```

Sin argumentos, `/rapid-feature` te propone la primera historia sin marcar del brief (`- [ ] H001: ...`) y espera tu confirmación. El agente redacta la spec, implementa tarea por tarea y corre los tests.

### 5. Aprueba en tu terminal

Cuando termina, el agente se detiene y te da el comando exacto. Ejecútalo en **otra terminal**, fuera del agente:

```bash
rapid approve gate.final-verification
```

Vuelve al agente y escribe `/rapid-next`: el run se cierra con su veredicto. Listo: tu primera funcionalidad quedó implementada, probada y aprobada por ti. Si quieres rechazar, ver en qué va o cancelar, mira [Cuando el agente se detiene](./when-the-agent-stops.md).

:::note Sin agente: `rapid init`
`rapid init` hace el onboarding desde la terminal con preguntas interactivas. Es la alternativa si no usas un agente; lo que no resuelvas queda pendiente para `/rapid-init`.
:::

### Siguientes pasos

- Un laboratorio por modo, con proyectos de ejemplo: [Laboratorios](../tutorials/index.md).
- Adoptarlo en un repositorio que ya tiene código: [Un proyecto que ya existe](./existing-project.md).

---

## Modo avanzado (comandos v3)

No lo necesitas para usar Rapid OS. Si quieres ver el mismo trabajo hecho a mano con los comandos v3 (para CI o auditoría), sigue el [recorrido manual (Bajo el capó)](../tutorials/first-governed-project.md) y el [ciclo de gobernanza v3](../governance-loop.md).
