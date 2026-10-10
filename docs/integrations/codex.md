# Integración con OpenAI Codex / CLI

Guía técnica para gobernar tareas asistidas por modelos de código en línea de comandos y entornos headless mediante **RAPID OS v3**.

---

## 1. Qué es y cómo encaja con RAPID OS

OpenAI Codex y sus herramientas de línea de comandos asociadas permiten la generación y transformación automatizada de código en entornos automatizados o terminales de desarrollo.

**Encaje con RAPID OS:**
RAPID OS actúa como la capa determinista de gobernanza que define qué cambios están autorizados mediante una especificación (`Spec`) y un contrato (`ExecutionContract`). Codex actúa como el motor de codificación externa que produce los parches y ejecuta comandos.

---

## 2. Configuración en RAPID OS

RAPID OS incluye el perfil integrado `codex`:

```bash
rapid harness show codex
```

Salida declarada:
- `context.consume`: `supported`
- `repository.read`: `supported`
- `workspace.current`: `supported`
- `repository.write`, `shell.execute`, `tests.execute`: `unknown` (declarados como sujetos a los permisos del entorno local).

Para sobreescribir estas capacidades y declarar que tu entorno local autoriza la ejecución de pruebas y modificación de archivos, puedes inicializar un perfil de proyecto en `.rapid-os/harnesses/codex.json`.

---

## 3. Configuración del Usuario en Codex

1. Configura tu entorno de ejecución con las variables y claves de API correspondientes según la documentación oficial de OpenAI.
2. Asegura que la herramienta tenga permisos de lectura y escritura en el repositorio.
3. Configura el sandbox de ejecución local para permitir que la herramienta corra `python -m unittest`.

---

## 4. Entrega del Context Bundle y Spec

RAPID OS compila un paquete de contexto optimizado:

```bash
rapid context --manifest
```

Entrega a la herramienta:
- La especificación activa (`.rapid-os/specs/<spec-id>/spec.json`).
- El manifiesto de contexto compilado (`.rapid-os/context/manifest.json`).
- Las instrucciones del contrato de ejecución (`.rapid-os/contracts/<run-id>.json`).

---

## 5. Respeto del Execution Contract y Herramientas Externas

El harness debe ceñirse a:
- La lista de tareas inmutables (`T001`, `T002`, ...).
- Los archivos autorizados en el alcance (`paths`).
- Las compuertas declaradas en la política.

---

## 6. Registro de Resultados y Evidencia

Una vez que Codex aplique los cambios y ejecute las pruebas en la terminal externa:

1. Ingerir evidencia de los archivos modificados (`file_change`):
```bash
rapid evidence add --run <run-id> --input evidence_files.json
```

2. Ingerir evidencia del resultado de las pruebas (`test_result`):
```bash
rapid evidence add --run <run-id> --input evidence_tests.json
```

3. Actualizar el estado del run:
```bash
rapid run gate <run-id> gate.tests acknowledged
rapid run task <run-id> T001 done
rapid run status <run-id> finished
```

---

## 7. Evaluación Determinista

Evalúa la validez de la ejecución:

```bash
rapid eval run --run <run-id> --write --require-pass
```

---

## 8. Problemas Frecuentes

- **El harness intenta modificar rutas fuera de scope:** La evaluación detectará discrepancias si la evidencia no coincide con las rutas del contrato.
- **Falta de evidencia de pruebas:** No intentes cerrar `gate.tests` sin una evidencia válida de `test_result` con `exit_code: 0`.
