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

## Flujo principal: shortcuts

La forma recomendada de trabajar con Cursor es con los shortcuts `/rapid-<modo>`. Los 9 shortcuts, el bucle que siguen, la aprobación humana y los errores frecuentes están en la [guía de shortcuts](../guides/shortcuts.md).

### Instalación

```bash
rapid init --shortcuts                                # al inicializar el proyecto
rapid shortcuts install --harness cursor              # en un proyecto ya inicializado
```

Genera `.cursor/skills/rapid-*/SKILL.md` (los 9 shortcuts; [documentación de skills de Cursor](https://cursor.com/docs/context/skills)). Tras actualizar Rapid OS, vuelve a ejecutar `rapid shortcuts install`. `.cursorrules` sigue aportando las reglas del proyecto.

### Primer paso: `/rapid-init` (onboarding)

El punto de entrada de un proyecto es `/rapid-init`: conduce el onboarding (`rapid setup next`), te pregunta el stack de cada componente, la arquitectura, los servicios y los documentos, y revisa contigo los borradores antes de cerrar. Después usas `/rapid-feature` y los demás modos. Ver [Primer proyecto](../getting-started/first-project.md).

Para tener `/rapid-init` y los demás shortcuts en todos tus proyectos sin instalarlos en cada uno, instálalos en tu carpeta de usuario (`~/.cursor/skills/`); el instalador de Rapid OS te lo pregunta al terminar:

```bash
rapid shortcuts install --global --harness cursor
```

Los shortcuts y los hooks ejecutan `rapid` desde el shell del agente: si no está en el `PATH`, `rapid init` y `rapid doctor` avisan con `RAPID1414` (aviso, no error). Ver la [guía de shortcuts](../guides/shortcuts.md).

### Invocación

En el chat del Agent escribe `/` y busca el shortcut:

```text
/rapid-feature añadir exportación CSV al informe mensual
```

- `/rapid-approve` lleva `disable-model-invocation`: solo se incluye si lo invocas tú. **No aprueba**: te da el comando para tu terminal (`RAPID1310` si lo intenta un agente).
- Cursor lee además `.agents/skills/` y `.claude/skills/`. Si usas Cursor junto con Claude Code, Codex o Antigravity, consulta [cómo combinar harnesses](../guides/shortcuts.md#si-combinas-harnesses) antes de añadir `cursor` a la instalación.

---

## Modo avanzado (comandos v3)

Los comandos v3 (`rapid spec`, `rapid run`, `rapid evidence`, `rapid eval`…) siguen disponibles para CI, depuración y auditoría, y tampoco hace falta usarlos a mano en el día a día. Las secciones 4 y 5 conservan el flujo manual completo.

## 4. Flujo de Trabajo en Cursor Composer

1. **Crear Run:**
```bash
rapid run create --spec <spec-id> --harness cursor
```

2. **Verificar Baseline:**
Ejecuta las pruebas base guardando el log auténtico como artefacto (`base.log`), registra la evidencia de baseline (conforme a [`evidence_baseline.json`](../tutorials/first-governed-project.md#1-registrar-evidencia-de-baseline-y-acreditar-gatebaseline)) y reconoce `gate.baseline` antes de activar el run:
```bash
python -m unittest discover -s tests -t . > base.log 2>&1
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
Ingiere los resultados mediante `rapid evidence add` (ver estructuras en el [laboratorio Bajo el capó](../tutorials/first-governed-project.md#7-evidence-collection)):
- [`evidence_files.json`](../tutorials/first-governed-project.md#3-registrar-evidencia-de-cambios-en-el-código-file_change): evidencia de modificación de archivos.
- [`evidence_tests.json`](../tutorials/first-governed-project.md#4-registrar-evidencia-de-pruebas-aprobadas-test_result): resultado de pruebas con log adjunto.
- [`evidence_workspace.json`](../tutorials/first-governed-project.md#5-registrar-evidencia-de-espacio-de-trabajo-workspace): espacio de trabajo actual (`workspace.current`).
- [`evidence_review.json`](../tutorials/first-governed-project.md#6-registrar-evidencia-de-revisión-final-review): revisión contractual aprobada.

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
