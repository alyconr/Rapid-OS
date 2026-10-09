---
title: Límites y fronteras del producto
description: Qué hace y qué NO hace Rapid OS v3. Separación estricta de responsabilidades.
---

# Límites y fronteras del producto

Para utilizar Rapid OS con éxito es indispensable comprender sus fronteras técnicas. Rapid OS es una capa de **gobernanza, especificación, auditoría y control de calidad**. No es un ejecutor de modelos ni un agente autónomo.

---

## Separación estricta de conceptos

Una de las fuentes más comunes de error en herramientas de IA es confundir declaraciones humanas con hechos físicos o conclusiones lógicas. Rapid OS establece distinciones rigurosas:

```text
Declaración != Capability != Evidencia != Evaluación
```

1. **Gate Acknowledged:** Un operador humano o script declara que un control fue satisfecho (`ACKNOWLEDGED`). Esto es una declaración, **no constituye evidencia** de que el código funcione.
2. **Harness Compatible:** Un harness declara que soporta `tests.execute`. Esto significa que la herramienta *dice poder correr pruebas*, **no prueba** que las haya ejecutado.
3. **Run Evidence:** Se almacena el archivo de salida con el exit code `0` del ejecutor de tests y su hash SHA-256. Esto es **evidencia física**.
4. **Evaluation PASS:** El evaluador analiza la evidencia registrada bajo reglas deterministas y emite un veredicto. Esto es una **evaluación formal**.

---

## Qué NO hace Rapid OS

:::warning Fronteras explícitas
Rapid OS mantiene un alcance estricto de ingeniería determinista. Las siguientes operaciones están fuera de su diseño:
:::

- **No invoca automáticamente LLMs o APIs de modelos:** Rapid OS no llama a OpenAI, Anthropic, Google u otros proveedores en segundo plano. La interacción con el modelo de lenguaje ocurre en el coding harness que el desarrollador decida utilizar (Codex, Claude, Cursor, Antigravity, etc.).
- **No orquesta agentes autónomos de fondo:** No es un daemon de ejecución continua ni un runtime de agentes recursivos.
- **No utiliza LLM-as-a-judge:** Las evaluaciones de comportamiento (`rapid eval`) son 100% deterministas, ejecutadas mediante código Python de la biblioteca estándar contra reglas lógicas.
- **No ejecuta comandos arbitrarios del repositorio durante la gobernanza:** `rapid scan`, `rapid context`, `rapid spec` y `rapid validate` no corren scripts arbitrarios del usuario. Operan de forma estática o leen archivos de configuración.
- **No crea automáticamente branches o worktrees de Git:** Cuando una política exige `workspace.isolated`, Rapid OS declara la necesidad en el contrato; la creación efectiva del entorno aislado o rama corresponde al operador o al harness.
- **No es una sandbox de sistema operativo:** Las "capabilities" en Rapid OS son declaraciones de capacidades de software, no jaulas de seguridad de kernel o contenedores forzados.
- **No garantiza matemáticamente ausencia de defectos:** Un veredicto `PASS` certifica que las reglas del contrato y la evidencia registrada fueron satisfechas. No equivale a una prueba formal de corrección matemática de todo el software ni sustituye el criterio de los ingenieros.

---

## Qué SÍ hace Rapid OS

- Analiza repositorios de forma determinista y extrae hechos con procedencia (`rapid scan`).
- Mantiene especificaciones de software con revisiones inmutables (`rapid spec`).
- Compila contexto estructurado respetando presupuestos estrictos de caracteres (`rapid context`).
- Modela políticas de riesgo y gates de control (`rapid policy`).
- Emite contratos inmutables de ejecución vinculados por digests SHA-256 (`rapid run`).
- Modela y valida capabilities declaradas por herramientas de codificación (`rapid harness`).
- Registra y custodia artefactos de evidencia de ejecución (`rapid evidence`).
- Evalúa evidencia física offline mediante reglas reproducibles (`rapid eval`).
- Audita la integridad cruzada completa del proyecto (`rapid validate`).
