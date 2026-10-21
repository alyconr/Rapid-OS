---
title: Catálogo de Diagnósticos RAPIDxxx
description: Referencia exhaustiva de códigos de diagnóstico de RAPID OS, causas comunes y acciones de remediación.
---

# Catálogo de Diagnósticos RAPIDxxx

Cuando ejecutas `rapid validate`, `rapid scan`, o comandos de gobernanza, RAPID OS emite diagnósticos deterministas identificados por códigos únicos. Esta guía documenta el significado de cada código y cómo resolverlo.

---

## 1. Configuración de Proyecto y Plantillas (`RAPID100–RAPID123`)

| Código | Severidad | Causa común | Acción de remediación |
| :--- | :--- | :--- | :--- |
| `RAPID100` | INFO | Configuración del proyecto válida y cargada. | Informativo. |
| `RAPID101` | ERROR | Archivo `.rapid-os/config.json` no encontrado. | Ejecutar `rapid init` para inicializar el proyecto. |
| `RAPID102` | ERROR | Error de sintaxis JSON en `.rapid-os/config.json`. | Corregir la sintaxis JSON o restaurar desde el archivo de backup `.bak`. |
| `RAPID103` | ERROR | Versión de esquema incompatible o inválida. | Verificar que `schema_version` coincida con la versión soportada. |
| `RAPID104` | ERROR | Campos requeridos ausentes en `config.json`. | Regenerar la configuración con `rapid init`. |
| `RAPID120` | WARNING | Archivos de plantilla faltantes en `templates/`. | Ejecutar `rapid doctor` para verificar la disponibilidad de plantillas integradas. |
| `RAPID121` | ERROR | Plantilla requerida dañada o ilegible. | Reinstalar RAPID OS o restaurar la carpeta `templates/`. |

---

## 2. Fase 1 — Project Intelligence (`RAPID600–RAPID604`)

| Código | Severidad | Causa común | Acción de remediación |
| :--- | :--- | :--- | :--- |
| `RAPID600` | INFO | Snapshot `.rapid-os/project.json` válido. | Informativo. |
| `RAPID601` | ERROR | Sintaxis JSON corrupta en `project.json`. | Ejecutar `rapid scan --write` para regenerar el snapshot. |
| `RAPID602` | ERROR | Permisos de lectura insuficientes en `project.json`. | Ajustar los permisos del sistema de archivos. |
| `RAPID603` | ERROR | Versión de esquema de snapshot no soportada. | Ejecutar `rapid scan --write` para actualizar al schema version 1. |
| `RAPID604` | ERROR | Hecho (`ProjectFact`) o evidencia corrupta en snapshot. | Regenerar el snapshot con `rapid scan --write`. |

---

## 3. Fase 2 — Context Compiler (`RAPID700–RAPID705`)

| Código | Severidad | Causa común | Acción de remediación |
| :--- | :--- | :--- | :--- |
| `RAPID700` | INFO | Compilación de contexto exitosa. | Informativo. |
| `RAPID701` | ERROR | Fuente de contexto requerida no encontrada. | Comprobar que los estándares (`.rapid-os/standards/`) existan o inicializarlos con `rapid init`. |
| `RAPID702` | ERROR | El presupuesto de tokens/caracteres fue excedido por fuentes obligatorias. | Aumentar el límite con `--max-chars <n>` o reducir las fuentes requeridas en `.rapid-os/config.json`. |
| `RAPID703` | WARNING | Conflicto detectado entre fuentes de contexto seleccionadas. | Revisar el manifest con `rapid context --manifest` y resolver reglas contradictorias. |
| `RAPID704` | ERROR | Snapshot o fuente inválida para el compilador. | Ejecutar `rapid scan --write` y verificar integridad de archivos. |
| `RAPID705` | ERROR | Petición de contexto inválida (harness o modo no reconocido). | Verificar que el modo sea `{feature,bugfix,refactor,hardening,research,general}` y el ID de harness válido. |

---

## 4. Fase 3 — Spec Registry (`RAPID800–RAPID809`)

| Código | Severidad | Causa común | Acción de remediación |
| :--- | :--- | :--- | :--- |
| `RAPID800` | INFO | Registro de especificaciones íntegro. | Informativo. |
| `RAPID801` | ERROR | Archivo `spec.json` con esquema o contenido inválido. | Revisar la estructura en `.rapid-os/specs/<id>/spec.json`. |
| `RAPID802` | ERROR | Historial de revisiones ausente o discontinuo. | Verificar que existan las carpetas `rev_0001`, `rev_0002` de forma secuencial. |
| `RAPID803` | ERROR | Archivo `revision.json` corrupto. | Restaurar o regenerar la revisión de la spec con `rapid spec revise`. |
| `RAPID804` | WARNING | Drift detectado entre markdown de spec y metadatos JSON. | Sincronizar el contenido o reexportar con `rapid spec export-legacy`. |
| `RAPID805` | ERROR | Transición de ciclo de vida inválida en spec. | Las specs solo pueden transicionar entre `draft`, `ready` y `archived`. |
| `RAPID806` | ERROR | Conflicto o formato inválido en identificador de spec. | Usar IDs alfanuméricos con guiones (`^[a-z0-9][a-z0-9-]{0,62}$`). |
| `RAPID807` | ERROR | Spec referenciada no encontrada en el registro. | Verificar con `rapid spec list` que la spec exista antes de crear un run. |
| `RAPID808` | ERROR | Ruta insegura detectada (path traversal intentado). | Mantener todas las operaciones dentro del árbol de trabajo del proyecto. |
| `RAPID809` | WARNING | Revisión huérfana no enlazada en el historial. | Verificar el array `revisions` en `spec.json`. |

---

## 5. Fase 4 — Execution Policy y Runs (`RAPID1000–RAPID1014`)

| Código | Severidad | Causa común | Acción de remediación |
| :--- | :--- | :--- | :--- |
| `RAPID1000` | INFO | Registro de runs y contratos íntegros. | Informativo. |
| `RAPID1001` | ERROR | Archivo `run.json` corrupto o con schema inválido. | Revisar `.rapid-os/runs/<id>/run.json`. |
| `RAPID1002` | ERROR | Archivo `contract.json` corrupto o digest alterado. | No modificar `contract.json` manualmente; es inmutable. |
| `RAPID1003` | ERROR | Discrepancia entre la spec del contrato y la spec registrada. | Regenerar el run asegurando que la spec esté en estado `ready`. |
| `RAPID1004` | ERROR | Discrepancia en el digest del snapshot de contexto. | Volver a compilar contexto consistente antes de iniciar el run. |
| `RAPID1005` | ERROR | Archivo `.rapid-os/policy.json` inválido o duplicado en `policy init`. | Corregir la sintaxis de la política o remover el archivo antes de inicializar uno nuevo. |
| `RAPID1006` | ERROR | Violación de política o intento no autorizado de degradar riesgo. | Respetar la evaluación calculada por la política según las rutas y tags. |
| `RAPID1007` | ERROR | Identificador de run no encontrado o duplicado. | Usar identificadores únicos con `rapid run list`. |
| `RAPID1008` | ERROR | Ruta de run insegura fuera del directorio raíz. | Corregir rutas relativas. |
| `RAPID1009` | ERROR | Transición de estado de run inválida. | Respetar el ciclo de vida: `prepared` → `active` → `finished` / `failed` / `cancelled`. |
| `RAPID1010` | ERROR | Transición de tarea del contrato inválida. | Las tareas solo admiten: `in_progress`, `done`, `blocked`, `skipped`. |
| `RAPID1011` | WARNING | Hueco en el historial secuencial de estados de run. | Comprobar que los archivos `state_0001.json` sigan secuencia numérica continua. |
| `RAPID1012` | ERROR | Archivo `RunState` corrupto o digest discrepante. | Verificar la integridad de los estados en `.rapid-os/runs/<id>/states/`. |
| `RAPID1013` | ERROR | Intento de eximir (`waive`) una compuerta que no está en `waivable_gates`. | Modificar la política en `policy.json` o satisfacer la compuerta con evidencia. |
| `RAPID1014` | ERROR | Fallo en precondiciones de límite de fase al transicionar el run. | Completar las tareas requeridas antes de marcar el run como `finished`. |

---

## 6. Fase 5 — Harness Capability Registry (`RAPID1100–RAPID1112`)

| Código | Severidad | Causa común | Acción de remediación |
| :--- | :--- | :--- | :--- |
| `RAPID1100` | INFO | Perfiles de harness y lock íntegros. | Informativo. |
| `RAPID1101` | ERROR | Identificador de capability no canónico o inválido. | Usar IDs canónicos (ej. `shell.execute`, `repository.write`). |
| `RAPID1102` | ERROR | Perfil de harness (`HarnessProfile`) inválido. | Corregir `.rapid-os/harnesses/<id>.json` según el schema v1. |
| `RAPID1103` | ERROR | Perfil de harness no encontrado. | Inicializar el perfil con `rapid harness init <id>` o usar uno integrado. |
| `RAPID1104` | ERROR | Formato de harness ID inválido. | Usar nombres alfanuméricos en minúsculas con guiones. |
| `RAPID1106` | ERROR | Nivel de soporte inválido en perfil. | Usar `supported`, `unsupported`, o `unknown`. |
| `RAPID1107` | ERROR | Requerimiento de capability malformado en contrato. | Verificar la especificación de capacidades del contrato. |
| `RAPID1108` | ERROR | Objeto `CapabilityResolution` inválido. | Ejecutar nuevamente `rapid harness resolve --run <id>`. |
| `RAPID1109` | ERROR | Discrepancia en el digest de resolución. | Asegurarse de que el perfil y el contrato no hayan cambiado. |
| `RAPID1110` | ERROR | Harness incompatible o no resuelto bajo `--require-compatible`. | Seleccionar un harness compatible o ajustar los requerimientos del contrato. |
| `RAPID1111` | ERROR | Archivo `.rapid-os/capabilities.lock` ausente o corrupto bajo `--locked`. | Ejecutar `rapid harness lock` para generar el lock file. |
| `RAPID1112` | WARNING | El archivo lock está desactualizado respecto a los perfiles actuales. | Regenerar el lock con `rapid harness lock`. |

---

## 7. Fase 6 — Evidence Engine (`RAPID1200–RAPID1211`)

| Código | Severidad | Causa común | Acción de remediación |
| :--- | :--- | :--- | :--- |
| `RAPID1200` | INFO | Registros de evidencia íntegros y continuos. | Informativo. |
| `RAPID1201` | ERROR | ID de evidencia inválido. | El Evidence Engine gestiona IDs canónicos como `E001`, `E002`. |
| `RAPID1202` | ERROR | Schema de `RunEvidence` o `content_digest` inválido. | No alterar los archivos JSON de evidencia manualmente. |
| `RAPID1203` | ERROR | Desalineación en el binding del contrato, estado o productor. | Asegurarse de que la evidencia corresponda al run y estado activo. |
| `RAPID1204` | ERROR | Ruta insegura de evidencia fuera de `.rapid-os/evidence/`. | Mantener la estructura canónica. |
| `RAPID1205` | ERROR | Artefacto copiado faltante o con hash SHA-256 / tamaño discrepante. | Verificar que el artefacto no haya sido modificado tras su registro. |
| `RAPID1206` | ERROR | Payload JSON no satisface los campos mínimos para el `EvidenceKind`. | Consultar el [Cookbook de Evidencias](../cookbooks/evidence-engine.md) para el schema requerido. |
| `RAPID1207` | ERROR | La evidencia referencia una tarea, compuerta o capability inexistente. | Verificar que el `task_id` o `gate_id` esté en el contrato. |
| `RAPID1208` | ERROR | Hueco en la secuencia numérica de evidencias (ej. falta `E002` entre `E001` y `E003`). | Restaurar la secuencia inmutable. |
| `RAPID1209` | WARNING | Directorio huérfano de artefactos detectado tras una interrupción. | Ejecutar `rapid evidence verify` para auditar inconsistencias. |
| `RAPID1210` | ERROR | Archivo de evidencia referenciado no encontrado en disco. | Verificar la existencia de los archivos en `.rapid-os/evidence/<run-id>/`. |
| `RAPID1211` | ERROR | Intento de sobreescritura de un archivo de evidencia existente. | La evidencia es append-only; nuevos registros deben usar el siguiente ordinal. |

---

## 8. Fase 6 — Behavioral Evals (`RAPID1220–RAPID1229`)

| Código | Severidad | Causa común | Acción de remediación |
| :--- | :--- | :--- | :--- |
| `RAPID1220` | INFO | Reportes de evaluación de comportamiento íntegros. | Informativo. |
| `RAPID1221` | ERROR | Esquema de `EvaluationReport` inválido. | Regenerar el reporte con `rapid eval run --write`. |
| `RAPID1222` | ERROR | Discrepancia en el hash SHA-256 del reporte de evaluación. | No editar manualmente los archivos en `.rapid-os/evals/`. |
| `RAPID1223` | ERROR | Fallo en repetición semántica (replay mismatch). | El reporte almacenado difiere del cómputo determinista sobre la evidencia real. |
| `RAPID1224` | ERROR | Ruta de reporte insegura. | Mantener los reportes en `.rapid-os/evals/<run-id>/reports/`. |
| `RAPID1225` | ERROR | Veredicto `UNVERIFIED` bajo la bandera `--require-pass`. | Registrar evidencia observable para todas las compuertas reconocidas. |
| `RAPID1226` | ERROR | Veredicto `FAIL` bajo la bandera `--require-pass`. | Corregir las pruebas o requerimientos fallidos antes de evaluar. |
| `RAPID1227` | WARNING | El reporte almacenado precede al estado o evidencias más recientes. | Ejecutar `rapid eval run --write` para generar una nueva revisión de reporte. |
| `RAPID1228` | ERROR | Reporte de evaluación referenciado no encontrado. | Ejecutar `rapid eval run --write` para crearlo. |
| `RAPID1229` | ERROR | Intento de sobreescribir una revisión existente de reporte. | Las revisiones son append-only (`eval_report_0001.json`, `eval_report_0002.json`). |

---

## 9. Capa de Intención y Configuración (`RAPID1300–RAPID1339`)

| Código | Severidad | Causa común | Acción de remediación |
| :--- | :--- | :--- | :--- |
| `RAPID1300` | WARNING | No se especificó ni detectó un harness en el entorno/configuración. Se aplicó fallback a `cursor`. | Especificar `--harness <id>`, fijar `RAPID_HARNESS=<id>`, configurar `"default_harness"` o dejar un solo harness soportado en `"tools"` de `.rapid-os/config.json` (con varios, el aviso los lista). |
| `RAPID1301` | WARNING | Comando de prueba (`test_command`) ausente o vacío en `.rapid-os/config.json`. | Configurar `"test_command": ["python", "-m", "pytest"]` (como lista argv) en `.rapid-os/config.json` o inicializar con `rapid init --test-command "<cmd>"`. |
| `RAPID1302` | ERROR | Entrada interactiva requerida en `rapid init` pero stdin no es una terminal (o finalizó con EOF). | Ejecutar con flag `-y` / `--yes` (modo desatendido con defaults) o proveer flags complementarios (`--stack`, `--topology`, `--agents`, `--test-command`). |
| `RAPID1303` | ERROR | Playbook o plantilla de modo no encontrada, corrupta o sin instrucciones para la acción requerida. | Verificar que el archivo de plantilla `.json` bajo `templates/modes/<mode>.json` exista y sea sintácticamente válido. |
| `RAPID1304` | ERROR | Sesión activa (`.rapid-os/session.json`) inválida o referencia un `run_id` inexistente en `RunRegistry`. | Verificar el run referenciado o reiniciar la sesión creando un nuevo run con `rapid run create`. |
| `RAPID1305` | WARNING | El run activo en `.rapid-os/session.json` alcanzó un estado terminal (`finished`, `failed`, `cancelled`). | Iniciar un nuevo run de especificación o limpiar la sesión. |
| `RAPID1306` | ERROR | Transición de tarea inválida, ambigua (múltiples en progreso sin ID explícito) o sin tareas pendientes. | Especificar explícitamente el `task_id` (ej. `T001`) o la razón obligatoria para `skip`. |
| `RAPID1307` | ERROR | No existe una sesión activa (`.rapid-os/session.json`) para ejecutar comandos dependientes del run actual. | Crear o activar un run primero mediante `rapid run create --spec <spec-id>` o `rapid start`. |
| `RAPID1308` | ERROR | Intento de iniciar un nuevo run (`rapid start`) cuando ya existe un run activo no terminal en sesión. | Continuar con `rapid next`, abortar el run existente con `rapid abort` o usar la bandera `--resume`. |
| `RAPID1309` | ERROR | Proyecto no inicializado (directorio `.rapid-os/standards/` ausente al ejecutar `rapid start`). | Ejecutar `rapid init` para inicializar los estándares y la configuración del proyecto. |
| `RAPID1310` | ERROR | Aprobación de compuerta humana (`rapid approve`) invocada sin terminal interactiva (TTY) o desde una sesión de agente (`CLAUDE_CODE_CHILD_SESSION == 1`), o bajo un proceso ancestro que es un harness de agente (hoy `claude`). La confirmación por TTY se puede emular (script/pty) y actúa como defensa en capas, no una garantía absoluta (reforzada en PRs 2.1 y 3.2). | Ejecutar `rapid approve <gate-id>` directamente por una persona en su propia terminal interactiva para confirmar la aprobación escribiendo `aprobar <gate-id>`. |
| `RAPID1311` | ERROR | Harness no soportado para shortcuts (`rapid shortcuts --harness <id>`). | Usar uno de `claude`, `codex`, `antigravity`, `cursor` o `vscode`. |
| `RAPID1312` | ERROR | No hay harness seleccionado: falta `--harness` y `.rapid-os/config.json` no existe o no lista ningún harness soportado en `tools`. | Pasar `--harness <id>` o ejecutar `rapid init --agents <lista>`. |
| `RAPID1313` | ERROR | Plantilla de shortcut ausente o inválida bajo `templates/shortcuts/<nombre>.md` (frontmatter, descripción o cuerpo). | Restaurar la plantilla desde la instalación de Rapid OS o reinstalar el paquete. |
| `RAPID1314` | ERROR | No se pudo leer, escribir o eliminar un archivo de shortcut: ruta insegura, enlace simbólico, error del sistema de archivos o contenido distinto renderizado por dos harnesses para la misma ruta. | Revisar permisos y que la ruta no sea un enlace simbólico; reintentar. |
| `RAPID1315` | WARNING | Shortcut de modo omitido: no existe el playbook `templates/modes/<modo>.json`. | Esperado hasta que el modo tenga playbook; al agregarlo, ejecutar `rapid shortcuts install` de nuevo. |
| `RAPID1316` | WARNING | Un archivo de shortcut existente no tiene el marcador `generated by rapid shortcuts` y será reemplazado. | La versión anterior queda como `.bak`; revisarla antes de continuar o usar otro nombre para el skill propio. |
| `RAPID1317` | WARNING | `rapid shortcuts remove` omitió un archivo sin el marcador `generated by rapid shortcuts`. | Eliminarlo manualmente si realmente se desea; Rapid OS solo borra archivos que generó. |
| `RAPID1318` | ERROR | `rapid shortcuts` se invocó sin subcomando. | Usar `install`, `list` o `remove`. |
| `RAPID1319` | WARNING / INFO | `rapid doctor`: no se pudo leer la cadena de procesos padre (WARNING; `rapid approve` no puede buscar un harness de agente entre sus ancestros y solo aplica las comprobaciones de TTY y `CLAUDE_CODE_CHILD_SESSION`), o `doctor` se ejecuta bajo un harness de agente (INFO; allí `rapid approve` se rechaza con `RAPID1310`). | En el caso WARNING, comprobar permisos de `/proc`, la disponibilidad de `ps` o el soporte de la plataforma; en el caso INFO, ejecutar `rapid approve` en tu propia terminal. |
| `RAPID1320` | ERROR | `rapid check --expect fail` ligado a una compuerta (`--gate`) o invocado sin una tarea válida (requiere `--task <id>` o exactamente una tarea `in_progress`). | Especificar `--task <task_id>` o verificar que haya exactamente una tarea `in_progress` en la sesión activa. No se permite ligar fallas esperadas a compuertas. |
| `RAPID1321` | WARNING | `rapid shortcuts install`, `list` y `rapid init --shortcuts`: la selección de harnesses deja el mismo `/rapid-*` en dos carpetas que una misma herramienta lee (`cursor` o `vscode` junto con `claude`, `codex` o `antigravity`). Es solo un aviso: no cambia el exit code ni lo que se escribe, y la documentación oficial de Cursor y de VS Code no especifica cómo muestran skills del mismo nombre en carpetas distintas. | Instalar solo la combinación recomendada en el aviso (la herramienta ya lee esas carpetas); ver «Si combinas harnesses» en la [guía de shortcuts](../guides/shortcuts.md#si-combinas-harnesses). |
| `RAPID1322` | ERROR | `rapid start <modo> --spec-file`: ya existe una spec con la misma identidad (id o título) y **contenido distinto** (o está archivada). Con el mismo contenido se reutiliza sin error. | Reutilizar la spec existente con `rapid start <modo> --spec <id>`, o cambiar el título/`id` del archivo de spec. |
| `RAPID1330` | ERROR | `rapid approve` con opciones incompatibles: `--reject` y `--waive` juntos, o cualquiera de los dos sin `<gate-id>`. | Usar una sola acción y pasar el gate (`rapid approve` lista los pendientes). |
| `RAPID1331` | ERROR | No se pudo determinar el revisor: no se pasó `--reviewer`, `git config user.name` no está definido y no se indicó un nombre en la terminal. | Pasar `--reviewer <nombre>` o ejecutar `git config user.name "<nombre>"`. |
| `RAPID1332` | ERROR | El gate no existe, no es un gate humano, ya no está pendiente, o fue rechazado (`changes_requested`) y permanece en FAIL durante el run. | Verificar el id con `rapid approve`; si fue rechazado, ejecutar `rapid abort` e iniciar un run nuevo. |
| `RAPID1333` | ERROR | Falta `--reason` en `--reject`/`--waive`, el gate no es dispensable según el contrato, o el run no está en un estado que permita modificar el gate (debe estar `active` y con todas las tareas terminales). | Indicar `--reason`, dispensar solo gates waivable (p. ej. `gate.review`) y completar las tareas antes de aprobar. |
| `RAPID1334` | ERROR | No se pudo crear el worktree aislado de `rapid start --worktree` (no es un repositorio git, no hay commits, la ruta `../<repo>-<run-id>` ya existe o `git worktree add` falló). | Confirmar un repositorio git con al menos un commit, liberar la ruta y reintentar `rapid start --resume --worktree`. |
| `RAPID1335` | ERROR | El worktree registrado en `workspace_path` de `session.json` ya no existe. | Restaurarlo con `git worktree add` en esa ruta o cancelar el run con `rapid abort`. |
| `RAPID1336` | ERROR | `rapid attach` falló: sin `--label`, archivo inexistente, fuera del proyecto y del workspace, bajo `.rapid-os/`, o tarea inexistente. | Corregir la ruta, indicar `--label` y, si aplica, un `--task` válido. |
| `RAPID1337` | ERROR | `rapid shortcuts install --hooks` / `remove --hooks` (o `rapid init --hooks`, donde se reporta como aviso) sin el harness `claude` seleccionado. | Seleccionar `claude` (`--harness claude` o `tools` en `.rapid-os/config.json`) o quitar `--hooks`. |
| `RAPID1338` | ERROR | `.claude/settings.json` no se puede fusionar: JSON inválido, raíz que no es un objeto, `hooks` o `hooks.<Evento>` con un tipo inesperado, o error al escribirlo. El archivo no se modifica. | Corregir el archivo a mano (o restaurar el `.bak`) y repetir el comando. |
| `RAPID1339` | WARNING | `rapid doctor`: hay hooks de Claude Code instalados pero `rapid` no se resuelve en el `PATH`; Claude Code trata el fallo como error no bloqueante y el run deja de reforzarse. | Instalar Rapid OS donde lo vea Claude Code (p. ej. `pipx install git+https://github.com/alyconr/Rapid-OS.git`) o añadir su directorio de scripts al `PATH`. |

## 10. Catálogo de stacks, onboarding y arquitectura (`RAPID1400–RAPID1429`)

| Código | Nivel | Significado | Acción |
|---|---|---|---|
| `RAPID1400` | INFO | `.rapid-os/setup.json` existe y es válido ("Setup válido"). Lo emite `rapid validate`. | Ninguna. |
| `RAPID1401` | ERROR | Sidecar de catálogo inválido bajo `templates/stacks/`, `templates/topologies/` o `templates/setup/`: JSON ilegible, `schema_version` distinto de 1, campo faltante o vacío, `id` distinto del nombre del archivo, topología desconocida en `compatible_topologies`, `default_topology` fuera de `compatible_topologies`, o banco de preguntas mal formado. `rapid init` aborta con este código en lugar de un traceback. | Corregir o restaurar el archivo indicado desde la instalación de Rapid OS, o reinstalar el paquete. |
| `RAPID1402` | ERROR | `rapid setup set topology <id>` con una topología incompatible con el stack ya elegido (según `compatible_topologies` del catálogo; un stack fuera del catálogo acepta todas menos `doc-site`). No se escribe nada. Al cambiar el stack con `set stack`, una topología que ya no encaja no es error: queda sin decidir. | Elegir una topología de la lista que muestra el mensaje o `rapid setup next`. |
| `RAPID1406` | ERROR | `.rapid-os/setup.json` es inválido: JSON ilegible, `schema_version` distinto de 1, o un campo con tipo o valor no permitido (`stack`, `docs.<id>.status`, etc.). `rapid setup next` y `show` salen con 1 sin traceback y no modifican el archivo. | Corregir el archivo según el mensaje, o moverlo para que el estado se derive del disco. |
| `RAPID1403` | WARNING / ERROR | Un documento del onboarding redactado por el agente (`source: drafted`) no tiene una sección requerida de su banco: falta un encabezado `## ` que coincida con cualquiera de sus títulos (es/en, sin distinguir mayúsculas). No se evalúa para `source: provided`. **Doble uso:** en `rapid validate` es un WARNING sobre un documento ya escrito; en `rapid setup doc <id> --source drafted` es un rechazo (ERROR, exit 1) y no se escribe nada. | Añadir la sección o rehacer el documento. |
| `RAPID1404` | WARNING / ERROR | Un documento del onboarding redactado por el agente supera `max_chars` de su banco. No se evalúa para `source: provided`. Mismo doble uso que `RAPID1403`: WARNING en `rapid validate`, rechazo (exit 1, nada escrito) en `rapid setup doc ... --source drafted`. | Acortar el documento. |
| `RAPID1405` | ERROR | `rapid setup doc <id> --source drafted` sobre un documento que una persona aportó (`source: provided`) o sobre un archivo escrito a mano: el borrador lo reemplazaría. No se escribe nada. | Repetir con `--replace` si se quiere reemplazar (queda un `.bak`), o dejar el documento como está. |
| `RAPID1407` | ERROR | `rapid setup finish` mientras queda una decisión abierta (stack, topología, arquetipo, agentes, comando de test un documento `pending` o la revisión de borradores, `review_drafts`, sin cerrar). No se escribe nada. | Ejecutar el comando que indica el mensaje (el `command` de `rapid setup next`) y repetir `finish`. |
| `RAPID1408` | WARNING | Un documento del onboarding redactado por el agente sigue sin confirmar por una persona; llega al agente como supuesto. | Que una persona lo revise y lo confirme. |
| `RAPID1409` | ERROR | `rapid setup stack --custom` recibió un `tech-stack.md` sin alguna de las secciones `Runtime`, `Framework` o `Testing` (un encabezado `## ` o una línea `- **Nombre:**`). No se escribe nada. | Añadir las secciones que nombra el mensaje y repetir el comando. |
| `RAPID1410` | WARNING | `standards/business.md` y `docs/BUSINESS_RULES.md` existen y sus cuerpos difieren (sin frontmatter y con espacios normalizados). Gana `docs/BUSINESS_RULES.md`; el estándar queda fuera del contexto. | Unificar el contenido o eliminar `standards/business.md`. |
| `RAPID1412` | WARNING | Una plantilla de stack o topología (`.md`) no tiene su sidecar `.json`. La plantilla sigue siendo utilizable y se trata como compatible con todas las topologías excepto `doc-site`. | Añadir `templates/<stacks\|topologies>/<id>.json` para declarar `compatible_topologies` y `default_topology`; no es obligatorio. |
| `RAPID1413` | ERROR | Subcomando, clave o valor de `rapid setup` inválido: clave de `set` desconocida, stack/topología/arquetipo/agente inexistente, `--file` ilegible o vacío, documento desconocido, combinación de modos de `doc` (`--skip`, `--confirm`, `--reopen`, `--from-legacy`, `--source`), nada que confirmar o importar, `--skip` de un documento ya escrito, o `rapid setup` sin subcomando, `rapid setup review` sin `--done`; también `rapid init --business-file` con una ruta vacía, un directorio o un archivo ilegible, y `rapid start bugfix|refactor|hardening` en un repositorio nuevo, sin código ni tests (`No hay código que arreglar|refactorizar|endurecer; usa /rapid-feature`), y `rapid shortcuts install|list|remove` con `--global` para un harness sin carpeta de usuario documentada (`vscode`), sin `--harness` o con `--hooks`, o con un `--only` que no es un shortcut. | Usar `next`, `show`, `set`, `stack`, `doc` o `finish` con valores de `rapid setup next`. |
| `RAPID1414` | WARNING | `rapid init` instaló shortcuts o hooks, o `rapid doctor` los encontró, y `rapid` no se resuelve en el `PATH`: se ejecutan desde el shell del agente. No cambia el exit code (0). | Instalar Rapid OS con el instalador o con `pipx install git+https://github.com/alyconr/Rapid-OS.git`, o añadir su directorio de scripts al `PATH`. |
| `RAPID1415` | ERROR / WARNING | El cuerpo de un documento del onboarding tiene un `?` entre dos letras o al inicio de una palabra (`vac?os`, `Decisi?n`, `?xito`): lo que deja una tubería que no es UTF-8 (la de Windows PowerShell 5.1 hacia programas nativos usa ASCII) de los acentos y la `ñ`. Se ignoran los bloques de código, el código en línea y las URL. En `rapid setup doc <id> --source drafted` es un rechazo (exit 1, no se escribe nada); con `--source provided` es un WARNING y el texto se guarda tal cual, porque Rapid OS no reescribe lo que pega la persona. | Escribir el documento en un archivo UTF-8 y enviarlo con `--file <ruta>`. En Windows PowerShell: `Set-Content -Encoding utf8 $env:TEMP\rapid-<id>.md` y `rapid setup doc <id> --source drafted --file $env:TEMP\rapid-<id>.md`. |
| `RAPID1416` | ERROR | `rapid start` en una carpeta que no es un repositorio git, sin git instalado, o en un repositorio en el que git no confía. Rapid OS observa los cambios del run con git y el run nunca podría pasar. Se comprueba antes de crear el run y antes del rechazo de repositorio vacío (`RAPID1413`): no se escribe nada en `.rapid-os/runs` ni en `session.json`. | Ejecutar `git init`, o `rapid setup finish`, que crea el repositorio (sin commits) si falta; instalar git si no está. **Carpeta en la que git no confía** (`detected dubious ownership`, habitual en Windows en otra unidad o en carpetas creadas por otro usuario): el mismo código, otro texto (`RAPID1416 git no confía en esta carpeta (dubious ownership) ...`); `git init` no lo arregla, hay que ejecutar `git config --global --add safe.directory <ruta>` con la ruta que imprime el mensaje. `rapid setup finish` no ejecuta `git init` en ese caso: avisa con el mismo comando. Rapid OS ejecuta todos sus comandos git con `-c safe.directory=<raíz del proyecto>`, así que `untrusted` solo ocurre si git no respeta ese ajuste (versiones anteriores a 2.38) o si el repositorio está en una carpeta superior a la raíz del proyecto. El caso habitual del sandbox de Codex en Windows (otro usuario) ya no bloquea a Rapid OS: lo único pendiente es la excepción para el git de la persona, que llega como `person_actions` (`git-safe-directory`) en `rapid setup finish`, `rapid setup next --json` y `rapid doctor`. Ver [Windows: sandbox y git](../integrations/codex.md#windows-sandbox-y-git). |
| `RAPID1420` | ERROR | `rapid arch check` encontró un import que rompe la regla de arquitectura de `.rapid-os/standards/architecture.json`; se emite una por violación, con archivo, línea, import y regla: `layer` (una capa importa una capa que no le toca), `cross_module` (un módulo importa de otro algo distinto de su punto público), `shared` (`shared` importa un módulo), `init_reexport` (el `__init__.py` de un módulo de Python importa algo distinto de su propio `public.py`) o `domain_forbidden_import` (`domain` importa `fastapi`, `sqlalchemy`, `react`, `@prisma/client`... según el stack). También se usa para un `architecture.json` ilegible o inválido y para un run cuyo contrato incluye `gate.architecture` cuando no hay `architecture.json` en el directorio actual ni en el proyecto principal de la sesión (`el run exige gate.architecture y no hay architecture.json`). En un run, hace fallar `rapid check --gate gate.architecture` y `rapid finish` no da `PASS`. | Cambiar el código para respetar la regla (importar solo el punto público del otro módulo, mover la lógica a la capa que toca, quitar la librería del `domain`). Nunca desactives ni edites `architecture.json` para que pase: pide a la persona que cambie la regla. |
