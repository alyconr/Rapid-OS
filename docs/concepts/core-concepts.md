---
title: Conceptos fundamentales
description: Guía de conceptos, modelos y entidades del ciclo de gobernanza de Rapid OS v3.
---

# Conceptos fundamentales

Rapid OS organiza la gobernanza de ingeniería en torno a entidades estructuradas, contratos inmutables y digests criptográficos SHA-256. A continuación se presentan los conceptos centrales del sistema.

---

## 1. Project Intelligence (`ProjectModel`)

`ProjectModel` representa el conocimiento determinista que Rapid OS posee sobre un repositorio. Se genera mediante `rapid scan` y contiene una colección de hechos normalizados (`ProjectFact`).

Cada hecho incluye:
- **Categoría:** lenguaje, framework, testing, base de datos, packaging, docker, monorepo, etc.
- **Valor y detalles:** nombres exactos y versiones detectadas.
- **Evidencia (`Evidence`):** la ruta del archivo que originó la detección (ej. `pyproject.toml`, `package.json`), el motivo y la confianza asignada.

Se persiste de forma explícita en `.rapid-os/project.json` cuando se usa `rapid scan --write`.

---

## 2. Context Compiler (`CompiledContext`)

El compilador de contexto (`rapid context`) extrae y ensambla la información mínima y estrictamente necesaria para que un coding harness complete una tarea específica.

Propiedades esenciales:
- **Modo de tarea:** `feature`, `bugfix`, `refactor`, `hardening`, `research`, o `general`.
- **Presupuesto estricto (`--max-chars`):** Limita el tamaño del markdown generado para no saturar la ventana de contexto del LLM.
- **Relevancia:** Prioriza estándares del proyecto, hechos del escaneo pertinentes al modo y especificaciones marcadas como listas.
- **Trazabilidad (`ContextManifest`):** Emite un registro con el digest SHA-256 de cada fragmento incorporado, permitiendo saber exactamente qué vio el agente.
- **Modo solo lectura:** `rapid context` nunca modifica archivos del repositorio.

---

## 3. Specification Registry (`SpecRecord` y `SpecRevision`)

Rapid OS sustituye las notas efímeras por un registro formal de especificaciones almacenado en `.rapid-os/specs/<spec-id>/`.

- **Estados de autoría:**
  - `draft`: La especificación se encuentra en elaboración.
  - `ready`: La especificación ha sido congelada y está lista para ser implementada en un run.
  - `archived`: La especificación ha sido retirada o completada.
- **Revisiones inmutables:** Cada modificación genera una nueva revisión (`0001.json`, `0002.json`, ...) con su propio digest SHA-256 (`content_digest`). Un run en ejecución se vincula permanentemente a una revisión específica; si la especificación cambia posteriormente, el run no sufre alteraciones silenciosas.

---

## 4. Execution Policy (`ExecutionPolicy`)

Ubicada en `.rapid-os/policy.json`, la política de ejecución define las reglas operativas del equipo:
- **Clasificación de riesgo:** `low`, `medium`, `high` y `critical`.
- **Requisitos de workspace:** si la tarea puede realizarse en el espacio de trabajo actual (`workspace.current`) o exige aislamiento (`workspace.isolated`).
- **Gates obligatorios:** puntos de control que deben cumplirse antes o después de la implementación (ej. `gate.tests`, `gate.lint`, `gate.review`).

---

## 5. Execution Contract (`ExecutionContract`)

El contrato de ejecución es el documento fundacional de un run (`rapid run create`). Congela de forma inmutable:
- La especificación y su revisión exacta (`spec_id`, `spec_content_digest`).
- El contexto compilado y su manifiesto (`context_digest`).
- La instantánea del proyecto (`project_model_digest`).
- La política de ejecución aplicable (`policy_digest`).
- El harness designado y las tareas asignadas (`T001`, `T002`, ...).

El digest del contrato (`contract_digest`) es la raíz criptográfica que gobierna todo el ciclo de vida posterior.

---

## 6. Run State Ledger (`RunState`)

El registro de estados (`.rapid-os/runs/<run-id>/states/`) funciona como un libro contable *append-only* (solo anexar). Cada transición genera un archivo numerado secuencialmente (`0001.json`, `0002.json`, ...).

- **Estados del run:** `prepared` → `active` → `finished` (o `failed` / `cancelled` / `blocked`).
- **Estados de tareas:** `pending` → `in_progress` → `done` (o `skipped` / `blocked`).
- **Disposición de gates:** `pending` → `acknowledged` (declarado por el operador) o `waived` (dispensado con justificación registrada).

---

## 7. Harness Capabilities (`HarnessProfile`)

Rapid OS no otorga permisos al sistema operativo; en su lugar, modela las **capabilities que un harness declara soportar**:
- `supported`: El perfil del harness declara explícitamente soportar la operación.
- `unsupported`: El perfil declara que no soporta la operación.
- `unknown`: No existe declaración; Rapid OS **no asume** soporte.

El comando `rapid harness resolve` contrasta las necesidades del contrato frente a las capabilities del perfil antes de autorizar el trabajo.

---

## 8. Run Evidence (`RunEvidence`)

El motor de evidencias (`rapid evidence`) ingiere pruebas físicas registradas durante la ejecución:
- Salidas de comandos y códigos de retorno.
- Resultados de suites de pruebas (`TEST_RESULT`).
- Diffs de control de versiones (`GIT_RESULT`).
- Archivos generados, copiados al directorio `.rapid-os/evidence/<run-id>/artifacts/` con su tamaño y hash SHA-256.

Toda evidencia está anclada a una revisión de estado (`state_revision`) y a un digest de contrato específico.

---

## 9. Behavioral Evaluations (`EvaluationReport`)

El evaluador de comportamiento (`rapid eval run`) es un motor determinista que corre de forma local e independiente de cualquier LLM:
- Ejecuta reglas lógicas (`BehavioralRuleset` v1) sobre la evidencia física recopilada.
- Emite un veredicto formal:
  - `PASS`: Todos los requisitos y gates cuentan con evidencia válida satisfactoria.
  - `PASS_WITH_WAIVERS`: Requisitos cumplidos y gates dispensados válidamente según la política.
  - `UNVERIFIED`: Falta evidencia para comprobar tareas o gates.
  - `FAIL`: Alguna prueba falló o violó las reglas del contrato.

---

## 10. Integrity Validation (`rapid validate`)

`rapid validate` comprueba la integridad referencial y criptográfica cruzada de todos los directorios y archivos de `.rapid-os/`, asegurando que no existan manipulaciones manuales, inconsistencias de esquemas o roturas en la cadena de procedencia SHA-256.
