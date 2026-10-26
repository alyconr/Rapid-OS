# Integración con OpenAI Codex / CLI

Guía técnica para gobernar tareas asistidas por modelos de código en línea de comandos y entornos headless mediante **RAPID OS v3**.

---

## 1. Qué es y cómo encaja con RAPID OS

OpenAI Codex y sus herramientas de línea de comandos asociadas permiten la generación y transformación automatizada de código en entornos automatizados o terminales de desarrollo.

**Encaje con RAPID OS:**
RAPID OS actúa como la capa determinista de gobernanza que define qué cambios están autorizados mediante una especificación (`Spec`) y un contrato (`ExecutionContract`). Codex actúa como el motor de codificación externa que produce los parches y ejecuta comandos.

---

## 2. Configuración en RAPID OS

RAPID OS incluye el perfil integrado `codex`:

```bash
rapid harness show codex
```

Salida declarada:
- `context.consume`: `supported`
- `repository.read`: `supported`
- `workspace.current`: `supported`
- `repository.write`, `shell.execute`, `tests.execute`: `unknown` (declarados como sujetos a los permisos del entorno local).

Para sobreescribir estas capacidades y declarar que tu entorno local autoriza la ejecución de pruebas y modificación de archivos, puedes inicializar un perfil de proyecto en `.rapid-os/harnesses/codex.json`.

---

## 3. Configuración del Usuario en Codex

1. Configura tu entorno de ejecución con las variables y claves de API correspondientes según la documentación oficial de OpenAI.
2. Asegura que la herramienta tenga permisos de lectura y escritura en el repositorio.
3. Configura el sandbox de ejecución local para permitir que la herramienta corra `python -m unittest`.

---

## Flujo principal: shortcuts

La forma recomendada de trabajar con Codex es con los shortcuts de Rapid OS. Los 9 shortcuts, el bucle que siguen, la aprobación humana y los errores frecuentes están en la [guía de shortcuts](../guides/shortcuts.md).

### Instalación

```bash
rapid init --shortcuts                                # al inicializar el proyecto
rapid shortcuts install --harness codex               # en un proyecto ya inicializado
```

Genera `.agents/skills/rapid-*/SKILL.md` (los 9 shortcuts; [documentación de skills de Codex](https://learn.chatgpt.com/docs/build-skills)). Es la misma carpeta que usa Antigravity: si seleccionas ambos, se escribe una sola vez. Tras actualizar Rapid OS, vuelve a ejecutar `rapid shortcuts install`.

### Invocación: Codex CLI y extensión de IDE

Los shortcuts son *skills* de Codex. Según la [documentación oficial de skills](https://learn.chatgpt.com/docs/build-skills): "In Codex CLI or the IDE extension, run `/skills` or type `$` to mention a skill". Por eso la forma que funciona en todas las variantes de Codex es `$`:

```text
$rapid-init API de facturación para pymes, en Python
$rapid-feature añadir exportación CSV al informe mensual
```

| Variante de Codex | Cómo invocar un shortcut | Qué muestra `/` |
| --- | --- | --- |
| **Codex CLI** (`codex` en una terminal) | `$rapid-<modo>`, o elegirlo desde `/skills` | Solo los comandos propios de Codex (`/model`, `/skills`…). **`/rapid-*` no aparece**: escribe `$`. |
| **Extensión de Codex para VS Code** | `$rapid-<modo>` o `/skills`; en la extensión también aparecen al escribir `/` | Comandos de Codex y, en la extensión, los skills. |

Las dos variantes leen la misma carpeta (`.agents/skills/` del proyecto, y `~/.agents/skills/` si instalaste con `--global`), así que no hace falta instalar nada distinto para cada una. Si `$` no muestra los `rapid-*`:

1. Abre Codex desde la raíz del proyecto (Codex busca `.agents/skills` desde el directorio de trabajo hacia la raíz del repositorio).
2. Comprueba que existan: `rapid shortcuts list --harness codex`.
3. Comprueba que `rapid` esté en el `PATH` de esa terminal (`rapid --version`): el skill le pide a Codex ejecutarlo.
4. Si actualizaste Rapid OS o los instalaste con Codex abierto, reinicia la sesión de Codex.

`$rapid-approve` **no aprueba**: muestra los gates pendientes y la evidencia, y te da el comando para tu terminal. `rapid approve` exige una terminal interactiva tuya y falla con `RAPID1310` si lo lanza un agente. El archivo `AGENTS.md` generado por `rapid init` sigue aportando el contexto del proyecto.

---

## Modo avanzado (comandos v3)

Los comandos v3 (`rapid spec`, `rapid run`, `rapid evidence`, `rapid eval`…) siguen disponibles para CI, depuración y auditoría, y tampoco hace falta usarlos a mano en el día a día. Las secciones 4 a 8 conservan el flujo manual completo.

## 4. Entrega del Context Bundle y Spec

RAPID OS compila un paquete de contexto optimizado:

```bash
rapid context --manifest
```

Entrega a la herramienta:
- La especificación activa (`.rapid-os/specs/<spec-id>/spec.json`).
- El manifiesto de contexto compilado (`.rapid-os/context/manifest.json`).
- Las instrucciones del contrato de ejecución (`.rapid-os/runs/<run-id>/contract.json`).

---

## 5. Respeto del Execution Contract y Herramientas Externas

El harness debe ceñirse a:
- La lista de tareas inmutables (`T001`, `T002`, ...).
- Los archivos autorizados en el alcance (`paths`).
- Las compuertas declaradas en la política.

Antes de comenzar la ejecución externa, captura el log de baseline como artefacto (`base.log`), registra la evidencia de baseline (conforme a [`evidence_baseline.json`](../tutorials/first-governed-project.md#1-registrar-evidencia-de-baseline-y-acreditar-gatebaseline)) y reconoce `gate.baseline`:
```bash
python -m unittest discover -s tests -t . > base.log 2>&1
rapid evidence add --run <run-id> --input evidence_baseline.json
rapid run gate <run-id> gate.baseline acknowledged
rapid run status <run-id> active
rapid run task <run-id> T001 in_progress
```

---

## 6. Registro de Resultados y Evidencia

Una vez que Codex aplique los cambios y ejecute las pruebas en la terminal externa (consulta la definición canónica de cada evidencia en el [laboratorio Bajo el capó](../tutorials/first-governed-project.md#7-evidence-collection)):

1. Ingerir evidencia de los archivos modificados ([`evidence_files.json`](../tutorials/first-governed-project.md#3-registrar-evidencia-de-cambios-en-el-código-file_change)):
```bash
rapid evidence add --run <run-id> --input evidence_files.json
```

2. Ingerir evidencia del resultado de las pruebas con log adjunto ([`evidence_tests.json`](../tutorials/first-governed-project.md#4-registrar-evidencia-de-pruebas-aprobadas-test_result)):
```bash
rapid evidence add --run <run-id> --input evidence_tests.json
```

3. Ingerir evidencia de espacio de trabajo ([`evidence_workspace.json`](../tutorials/first-governed-project.md#5-registrar-evidencia-de-espacio-de-trabajo-workspace)) y revisión final ([`evidence_review.json`](../tutorials/first-governed-project.md#6-registrar-evidencia-de-revisión-final-review)):
```bash
rapid evidence add --run <run-id> --input evidence_workspace.json
rapid evidence add --run <run-id> --input evidence_review.json
```

4. Actualizar el estado del run:
```bash
rapid run gate <run-id> gate.tests acknowledged
rapid run gate <run-id> gate.final-verification acknowledged
rapid run task <run-id> T001 done
rapid run status <run-id> finished
```

---

## 7. Evaluación Determinista

Evalúa la validez de la ejecución:

```bash
rapid eval run --run <run-id> --write --require-pass
```

---

## Windows: sandbox y git

**Por qué pasa.** En Windows, Codex ejecuta los comandos dentro de un sandbox. En su modo por defecto (`elevated`) los comandos corren con usuarios de sandbox dedicados y de menos privilegios ([Windows sandbox](https://learn.chatgpt.com/docs/windows/windows-sandbox.md)). git, por su parte, se niega a leer una carpeta cuyo dueño no es el usuario que lo ejecuta (`detected dubious ownership`). Esa página de Codex describe el sandbox pero no menciona git: la relación entre ambos es esta, observada en la práctica. Resultado: lo que corre el harness y lo que corres tú a mano en tu terminal ven la misma carpeta con distinto dueño.

**Lo que Rapid OS ya resuelve.** Todos los comandos git de Rapid OS pasan por una sola puerta (`rapid_os/orchestration/git.py`) que añade `-c safe.directory=<raíz del proyecto>` y `-c core.fsmonitor=false`. Confía solo en la raíz del proyecto, nunca en `*`, y desactiva el fsmonitor (lo que permite que un repositorio ajeno ejecute programas al leerlo). Por eso `rapid setup finish`, `rapid start` y `rapid finish` funcionan dentro del sandbox sin pedirte nada. `safe.directory` por línea de comandos se respeta desde git 2.38; en versiones anteriores git lo ignora y Rapid OS lo trata como `untrusted` (`RAPID1416`).

**Lo único que te toca a ti.** Para usar git tú mismo en esa carpeta (`git status`, `git commit`...), el git de tu usuario necesita la excepción. Rapid OS lo detecta (pregunta a git como lo harías tú, sin esos `-c`) y lo entrega como una acción en `person_actions` de `rapid setup finish`, `rapid setup next --json` (`kind: done`) y `rapid doctor`, y el shortcut te la muestra con su explicación:

```bash
git config --global --add safe.directory C:/ruta/de/tu/proyecto
```

La ruta es la raíz del proyecto con `/`. No necesita permisos de administrador (solo lo lee tu usuario) y nunca se usa `--system` ni `*`. Ejecútalo en tu propia terminal: el agente no debe hacerlo por ti.

**Alternativa: `unelevated`.** Si prefieres que los comandos corran con tu propio usuario, Codex permite el sandbox `unelevated` en `config.toml`:

```toml
[windows]
sandbox = "unelevated"
```

Tiene un costo de aislamiento: según la misma página es un modo heredado (*legacy fallback*) que usa un token restringido derivado de tu usuario en lugar del límite de usuario de sandbox de `elevated`, con un aislamiento de red más débil (controles a nivel de entorno en vez de la regla de firewall dedicada) y sin soporte para rutas de lectura denegadas. Rapid OS funciona igual con cualquiera de los dos.

## 8. Problemas Frecuentes

- **El harness intenta modificar rutas fuera de scope:** La evaluación detectará discrepancias si la evidencia no coincide con las rutas del contrato.
- **Falta de evidencia de pruebas:** No intentes cerrar `gate.tests` sin una evidencia válida de `test_result` con `exit_code: 0`.
