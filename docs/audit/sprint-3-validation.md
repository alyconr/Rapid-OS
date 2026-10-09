---
title: Validación y Cierre de Sprint 3
description: Auditoría de cobertura, matriz de validación y Definition of Done para el Sprint 3 de RAPID OS Documentation Platform.
---

# Validación y Cierre de Sprint 3

Este documento registra formalmente la auditoría técnica y la cobertura del **Sprint 3: Governance Guides, Engineering Modes & Diagnostic Cookbooks** de la plataforma documental de RAPID OS v3.0.0.

---

## 1. Alcance y Objetivos del Sprint 3

El Sprint 3 tuvo como objetivo profundizar en los aspectos operativos avanzados de RAPID OS:
- Documentar detalladamente los **5 modos de ingeniería** (`feature`, `bugfix`, `refactor`, `hardening`, `research`).
- Proveer **cookbooks prácticos** con payloads reales para políticas, contratos, perfiles de harness, los 9 tipos de evidencia y evaluaciones de comportamiento.
- Compilar un **catálogo exhaustivo de diagnósticos `RAPIDxxx`** con explicaciones y pasos de remediación.
- Documentar la **integración en pipelines CI/CD** (GitHub Actions, exit codes y validación estricta).

---

## 2. Matriz de Archivos Entregados

| Categoría | Ruta del Documento | Descripción / Propósito |
| :--- | :--- | :--- |
| **Modos de Ingeniería** | `docs/guides/modes/index.md` | Visión general de modos, relación con el Context Compiler y Policy. |
| **Modos de Ingeniería** | `docs/guides/modes/feature.md` | Ciclo completo para desarrollo de nuevas funcionalidades gobernadas. |
| **Modos de Ingeniería** | `docs/guides/modes/bugfix.md` | Flujo de reproducción, test de regresión obligatorio y resolución. |
| **Modos de Ingeniería** | `docs/guides/modes/refactor.md` | Refactorización con baseline obligatorio y paridad de tests al 100%. |
| **Modos de Ingeniería** | `docs/guides/modes/hardening.md` | Seguridad, CVEs, análisis SAST y compuertas de alto riesgo. |
| **Modos de Ingeniería** | `docs/guides/modes/research.md` | Spikes exploratorios (`ExecutionClass.SPIKE`), benchmarks y artefactos. |
| **Cookbooks** | `docs/cookbooks/policies-and-contracts.md` | Configuración de `.rapid-os/policy.json`, compuertas, riesgos y waivers. |
| **Cookbooks** | `docs/cookbooks/harness-profiles.md` | Perfiles integrados, perfiles de proyecto y `capabilities.lock`. |
| **Cookbooks** | `docs/cookbooks/evidence-engine.md` | Formatos JSON reales para los 9 tipos de evidencia y verificación. |
| **Cookbooks** | `docs/cookbooks/behavioral-evaluations.md` | Evaluaciones deterministas, veredictos y protección de replay semántico. |
| **Troubleshooting** | `docs/troubleshooting/diagnostics.md` | Catálogo de diagnósticos `RAPID100` a `RAPID1229` y remediación. |
| **CI/CD** | `docs/guides/ci-cd-integration.md` | Integración en GitHub Actions, pre-commit y validación estricta. |
| **Auditoría** | `docs/audit/sprint-3-validation.md` | Matriz de cumplimiento y Definition of Done del Sprint 3. |

---

## 3. Verificación de Product Truth

Durante la elaboración de todo el material del Sprint 3 se verificaron rigurosamente las siguientes fronteras de verdad del producto:

1. **No ejecución autónoma de LLMs**: Se enfatizó que RAPID OS no invoca agentes ni modelos por su cuenta; gobierna las especificaciones, el contexto y los contratos.
2. **Evaluación offline y determinista**: Se aclaró explícitamente que `rapid eval run` no utiliza "LLM-as-a-judge", sino reglas lógicas y matemáticas sobre el estado y las evidencias.
3. **Capabilities como declaraciones**: Se reforzó que una capability del harness es una declaración de compatibilidad de herramientas, no una garantía de ejecución correcta ni sandboxing del sistema operativo.
4. **Veredicto PASS sin claims absolutos**: Se aclaró que `EvaluationVerdict.PASS` certifica que las compuertas y reglas de evidencia se cumplen, pero no garantiza matemáticamente ausencia total de bugs en el software.

---

## 4. Definition of Done (DoD) Checklist

- [x] Todas las nuevas páginas de documentación cuentan con frontmatter válido (`title`, `description`).
- [x] Los diagramas de flujo utilizan sintaxis estándar de Mermaid (`mermaid`).
- [x] Los bloques de código reflejan la interfaz real del CLI v3.0.0 sin flags ficticios.
- [x] Navegación integrada en `website/sidebars.ts` con jerarquía intuitiva.
- [x] `tests/test_documentation_contract.py` actualizado con validaciones para los nuevos slugs y contratos.
- [x] `npm run typecheck` aprueba con 0 errores TypeScript.
- [x] `npm run build` aprueba con 0 enlaces rotos (`onBrokenLinks: 'throw'`).
- [x] Suite completa de pruebas de Python ejecutada y aprobada al 100%.

---

## 5. Post-Merge Product Truth Remediation — Issue #40

Tras la integración del Sprint 3 en `main` (PR #38), una auditoría posterior identificó discrepancias técnicas en ejemplos documentales que no fueron capturadas por las pruebas unitarias originales. Se ejecutó una remediación integral (Issue #40) bajo la rama `fix/docs-sprint3-product-truth`.

### 5.1 Hallazgos y Causa Raíz

1. **Evidence Engine CLI (`rapid evidence add`)**:
   - *Discrepancia*: Se documentaron flags ficticios como `--kind`, `--producer`, `--summary`.
   - *Causa*: CLI únicamente soporta `--run <id>`, `--input <file>`, y `--json`.
   - *Remediación*: Reescritura completa del cookbook `docs/cookbooks/evidence-engine.md` y guías de modos (`feature.md`, `bugfix.md`, `refactor.md`, `hardening.md`, `research.md`) para estructurar archivos de autoría JSON y pasarlos vía `--input <file>`.

2. **Esquema de Autoría de Evidencia y Validación Estricta**:
   - *Discrepancia*: Documentos de ejemplo incluían campos no permitidos en `payload` o identificadores de compuertas basados en enums (`implementation_tests`) en vez de IDs canónicos del contrato (`gate.tests`, `gate.baseline`, `gate.review`).
   - *Causa*: `RunEvidence.from_dict` y `PAYLOAD_REQUIRED_KEYS` aplican validación estricta de claves cerradas (`RAPID1206`, `RAPID1207`).
   - *Remediación*: Documentación precisa de los 9 tipos canónicos de `EvidenceKind` con esquemas mínimos y exactos.

3. **Harness Profiles Schema y Catálogo de Capabilities**:
   - *Discrepancia*: `harness-profiles.md` presentaba `capabilities` como diccionario con estado no existente `conditional` y capabilities inventadas (`terminal.execute`, `filesystem.write`).
   - *Causa*: `HarnessProfile` requiere una lista de objetos `CapabilitySupportDeclaration` (`capability_id`, `status`, `reason`). Los únicos estados válidos son `supported`, `unsupported`, `unknown` (`CapabilitySupportStatus`).
   - *Remediación*: Alineación total con el catálogo canónico de 11 capabilities (`CANONICAL_CAPABILITY_IDS`).

4. **Catálogo de Diagnósticos**:
   - *Discrepancia*: En `RAPID1101` y `RAPID1106` figuraban IDs ficticios y estados `conditional`.
   - *Remediación*: Actualización en `docs/troubleshooting/diagnostics.md` a IDs y estados canónicos.

5. **Integración CI/CD**:
   - *Discrepancia*: Pipeline de ejemplo iteraba a ciegas sobre `.rapid-os/runs/*/` con `--require-pass`, rompiendo ejecuciones activas o branches concurrentes.
   - *Remediación*: Separación de los 3 checks independientes de CI (`rapid validate --strict`, `rapid harness resolve`, `rapid eval run`), eliminación de afirmaciones sobre "listo para producción", y adición de permisos mínimos (`contents: read`).

### 5.2 Pruebas de Contrato Automatizadas Añadidas

Se incorporó `tests/test_sprint3_remediation_contract.py` (11 pruebas automatizadas rigurosas) validando:
- Inexistencia de flags inválidos en el parser CLI de `rapid evidence add`.
- Validación estricta sin omisiones silenciosas de los 9 bloques JSON del cookbook contra `PAYLOAD_REQUIRED_KEYS`.
- Rechazo estricto (`RAPID1206`) de campos desconocidos en payloads de evidencia.
- Validación de deserialización y serialización de `HarnessProfile` con lista de `CapabilitySupportDeclaration`.
- Rechazo de estados no canónicos (como `conditional`) en perfiles de harness.
- Coherencia del catálogo de 11 capabilities en documentación contra `CANONICAL_CAPABILITY_IDS`.
- Semántica de gobernanza de aislamiento: prueba explícita que confirma que `mode: "current"` produce `FAIL` para la compuerta `gate.workspace-isolation` (`rule.gate.workspace_isolation.v1`), exigiendo `mode: "isolated"`.
- Conexión directa docs-to-fixtures: la prueba end-to-end ingesta directamente los 9 bloques JSON extraídos de `evidence-engine.md` sin intermediarios ni duplicación, validando la ingesta y verificación de los 9 tipos vía CLI (`rapid evidence verify`).

### 5.3 Verificación de Quality Gates

- **Python Tests**: 316/316 pruebas exitosas (`discover tests`).
- **Docusaurus TypeScript**: 0 errores de tipo (`npm run typecheck`).
- **Docusaurus Build**: Compilación limpia, 0 enlaces rotos (`npm run build`).
