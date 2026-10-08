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
- validar integridad cruzada entre specs, runs, evidence y evals.

## Qué no hace

Rapid OS no:

- invoca automáticamente LLMs o coding agents;
- ejecuta comandos arbitrarios del repositorio durante un run;
- crea branches o worktrees automáticamente;
- considera un gate `acknowledged` como evidencia;
- considera una capability declarada como prueba de que fue utilizada;
- garantiza que un `PASS` significa ausencia total de bugs o seguridad perfecta.

## Compatibilidad

Rapid OS v3 conserva los flujos heredados de v2, incluyendo `rapid init`, `rapid scope`, `rapid skill`, `rapid mcp`, `rapid vision`, `rapid deploy`, `rapid refine`, `rapid inspect-context`, `rapid validate` y `rapid doctor`, mientras agrega el ciclo de gobernanza v3.
