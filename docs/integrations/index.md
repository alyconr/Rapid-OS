# Integración con Coding Harnesses

Guías completas de integración técnica y operativa entre **RAPID OS v3** y los principales entornos y asistentes de programación asistida por IA.

---

## 1. Principio Fundamental: Declaración vs Capacidad Real

En RAPID OS, un perfil de harness (`HarnessProfile`) modela de forma **declarativa y conservadora** las capacidades estándar asociadas a una herramienta. 

> **Regla de oro de Product Truth:**  
> Un perfil incorporado (`builtin:cursor`, `builtin:codex`, etc.) **no** otorga permisos mágicos a un modelo ni garantiza que el entorno local pueda realizar una operación. El coding harness solo puede realizar aquellas acciones para las que el desarrollador le haya otorgado permisos en su terminal, sandbox o configuración local.

---

## 2. Matriz Canónica de Capabilities

RAPID OS evalúa exclusivamente los **11 identificadores canónicos de capacidades**:

| ID Canónico | Descripción de la Capacidad | Estado Típico Built-in |
|---|---|---|
| `context.consume` | Capacidad del harness para leer y consumir el Context Bundle | `supported` |
| `repository.read` | Lectura de archivos y directorios del repositorio | `supported` |
| `workspace.current` | Operación dentro del espacio de trabajo activo | `supported` |
| `repository.write` | Modificación de archivos en disco | `unknown` (requiere permisos locales) |
| `shell.execute` | Ejecución de comandos en la terminal / shell | `unknown` (sujeto a sandbox y aprobación) |
| `tests.execute` | Ejecución de suites de prueba automáticas | `unknown` (depende del test runner local) |
| `git.inspect` | Inspección de ramas, diffs y estados de git | `unknown` |
| `git.modify` | Creación de commits, ramas o modificaciones en git | `unknown` |
| `workspace.isolated` | Operación en ramas aisladas o git worktrees | `unknown` |
| `mcp.invoke` | Invocación de herramientas mediante el protocolo MCP | `unknown` |
| `subagents.delegate` | Delegación de tareas a subagentes secundarios | `unknown` |

---

## 3. Catálogo de Guías por Harness

Selecciona la guía correspondiente a tu herramienta:

1. [**OpenAI Codex / CLI Integration**](codex.md): Flujos de ejecución headless y scripts gobernados.
2. [**Anthropic Claude Code**](claude-code.md): Integración con la CLI interactiva y permisos de terminal.
3. [**Cursor IDE**](cursor.md): Integración mediante Composer, reglas de proyecto `.cursorrules` y context injection.
4. [**Visual Studio Code**](vscode.md): Integración con GitHub Copilot Chat, extensiones y terminales integradas.
5. [**Google Antigravity**](antigravity.md): Orquestación multi-agente, subagentes autónomos y sandboxing avanzado.
