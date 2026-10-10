---
title: Validación y Cierre de Sprint 4
description: Auditoría técnica, matriz de cobertura de laboratorios reproducibles, validación de Product Truth y Definition of Done para Sprint 4 de RAPID OS.
---

# Validación y Cierre de Sprint 4

Este documento registra formalmente la auditoría técnica, la cobertura pedagógica y la verificación determinista del **Sprint 4: Hands-on Tutorials, Reproducible Labs & Coding Harness Integration** de la plataforma documental de RAPID OS v3.0.0.

---

## 1. Alcance y Objetivos del Sprint 4

El Sprint 4 tuvo como objetivo primordial transformar el conocimiento teórico y normativo de RAPID OS v3 en experiencias de aprendizaje prácticas, reproducibles y directamente ejecutables por ingenieros de software y agentes de IA:

1. **Laboratorios Prácticos Canónicos**: Crear 6 tutoriales completos guiados que cubren el espectro de modos de ingeniería (`first-governed-project`, `feature`, `bugfix`, `refactor`, `hardening`, `research`).
2. **Proyectos de Ejemplo Reproducibles**: Proveer 6 directorios en `examples/` con estructura canónica (`starter/`, `solution/`, `tests/`, `README.md`) utilizando **únicamente la biblioteca estándar de Python** (cero dependencias externas).
3. **Guías de Integración con Coding Harnesses**: Diseñar guías operativas realistas para los 5 principales entornos de ejecución (`Claude Code`, `Codex / OpenAI CLI`, `Cursor`, `VS Code`, `Google Antigravity`).
4. **Frontera de Ejecución Externa Rigurosa**: Establecer sin ambigüedades la separación entre el plano de gobernanza (RAPID OS) y el plano de ejecución externa (desarrollador / coding harness).
5. **Product Truth y Automatización E2E**: Validar cada tutorial, ejemplo, comando de CLI y JSON authoring contract mediante pruebas automatizadas (`tests/test_documentation_labs.py`).

---

## 2. Matriz de Archivos Entregados

### 2.1 Documentación Canónica (`docs/`)

| Categoría | Ruta del Documento | Descripción / Propósito |
| :--- | :--- | :--- |
| **Tutoriales** | `docs/tutorials/index.md` | Catálogo de laboratorios, progresión recomendada y requisitos previos. |
| **Tutoriales** | `docs/tutorials/first-governed-project.md` | Lab 1: First Governed Project (Task Tracker CLI, Governance Loop completo). |
| **Tutoriales** | `docs/tutorials/feature-lab.md` | Lab 2: Feature Lab (Booking Service, prevención de reservas duplicadas). |
| **Tutoriales** | `docs/tutorials/bugfix-lab.md` | Lab 3: Bugfix Lab (Discount Calculator, división por cero, regression tests obligatorios). |
| **Tutoriales** | `docs/tutorials/refactor-lab.md` | Lab 4: Refactor Lab (Payroll Processor, deduplicación de impuestos con baseline estricto). |
| **Tutoriales** | `docs/tutorials/hardening-lab.md` | Lab 5: Hardening Lab (Auth Token Manager, remediación de timing attacks y SAST). |
| **Tutoriales** | `docs/tutorials/research-lab.md` | Lab 6: Research Lab (Cache Eviction Spike, benchmark LRU vs FIFO y artefacto de decisión). |
| **Troubleshooting** | `docs/troubleshooting/tutorials.md` | Guía de diagnóstico y resolución de errores comunes en laboratorios. |
| **Integraciones** | `docs/integrations/index.md` | Visión general de integración con coding harnesses y frontera de ejecución. |
| **Integraciones** | `docs/integrations/claude-code.md` | Integración operativa con Claude Code (terminal interactiva, hooks de gobernanza). |
| **Integraciones** | `docs/integrations/codex.md` | Integración con OpenAI Codex CLI (ejecución no interactiva por lotes). |
| **Integraciones** | `docs/integrations/cursor.md` | Integración con Cursor AI IDE (Agent mode, prompts de contexto compilado). |
| **Integraciones** | `docs/integrations/vscode.md` | Integración con VS Code y GitHub Copilot (extensiones y terminal integrada). |
| **Integraciones** | `docs/integrations/antigravity.md` | Integración con Google Antigravity (Advanced Agentic Coding, subagents). |
| **Auditoría** | `docs/audit/sprint-4-validation.md` | Este documento de validación, matriz de cobertura y DoD. |

### 2.2 Proyectos de Ejemplo Reproducibles (`examples/`)

| Laboratorio | Directorio | Descripción del Problema | Suites de Tests |
| :--- | :--- | :--- | :--- |
| **Lab 1** | `examples/first-governed-project/` | Task Tracker CLI: agregado de prioridad `high`/`medium`/`low`. | `tests/test_app.py` |
| **Lab 2** | `examples/feature-lab/` | Booking Service: validación de colisión de franjas horarias. | `tests/test_booking.py` |
| **Lab 3** | `examples/bugfix-lab/` | Discount Calculator: corrección de división por cero y prueba de regresión. | `tests/test_discount.py` |
| **Lab 4** | `examples/refactor-lab/` | Payroll Processor: extracción de cálculo de deducciones fiscales sin alterar baseline. | `tests/test_payroll.py` |
| **Lab 5** | `examples/hardening-lab/` | Auth Token Manager: uso de `hmac.compare_digest` para neutralizar timing attacks. | `tests/test_auth.py` |
| **Lab 6** | `examples/research-lab/` | Cache Eviction Spike: benchmark determinista comparando hits/misses entre LRU y FIFO. | `tests/test_cache.py` |
| **Catálogo** | `examples/README.md` | Índice de ejemplos, guía de ejecución y verificación reproducible. | — |

Todos los proyectos incluyen carpetas independientes `starter/` (con el estado inicial o tests que fallan) y `solution/` (con la solución completa y tests en verde), además de `__init__.py` para descubrimiento estándar con `unittest`.

---

## 3. Verificación de Product Truth y Restricciones Arquitectónicas

En estricta consonancia con los principios rectores de RAPID OS y las lecciones aprendidas del Issue #40:

### 3.1 Cero Modificaciones en el Runtime (`rapid_os/`)
- No se alteró ningún archivo en `rapid_os/cli/`, `rapid_os/domain/`, `rapid_os/adapters/` o `rapid_os/core/`.
- Toda la funcionalidad probada en los laboratorios utiliza el comportamiento real de la versión `3.0.0` ya implementada.

### 3.2 Formato de Autoría de Evidencia (Evidence Authoring vs RunEvidence)
- Se respeta rigurosamente que los inputs para `rapid evidence add --input <file>` representan un archivo de **autoría**, por lo cual **NO** deben contener `id`, `schema_version`, o `run_id`. El CLI y el dominio asignan secuencialmente el ID (`E001`, `E002`, etc.) y vinculan la evidencia al contrato del Run activo.
- Todos los payloads documentados contienen únicamente las claves permitidas por cada `EvidenceKind` canónico.

### 3.3 Orden Determinista de Reconocimiento de Gates
- Se documenta y verifica que compuertas posteriores a la ejecución (`gate.tests`, `gate.final-verification`) requieren que las tareas del Run hayan alcanzado el estado `done` (`rapid run task update ... --status done`). Reconocer gates antes de completar tareas dispara `RAPID1014` (Precondition failed).
- Se documenta que compuertas como `gate.baseline` y `gate.tests` requieren evidencia con lista no vacía de artefactos (`artifacts: ["..."]`).

### 3.4 Frontera de Ejecución Externa
- Se enfatiza en todos los tutoriales e integraciones que RAPID OS **no es un ejecutor de modelos ni un runner de código**.
- El desarrollador o el coding harness es el único actor responsable de crear archivos, ejecutar `python -m unittest`, generar logs de salida y luego invocar al CLI de RAPID OS para registrar la evidencia producida.

---

## 4. Matriz de Pruebas Automatizadas (`tests/test_documentation_labs.py`)

Se implementó una suite integral de 5 pruebas automatizadas que verifican la integridad total del material del Sprint 4:

1. `test_sprint4_mandatory_documents_exist`:
   - Verifica la existencia física en disco de los 6 tutoriales, las 5 guías de integración, el troubleshooting, el README de ejemplos y el documento de auditoría.
2. `test_all_tutorial_labs_follow_canonical_pedagogical_template`:
   - Valida que los 6 laboratorios contengan **todas** las 12 secciones pedagógicas obligatorias: Overview, Learning Outcomes, Initial State, Engineering Requirements, Guided Procedure, Expected Artifacts, External Execution, Evidence Collection, Evaluation, Validation, Troubleshooting, Next Steps / Assessment.
3. `test_all_example_labs_starters_and_solutions_pass_tests`:
   - Ejecuta programáticamente la suite de pruebas `unittest` de los 6 ejemplos tanto en su versión `starter/` (para los laboratorios aplicables) como en su versión `solution/`. 12 suites ejecutadas con 100% de éxito.
4. `test_documented_cli_commands_in_tutorials_match_argparse`:
   - Extrae mediante regex todos los bloques de código `bash` en los tutoriales y valida que cada comando y subcomando invocado exista formalmente en el árbol de parsers `argparse` del CLI de RAPID OS (`rapid init`, `rapid scan`, `rapid spec`, `rapid context`, `rapid policy`, `rapid run`, `rapid harness`, `rapid evidence`, `rapid eval`, `rapid validate`).
5. `test_governance_e2e_full_lifecycle_in_temp_project`:
   - Ejecuta un proceso E2E real en un directorio temporal (`tempfile.TemporaryDirectory`) invocando subprocesos del CLI de RAPID OS:
     - `rapid init --stack docs-modern --archetype mvp --no-scan`
     - `rapid scan`
     - `rapid spec create --type feature ...`
     - `rapid context compile ...`
     - `rapid policy inspect`
     - `rapid run create --mode feature ...`
     - `rapid harness resolve --profile cursor`
     - `rapid evidence add --run ... --input <authoring_json>` (3 evidencias canónicas reales: test_result para baseline, test_result para tests, review para final-verification)
     - `rapid run task update ... --status done`
     - `rapid run gate ack ...` (`gate.baseline`, `gate.tests`, `gate.final-verification`)
     - `rapid eval run --run ...` (valida veredicto determinista **PASS**)
     - `rapid validate --strict`

---

## 5. Resultados de Quality Gates

| Quality Gate | Herramienta / Comando | Resultado | Estado |
| :--- | :--- | :--- | :--- |
| **Python Unit & Contract Tests** | `python -m unittest discover tests` | **321 tests pasados**, 0 fallos, 0 errores (35.5s) | ✅ PASS |
| **Docusaurus TypeScript Types** | `npm run typecheck` en `website/` | 0 errores TypeScript | ✅ PASS |
| **Docusaurus Static Build** | `npm run build` en `website/` | Compilación HTML exitosa, **0 enlaces rotos** | ✅ PASS |
| **Git Working Tree Hygiene** | `git status --short` | Solo archivos de docs, examples, sidebars y tests de Sprint 4 | ✅ PASS |

---

## 6. Definition of Done (DoD) Checklist

- [x] Los 6 tutoriales prácticos implementados siguiendo la estructura pedagógica canónica.
- [x] Los 6 proyectos de ejemplo implementados con `starter/`, `solution/`, `tests/` y `README.md`.
- [x] Todos los ejemplos utilizan exclusivamente Python estándar sin librerías externas.
- [x] Las 5 guías de integración con coding harnesses completadas con delimitación clara de responsabilidades.
- [x] Troubleshooting específico para laboratorios documentado en `docs/troubleshooting/tutorials.md`.
- [x] Navegación Docusaurus actualizada en `website/sidebars.ts` con categorías intuitivas.
- [x] Cero modificaciones funcionales en el runtime `rapid_os/`.
- [x] Suite de pruebas automatizadas `tests/test_documentation_labs.py` incorporada y aprobada al 100%.
- [x] Ciclo E2E completo validado en entorno real con veredicto determinista `PASS`.
- [x] Documento de auditoría `docs/audit/sprint-4-validation.md` creado.
- [x] Ningún secreto, API key o dato privado expuesto en documentación o código.
- [x] Rama `docs/sprint-4-hands-on-tutorials` lista para Pull Request hacia `develop`.
