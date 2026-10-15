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

## Flujo principal: shortcuts

La forma recomendada de trabajar con Antigravity es con los shortcuts `/rapid-<modo>`. Los 8 shortcuts, el bucle que siguen, la aprobación humana y los errores frecuentes están en la [guía de shortcuts](../guides/shortcuts.md).

### Instalación

```bash
rapid init --shortcuts                                # al inicializar el proyecto
rapid shortcuts install --harness antigravity         # en un proyecto ya inicializado
```

Genera `.agents/skills/rapid-*/SKILL.md` (los 8 shortcuts; [documentación de skills de Antigravity](https://antigravity.google/docs/skills)). Es la misma carpeta que usa Codex: si seleccionas ambos, se escribe una sola vez. Tras actualizar Rapid OS, vuelve a ejecutar `rapid shortcuts install`.

### Invocación

Se invocan con `/` en el chat:

```text
/rapid-feature añadir exportación CSV al informe mensual
```

`/rapid-approve` **no aprueba**: muestra los gates pendientes y la evidencia, y te da el comando para tu terminal. Si Antigravity delega en subagentes, el shortcut sigue siendo el mismo: el bucle `rapid next` → `rapid check` → `rapid finish` y la aprobación humana en tu terminal.

---

## Modo avanzado (comandos v3)

Los comandos v3 (`rapid spec`, `rapid run`, `rapid evidence`, `rapid eval`…) siguen disponibles para CI, depuración y auditoría, y tampoco hace falta usarlos a mano en el día a día. La sección 4 conservan el flujo manual completo.

## 4. Gobernanza de Tareas Complejas con Subagentes

En tareas de gran envergadura (como refactorizaciones o hardening), Antigravity puede invocar subagentes:

1. **Crear Run:**
```bash
rapid run create --spec spec-complex-refactor --harness antigravity
```

2. **Verificar Baseline:**
Ejecuta las pruebas iniciales guardando el log auténtico como artefacto (`base.log`), registra la evidencia de baseline (conforme a [`evidence_baseline.json`](../tutorials/first-governed-project.md#1-registrar-evidencia-de-baseline-y-acreditar-gatebaseline)) y reconoce `gate.baseline` antes de activar el run:
```bash
python -m unittest discover -s tests -t . > base.log 2>&1
rapid evidence add --run <run-id> --input evidence_baseline.json
rapid run gate <run-id> gate.baseline acknowledged
rapid run status <run-id> active
rapid run task <run-id> T001 in_progress
```

3. **Evidencia de Delegación:**
Si Antigravity delega una subtarea en un subagente especializado, se puede registrar una evidencia canónica de tipo `delegation`:

```json
{
  "kind": "delegation",
  "producer": "antigravity-orchestrator",
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

4. **Evidencia de Pruebas Unitarias:**
El agente ejecuta las pruebas en un entorno temporal y captura la salida con `test_result`.

5. **Evaluación de Cumplimiento:**
```bash
rapid eval run --run <run-id> --write --require-pass
```

El evaluador verificará deterministamente que todas las compuertas, tareas y capacidades requeridas hayan sido satisfechas.
