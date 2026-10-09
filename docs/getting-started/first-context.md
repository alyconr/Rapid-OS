---
title: Compilación de contexto estructurado
description: Cómo generar contexto presupuestado, relevante y auditable para coding harnesses con rapid context.
---

# Compilación de contexto estructurado

Uno de los principales problemas al trabajar con coding agents es la sobrecarga y degradación del contexto. Enviar el repositorio entero a un modelo de lenguaje desperdicia presupuesto de tokens, satura la memoria del modelo e incrementa la probabilidad de alucinaciones.

El subcomando `rapid context` actúa como un **compilador de contexto determinista**: selecciona, prioriza y presupuesta exactamente lo que el agente necesita saber para una tarea específica.

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

Supongamos que deseamos implementar la especificación `rate-limiting` utilizando Codex:

```bash
rapid context \
  --mode feature \
  --spec rate-limiting \
  --harness codex \
  --max-chars 8000 \
  --manifest
```

### ¿Qué contiene la salida?
El comando emite en `stdout` un documento Markdown estructurado listo para ser pegado en el prompt o inyectado por una herramienta de automatización:
1. **Directivas generales del proyecto:** Estándares clave de arquitectura y codificación extraídos de `.rapid-os/standards/`.
2. **Hechos relevantes del escaneo:** Lenguaje, frameworks de pruebas y librerías pertinentes al modo `feature`.
3. **Especificación activa:** Los objetivos, alcance, criterios de aceptación y tareas de la revisión congelada de la spec.
4. **Resumen de manifiesto (`--manifest`):**
   ```text
   Rapid OS Context Manifest

   Mode: feature
   Harness: codex
   Budget: 4230 / 8000 chars

   SELECTED
     standard.topology      high      776 chars
     standard.tech-stack    high      456 chars
     spec.rate-limiting     high      1200 chars
     project.intelligence   medium    19 chars
   ```

---

## El Manifiesto de Contexto (`ContextManifest`)

Cada compilación genera un hash criptográfico de su contenido (`content_digest`). Cuando posteriormente se crea un run con `rapid run create`, este digest queda registrado de forma inmutable en el contrato de ejecución (`ExecutionContract.context_digest`).

Esto garantiza una **auditoría perfecta**: meses después de implementado un cambio, el equipo puede reproducir con certeza matemática exactamente qué información y directivas vio el agente en el momento de la ejecución.
