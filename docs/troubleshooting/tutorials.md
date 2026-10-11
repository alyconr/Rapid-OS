# Troubleshooting en Laboratorios y Tutoriales

Guía de resolución de problemas e incidencias comunes al ejecutar los laboratorios prácticos de **RAPID OS v3**.

---

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
