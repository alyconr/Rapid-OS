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

2. **Asistencia con Copilot Chat:**
En Copilot Chat, usa `#file:.rapid-os/contracts/<run-id>.json` para enfocar al modelo en los objetivos y restricciones de la tarea.

3. **Ejecución de Pruebas:**
Ejecuta la suite de pruebas desde la terminal o mediante el panel de testing de VS Code.

4. **Registro de Evidencias:**
Usa el CLI de RAPID OS en la terminal para registrar el progreso:
```bash
rapid evidence add --run <run-id> --input evidence_test_result.json
```

5. **Evaluación Final:**
```bash
rapid eval run --run <run-id> --write --require-pass
```
