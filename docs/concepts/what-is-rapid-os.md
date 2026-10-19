---
title: Qué es Rapid OS
description: Objetivo, alcance, usuarios y modelo mental de Rapid OS v3.
---

# Qué es Rapid OS

Rapid OS es una capa de **gobernanza de ingeniería para desarrollo asistido por IA**. Se instala como CLI y mantiene artefactos versionables dentro del repositorio para que el trabajo de un coding harness tenga contexto, alcance, reglas, trazabilidad y evidencia verificable.

## Objetivo

El objetivo principal es que una tarea ejecutada con IA pueda responder de forma verificable estas preguntas:

1. **¿Qué sabemos del repositorio?**
2. **¿Qué se debe construir?**
3. **¿Qué contexto necesita el agente para esa tarea?**
4. **¿Qué nivel de riesgo y qué controles aplican?**
5. **¿El harness declara las capabilities necesarias?**
6. **¿Qué ocurrió durante la ejecución?**
7. **¿Qué evidencia respalda que la tarea y sus gates fueron satisfechos?**
8. **¿El estado completo del proyecto continúa siendo íntegro?**

## Para quién sirve

Rapid OS está orientado a:

- desarrolladores que usan Codex, Claude, Cursor, VS Code u otros coding harnesses;
- equipos que necesitan estandarizar cómo se entrega contexto a agentes de IA;
- arquitectos que quieren separar decisiones humanas de inferencias automáticas;
- equipos con controles de calidad, seguridad, revisión o migraciones;
- organizaciones que necesitan trazabilidad entre especificación, ejecución y evidencia.

## Modelo mental

Rapid OS funciona como una **capa de control**, no como el constructor.

```text
Usuario / equipo
    ↓ define intención y restricciones
Rapid OS
    ↓ produce contexto, contratos, gates y registros
Coding harness externo
    ↓ implementa o modifica el software
Rapid OS
    ↓ ingiere evidencia y evalúa reglas deterministas
Resultado gobernado
```

## Qué hace

Rapid OS puede:

- detectar lenguajes, frameworks, bases de datos, testing, Docker, monorepos y señales de deploy;
- mantener especificaciones con revisiones inmutables;
- compilar contexto específico para una tarea;
- clasificar riesgo y requerir gates;
- modelar capabilities de un harness;
- mantener un ledger append-only de estados del run;
- copiar y verificar artefactos de evidencia con SHA-256;
- producir evaluaciones deterministas y reproducibles;
- validar integridad cruzada entre specs, runs, evidence y evals;
- conducir un run gobernado con el porcelain (`rapid start`, `rapid next`, `rapid check`, `rapid task`, `rapid attach`, `rapid finish`) y generar los shortcuts `/rapid-<modo>` de cada harness.

## Qué no hace

Rapid OS:

- no invoca automáticamente LLMs o coding agents;
- el plumbing (`rapid scan`, `rapid context`, `rapid spec`, `rapid policy`, `rapid run`, `rapid harness`, `rapid evidence`, `rapid eval`, `rapid validate`) no ejecuta nada del repositorio: opera sobre archivos y registros;
- el porcelain ejecuta solo el `test_command` de `.rapid-os/config.json` o el argv que se pasa a `rapid check -- <comando>`, sin shell, más comandos `git` de lectura para registrar los cambios del run; no ejecuta ningún otro comando del proyecto;
- no crea branches o worktrees por su cuenta: solo `rapid start --worktree` crea, a petición explícita, el worktree aislado (`../<repo>-<run-id>`, rama `rapid/<run-id>`) de un run cuyo contrato exige workspace aislado;
- no invoca agentes con los hooks de Claude Code: `rapid hook stop|pre-tool` los ejecuta Claude Code y solo responden con una denegación de herramienta o un bloqueo de parada (`rapid shortcuts install --hooks` es la única vía que los escribe en `.claude/settings.json`);
- no escribe shortcuts `/rapid-<modo>` en las carpetas del harness (`.claude/skills`, `.agents/skills`, `.cursor/skills`, `.github/prompts`) salvo cuando se ejecuta `rapid shortcuts install` o `rapid init --shortcuts`, y solo con `rapid shortcuts install --global` escribe fuera del proyecto, en la carpeta de skills de tu usuario (los instaladores `install.sh` e `install.ps1` solo lo ofrecen, nunca por defecto);
- no escribe `docs/PRODUCT_BRIEF.md`, `docs/BUSINESS_RULES.md`, `docs/DATA_MODEL.md` ni `docs/ARCHITECTURE.md` salvo cuando se ejecuta `rapid setup doc` o `rapid init`, ni copia los estándares de `.rapid-os/standards/` salvo `rapid setup finish` o `rapid init`; `rapid init` ya no crea el andamiaje `TODO` de `docs/` (`SPECS.md` y similares);
- no marca las historias del brief como hechas: `rapid finish` solo sugiere `Marca H002 como hecha en docs/PRODUCT_BRIEF.md` y la persona edita el documento; tampoco deja copias `.bak` de los archivos de agente que regenera (`CLAUDE.md`, `AGENTS.md`, `.cursorrules`...) en la raíz del proyecto: van a `.rapid-os/backups/`, solo si el contenido cambió y con las 5 más recientes por archivo;
- nunca marca como confirmado lo que la persona no confirmó: un documento redactado por el agente queda como `source: drafted` y `status: draft` hasta un `rapid setup doc <id> --confirm` explícito, y llega al contexto marcado como supuesto;
- nunca invoca agentes y nunca aprueba gates humanos: `rapid approve` lo ejecuta una persona en su terminal (exige TTY y falla con `RAPID1310` bajo un agente);
- no considera un gate `acknowledged` como evidencia;
- no considera una capability declarada como prueba de que fue utilizada;
- no garantiza que un `PASS` significa ausencia total de bugs o seguridad perfecta.

## Compatibilidad

Rapid OS v3 conserva los flujos heredados de v2, incluyendo `rapid init`, `rapid scope`, `rapid skill`, `rapid mcp`, `rapid vision`, `rapid deploy`, `rapid refine`, `rapid inspect-context`, `rapid validate` y `rapid doctor`, mientras agrega el ciclo de gobernanza v3.
