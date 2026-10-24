---
title: Primeros pasos
description: Empieza en 3 pasos (instalar, /rapid-init, /rapid-feature), el mapa de la sección y, plegado, el recorrido avanzado con los comandos v3.
---

# Primeros pasos con Rapid OS

Rapid OS gobierna el trabajo de tu agente de código: cada cambio ocurre dentro de un **run** con spec, tareas, gates y evidencia verificable. Tú no tienes que aprender esos comandos: los ejecuta el agente a través de los **shortcuts** (`/rapid-…`). En tu terminal solo instalas y apruebas.

---

## 1. Empieza en 3 pasos

Necesitas Python 3.10+, Git y un agente de código: Claude Code, Codex, Cursor, Antigravity o VS Code (Copilot).

### Paso 1: instalar

Usa el instalador de tu sistema ([Linux](./installation/linux.md), [macOS](./installation/macos.md), [Windows](./installation/windows.md) o [WSL](./installation/wsl.md)). Al final pregunta para qué agentes instalar los shortcuts: escribe el tuyo (por ejemplo `claude`) y quedan disponibles en todos tus proyectos. Si te lo saltaste, una sola vez:

```bash
rapid shortcuts install --global --harness claude
```

:::note VS Code y versiones anteriores
VS Code no tiene carpeta de usuario para shortcuts: instálalos en cada proyecto con `rapid init --shortcuts`. Lo mismo si tu versión de Rapid OS aún no trae `/rapid-init` ni `--global` (lo verás en `rapid shortcuts install --help`).
:::

### Paso 2: describir el proyecto con `/rapid-init`

Abre tu agente en la carpeta del proyecto (nueva o con código) y escribe:

```text
/rapid-init una API en Python para validar nombres de usuario
```

El agente te propone, una decisión a la vez, el stack, el comando de tests y los documentos del proyecto (brief, reglas de negocio, modelo de datos, arquitectura). Para cada documento eliges: lo pegas, lo redacta el agente o lo omites. Lo que redacta queda como **borrador** hasta que tú digas que lo confirmas. En Codex se escribe `$rapid-init`.

### Paso 3: pedir el trabajo

```text
/rapid-feature añadir exportación CSV al informe mensual
```

El agente redacta la spec, implementa tarea por tarea y corre los tests. Cuando necesita a una persona se detiene y te da el comando exacto para **tu** terminal, por ejemplo:

```bash
rapid approve gate.final-verification
```

Después escribe `/rapid-next` en el agente y el run se cierra. Ningún shortcut aprueba por ti.

| Quieres… | Escribe en tu agente |
| :--- | :--- |
| Una funcionalidad nueva | `/rapid-feature <objetivo>` |
| Corregir un bug | `/rapid-bugfix <qué falla>` |
| Refactorizar sin romper tests | `/rapid-refactor <alcance>` |
| Endurecer seguridad | `/rapid-hardening <área>` |
| Investigar una opción | `/rapid-research <pregunta>` |
| Ver en qué va o seguir | `/rapid-status` · `/rapid-next` |
| Saber qué aprobar | `/rapid-approve` |

Carpetas y forma de invocarlos en cada agente: [guía de shortcuts](./guides/shortcuts.md).

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

No lo necesitas para usar Rapid OS. Los comandos v3 hacen a mano lo que hace el agente con los shortcuts; sirven para CI, depuración y auditoría. El ciclo completo, con diagramas, está en [Ciclo de gobernanza v3](./governance-loop.md).

<details>
<summary>Ver el recorrido completo con los comandos v3</summary>


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

</details>
