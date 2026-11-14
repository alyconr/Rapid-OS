# Troubleshooting en Laboratorios y Tutoriales

Guía de resolución de problemas e incidencias comunes al ejecutar los laboratorios prácticos de **RAPID OS v3**.

---

## Ruta con shortcuts

Errores típicos al trabajar con `/rapid-*`. La guía completa está en [Shortcuts por harness](../guides/shortcuts.md) y el catálogo en [Diagnósticos](./diagnostics.md).

### `RAPID1301`: falta `test_command`
- **Causa:** `.rapid-os/config.json` no tiene `test_command` (o está vacío), así que `rapid check` no sabe qué comando de tests ejecutar. Es un aviso.
- **Solución:** `rapid init --test-command "python -m unittest discover"`, o define `"test_command": ["python", "-m", "unittest", "discover"]` (lista argv) en `.rapid-os/config.json`.

### `RAPID1307`: no hay un run activo
- **Causa:** `rapid check`, `task`, `finish`… se ejecutaron sin `.rapid-os/session.json` (no se hizo `rapid start`, o el run terminó o se abortó).
- **Solución:** inicia un run con el shortcut del modo (`/rapid-feature <objetivo>`) o con `rapid start <modo>`.

### `RAPID1308`: ya hay un run activo
- **Causa:** ejecutaste `rapid start` (o un shortcut de modo) mientras hay un run no terminal en `.rapid-os/session.json`.
- **Solución:** continúa con `rapid next`, usa `rapid start <modo> --resume`, o abandona el run con `rapid abort`.

### `RAPID1310`: `rapid approve` se niega
- **Causa:** no hay terminal interactiva, la sesión es de un agente (`CLAUDE_CODE_CHILD_SESSION=1`) o un ancestro del proceso es Claude Code (por ejemplo, el modo `!`).
- **Solución:** ejecuta `rapid approve <gate>` tú, en tu propia terminal (sirve la terminal integrada del editor). Un shortcut nunca aprueba gates humanos.

### `RAPID1321`: aviso de carpetas solapadas
- **Causa:** seleccionaste Cursor o VS Code junto con Claude, Codex o Antigravity, y el mismo `/rapid-*` queda en dos carpetas que esa herramienta lee.
- **Solución:** es solo un aviso. Para evitarlo, instala un único harness que cubra ambas herramientas; ver [Si combinas harnesses](../guides/shortcuts.md#si-combinas-harnesses).

### `RAPID1415`: la spec perdió las tildes (`rapid start`, `rapid spec create`, `rapid spec revise`)
- **Causa:** la spec pasó por una tubería de Windows PowerShell 5.1 (`$spec | rapid start feature --spec-file -`), que la convierte a ASCII: `creación` llega como `creaci?n` y el id de la spec saldría `reserva-p-blica`. El mensaje dice el campo y la palabra. No se escribió nada: ni spec, ni revisión, ni run.
- **Solución:** escribe la spec en un archivo temporal UTF-8 fuera de `.rapid-os` y pasa la ruta: `$spec | Set-Content -Encoding utf8 $env:TEMP\rapid-spec.json` y después `rapid start <modo> --spec-file $env:TEMP\rapid-spec.json`. No la vuelvas a mandar por tubería. En bash o zsh, stdin con un heredoc sigue bien. Ver [Enviar specs y documentos desde PowerShell](../installation/windows.md#text-from-powershell).

### `rapid check` en Windows: el log no tiene la salida y los tests no se cuentan
- **Causa:** hasta 3.2.0rc3, `rapid check` decodificaba la salida del comando con la página de códigos de Windows (cp1252). El UTF-8 que imprime Vitest (`✓`, `⎯`, `❯`) rompía el lector con `UnicodeDecodeError: 'charmap' codec can't decode byte 0x9d`: el log quedaba sin la salida y el resumen no se contaba. `rapid task done` usa el mismo check.
- **Solución:** actualiza Rapid OS; ahora la salida se lee como UTF-8 y ya no hace falta `PYTHONUTF8=1`. Después vuelve a ejecutar el check: `rapid check -- <comando>`.

### `RAPID1440`: el check no contó para `gate.tests`
- **Causa:** el check de `gate.tests` o `gate.baseline` ejecutó otro comando que el `test_command` configurado (un `python -c "print(...)"`, un script de `%TEMP%`, una copia del comando citada a mano). Rapid OS lo registró como un check normal, sin el gate: no puede probar qué se ejecutó.
- **Solución:** ejecuta `rapid check --gate gate.tests` sin comando; Rapid OS ejecuta él mismo el `test_command`, sin shell, así que no hay nada que citar en PowerShell. Si de verdad otro comando debe verificar el gate, solo la persona puede aceptarlo, en su terminal: `rapid check --gate gate.tests --accept-test-command "<motivo>" -- <comando>` pregunta `[s/N]`.

### Un refactor compara con su baseline solo los tests del frontend
- **Causa:** hasta 3.2.0rc3, con un comando de test combinado (backend y frontend) `rapid check` contaba solo el último resumen de la salida: `gate.tests` registraba `2 passed` (Angular) y no los 31 tests del backend.
- **Solución:** actualiza Rapid OS. `rapid check --gate gate.tests` ejecuta cada componente del comando combinado, suma los conteos y guarda el desglose (`components`). Vuelve a tomar la baseline si se registró antes de actualizar.

### `RAPID1441`: `rapid finish` no da PASS porque el run no cambió nada
- **Causa:** el árbol fuera de `.rapid-os/` es el del punto de partida del run: el cambio se deshizo (un archivo devuelto a su versión anterior) después de que un `rapid finish` anterior registrara `file_change`. Un run que nunca hizo el cambio termina `UNVERIFIED`, con su motivo. Un run de feature, bugfix, refactor o hardening no termina en PASS sin el cambio que declara.
- **Solución:** haz el cambio, ejecuta lo que da `rapid next` (el check de tests), aprueba de nuevo y repite `rapid finish`; o `rapid abort` si el run ya no hace falta. `RAPID1442` es solo un aviso: el cambio no toca ningún `affected_path` de la spec, así que comprueba que sea el correcto.

---

### El workflow de seguridad sale en verde pero dice «Nada que auditar»

- **Causa:** el job de dependencias no encontró código de su lenguaje en la carpeta del componente (`backend/`, `frontend/`, o la raíz en un proyecto de una carpeta): la carpeta todavía no existe o no tiene archivos de código. No se auditó nada. Hasta 3.2.0rc3 el job buscaba el manifiesto y el lockfile solo en la raíz, así que con `fullstack-separated` decía «Sin dependencias declaradas todavía» o «Sin lockfile todavía» y pasaba aunque `backend/` y `frontend/` los tenían.
- **Solución:** ninguna mientras el repositorio es nuevo. En un proyecto existente ejecuta `rapid doctor`: `RAPID1443` sugiere `rapid setup ci --regenerate`, que pone el workflow al día (uno editado no se pisa: el nuevo queda al lado como `.new`).

### semgrep bloquea `pnpm-workspace.yaml` (o `.npmrc`, `.yarnrc.yml`, `pyproject.toml`, `Gemfile`)

- **Causa:** `p/owasp-top-ten` incluye reglas sobre la configuración del gestor de paquetes, como `pnpm-missing-minimum-release-age`, `pnpm-trust-policy` y `pnpm-block-exotic-sub-dependencies`. Un proyecto creado sin esos ajustes falla el job de semgrep en su primer push. Hasta 3.2.0rc3 bandit corría después de semgrep en el mismo job, así que no llegaba a correr.
- **Solución:** añade los ajustes de tu gestor de paquetes (tabla en [la base de seguridad](../concepts/security-baseline.md#ajustes-del-gestor-de-paquetes-que-comprueba-semgrep)); con pnpm, `minimumReleaseAge: 10080`, `trustPolicy: no-downgrade` y `blockExoticSubdeps: true` en `pnpm-workspace.yaml`. Después ejecuta `rapid setup ci --regenerate` para que cada escáner tenga su propio job.

### El job de dependencias falla: «tiene código ... pero no tiene ...»

- **Causa:** la carpeta del componente tiene archivos de código pero no tiene manifiesto o lockfile, por ejemplo `frontend tiene package.json pero ningún lockfile`. Sin el lockfile la auditoría no sabe qué versiones se instalan.
- **Solución:** instala las dependencias en esa carpeta y haz commit del lockfile (`pnpm-lock.yaml`, `package-lock.json`, `yarn.lock`, `uv.lock`, `Cargo.lock`, `Gemfile.lock`, `composer.lock`), o decláralas (`pyproject.toml`, `requirements.txt`, `go.mod`).

## 1. Problemas de Inicialización y Scanner

### Error: `RAPID1001` (Project Model Error) o facts incompletos
- **Causa:** El scanner se ejecutó antes de que existieran archivos con extensiones reconocidas o directorios de prueba.
- **Solución:** Crea al menos un archivo `.py` y el directorio `tests/`, y vuelve a ejecutar:
  ```bash
  rapid scan --write
  ```

---

## 2. Problemas con Specs y Context Bundles

### Error: `RAPID1010` (Spec Not Ready) al intentar crear un Run
- **Causa:** Se intentó crear un `ExecutionContract` vinculando una especificación que está en estado `draft` o `in_progress`.
- **Solución:** Un Run solo puede crearse a partir de una Spec en estado `ready`:
  ```bash
  rapid spec update <spec-id> --status ready
  ```

---

## 3. Problemas con Estados de Run y Transición de Tareas

### Error: `InvalidRunStateTransitionError`
- **Causa:** Se intentó modificar una tarea o compuerta en un Run cuyo estado es `prepared` o `finished`.
- **Solución:** Transiciona el Run al estado `active` antes de modificar tareas:
  ```bash
  rapid run status <run-id> active
  ```

---

## 4. Problemas con Evidencias (`rapid evidence add`)

### Error: `RAPID1203` (Evidence Binding Mismatch)
- **Causa:** El hash de estado (`state_digest`) o la revisión (`state_revision`) no coinciden con la versión activa del Run.
- **Solución:** Si estás preparando el JSON manualmente, asegúrate de utilizar los valores exactos reportados por `rapid run show <run-id> --json`.

### Error: `RAPID1206` (Invalid Evidence Payload)
- **Causa:** El objeto `payload` contiene campos adicionales o faltantes según el schema canónico de ese `EvidenceKind`.
- **Solución:** Consulta la tabla de esquemas en [Cookbook: Evidence Engine](../cookbooks/evidence-engine.md). Por ejemplo, para `test_result`, los campos obligatorios son exactamente: `suite`, `exit_code`, `passed`, `failed`, `skipped`.

---

## 5. Problemas con la Evaluación Conductual (`rapid eval run`)

### Veredicto: `unverified`
- **Causa:** Uno o más gates obligatorios quedaron en estado `pending` en el `RunState`.
- **Solución:** Registra la evidencia pertinente y reconoce la compuerta:
  ```bash
  rapid run gate <run-id> <gate-id> acknowledged
  ```

### Veredicto: `fail`
- **Causa:** Se detectó evidencia contradictoria (ejemplo: un `test_result` con `exit_code != 0` o un `file_change` que tocó rutas no autorizadas en el contrato).
- **Solución:** Corrige el defecto en el código, re-ejecuta la suite de pruebas y registra una nueva evidencia con el resultado correcto antes de re-evaluar.
