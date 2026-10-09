---
title: Perfiles y Capabilities del Harness
description: Cookbook para configurar perfiles de coding harness, resolver compatibilidad de capacidades y generar locks en RAPID OS.
---

# Perfiles y Capabilities del Harness

En el ecosistema de ingeniería asistida por agentes, distintos editores y plataformas (Cursor, Claude Code, GitHub Copilot, Codex, Antigravity) ofrecen diferentes conjuntos de herramientas e integraciones.

RAPID OS no asume que todos los entornos pueden ejecutar las mismas acciones. Mediante el **Harness Capability Registry**, declara, versiona y audita qué capacidades soporta cada asistente.

---

## Product Truth: Qué representa una Capability

> **Principio de Verdad del Producto**:
> 1. Una capability declarada (ej. `filesystem.write`, `git.commit`) expresa el **soporte que el harness declara ofrecer**.
> 2. RAPID OS **no** invoca directamente el harness ni controla los procesos del sistema operativo.
> 3. Que un harness declare una capability **no constituye evidencia** de que haya sido ejecutada o que el resultado esté libre de defectos.

---

## 1. Perfiles integrados (Built-in Profiles)

RAPID OS incluye perfiles canónicos predeterminados:

```bash
# Listar todos los perfiles disponibles
rapid harness list

# Ver capacidades detalladas de un perfil
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

### Estructura de `.rapid-os/harnesses/<id>.json`

```json
{
  "schema_version": 1,
  "id": "mi-agente-interno",
  "name": "Agente Interno de Ingeniería",
  "vendor": "Mi Empresa",
  "version": "2.4.0",
  "capabilities": {
    "context.spec": {
      "support": "supported",
      "notes": "Lee specs directamente desde .rapid-os/specs"
    },
    "filesystem.read": {
      "support": "supported",
      "notes": "Acceso de lectura a todo el repositorio"
    },
    "filesystem.write": {
      "support": "supported",
      "notes": "Escritura restringida a src/ y tests/"
    },
    "terminal.execute": {
      "support": "supported",
      "notes": "Ejecución de tests y herramientas linters"
    },
    "git.diff": {
      "support": "supported",
      "notes": "Genera diffs estructurados para evidencia"
    },
    "git.commit": {
      "support": "unsupported",
      "notes": "Los commits son realizados exclusivamente por el desarrollador"
    }
  }
}
```

### Niveles de soporte permitidos (`CapabilitySupport`)
- `supported`: La capacidad está disponible y operativa en el entorno.
- `conditional`: La capacidad está disponible bajo condiciones específicas (ej. flags de permisos o aprobación humana previa).
- `unsupported`: La capacidad no está disponible en este harness.

---

## 3. Bloqueo determinista (`rapid harness lock`)

Para garantizar que los pipelines de CI o los desarrolladores utilicen exactamente las mismas definiciones de harness, puedes generar el archivo `.rapid-os/capabilities.lock`:

```bash
rapid harness lock
```

Este comando inspecciona todos los perfiles activos, calcula su digest SHA-256 canónico y los congela en un archivo inmutable versionado en git.

---

## 4. Resolución de Compatibilidad contra un Run

Cuando se crea un `ExecutionContract`, este define qué capacidades requiere la tarea. Puedes verificar si el harness asignado satisface dichos requisitos:

```bash
# Resolución básica
rapid harness resolve --run feature-pago-r1-run-001

# Resolución estricta contra el archivo lock
rapid harness resolve --run feature-pago-r1-run-001 --locked

# Resolución en modo compuerta de CI (exit code 1 si incompatible o unresolved)
rapid harness resolve --run feature-pago-r1-run-001 --require-compatible
```

### Estados de resolución
1. **`compatible`**: El harness soporta todas las capabilities obligatorias requeridas por el contrato. (Exit code 0).
2. **`incompatible`**: El harness marca como `unsupported` una capacidad requerida por el contrato. (Exit code 1 con `RAPID1110` si se especificó `--require-compatible`).
3. **`unresolved`**: El harness tiene requerimientos con estado `conditional` o no definidos.

---

## 5. Exigir Capabilities adicionales en CLI

Si una corrida particular requiere una capacidad no declarada en el perfil por defecto, puedes exigir su presencia en tiempo de resolución:

```bash
rapid harness resolve \
  --run feature-pago-r1-run-001 \
  --require "terminal.execute" \
  --require-compatible
```
