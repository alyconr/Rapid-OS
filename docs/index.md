---
id: index
slug: /
title: Rapid OS
description: Documentación oficial de Rapid OS v3, un Contract-Driven Engineering OS para gobernar el trabajo de coding harnesses y agentes de IA.
---

# Rapid OS

<div className="hero--rapid">

**Rapid OS v3** es un **Contract-Driven Engineering OS** para equipos que desarrollan software con coding harnesses y asistentes de IA.

Su objetivo no es reemplazar al agente que escribe código. Su objetivo es convertir el trabajo asistido por IA en un proceso **explícito, trazable, reproducible y verificable**: entender el repositorio, definir qué se debe construir, compilar el contexto correcto, establecer reglas de ejecución, declarar capacidades, registrar evidencia y evaluar el resultado.

</div>

## Qué problema resuelve

Los coding agents pueden trabajar rápido, pero tienden a sufrir tres problemas recurrentes:

- **Pérdida de contexto**: no siempre conocen las reglas de negocio, arquitectura, seguridad o decisiones previas.
- **Instrucciones ambiguas**: un prompt no equivale a una especificación versionada y verificable.
- **Falta de evidencia**: que un agente diga “terminado” no demuestra que se ejecutaron pruebas, revisiones o controles.

Rapid OS introduce contratos y registros deterministas alrededor de ese flujo.

<div className="rapid-grid">
  <div className="rapid-card">
    <h3>Qué existe</h3>
    <p><code>rapid scan</code> crea inteligencia del proyecto con evidencia y procedencia.</p>
  </div>
  <div className="rapid-card">
    <h3>Qué se debe construir</h3>
    <p><code>rapid spec</code> administra especificaciones y revisiones inmutables.</p>
  </div>
  <div className="rapid-card">
    <h3>Qué necesita saber el agente</h3>
    <p><code>rapid context</code> compila contexto relevante, priorizado y limitado por presupuesto.</p>
  </div>
  <div className="rapid-card">
    <h3>Bajo qué reglas puede trabajar</h3>
    <p><code>rapid policy</code> y <code>rapid run</code> fijan riesgo, workspace, gates y tareas.</p>
  </div>
  <div className="rapid-card">
    <h3>Qué puede hacer el harness</h3>
    <p><code>rapid harness</code> resuelve capabilities declaradas contra el contrato del run.</p>
  </div>
  <div className="rapid-card">
    <h3>Qué ocurrió realmente</h3>
    <p><code>rapid evidence</code> y <code>rapid eval</code> registran prueba verificable y producen un veredicto determinista.</p>
  </div>
</div>

## Cómo se usa

El ciclo de gobernanza v3 sigue ocho pasos:

```text
1. scan
2. spec
3. context
4. policy / run
5. harness
6. ejecución externa + actualización del run
7. evidence
8. eval + validate
```

Rapid OS **no ejecuta de forma autónoma un LLM**, no crea worktrees por sí solo, no corre comandos arbitrarios del proyecto y no usa un LLM como juez. El coding harness externo realiza el trabajo; Rapid OS gobierna y verifica los artefactos alrededor de ese trabajo.

## Empieza por aquí

- [Qué es Rapid OS y para quién sirve](./concepts/what-is-rapid-os)
- [Instalación y primer flujo](./getting-started)
- [Casos de uso](./guides/use-cases)
- [Ciclo de gobernanza v3](./governance-loop)
- [Capabilities y permisos](./guides/permissions-capabilities)
- [Estructura de archivos](./guides/project-layout)
- [Referencia completa de CLI](./cli)
- [Arquitectura técnica v3](./architecture/rapid-os-v3)
