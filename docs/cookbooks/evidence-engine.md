---
title: Ingesta y Verificación de Evidencia
description: Cookbook de formatos de evidencia (EvidenceKind), payloads JSON y verificación de integridad en RAPID OS.
---

# Ingesta y Verificación de Evidencia

El **Evidence Engine** de RAPID OS garantiza que cualquier afirmación sobre la ejecución del trabajo (pruebas pasadas, revisiones aprobadas, archivos editados) esté respaldada por registros inmutables, secuenciales y vinculados matemáticamente al contrato del run.

---

## Principios de la Evidencia en RAPID OS

1. **Inmutabilidad y Secuencia estricta**: Los registros se guardan como `E001.json`, `E002.json`, ... en `.rapid-os/evidence/<run-id>/`. No se permiten huecos de secuencia ni sobreescrituras.
2. **Vinculación criptográfica**: Cada registro incluye el digest SHA-256 del contrato (`contract_digest`) y del estado del run (`state_digest`).
3. **Determinismo libre de tiempo de reloj**: El payload y el cálculo de digest no dependen de la hora del sistema (`wall-clock timestamp`) para asegurar reproducibilidad.
4. **Artefactos verificados por contenido**: Los archivos pesados adjuntos se copian a la carpeta de evidencia y se verifican por su hash SHA-256 y tamaño en bytes (`size_bytes`).

---

## Los 9 tipos de Evidencia (`EvidenceKind`)

A continuación se presentan ejemplos reales y validados para cada clase de evidencia soportada:

### 1. `test_result` (Resultados de Pruebas)
Registra la ejecución cuantitativa de pruebas unitarias, de integración o end-to-end:

```json
{
  "framework": "pytest",
  "passed": 42,
  "failed": 0,
  "skipped": 2,
  "exit_code": 0,
  "duration_seconds": 1.84,
  "suite": "unit-tests"
}
```

```bash
rapid evidence add \
  --run my-run-001 \
  --kind test_result \
  --producer "ci-runner" \
  --summary "42 tests unitarios pasando al 100%" \
  --input test-payload.json
```

---

### 2. `command_result` (Ejecución de Comandos o Herramientas)
Registra la salida y el código de retorno de linters, formateadores o scripts:

```json
{
  "command": "ruff check .",
  "exit_code": 0,
  "stdout_snippet": "All checks passed!",
  "stderr_snippet": "",
  "duration_seconds": 0.45
}
```

```bash
rapid evidence add \
  --run my-run-001 \
  --kind command_result \
  --producer "ruff-linter" \
  --summary "Linter Ruff ejecutado sin violaciones de estilo" \
  --input ruff-payload.json
```

---

### 3. `file_change` (Modificación de Archivos)
Registra los módulos alterados durante la tarea:

```json
{
  "modified": ["src/payments/service.py", "src/payments/models.py"],
  "added": ["tests/unit/test_webhook_retry.py"],
  "deleted": []
}
```

```bash
rapid evidence add \
  --run my-run-001 \
  --kind file_change \
  --producer "git-inspector" \
  --summary "3 archivos modificados en el módulo payments" \
  --input files-payload.json
```

---

### 4. `git_result` (Operaciones Git y Diffs)
Registra operaciones del control de versiones:

```json
{
  "operation": "diff_summary",
  "commit_sha": "d4e5f6a1b2c3",
  "insertions": 145,
  "deletions": 12,
  "status": "clean"
}
```

```bash
rapid evidence add \
  --run my-run-001 \
  --kind git_result \
  --producer "git-agent" \
  --summary "Diff consolidado del branch de trabajo" \
  --input git-payload.json
```

---

### 5. `workspace` (Aislamiento de Espacio de Trabajo)
Acredita el cumplimiento de la compuerta `workspace_isolation`:

```json
{
  "workspace_type": "git_worktree",
  "branch": "feature/webhook-retry",
  "isolation_mode": "isolated_required",
  "verified_clean": true
}
```

```bash
rapid evidence add \
  --run my-run-001 \
  --kind workspace \
  --producer "workspace-manager" \
  --summary "Ejecución aislada en worktree independiente verificado" \
  --input workspace-payload.json
```

---

### 6. `review` (Revisiones Humanas por Pares o Seguridad)
Registra la aprobación formal requerida por compuertas como `peer_review` o `security_review`:

```json
{
  "reviewer": "senior-engineer@company.com",
  "review_type": "peer_review",
  "outcome": "approved",
  "comments": "Implementación limpia y compatible con versiones anteriores"
}
```

```bash
rapid evidence add \
  --run my-run-001 \
  --kind review \
  --producer "github-pr-review" \
  --summary "Aprobación formal de revisión por pares" \
  --input review-payload.json
```

---

### 7. `tool_invocation` (Invocación de Herramientas del Entorno)
Registra el uso de compiladores, generadores de código o analizadores de tipos:

```json
{
  "tool_name": "mypy",
  "version": "1.10.0",
  "exit_code": 0,
  "target_directory": "src/"
}
```

```bash
rapid evidence add \
  --run my-run-001 \
  --kind tool_invocation \
  --producer "typechecker" \
  --summary "Validación estática de tipos con Mypy estricto" \
  --input mypy-payload.json
```

---

### 8. `delegation` (Delegación de Tareas o Aprobaciones)
Registra la transferencia o aprobación por un sistema externo:

```json
{
  "delegated_to": "compliance-pipeline",
  "ticket_id": "SEC-8891",
  "status": "authorized"
}
```

```bash
rapid evidence add \
  --run my-run-001 \
  --kind delegation \
  --producer "jira-service-desk" \
  --summary "Autorización de cambio por equipo de compliance" \
  --input delegation-payload.json
```

---

### 9. `artifact` (Archivos Adjuntos Verificados)
Permite anexar reportes pesados externos (ej. reportes HTML de cobertura, snapshots binarios o logs extensos):

```json
{
  "artifact_type": "coverage_report",
  "format": "json",
  "line_coverage_pct": 94.5
}
```

```bash
rapid evidence add \
  --run my-run-001 \
  --kind artifact \
  --producer "coverage-tool" \
  --summary "Reporte estructurado de cobertura de código" \
  --input coverage-summary.json
```

---

## 3. Verificación de Integridad (`rapid evidence verify`)

Para asegurar que ningún archivo de evidencia fue alterado manualmente, eliminado o dañado en el disco:

```bash
rapid evidence verify --run my-run-001
```

Este comando verifica:
- Continuidad estricta de la numeración (`E001`, `E002`, ...).
- Correspondencia exacta del `content_digest` calculado.
- Consistencia del hash SHA-256 de los artefactos copiados en disco.
- Coincidencia del `contract_digest` con el contrato del run.
