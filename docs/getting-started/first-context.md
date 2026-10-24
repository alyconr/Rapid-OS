---
title: Qué sabe el agente de tu proyecto
description: De dónde saca el agente las reglas de tu proyecto (documentos, estándares, spec), qué pasa con los borradores y cómo cambiarlos; la compilación a mano con rapid context queda como modo avanzado.
---

# Qué sabe el agente de tu proyecto

Un agente sin contexto improvisa: inventa reglas de negocio, mezcla estilos de arquitectura y olvida decisiones previas. Rapid OS le da, en cada trabajo, solo lo que necesita saber.

## Con shortcuts

No tienes que hacer nada: el agente recibe el contexto en cada trabajo. Viene de tres sitios:

| Qué | De dónde sale | Dónde vive |
| :--- | :--- | :--- |
| **Documentos del proyecto**: brief, reglas de negocio, modelo de datos, arquitectura | Los decidiste en `/rapid-init` (pegados, redactados por el agente u omitidos) | `docs/` |
| **Estándares**: stack, arquitectura, seguridad, estilo de código | Rapid OS los genera con tus decisiones del onboarding | `.rapid-os/standards/` y el archivo de tu agente (`CLAUDE.md`, `AGENTS.md`…) |
| **La spec del trabajo actual** | El agente la redacta con tu pedido | `.rapid-os/specs/` |

### Borradores y documentos confirmados

Lo que **confirmaste** el agente lo trata como regla del proyecto y la cumple sin discutirla. Lo que quedó como **borrador** (lo redactó el agente y no lo confirmaste) lo trata como supuesto: puede cuestionarlo y preguntarte, y cada trabajo te lo recuerda. Para confirmar un borrador más tarde:

```bash
rapid setup doc business --confirm
```

Cambia `business` por `brief`, `data-model` o `architecture`.

### Cambiar un documento

Los documentos de `docs/` los escribe Rapid OS (`rapid setup doc`), no se editan a mano. Si omitiste uno y ahora lo quieres, ábrelo de nuevo:

```bash
rapid setup doc business --reopen
```

Después escribe `/rapid-init` en el agente: te lo vuelve a ofrecer para pegarlo, redactarlo u omitirlo. Para reemplazar un documento que ya tiene contenido, ver [Documentos del proyecto](../concepts/project-docs.md).

<details>
<summary>Qué hace el agente por debajo</summary>

Al ejecutar `rapid start <modo> --spec-file -`, Rapid OS crea el contrato del run con la spec y los estándares del proyecto, y el shortcut le indica al agente que trabaje solo con la tarea que devuelve `rapid next --json` (`implement_task`). Para ver exactamente qué contexto recibiría un harness (por ejemplo, para depurar una respuesta o para CI), usa `rapid context`, descrito en el modo avanzado.

</details>

## Modo avanzado

No lo necesitas con shortcuts. Explica el compilador de contexto (`rapid context`): presupuesto, relevancia, manifiesto y procedencia, útil para depurar y para CI.

<details>
<summary>Ver el compilador de contexto</summary>

---

## Por qué no volcar todo el repositorio

```mermaid
flowchart LR
    subgraph Sin Rapid OS
        A[Todo el Repositorio] -->|Volcado masivo sin filtro| B[Agente de IA]
        B --> C[Ruido, alucinaciones y límite de tokens excedido]
    end

    subgraph Con Rapid OS Context Compiler
        D[Standards + ProjectModel + Spec] -->|rapid context (Modo + Presupuesto)| E[Contexto Sintetizado]
        E --> F[Agente de IA]
        F --> G[Implementación precisa y focalizada]
    end
```

---

## Opciones principales de `rapid context`

| Flag | Tipo | Descripción |
| :--- | :--- | :--- |
| `--mode` | string | Modo de tarea: `feature`, `bugfix`, `refactor`, `hardening`, `research` o `general`. |
| `--spec` | string | Identificador de una especificación en estado `ready` a incluir. |
| `--harness` | string | Identificador del harness destino (ej. `codex`, `claude`, `cursor`, `vscode`, `antigravity`). |
| `--objective` | string | Objetivo explícito para refinamiento de relevancia. |
| `--max-chars` | entero | Presupuesto máximo de caracteres en el Markdown resultante. |
| `--manifest` | flag | Imprime un resumen legible de procedencia (`ContextManifest`). |
| `--json` | flag | Emite el objeto estructurado `CompiledContext` en formato JSON. |

---

## Ejemplo: Compilar contexto para una Feature

Supongamos una spec `api-rate-limiting` en estado `ready` (ver [Cómo se escribe la spec](./first-spec.md)):

```bash
rapid context --spec api-rate-limiting --manifest
```

Con `--mode`, `--harness` o `--max-chars` (ver la tabla de arriba) ajustas el modo, el agente destino y el presupuesto.

### ¿Qué contiene la salida?
El comando emite en `stdout` un documento Markdown estructurado listo para ser pegado en el prompt o inyectado por una herramienta de automatización:
1. **Directivas generales del proyecto:** Estándares clave de arquitectura y codificación extraídos de `.rapid-os/standards/`.
2. **Hechos relevantes del escaneo:** Lenguaje, frameworks de pruebas y librerías pertinentes al modo.
3. **Especificación activa:** Los objetivos, alcance, criterios de aceptación y tareas de la revisión congelada de la spec.
4. **Resumen de manifiesto (`--manifest`):**
   ```text
   Rapid OS Context Manifest

   Mode: general
   Harness: cursor
   Budget: 17550 / 24000 chars

   SELECTED
     standard.security      critical  9450 chars   relevant to general mode
     standard.architecture  high      5159 chars   relevant to general mode
     standard.tech-stack    high      445 chars    relevant to general mode
     spec.api-rate-limiting.requirements high      467 chars    relevant to general mode; selected spec 'api-rate-limiting'
   ```

---

## El Manifiesto de Contexto (`ContextManifest`)

Cada compilación genera un hash criptográfico de su contenido (`content_digest`). Cuando posteriormente se crea un run con `rapid run create`, este digest queda registrado de forma inmutable en el contrato de ejecución (`ExecutionContract.context_digest`).

Esto garantiza una **auditoría perfecta**: meses después de implementado un cambio, el equipo puede reproducir con certeza matemática exactamente qué información y directivas vio el agente en el momento de la ejecución.

</details>
