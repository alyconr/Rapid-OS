---
title: Capabilities y permisos
description: Cómo Rapid OS modela lo que un coding harness declara poder hacer y cómo se relaciona con riesgo, workspace y evidencia.
---

# Capabilities y permisos

En Rapid OS, “permisos” se modelan principalmente como **capabilities declaradas por el harness**. No son permisos del sistema operativo ni una sandbox de seguridad.

Una capability responde:

> ¿El harness seleccionado declara que puede realizar esta clase de operación?

## Catálogo canónico

| Capability | Categoría | Significado |
| --- | --- | --- |
| `context.consume` | context | Puede consumir el contexto compilado. |
| `repository.read` | repository | Puede leer el repositorio. |
| `repository.write` | repository | Puede modificar archivos del repositorio. |
| `workspace.current` | workspace | Puede trabajar en el workspace actual. |
| `workspace.isolated` | workspace | Puede trabajar en un workspace aislado. |
| `shell.execute` | execution | Puede ejecutar comandos de shell. |
| `tests.execute` | testing | Puede ejecutar pruebas. |
| `git.inspect` | git | Puede inspeccionar Git. |
| `git.modify` | git | Puede modificar estado Git. |
| `mcp.invoke` | integration | Puede invocar herramientas MCP. |
| `subagents.delegate` | delegation | Puede delegar trabajo a subagentes. |

## Estados de soporte

Cada capability puede estar en uno de tres estados:

- `supported`: el profile declara soporte;
- `unsupported`: el profile declara explícitamente que no la soporta;
- `unknown`: Rapid OS no tiene evidencia declarativa suficiente para asumir soporte.

`unknown` **no equivale** a `supported`.

## Profiles built-in

Los profiles built-in son conservadores. Declaran como `supported` únicamente:

- `context.consume`
- `repository.read`
- `workspace.current`

Las demás capabilities empiezan como `unknown`.

Puedes materializar un profile para editarlo:

```bash
rapid harness init codex
```

Esto crea:

```text
.rapid-os/harnesses/codex.json
```

Cuando existe un profile de proyecto, reemplaza completamente al built-in para ese harness; no se hace merge silencioso.

## Cómo se derivan las capabilities requeridas

Rapid OS deriva requisitos desde el `ExecutionContract`.

Reglas principales:

- siempre exige `context.consume` y `repository.read`;
- si el contrato contiene tareas, exige `repository.write`;
- si el workspace es actual, exige `workspace.current`;
- si el riesgo requiere aislamiento, exige `workspace.isolated`;
- si existe `gate.tests`, exige `tests.execute`;
- `--require <capability-id>` agrega requisitos adicionales.

## Riesgo y aislamiento

La política de ejecución clasifica el run como `low`, `medium`, `high` o `critical`.

Por defecto:

- `low` y `medium` permiten el workspace actual;
- `high` y `critical` requieren workspace aislado.

Rapid OS declara esta necesidad en el contrato. No crea automáticamente el worktree, contenedor o sandbox.

## Resolver compatibilidad

```bash
rapid harness show codex
rapid harness resolve --run checkout-r1-run-001
rapid harness resolve --run checkout-r1-run-001 --require-compatible
```

Resultados:

- `compatible`: todos los requisitos están `supported`;
- `incompatible`: al menos uno está `unsupported`;
- `unresolved`: no hay `unsupported`, pero al menos uno está `unknown`.

Con `--require-compatible`, `incompatible` y `unresolved` producen error `RAPID1110` y exit code `1`.

## Capability no es evidencia

Una capability declarada no prueba que fue utilizada.

Ejemplo:

- el profile puede declarar `tests.execute = supported`;
- el run puede requerir `gate.tests`;
- aun así, la evaluación será `UNVERIFIED` si no existe evidencia válida de una ejecución de tests.

La separación es deliberada:

```text
Capability = qué se declara que el harness puede hacer
Evidence   = qué se observó que ocurrió
Eval       = qué puede concluir Rapid OS de esa evidencia
```
