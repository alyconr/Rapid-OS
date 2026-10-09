---
title: Ingesta y Verificación de Evidencia
description: Cookbook de formatos de evidencia (EvidenceKind), documentos de autoría JSON y verificación de integridad en RAPID OS.
---

# Ingesta y Verificación de Evidencia

El **Evidence Engine** de RAPID OS garantiza que cualquier afirmación sobre la ejecución del trabajo (pruebas ejecutadas, revisiones aprobadas, archivos editados, comandos ejecutados) esté respaldada por registros inmutables, secuenciales y vinculados matemáticamente al contrato y estado activo del run.

---

## Contrato de la Interfaz CLI

La invocación para registrar evidencia en RAPID OS utiliza el subcomando `rapid evidence add`:

```bash
rapid evidence add --run <run-id> --input <ruta-al-archivo-json> [--json]
```

> **Product Truth**: `rapid evidence add` **no** acepta banderas directas como `--kind`, `--producer` o `--summary`. La metadata de autoría, las referencias a tareas/compuertas y el payload específico de cada tipo de evidencia se declaran **dentro del documento JSON de entrada** provisto a `--input`.

Comandos complementarios del Evidence Engine:
```bash
# Listar registros E001..E00N y el digest consolidado del run
rapid evidence list --run <run-id> [--json]

# Inspeccionar el detalle y bindings de una evidencia específica
rapid evidence show --run <run-id> <evidence-id> [--json]

# Verificar la secuencia ordinal, integridad de artefactos y hashes
rapid evidence verify --run <run-id> [--json]
```

---

## Estructura del Documento JSON de Autoría (`Authoring JSON`)

El archivo JSON provisto mediante `--input` debe contener la siguiente estructura canónica:

```json
{
  "kind": "<EvidenceKind>",
  "producer": "<identificador-del-productor>",
  "summary": "<resumen-descriptivo-del-registro>",
  "payload": {
    /* Campos requeridos estrictos según el kind */
  },
  "task_ids": ["T1"],
  "gate_ids": ["gate.tests"],
  "capability_ids": ["tests.execute"],
  "artifacts": ["reports/summary.txt"]
}
```

### Campos del documento de autoría:

| Campo | Obligatorio | Descripción | Restricciones |
| :--- | :--- | :--- | :--- |
| `kind` | **Sí** | Tipo canónico de evidencia | Uno de los 9 valores de [`EvidenceKind`](#los-9-tipos-de-evidencia-evidencekind). |
| `producer` | **Sí** | Identificador del sistema o herramienta que produjo la evidencia | Alfanumérico portable. Si incluye prefijo con dos puntos (`:`), debe coincidir con el harness del contrato (ej. `harness:codex`) o formato permitido. |
| `summary` | **Sí** | Resumen conciso de la evidencia | Texto portable no vacío. |
| `payload` | **Sí** | Diccionario de datos específicos del tipo | Debe contener **única y estrictamente** los campos requeridos por el tipo. Campos inesperados provocan rechazo inmediato (`RAPID1206`). |
| `task_ids` | No | Lista de identificadores de tareas vinculadas | Deben existir en el `ExecutionContract` del run. |
| `gate_ids` | No | Lista de compuertas de calidad vinculadas | Deben coincidir con los IDs del catálogo canónico presentes en el contrato (`gate.tests`, `gate.baseline`, `gate.review`, etc.). |
| `capability_ids` | No | Capabilities del harness acreditadas | Deben pertenecer al catálogo canónico de capabilities. |
| `artifacts` | No | Archivos fuente a copiar y verificar con SHA-256 | Rutas relativas POSIX existentes. Obligatorio si `kind == "artifact"`. |

---

## Los 9 tipos de Evidencia (`EvidenceKind`)

A continuación se presentan los documentos JSON completos y válidos para cada uno de los 9 tipos soportados, listos para ser utilizados con `rapid evidence add --run <run-id> --input <file>`.

### 1. `test_result` (Resultados de Pruebas Automatizadas)
Registra el resultado cuantitativo de una suite de pruebas.

**Campos requeridos de `payload`**: `suite`, `exit_code`, `passed`, `failed`, `skipped`.

**Archivo `test-evidence.json`**:
```json
{
  "kind": "test_result",
  "producer": "pytest",
  "summary": "Suite de tests unitarios aprobada al 100%",
  "gate_ids": ["gate.tests"],
  "capability_ids": ["tests.execute"],
  "payload": {
    "suite": "unit-tests",
    "exit_code": 0,
    "passed": 42,
    "failed": 0,
    "skipped": 1
  }
}
```

**Ejecución**:
```bash
rapid evidence add --run feature-auth-r1-run-001 --input test-evidence.json
```

---

### 2. `command_result` (Resultado de Comandos o Herramientas)
Registra la salida y código de retorno de comandos de terminal, linters o herramientas del sistema.

**Campos requeridos de `payload`**: `label`, `exit_code`.

**Archivo `command-evidence.json`**:
```json
{
  "kind": "command_result",
  "producer": "ruff",
  "summary": "Verificación estática de código con Ruff",
  "capability_ids": ["shell.execute"],
  "payload": {
    "label": "ruff check .",
    "exit_code": 0
  }
}
```

**Ejecución**:
```bash
rapid evidence add --run feature-auth-r1-run-001 --input command-evidence.json
```

---

### 3. `file_change` (Modificación de Archivos del Repositorio)
Registra las rutas relativas de los archivos tocados durante la implementación.

**Campos requeridos de `payload`**: `paths` (lista de rutas relativas POSIX no vacía).

**Archivo `file-change-evidence.json`**:
```json
{
  "kind": "file_change",
  "producer": "git-inspector",
  "summary": "Archivos implementados en el servicio de autenticación",
  "capability_ids": ["repository.write"],
  "payload": {
    "paths": [
      "src/auth/service.py",
      "tests/unit/test_auth.py"
    ]
  }
}
```

**Ejecución**:
```bash
rapid evidence add --run feature-auth-r1-run-001 --input file-change-evidence.json
```

---

### 4. `git_result` (Operaciones del Repositorio Git)
Registra operaciones del control de versiones.

**Campos requeridos de `payload`**: `operation` (estrictamente `"inspect"` o `"modify"`).

**Archivo `git-evidence.json`**:
```json
{
  "kind": "git_result",
  "producer": "git-cli",
  "summary": "Inspección de estado y diff limpio del working tree",
  "capability_ids": ["git.inspect"],
  "payload": {
    "operation": "inspect"
  }
}
```

**Ejecución**:
```bash
rapid evidence add --run feature-auth-r1-run-001 --input git-evidence.json
```

---

### 5. `workspace` (Modo y Aislamiento del Espacio de Trabajo)
Acredita el cumplimiento del requisito de espacio de trabajo o la compuerta `workspace_isolation`.

**Campos requeridos de `payload`**: `mode` (estrictamente `"current"` o `"isolated"`).

**Archivo `workspace-evidence.json`**:
```json
{
  "kind": "workspace",
  "producer": "workspace-manager",
  "summary": "Entorno de ejecución verificado en rama de trabajo",
  "gate_ids": ["gate.workspace-isolation"],
  "capability_ids": ["workspace.current"],
  "payload": {
    "mode": "current"
  }
}
```

**Ejecución**:
```bash
rapid evidence add --run feature-auth-r1-run-001 --input workspace-evidence.json
```

---

### 6. `review` (Revisiones Formales por Pares o Seguridad)
Registra la aprobación formal de compuertas como `gate.review`, `gate.security-review` o `gate.manual-approval`.

**Campos requeridos de `payload`**:
- `review_type`: estrictamente `"peer"`, `"security"`, `"migration"`, `"manual"`, o `"final"`.
- `outcome`: estrictamente `"approved"`, `"changes_requested"`, o `"rejected"`.
- `reviewer`: identificador portable del revisor (sin diagonales `/`).

**Archivo `review-evidence.json`**:
```json
{
  "kind": "review",
  "producer": "github-pr",
  "summary": "Aprobación técnica de revisión por pares",
  "gate_ids": ["gate.review"],
  "payload": {
    "review_type": "peer",
    "outcome": "approved",
    "reviewer": "lead-architect"
  }
}
```

**Ejecución**:
```bash
rapid evidence add --run feature-auth-r1-run-001 --input review-evidence.json
```

---

### 7. `tool_invocation` (Invocación de Herramientas o Analizadores)
Registra la ejecución de analizadores de tipos, linters o herramientas de desarrollo.

**Campos requeridos de `payload`**:
- `tool_id`: identificador de la herramienta (sin diagonales `/`).
- `outcome`: estrictamente `"success"` o `"failure"`.

**Archivo `tool-evidence.json`**:
```json
{
  "kind": "tool_invocation",
  "producer": "typecheck-runner",
  "summary": "Análisis de tipos estáticos ejecutado exitosamente",
  "payload": {
    "tool_id": "mypy",
    "outcome": "success"
  }
}
```

**Ejecución**:
```bash
rapid evidence add --run feature-auth-r1-run-001 --input tool-evidence.json
```

---

### 8. `delegation` (Delegación de Subtareas o Servicios Externos)
Registra la transferencia o delegación a un servicio o subagente.

**Campos requeridos de `payload`**:
- `target`: identificador del destinatario delegado (sin diagonales `/`).
- `outcome`: estrictamente `"success"` o `"failure"`.

**Archivo `delegation-evidence.json`**:
```json
{
  "kind": "delegation",
  "producer": "orchestrator",
  "summary": "Delegación de compilación de assets al pipeline de frontend",
  "capability_ids": ["subagents.delegate"],
  "payload": {
    "target": "frontend-build-worker",
    "outcome": "success"
  }
}
```

**Ejecución**:
```bash
rapid evidence add --run feature-auth-r1-run-001 --input delegation-evidence.json
```

---

### 9. `artifact` (Archivos Adjuntos Verificados por Hash)
Permite adjuntar archivos del proyecto (reportes de cobertura, logs, binarios) que son copiados físicamente a `.rapid-os/evidence/<run-id>/artifacts/<evidence-id>/` y protegidos por digest SHA-256.

**Campos requeridos de `payload`**: `label`.  
**Campo adicional requerido en el documento de autoría**: `artifacts` (lista de rutas relativas a archivos existentes).

**Archivo `artifact-evidence.json`**:
```json
{
  "kind": "artifact",
  "producer": "coverage-agent",
  "summary": "Reporte consolidado de cobertura de código",
  "artifacts": [
    "reports/coverage.json"
  ],
  "payload": {
    "label": "coverage-report"
  }
}
```

**Ejecución**:
```bash
rapid evidence add --run feature-auth-r1-run-001 --input artifact-evidence.json
```

---

## Gestión y Comportamiento de Artefactos (`Artifacts`)

Cuando un documento de autoría incluye el arreglo `"artifacts"`:
1. **Copia Segura**: RAPID OS lee el archivo de origen (ej. `reports/coverage.json`), verifica que no sea un enlace simbólico y lo copia a `.rapid-os/evidence/<run-id>/artifacts/<evidence-id>/reports/coverage.json`.
2. **Cálculo de Digest y Tamaño**: Calcula de forma determinista el hash SHA-256 y el tamaño en bytes (`size_bytes`), registrándolos en el registro `RunEvidence`.
3. **Integridad Inmutable**: Si el archivo copiado en `.rapid-os/evidence/` es posteriormente alterado o eliminado, `rapid evidence verify` detecta la manipulación y emite el diagnóstico `RAPID1205` (`EvidenceArtifactIntegrityError`).

> **Product Truth sobre Autenticidad**: El cálculo del hash SHA-256 verifica la **integridad física local** del archivo copiado frente al registro inmutable. No constituye una atestación criptográfica externa ni garantiza la veracidad o fiabilidad del productor que generó el contenido.

---

## Verificación de Integridad (`rapid evidence verify`)

Para comprobar la continuidad de la secuencia y la consistencia matemática de todas las evidencias de un run:

```bash
rapid evidence verify --run feature-auth-r1-run-001
```

Este comando verifica:
- **Secuencia continua**: No existen huecos en la numeración (`E001`, `E002`, `E003` sin omisiones).
- **Binding de Estado y Contrato**: Los digests `contract_digest` y `state_digest` de cada evidencia corresponden exactamente al contrato y estado activo del run.
- **Integridad de Artefactos**: Cada archivo en la carpeta de artefactos coincide en bytes y hash SHA-256 con su declaración en el registro JSON.
- **Hash de Conjunto (`evidence_set_digest`)**: Computa el digest canónico global del conjunto ordenado de evidencias, el cual es insumo para la evaluación de comportamiento con `rapid eval run`.
