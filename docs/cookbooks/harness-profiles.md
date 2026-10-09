---
title: Perfiles y Capabilities del Harness
description: Cookbook para configurar perfiles de coding harness, resolver compatibilidad de capacidades y generar locks en RAPID OS.
---

# Perfiles y Capabilities del Harness

En el ecosistema de ingeniería asistida por agentes, distintos editores y asistentes (Cursor, Claude Code, GitHub Copilot, Codex, Antigravity) ofrecen diferentes conjuntos de herramientas e integraciones.

RAPID OS no asume que todos los entornos pueden ejecutar las mismas acciones. Mediante el **Harness Capability Registry**, declara, versiona y audita qué capacidades declara soportar cada asistente.

---

## Product Truth: Qué representa una Capability

> **Principio de Verdad del Producto**:
> 1. Una capability declarada (ej. `repository.write`, `shell.execute`) expresa el **soporte que el harness declara ofrecer**.
> 2. RAPID OS **no** invoca directamente el harness ni controla los procesos o permisos del sistema operativo.
> 3. Que un harness declare una capability **no constituye evidencia** de que haya sido ejecutada o que el resultado esté libre de defectos.

---

## Catálogo de Capabilities Canónicas

El catálogo de RAPID OS define exactamente las siguientes 11 capacidades canónicas:

| Identificador | Categoría | Descripción |
| :--- | :--- | :--- |
| `context.consume` | `context` | Capacidad de leer y consumir el contexto compilado y contratos de ejecución. |
| `git.inspect` | `git` | Capacidad de inspeccionar estado, historial y diffs de git. |
| `git.modify` | `git` | Capacidad de crear ramas, commits o worktrees en git. |
| `mcp.invoke` | `integration` | Capacidad de invocar herramientas y recursos Model Context Protocol (MCP). |
| `repository.read` | `repository` | Capacidad de leer archivos y estructura del repositorio. |
| `repository.write` | `repository` | Capacidad de crear o modificar archivos del repositorio durante la tarea. |
| `shell.execute` | `execution` | Capacidad de ejecutar comandos de terminal o shell local. |
| `subagents.delegate` | `delegation` | Capacidad de delegar subtareas a subagentes especializados. |
| `tests.execute` | `testing` | Capacidad de ejecutar suites de pruebas automatizadas para verificación. |
| `workspace.current` | `workspace` | Capacidad de operar en el working tree actual cuando la política lo permite. |
| `workspace.isolated` | `workspace` | Capacidad de operar en un espacio de trabajo o worktree aislado cuando la política lo exige. |

---

## 1. Perfiles integrados (Built-in Profiles)

RAPID OS incluye perfiles canónicos predeterminados:

```bash
# Listar todos los perfiles disponibles
rapid harness list

# Ver capacidades detalladas de un perfil integrado
rapid harness show codex
rapid harness show claude
rapid harness show cursor
rapid harness show antigravity
```

---

## 2. Personalizar o crear un perfil local

Puedes sobrescribir un perfil predeterminado o registrar un harness propietario de tu equipo en `.rapid-os/harnesses/<id>.json`:

```bash
# Inicializar la plantilla de un perfil existente o nuevo
rapid harness init mi-agente-interno
```

### Estructura Canónica de `.rapid-os/harnesses/<id>.json`

El archivo de perfil sigue el esquema versión 1 (`HarnessProfile`):

```json
{
  "schema_version": 1,
  "id": "mi-agente-interno",
  "capabilities": [
    {
      "capability_id": "context.consume",
      "status": "supported",
      "reason": "Lee el contexto compilado directamente desde .rapid-os/context"
    },
    {
      "capability_id": "repository.read",
      "status": "supported",
      "reason": "Acceso completo de lectura a todo el árbol del repositorio"
    },
    {
      "capability_id": "repository.write",
      "status": "supported",
      "reason": "Escritura restringida a archivos de código y pruebas"
    },
    {
      "capability_id": "shell.execute",
      "status": "supported",
      "reason": "Ejecución de herramientas linters y comandos locales"
    },
    {
      "capability_id": "tests.execute",
      "status": "supported",
      "reason": "Ejecución de suites de pytest en terminal"
    },
    {
      "capability_id": "git.inspect",
      "status": "supported",
      "reason": "Inspección de diffs y estado de git"
    },
    {
      "capability_id": "git.modify",
      "status": "unsupported",
      "reason": "Los commits y modificaciones de ramas son gestionados por el desarrollador"
    },
    {
      "capability_id": "subagents.delegate",
      "status": "unknown",
      "reason": "Soporte de subagentes pendiente de validación en entorno corporativo"
    }
  ]
}
```

### Niveles de soporte permitidos (`CapabilitySupportStatus`)

Los únicos tres estados canónicos permitidos para `status` son:

- **`supported`**: La capacidad está disponible y declarada como soportada por el entorno.
- **`unsupported`**: La capacidad no está disponible ni soportada en este entorno de trabajo.
- **`unknown`**: El estado de soporte no está determinado o no ha sido declarado explícitamente.

> **Importante**: RAPID OS **no** admite estados como `conditional`. Si una capacidad tiene restricciones operativas, se declara como `supported` o `unsupported` y las condiciones específicas se detallan en el campo `reason`.

---

## 3. Bloqueo determinista (`rapid harness lock`)

Para garantizar que los pipelines de CI o los desarrolladores utilicen exactamente las mismas definiciones de perfiles y hashes de capabilities, puedes generar el archivo `.rapid-os/capabilities.lock`:

```bash
rapid harness lock
```

Este comando inspecciona todos los perfiles activos, calcula su digest SHA-256 canónico y los congela en un archivo inmutable versionado en git.

---

## 4. Resolución de Compatibilidad contra un Run

Cuando se crea un `ExecutionContract`, este define qué capacidades requiere la tarea. Puedes verificar deterministamente si el harness asignado satisface dichos requisitos:

```bash
# Resolución básica
rapid harness resolve --run feature-pago-r1-run-001

# Resolución estricta contra el archivo lock (.rapid-os/capabilities.lock)
rapid harness resolve --run feature-pago-r1-run-001 --locked

# Resolución en modo compuerta de CI (exit code 1 si incompatible o unresolved)
rapid harness resolve --run feature-pago-r1-run-001 --require-compatible
```

### Estados de resolución (`CapabilityResolutionStatus`):
1. **`compatible`**: El harness declara soporte (`supported`) para todas las capabilities obligatorias exigidas por el contrato. (Exit code `0`).
2. **`incompatible`**: El harness marca como no soportada (`unsupported`) al menos una capability requerida por el contrato. (Exit code `1` con diagnóstico `RAPID1110` bajo `--require-compatible`).
3. **`unresolved`**: Una o más capabilities requeridas están en estado `unknown` o no han sido declaradas. (Exit code `1` bajo `--require-compatible`).

---

## 5. Exigir Capabilities adicionales en CLI

Si una corrida particular requiere una capacidad no exigida originalmente por la spec, puedes forzar su evaluación en tiempo de resolución:

```bash
rapid harness resolve \
  --run feature-pago-r1-run-001 \
  --require "shell.execute" \
  --require-compatible
```
