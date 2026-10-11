# Integración con Visual Studio Code

Guía técnica para gobernar entornos de desarrollo en **Visual Studio Code** y GitHub Copilot con **RAPID OS v3**.

---

## 1. Qué es y cómo encaja con RAPID OS

Visual Studio Code es el editor de código estándar ampliamente extendido que ofrece terminales integradas, paneles de depuración y extensiones de IA como GitHub Copilot Chat.

**Encaje con RAPID OS:**
El desarrollador trabaja en VS Code utilizando su terminal integrada para ejecutar comandos de `rapid` y Copilot Chat para asistir la escritura de código. RAPID OS garantiza que cada cambio tenga un contrato trazable y evidencia de pruebas verificable.

---

## 2. Configuración en RAPID OS

RAPID OS incluye el perfil integrado `vscode`:

```bash
rapid harness show vscode
```

Salida canónica:
- `context.consume`: `supported`
- `repository.read`: `supported`
- `workspace.current`: `supported`
- Capacidades de ejecución y escritura: configurables según las extensiones locales instaladas.

---

## 3. Configuración en VS Code

1. Abre el repositorio en VS Code.
2. Abre la terminal integrada (`Ctrl+\`` o `Cmd+\``).
3. Asegura que el entorno virtual de Python esté seleccionado en la barra de estado.

---

## 4. Flujo de Trabajo en VS Code

1. **Creación del Run:**
En la terminal integrada:
```bash
rapid run create --spec <spec-id> --harness vscode
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

3. **Asistencia con Copilot Chat:**
En Copilot Chat, usa `#file:.rapid-os/runs/<run-id>/contract.json` para enfocar al modelo en los objetivos y restricciones de la tarea.

4. **Ejecución de Pruebas:**
Ejecuta la suite de pruebas desde la terminal o mediante el panel de testing de VS Code.

5. **Registro de Evidencias:**
Usa el CLI de RAPID OS en la terminal para registrar el progreso (ver detalles y esquemas en el [Tutorial del Primer Proyecto Gobernado](../tutorials/first-governed-project.md#7-evidence-collection)):
- [`evidence_files.json`](../tutorials/first-governed-project.md#3-registrar-evidencia-de-cambios-en-el-código-file_change): modificación de archivos (`file_change`).
- [`evidence_test_result.json`](../tutorials/first-governed-project.md#4-registrar-evidencia-de-pruebas-aprobadas-test_result): resultado de pruebas con artefacto de log (`test_result`).
- [`evidence_workspace.json`](../tutorials/first-governed-project.md#5-registrar-evidencia-de-espacio-de-trabajo-workspace): espacio de trabajo actual (`workspace.current`).
- [`evidence_review.json`](../tutorials/first-governed-project.md#6-registrar-evidencia-de-revisión-final-review): revisión final contractual aprobada (`review`).

```bash
rapid evidence add --run <run-id> --input evidence_files.json
rapid evidence add --run <run-id> --input evidence_test_result.json
rapid evidence add --run <run-id> --input evidence_workspace.json
rapid evidence add --run <run-id> --input evidence_review.json
rapid run gate <run-id> gate.tests acknowledged
rapid run gate <run-id> gate.final-verification acknowledged
rapid run task <run-id> T001 done
rapid run status <run-id> finished
```

6. **Evaluación Final:**
```bash
rapid eval run --run <run-id> --write --require-pass
```
