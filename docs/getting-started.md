---
title: Primeros pasos
description: La ruta principal para trabajar con Rapid OS (instalar, rapid init --shortcuts, /rapid-feature), el mapa de la sección y el recorrido avanzado con los comandos v3.
---

# Primeros pasos con Rapid OS

Rapid OS gobierna el trabajo de tu agente de código: cada cambio ocurre dentro de un **run** con spec, tareas, gates y evidencia verificable. La forma habitual de usarlo es con **shortcuts**: tú describes el objetivo y el agente conduce el run. Los comandos v3 siguen disponibles como [Modo avanzado](#modo-avanzado).

---

## 1. Ruta principal: shortcuts

### Requisitos

- **Python 3.10 o superior** (el núcleo de gobernanza usa solo la biblioteca estándar) y **Git**.
- Un coding harness compatible: Claude Code, Codex, Antigravity, Cursor o VS Code (Copilot).
- **Node.js / `npx` (opcional)**: solo para la instalación remota de skills (`rapid skill add`).

### Paso 1: instalar

Elige el método de tu sistema en [Instalación](./installation/index.md) ([Linux](./installation/linux.md), [macOS](./installation/macos.md), [Windows](./installation/windows.md) o [WSL](./installation/wsl.md)) y comprueba que el comando responde:

```bash
rapid --version
```

Los canales (versión estable y desarrollo) y la actualización se explican en [Instalación](./installation/index.md) y [Actualización](./installation/upgrade.md).

### Paso 2: inicializar el proyecto con `rapid init`

Desde la raíz de tu proyecto. No hace falta que ya sea un repositorio git: el onboarding (`rapid init` o `rapid setup finish`) lo crea, siempre en la rama `main`, sin hacer commits:

```bash
rapid init --shortcuts
```

Esto crea `.rapid-os/` (estándares y `config.json`) y genera los 9 shortcuts `/rapid-*` para los agentes que elijas. Añade a `.gitignore` el estado local de la sesión:

```gitignore
.rapid-os/session.json
.rapid-os/scratch/
```

Define el comando de tests que usará `rapid check` (por ejemplo `rapid init --test-command "python -m unittest discover"`, o `test_command` en `.rapid-os/config.json`). En un proyecto ya inicializado usa `rapid shortcuts install`.

### Paso 3: completar el onboarding con `/rapid-init`

En tu agente (en Codex, `$rapid-init`), o a mano con `rapid setup next`:

```text
/rapid-init una API en Python para validar nombres de usuario
```

El agente lee `rapid setup next --json` y te propone, una decisión a la vez: el stack de cada componente, la arquitectura, los servicios y los documentos del proyecto. Lo que redacta el agente queda como **borrador** (`status: draft`) y entra al contexto como supuesto. Antes de cerrar, `rapid setup next` devuelve `review_drafts`: el agente te resume cada borrador y tú decides cuáles confirmas (`rapid setup doc <id> --confirm`) y cuáles se quedan como supuesto; después `rapid setup review --done` y `rapid setup finish`. Rapid OS nunca confirma por ti. Detalle en [Tu primer proyecto](./getting-started/first-project.md).

### Paso 4: pedir el trabajo

En tu agente:

```text
/rapid-feature añadir exportación CSV al informe mensual
```

El agente sigue el bucle `rapid next` → `rapid start` → `rapid check` → `rapid finish` y se detiene cuando hace falta una persona. Entonces tú ejecutas `rapid approve <gate>` **en tu propia terminal**: ningún shortcut aprueba gates humanos. Qué carpeta se genera en cada harness y cómo se invoca está en la [guía de shortcuts](./guides/shortcuts.md).

Los otros shortcuts: `/rapid-bugfix`, `/rapid-refactor`, `/rapid-hardening`, `/rapid-research`, `/rapid-next`, `/rapid-status` y `/rapid-approve`.

---

## 2. Mapa de esta sección

| Página | Para qué sirve |
| :--- | :--- |
| [Tu primer proyecto gobernado](./getting-started/first-project.md) | Tutorial guiado desde cero: shortcuts primero, comandos v3 después. |
| [Gobernar un proyecto existente](./getting-started/existing-project.md) | Adoptar Rapid OS en un repositorio con código previo sin tocar tu código de negocio. |
| [Creación y gestión de especificaciones](./getting-started/first-spec.md) | Qué es una spec, cómo la redacta el agente (`author_spec`) y cómo se crea a mano. |
| [Compilación de contexto estructurado](./getting-started/first-context.md) | Qué contexto recibe el agente y cómo compilarlo a mano. |
| [Próximos pasos](./getting-started/next-steps.md) | Hacia dónde seguir: laboratorios, integraciones y referencia. |

Fuera de esta sección:

- [Guía de shortcuts](./guides/shortcuts.md): instalación por harness, el bucle y la aprobación humana.
- [Laboratorios](./tutorials/index.md): un laboratorio por modo, cada uno con su shortcut.
- [Referencia de CLI](./cli.md) y [diagnósticos](./troubleshooting/diagnostics.md).

---

## Modo avanzado

Los comandos v3 (`rapid scan`, `rapid spec`, `rapid context`, `rapid run`, `rapid evidence`, `rapid eval`, `rapid validate`) hacen a mano lo que hace el agente con los shortcuts. Son útiles para CI, depuración y auditoría, y para entender qué registra cada paso. El recorrido completo:

### Inicializar o inspeccionar tu proyecto

```bash
cd /ruta/a/tu-proyecto
rapid doctor
```

Para inicializar estándares (`.rapid-os/standards/`, `.rapid-os/config.json` y archivos de instrucciones del agente):

```bash
rapid init
```

También puedes crear la estructura mínima de estándares de forma no interactiva antes de ejecutar el ciclo de gobernanza v3.

---

## Recorrido completo con los comandos v3

### Paso 1: Scan Project Intelligence (`rapid scan`)

Scan the repository for deterministic facts (`ProjectModel`) and persist `.rapid-os/project.json`:

```bash
rapid scan --write
```

### Paso 2: Create and Ready an Immutable Spec (`rapid spec`)

Create a structured specification in `.rapid-os/specs/checkout-idempotency/` and mark it `ready`:

```bash
rapid spec create \
  --id checkout-idempotency \
  --title "Checkout Idempotency" \
  --mode feature \
  --objective "Prevent duplicate charges on payment retries" \
  --problem "Network retries can submit duplicate payment requests" \
  --scope "src/checkout.py" \
  --acceptance "Duplicate idempotency keys return the original result" \
  --task "Implement idempotency key store and unit tests" \
  --status ready
```

### Paso 3: Compile Task-Specific Context (`rapid context`)

Compile a budgeted, provenance-backed context bundle (`CompiledContext`) for your coding harness:

```bash
rapid context compile --mode feature --spec checkout-idempotency --harness codex --manifest
```

### Paso 4: Create an Immutable Run Contract (`rapid policy` & `rapid run`)

Inspect the active execution policy and create a governed Run (`checkout-idempotency-r1-run-001`):

```bash
rapid policy show
rapid run create --spec checkout-idempotency --harness codex
```

### Paso 5: Resolve Harness Capabilities (`rapid harness`)

Initialize and lock a project harness profile if your run requires capabilities beyond the conservative built-in profile (such as `repository.write` and `tests.execute`), then verify compatibility:

```bash
rapid harness list
rapid harness show codex
rapid harness resolve --run checkout-idempotency-r1-run-001
```

### Paso 6: Execute Work & Advance Run State (`rapid run`)

Acknowledge pre-execution gates, activate the run, and record task progress as your coding harness executes the work:

```bash
rapid run gate checkout-idempotency-r1-run-001 gate.baseline acknowledged --reason "Baseline test suite green"
rapid run status checkout-idempotency-r1-run-001 active
rapid run task checkout-idempotency-r1-run-001 T001 in_progress
rapid run task checkout-idempotency-r1-run-001 T001 done
rapid run gate checkout-idempotency-r1-run-001 gate.tests acknowledged --reason "Unit tests passing"
rapid run gate checkout-idempotency-r1-run-001 gate.final-verification acknowledged --reason "Ready for final verification"
rapid run status checkout-idempotency-r1-run-001 finished
```

### Paso 7: Attach Verifiable Run Evidence (`rapid evidence`)

> **Important**: Acknowledging gates in Step 6 is a *declaration*, not proof. Without evidence, `rapid eval run` will report `unverified`.

Ingest immutable `RunEvidence` records (`E001`, `E002`, ...) and copy supporting artifacts into `.rapid-os/evidence/<run-id>/`:

```bash
rapid evidence add --run checkout-idempotency-r1-run-001 --input baseline-evidence.json
rapid evidence add --run checkout-idempotency-r1-run-001 --input implementation-evidence.json
rapid evidence verify --run checkout-idempotency-r1-run-001
```

### Paso 8: Run Behavioral Evaluation & Validate Project (`rapid eval` & `rapid validate`)

Evaluate the run against Phase 6 behavioral rules and require a passing verdict:

```bash
rapid eval run --run checkout-idempotency-r1-run-001 --write --require-pass
rapid validate
```

When all required lifecycle, task, gate, and observable capability assertions are backed by verified evidence, `rapid eval run --require-pass` emits `Verdict: pass` and exits `0`.
