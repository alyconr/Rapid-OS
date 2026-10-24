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

## Empieza en 3 pasos

No necesitas aprender comandos: trabajas con **shortcuts** (`/rapid-…`) dentro de tu agente de código, y en tu terminal solo instalas y apruebas.

**1. Instala Rapid OS** ([Instalación](./installation/index.md)). Al final, el instalador pregunta para qué agentes instalar los shortcuts: escribe el tuyo (por ejemplo `claude`). Si te lo saltaste, una sola vez:

```bash
rapid shortcuts install --global --harness claude
```

**2. Describe tu proyecto en el agente.** Te propone el stack, el comando de tests y los documentos; tú decides:

```text
/rapid-init una API en Python para validar nombres de usuario
```

**3. Pide el trabajo:**

```text
/rapid-feature añadir exportación CSV al informe mensual
```

Cuando termina, el agente se detiene y te da el comando para aprobar en **tu** terminal (por ejemplo `rapid approve gate.final-verification`). Después escribe `/rapid-next` para cerrar.

| Quieres… | Escribe en tu agente |
| :--- | :--- |
| Configurar el proyecto | `/rapid-init <descripción>` |
| Una funcionalidad nueva | `/rapid-feature <objetivo>` |
| Corregir un bug | `/rapid-bugfix <qué falla>` |
| Refactorizar sin romper tests | `/rapid-refactor <alcance>` |
| Endurecer seguridad | `/rapid-hardening <área>` |
| Investigar una opción | `/rapid-research <pregunta>` |
| Ver en qué va o seguir | `/rapid-status` · `/rapid-next` |

En Codex se escriben con `$` (`$rapid-init`). En VS Code, y si prefieres versionar los shortcuts con el repositorio, instálalos en el proyecto con `rapid init --shortcuts`. Detalle por agente en la [guía de shortcuts](./guides/shortcuts.md).

## Modo avanzado: el ciclo de gobernanza v3

Los comandos v3 (`rapid scan`, `rapid spec`, `rapid run`, `rapid evidence`, `rapid eval`…) siguen disponibles para CI, depuración y auditoría. El ciclo de gobernanza v3 sigue ocho pasos:

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

Rapid OS **no ejecuta de forma autónoma un LLM**, no aprueba gates humanos, solo crea un worktree con `rapid start --worktree`, ejecuta únicamente el `test_command` configurado o el argv de `rapid check` (el plumbing no ejecuta nada) y no usa un LLM como juez. El coding harness externo realiza el trabajo; Rapid OS gobierna y verifica los artefactos alrededor de ese trabajo.

## Empieza por aquí

- [Qué es Rapid OS y para quién sirve](./concepts/what-is-rapid-os.md)
- [Por qué Rapid OS y problemas que resuelve](./concepts/why-rapid-os.md)
- [Requisitos e instalación](./installation/index.md)
- [Shortcuts por harness (`/rapid-<modo>`)](./guides/shortcuts.md)
- [Tu primer proyecto (Quickstart)](./getting-started/first-project.md)
- [Un proyecto que ya existe](./getting-started/existing-project.md)
- [Cuando el agente se detiene](./getting-started/when-the-agent-stops.md)
- [Modos de ingeniería](./guides/modes/index.md)
- [Cookbooks de Gobernanza y Evidencia](./cookbooks/policies-and-contracts.md)
- [Catálogo de Diagnósticos RAPIDxxx](./troubleshooting/diagnostics.md)
- [Integración en CI/CD](./guides/ci-cd-integration.md)
- [Ciclo de gobernanza v3](./governance-loop.md)
- [Capabilities y permisos](./guides/permissions-capabilities.md)
- [Estructura de archivos](./guides/project-layout.md)
- [Referencia completa de CLI](./cli.md)
- [Arquitectura técnica v3](./architecture/rapid-os-v3.md)
- [Arquitectura de orquestación (porcelain sobre plumbing)](./architecture/orchestration.md)
