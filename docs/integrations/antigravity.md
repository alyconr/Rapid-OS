# Integración con Google Antigravity

Guía técnica para gobernar entornos de agentes autónomos y multi-agente en **Google Antigravity** con **RAPID OS v3**.

---

## 1. Qué es Google Antigravity y cómo encaja con RAPID OS

Google Antigravity es un entorno de desarrollo asistido por IA diseñado para pair programming avanzado y ejecución de subagentes especializados con acceso a herramientas de shell, edición de archivos y protocolos MCP.

**Encaje con RAPID OS:**
Antigravity es un harness altamente capaz que puede leer, escribir, ejecutar comandos y delegar en subagentes concurrentes. RAPID OS aporta la estructura determinista de gobernanza: contratos inmutables, gates de riesgo y verificación criptográfica de evidencias generadas por los agentes.

---

## 2. Configuración en RAPID OS

RAPID OS incluye el perfil integrado `antigravity`:

```bash
rapid harness show antigravity
```

Capacidades declaradas:
- `context.consume`: `supported`
- `repository.read`: `supported`
- `workspace.current`: `supported`
- `subagents.delegate`: disponible como capacidad canónica de gobernanza.

---

## 3. Configuración en Antigravity

1. Configura tu espacio de trabajo y MCP servers necesarios en Antigravity.
2. Utiliza reglas de proyecto para instruir al agente principal a verificar siempre el estado de los contratos de RAPID OS antes de declarar una tarea completada.
3. Permite al agente ejecutar pruebas en terminales controladas.

---

## 4. Gobernanza de Tareas Complejas con Subagentes

En tareas de gran envergadura (como refactorizaciones o hardening), Antigravity puede invocar subagentes:

1. **Crear Run:**
```bash
rapid run create --spec spec-complex-refactor --harness antigravity
```

2. **Evidencia de Delegación:**
Si Antigravity delega una subtarea en un subagente especializado, se puede registrar una evidencia canónica de tipo `delegation`:

```json
{
  "schema_version": 1,
  "id": "E002",
  "run_id": "spec-complex-refactor-r1-run-001",
  "kind": "delegation",
  "producer": "harness:antigravity",
  "summary": "Delegación de análisis de dependencias al subagente de arquitectura",
  "task_ids": ["T001"],
  "gate_ids": [],
  "capability_ids": ["subagents.delegate"],
  "payload": {
    "target": "subagent-architect",
    "outcome": "success"
  }
}
```

3. **Evidencia de Pruebas Unitarias:**
El agente ejecuta las pruebas en un entorno temporal y captura la salida con `test_result`.

4. **Evaluación de Cumplimiento:**
```bash
rapid eval run --run <run-id> --write --require-pass
```

El evaluador verificará deterministamente que todas las compuertas, tareas y capacidades requeridas hayan sido satisfechas.
