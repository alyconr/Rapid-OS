# Integración con Anthropic Claude Code

Guía técnica para gobernar flujos interactivos y de terminal con **Claude Code** utilizando **RAPID OS v3**.

---

## 1. Qué es Claude Code y cómo encaja con RAPID OS

Claude Code es una herramienta de desarrollo en línea de comandos de Anthropic diseñada para operar directamente sobre bases de código mediante herramientas de edición, búsqueda y ejecución de comandos.

**Encaje con RAPID OS:**
Claude Code opera como el agente ejecutor externo. RAPID OS opera como el marco de gobernanza, definiendo la especificación previa, controlando el riesgo arquitectónico y evaluando mediante evidencia determinista que todo lo prometido se haya cumplido antes de dar por buena la tarea.

---

## 2. Configuración en RAPID OS

RAPID OS incluye el identificador de perfil `claude`:

```bash
rapid harness show claude
```

Perfil declarativo:
- `context.consume`: `supported`
- `repository.read`: `supported`
- `workspace.current`: `supported`
- Otras capacidades: marcadas como `unknown` hasta que el entorno local las configure explícitamente en el proyecto.

---

## 3. Configuración en Claude Code

1. Inicia sesión en Claude Code siguiendo las guías oficiales (`claude login`).
2. Concede permisos para ejecutar tests locales y editar archivos según las políticas de tu equipo.
3. Asegura que Claude Code lea el archivo `.rapid-os/standards/` para alinearse con los estándares arquitectónicos del proyecto.

---

## 4. Flujo de Trabajo Gobernado

1. **Crear Spec y Run en RAPID OS:**
```bash
rapid spec create --id spec-feature --title "Nueva funcionalidad" --mode feature --status ready
rapid context --manifest
rapid run create --spec spec-feature --harness claude
```

2. **Instruir a Claude Code:**
Pide a Claude Code en la terminal:
> *"Lee la especificación en `.rapid-os/specs/spec-feature/spec.json` y el contrato en `.rapid-os/contracts/<run-id>.json`. Implementa los cambios necesarios y corre la suite de pruebas."*

3. **Ejecución Externa:**
Claude Code edita los archivos y corre `python -m unittest`.

4. **Captura e Ingesta de Evidencias:**
El desarrollador o el propio Claude Code invoca el CLI de RAPID OS para registrar el avance:
```bash
rapid run status <run-id> active
rapid run task <run-id> T001 in_progress
rapid evidence add --run <run-id> --input evidence_files.json
rapid evidence add --run <run-id> --input evidence_tests.json
rapid run gate <run-id> gate.tests acknowledged
rapid run gate <run-id> gate.final-verification acknowledged
rapid run task <run-id> T001 done
rapid run status <run-id> finished
```

5. **Evaluación:**
```bash
rapid eval run --run <run-id> --write --require-pass
```

---

## 5. Problemas Frecuentes

- **Claude Code edita sin correr pruebas:** La evaluación marcará `fail` o `unverified` si no se aporta evidencia con `test_result` válido.
- **Rutas no canónicas:** Las rutas en los payloads de evidencia deben ser rutas relativas POSIX (ej. `src/app.py`, no rutas absolutas con `C:\`).
