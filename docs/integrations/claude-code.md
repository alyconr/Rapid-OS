# Integración con Anthropic Claude Code

Guía técnica para gobernar flujos interactivos y de terminal con **Claude Code** utilizando **RAPID OS v3**.

---

## 1. Qué es Claude Code y cómo encaja con RAPID OS

Claude Code es una herramienta de desarrollo en línea de comandos de Anthropic diseñada para operar directamente sobre bases de código mediante herramientas de edición, búsqueda y ejecución de comandos.

**Encaje con RAPID OS:**
Claude Code opera como el agente ejecutor externo. RAPID OS opera como el marco de gobernanza, definiendo la especificación previa, controlando el riesgo arquitectónico y evaluando mediante evidencia determinista que todo lo prometido se haya cumplido antes de dar por buena la tarea.

---

## 2. Configuración en RAPID OS

RAPID OS incluye el identificador de perfil `claude`:

```bash
rapid harness show claude
```

Perfil declarativo:
- `context.consume`: `supported`
- `repository.read`: `supported`
- `workspace.current`: `supported`
- Otras capacidades: marcadas como `unknown` hasta que el entorno local las configure explícitamente en el proyecto.

---

## 3. Configuración en Claude Code

1. Inicia sesión en Claude Code siguiendo las guías oficiales (`claude login`).
2. Concede permisos para ejecutar tests locales y editar archivos según las políticas de tu equipo.
3. Asegura que Claude Code lea el archivo `.rapid-os/standards/` para alinearse con los estándares arquitectónicos del proyecto.

---

## 4. Flujo de Trabajo Gobernado

1. **Crear Spec y Run en RAPID OS:**
```bash
rapid spec create --id spec-feature --title "Nueva funcionalidad" --mode feature --task "T001: Implementar funcionalidad" --status ready
rapid context --manifest
rapid run create --spec spec-feature --harness claude
```

2. **Verificar y Registrar Baseline:**
Ejecuta la suite base de pruebas guardando el log auténtico como artefacto (`base.log`), registra la evidencia de baseline (conforme a la estructura de [`evidence_baseline.json`](../tutorials/first-governed-project.md#1-registrar-evidencia-de-baseline-y-acreditar-gatebaseline)) y reconoce la compuerta antes de activar el run:
```bash
python -m unittest discover -s tests -t . > base.log 2>&1
rapid evidence add --run <run-id> --input evidence_baseline.json
rapid run gate <run-id> gate.baseline acknowledged
```

3. **Instruir a Claude Code:**
Pide a Claude Code en la terminal:
> *"Lee la especificación en `.rapid-os/specs/spec-feature/spec.json` y el contrato en `.rapid-os/runs/<run-id>/contract.json`. Implementa los cambios necesarios y corre la suite de pruebas."*

4. **Ejecución Externa:**
Claude Code edita los archivos y corre `python -m unittest`.

5. **Captura e Ingesta de Evidencias:**
El desarrollador o el propio Claude Code invoca el CLI de RAPID OS para registrar el avance (ver la estructura canónica de cada archivo en el [Tutorial del Primer Proyecto Gobernado](../tutorials/first-governed-project.md#7-evidence-collection)):
- [`evidence_files.json`](../tutorials/first-governed-project.md#3-registrar-evidencia-de-cambios-en-el-código-file_change): evidencia de modificación de archivos (`file_change`).
- [`evidence_tests.json`](../tutorials/first-governed-project.md#4-registrar-evidencia-de-pruebas-aprobadas-test_result): resultados de pruebas aprobadas con su archivo de log adjunto (`test_result`).
- [`evidence_workspace.json`](../tutorials/first-governed-project.md#5-registrar-evidencia-de-espacio-de-trabajo-workspace): verificación de espacio de trabajo actual (`workspace`).
- [`evidence_review.json`](../tutorials/first-governed-project.md#6-registrar-evidencia-de-revisión-final-review): revisión contractual aprobada (`review`).

```bash
rapid run status <run-id> active
rapid run task <run-id> T001 in_progress
rapid evidence add --run <run-id> --input evidence_files.json
rapid evidence add --run <run-id> --input evidence_tests.json
rapid evidence add --run <run-id> --input evidence_workspace.json
rapid evidence add --run <run-id> --input evidence_review.json
rapid run gate <run-id> gate.tests acknowledged
rapid run gate <run-id> gate.final-verification acknowledged
rapid run task <run-id> T001 done
rapid run status <run-id> finished
```

6. **Evaluación:**
```bash
rapid eval run --run <run-id> --write --require-pass
```

---

## 5. Problemas Frecuentes

- **Claude Code edita sin correr pruebas:** La evaluación marcará `fail` o `unverified` si no se aporta evidencia con `test_result` válido.
- **Rutas no canónicas:** Las rutas en los payloads de evidencia deben ser rutas relativas POSIX (ej. `src/app.py`, no rutas absolutas con `C:\`).

---

## 6. Hooks de Claude Code (refuerzo opcional del bucle)

Los hooks de Claude Code ejecutan un comando en puntos del ciclo del agente ([documentación oficial](https://code.claude.com/docs/en/hooks)). Rapid OS aporta dos, `rapid hook stop` y `rapid hook pre-tool`, para que el agente no se detenga a mitad de un run, no lance comandos reservados a la persona y no edite `.rapid-os/`.

> Los hooks los ejecuta Claude Code, no Rapid OS: Rapid OS sigue sin invocar agentes. Solo responden con una parada bloqueada o una herramienta denegada.

### Instalación

```bash
rapid shortcuts install --harness claude --hooks
rapid shortcuts install --harness claude --hooks --dry-run --json   # ver qué cambiaría
rapid shortcuts remove --harness claude --hooks                      # quita solo lo propio
```

Fusiona en `.claude/settings.json` del proyecto un grupo `Stop` y un grupo `PreToolUse` (matcher `Bash|PowerShell|Write|Edit|MultiEdit|NotebookEdit`) cuyo comando es `rapid` con los argumentos `hook stop` / `hook pre-tool` (forma *exec* de Claude Code: sin shell, igual en Linux, macOS y Windows). No toca otras claves ni los hooks del usuario, hace una copia `.bak` y es idempotente. `rapid init --shortcuts` **no** instala hooks: hay que pedirlos con `--hooks` (en `rapid init` o en `rapid shortcuts install`).

`rapid` debe estar en el `PATH` del equipo donde corre Claude Code (por ejemplo con `pipx install rapid-os`). Si no se resuelve, Claude Code lo trata como un error no bloqueante y el refuerzo deja de actuar; `rapid doctor` lo avisa con `RAPID1339`.

### Qué hace `Stop`

Bloquea la parada con la razón (`instructions` más el comando exacto) mientras `rapid next` proponga `run_baseline`, `activate`, `implement_task`, `verify` o `finish`. No bloquea en `author_spec`, `await_human_approval`, `blocked` (tampoco cuando se propone `rapid abort` tras un `--reject`), `done` ni sin sesión.

Guarda de bucle: como máximo `hooks.max_stop_blocks` bloqueos consecutivos (3 por defecto) por sesión y acción; configurable en `.rapid-os/config.json`:

```json
{ "hooks": { "max_stop_blocks": 3 } }
```

Claude Code aplica además su propio tope de continuaciones consecutivas.

### Qué hace `PreToolUse`

| Acción del agente | Resultado |
| :--- | :--- |
| `rapid approve …`, `rapid run gate …`, `rapid run status …`, `rapid evidence add …`, `rapid spec status …`, `rapid abort` | Denegado. Para `approve` el motivo da el comando exacto que la persona debe teclear en su terminal. |
| `rapid status`, `next`, `check`, `task`, `attach`, `finish`, `start` | Permitido. |
| `Write`, `Edit`, `MultiEdit`, `NotebookEdit` sobre `.rapid-os/` | Denegado. |
| Comandos de shell que escriben en `.rapid-os/` (`>`, `>>`, `tee`, `cp`, `mv`, `rm`, `sed -i`, `find -delete`, …) | Denegado. |
| Quitar o redefinir `CLAUDE_CODE_CHILD_SESSION` o `CLAUDECODE` (`env -u`, `env --unset`, `env -i`, `unset`, prefijos `VAR=` o `VAR=0`, `export`, `Remove-Item Env:`, `$env:VAR = …`) | Denegado, con un motivo que remite a `rapid next`: esas variables son lo que hace que `rapid approve` se niegue a correr dentro de una sesión de agente. |
| `rapid approve --help` (o `-h`) | Permitido: solo imprime la ayuda. |

También se detectan `python -m rapid_os …`, `python rapid.py …`, rutas absolutas al ejecutable, prefijos de entorno (`VAR=1 rapid …`), `sudo`/`env`/`timeout`, comandos que ejecutan una cadena (`bash -c`, `bash -xc`, `script -qec`, `su -c`, `eval`) y `find … -exec`, además de comandos encadenados o anidados (`;`, `&&`, `||`, `|`, `$(…)`, comillas invertidas). `script` merece mención aparte: da una terminal al comando, así que junto con `env -u CLAUDE_CODE_CHILD_SESSION` permitiría esquivar la comprobación de TTY de `rapid approve`; por eso se analiza igual que `bash -c` y se deniega quitar esas variables.

> **Defensa en profundidad en `rapid approve`.** Los hooks no son la única barrera: `rapid approve` rechaza (`RAPID1310`) cuando falta un TTY, cuando `CLAUDE_CODE_CHILD_SESSION` vale `1` y, además, cuando algún proceso ancestro es el binario `claude` (se recorre la cadena de procesos padre con la biblioteca estándar). La detección por ascendencia es de mejor esfuerzo: un proceso que se desacopla de su padre (doble fork, `setsid`, `nohup … &`) pasa a colgar de `init` y deja de tener a `claude` como ancestro; junto al `claude.exe` renombrado y el pid reutilizado de un padre ya muerto, es un límite conocido. La regla sigue siendo que una persona apruebe en su propia terminal. Si la ascendencia no se puede leer, no se rechaza por ello y `rapid doctor` lo avisa (`RAPID1319`). Una persona que aprueba en su propia terminal no se ve afectada.
>
> **La detección de comandos es de mejor esfuerzo.** Analiza la línea de comandos que ve el hook; no puede impedir que un agente decidido construya el comando en tiempo de ejecución ni que escriba en `.rapid-os/` con un lenguaje de programación. Los hooks refuerzan el bucle, no sustituyen la regla de que una persona apruebe en su terminal (`rapid approve` exige TTY y falla con `RAPID1310`).

### Worktrees y errores

- La resolución del proyecto sube desde el `cwd` del payload hasta el primer `.rapid-os/`. Si el `cwd` es el worktree de `rapid start --worktree`, se usa el ledger del repositorio principal (el que guarda `workspace_path` en `session.json`).
- Sin proyecto: sin salida y exit 0.
- Cualquier error interno, un stdin que no es JSON o un `.rapid-os/` corrupto: sin salida, exit 0 y una línea en `.rapid-os/scratch/hooks.log`. Un hook nunca debe romper al agente.
