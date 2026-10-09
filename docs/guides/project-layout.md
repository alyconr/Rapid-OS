---
title: Estructura de archivos
description: Qué archivos crea Rapid OS, cuáles son inmutables y qué comandos son de solo lectura o escritura.
---

# Estructura de archivos

Rapid OS guarda la mayor parte de su estado de gobernanza dentro de `.rapid-os/`, dejando visibles los artefactos que deben poder versionarse, inspeccionarse y auditarse.

## Estructura principal

```text
project/
├── .rapid-os/
│   ├── config.json
│   ├── project.json
│   ├── policy.json
│   ├── capabilities.lock
│   ├── standards/
│   ├── specs/
│   │   └── <spec-id>/
│   │       ├── spec.json
│   │       └── revisions/
│   ├── runs/
│   │   └── <run-id>/
│   │       ├── run.json
│   │       ├── contract.json
│   │       ├── context.md
│   │       ├── context-manifest.json
│   │       └── states/
│   ├── harnesses/
│   ├── evidence/
│   │   └── <run-id>/
│   │       ├── records/
│   │       └── artifacts/
│   └── evals/
│       └── <run-id>/
│           └── reports/
├── SPECS.md
├── TASKS.md
├── ACCEPTANCE.md
├── references/
└── archivos específicos del harness
```

No todos los archivos existen desde el inicio; aparecen cuando se usa el módulo correspondiente.

## Archivos heredados de contexto

`rapid init` puede generar archivos como:

- `.cursorrules`
- `CLAUDE.md`
- `.agent/rules/constitution.md`
- `INSTRUCTIONS.md`
- `AGENTS.md`

También mantiene estándares dentro de `.rapid-os/standards/`.

## Artefactos inmutables

Los registries v3 priorizan append-only e integridad por digest.

Ejemplos:

- revisiones de Specs no se editan en sitio;
- snapshots históricos de `RunState` no se sobrescriben;
- records de Evidence usan IDs secuenciales;
- reportes de evaluación se agregan por revisión;
- artefactos de Evidence se copian y verifican por SHA-256 y tamaño.

## Comandos de solo lectura

Ejemplos:

```text
rapid guide
rapid scan
rapid validate
rapid doctor
rapid inspect-context
rapid context
rapid spec list
rapid spec show
rapid policy show
rapid run list
rapid run show
rapid harness list
rapid harness show
rapid harness resolve
rapid evidence list
rapid evidence show
rapid evidence verify
rapid eval list
rapid eval show
```

Algunos comandos cambian de comportamiento con flags. Por ejemplo, `rapid scan` es de solo lectura salvo que se use `--write`, y `rapid eval run` solo persiste un reporte con `--write`.

## Comandos que escriben estado

Ejemplos:

```text
rapid init
rapid scan --write
rapid scope
rapid spec create
rapid spec revise
rapid spec status
rapid spec export-legacy
rapid policy init
rapid run create
rapid run status
rapid run task
rapid run gate
rapid harness init
rapid harness lock
rapid evidence add
rapid eval run --write
rapid mcp
rapid vision
rapid deploy
```

Consulta [la referencia CLI](../cli) para los flags y contratos exactos de cada comando.

## Protección de rutas y backups

Rapid OS valida contención de rutas para evitar path traversal y escapes mediante symlinks en los registries gobernados. Las operaciones heredadas que sobrescriben ciertos archivos utilizan backups `.bak` cuando corresponde.

La seguridad de rutas protege los artefactos de Rapid OS, pero no sustituye los controles de permisos del sistema operativo o del entorno donde se ejecute el coding harness.
