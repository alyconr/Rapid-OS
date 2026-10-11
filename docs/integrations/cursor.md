# Integración con Cursor IDE

Aprende a integrar **Cursor** (Composer y reglas de workspace) con la arquitectura determinista de **RAPID OS v3**.

---

## 1. Qué es Cursor y cómo encaja con RAPID OS

Cursor es un editor de código bifurcado de VS Code optimizado para asistencia por IA en múltiples archivos a través de Composer, chat contextual y reglas de proyecto.

**Encaje con RAPID OS:**
Cursor proporciona la interfaz de usuario y las capacidades de edición asistida en el editor, mientras que RAPID OS gobierna el ciclo de vida del cambio técnico, evitando que el modelo haga modificaciones no autorizadas o cierre tareas sin evidencia de pruebas reales.

---

## 2. Configuración en RAPID OS

El perfil `cursor` viene predefinido en RAPID OS:

```bash
rapid harness show cursor
```

Declara soporte nativo para consumir contexto y operar en el workspace actual del editor.

---

## 3. Configuración en Cursor (`.cursorrules`)

Para que el modelo en Cursor respete automáticamente las reglas de RAPID OS, agrega en la raíz de tu proyecto un archivo `.cursorrules`:

```markdown
# Reglas de Gobernanza RAPID OS
1. Antes de iniciar cualquier tarea, consulta `.rapid-os/specs/` para conocer los requerimientos.
2. No modifiques archivos que no formen parte del alcance del contrato de ejecución actual.
3. Tras modificar código, ejecuta siempre las pruebas unitarias en la terminal.
4. No des por finalizada una tarea sin generar y registrar la evidencia en RAPID OS.
```

---

## 4. Flujo de Trabajo en Cursor Composer

1. **Crear Run:**
```bash
rapid run create --spec <spec-id> --harness cursor
```

2. **Verificar Baseline:**
Ejecuta las pruebas base, registra la evidencia de baseline y reconoce `gate.baseline` antes de activar el run:
```bash
python -m unittest discover -s tests -t .
rapid evidence add --run <run-id> --input evidence_baseline.json
rapid run gate <run-id> gate.baseline acknowledged
rapid run status <run-id> active
rapid run task <run-id> T001 in_progress
```

3. **Inyectar Contexto en Composer:**
En la ventana de Composer de Cursor, referencia el archivo generado:
> `@.rapid-os/runs/<run-id>/contract.json implementa la tarea T001 y corre las pruebas.`

4. **Verificar Pruebas en Terminal:**
Comprueba que los tests pasen en la terminal integrada de Cursor.

5. **Registrar Evidencia:**
Ingiere los resultados mediante `rapid evidence add`:
```bash
rapid evidence add --run <run-id> --input evidence_files.json
rapid evidence add --run <run-id> --input evidence_tests.json
rapid evidence add --run <run-id> --input evidence_workspace.json
rapid evidence add --run <run-id> --input evidence_review.json
rapid run gate <run-id> gate.tests acknowledged
rapid run gate <run-id> gate.final-verification acknowledged
rapid run task <run-id> T001 done
rapid run status <run-id> finished
```

6. **Evaluar:**
```bash
rapid eval run --run <run-id> --write --require-pass
```

---

## 5. Problemas Frecuentes

- **Composer añade archivos temporales no deseados:** Asegúrate de que `.gitignore` excluya archivos temporales y que solo las rutas necesarias figuren en la evidencia de tipo `file_change`.
