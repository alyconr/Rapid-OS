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
Ejecuta las pruebas iniciales y registra la evidencia de baseline antes de activar el run:
```bash
python -m unittest discover -s tests -t .
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
Usa el CLI de RAPID OS en la terminal para registrar el progreso:
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
