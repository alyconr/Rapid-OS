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
| `RAPID1101` | ERROR | Identificador de capability no canónico o inválido. | Usar IDs canónicos (ej. `terminal.execute`, `filesystem.write`). |
| `RAPID1102` | ERROR | Perfil de harness (`HarnessProfile`) inválido. | Corregir `.rapid-os/harnesses/<id>.json` según el schema v1. |
| `RAPID1103` | ERROR | Perfil de harness no encontrado. | Inicializar el perfil con `rapid harness init <id>` o usar uno integrado. |
| `RAPID1104` | ERROR | Formato de harness ID inválido. | Usar nombres alfanuméricos en minúsculas con guiones. |
| `RAPID1106` | ERROR | Nivel de soporte inválido en perfil. | Usar `supported`, `conditional`, o `unsupported`. |
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
