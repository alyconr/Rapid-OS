---
title: Tu primer proyecto gobernado con RAPID OS
description: De una carpeta vacía a tu primera funcionalidad aprobada con /rapid-init y /rapid-feature, y el mismo recorrido con los comandos v3 como modo avanzado.
---

# Tu primer proyecto gobernado con RAPID OS

De una carpeta vacía a tu primera funcionalidad terminada y aprobada. Escribes tres cosas en tu agente y una en tu terminal.

- **Necesitas:** Rapid OS instalado (`rapid --version` responde) y un agente de código (Claude Code, Codex, Cursor, Antigravity o VS Code).
- **Tiempo:** unos 15 minutos.

---

## Camino principal: `/rapid-init`

### 1. Ten los shortcuts disponibles

Si al instalar Rapid OS respondiste con tu agente a la pregunta de los shortcuts, ya están. Si no, una sola vez:

```bash
rapid shortcuts install --global --harness claude
```

Cambia `claude` por `codex`, `cursor` o `antigravity`. En VS Code (o si prefieres los shortcuts dentro del repositorio) usa `rapid init --shortcuts` en la carpeta del proyecto.

### 2. Crea la carpeta y describe el proyecto

```bash
mkdir hello-rapid && cd hello-rapid
```

Abre tu agente en esa carpeta y escribe (en Codex, `$rapid-init`):

```text
/rapid-init una API en Python para validar nombres de usuario
```

### 3. Responde a sus propuestas

El agente te pregunta, una decisión a la vez: stack, topología, arquetipo (MVP o Corporate), comando de tests y los cuatro documentos del proyecto (brief, reglas de negocio, modelo de datos y arquitectura). Para cada decisión te recomienda una opción y una alternativa. Para cada documento eliges:

- **Pegarlo** si ya lo tienes.
- **Que lo redacte el agente**: te muestra el borrador completo antes de guardarlo.
- **Omitirlo**.

Lo que redacta el agente queda como **borrador**. Antes de cerrar te resume cada uno y te pregunta si lo confirmas: confirmado pasa a ser regla del proyecto; sin confirmar queda como supuesto que el agente puede cuestionar. Solo se confirma lo que tú digas explícitamente.

<details>
<summary>Qué ejecuta el agente por debajo</summary>

Los mismos comandos que puedes usar tú sin agente:

```bash
rapid setup next --json
rapid setup set stack python-fastapi
rapid setup set archetype mvp
rapid setup set test-command "python -m unittest discover"
rapid setup doc business --source drafted --file -   # el cuerpo por stdin; queda como borrador
rapid setup doc brief --skip
rapid setup review --done
rapid setup finish
```

Todos están en la [referencia de `rapid setup`](../cli.md#onboarding-rapid-setup).

</details>

### 4. Pide tu primera funcionalidad

```text
/rapid-feature añadir una función validate_username a app.py
```

Sin argumentos, `/rapid-feature` te propone la primera historia sin marcar del brief (`- [ ] H001: ...`) y espera tu confirmación. El agente redacta la spec, implementa tarea por tarea y corre los tests.

### 5. Aprueba en tu terminal

Cuando termina, el agente se detiene y te da el comando exacto. Ejecútalo en **otra terminal**, fuera del agente:

```bash
rapid approve gate.final-verification
```

Vuelve al agente y escribe `/rapid-next`: el run se cierra con su veredicto. Listo: tu primera funcionalidad quedó implementada, probada y aprobada por ti.

:::note Sin agente: `rapid init`
`rapid init` hace el onboarding desde la terminal con preguntas interactivas. Es la alternativa si no usas un agente; lo que no resuelvas queda pendiente para `/rapid-init`.
:::

### Siguientes pasos

- Un laboratorio por modo, con proyectos de ejemplo: [Laboratorios](../tutorials/index.md).
- Adoptarlo en un repositorio que ya tiene código: [Gobernar un proyecto existente](./existing-project.md).

---

## Modo avanzado (comandos v3)

No lo necesitas para usar Rapid OS: es el mismo proyecto hecho a mano con los comandos v3 (`rapid scan`, `rapid spec`, `rapid context`…), útil para entender qué registra cada paso, para CI y para auditoría.

<details>
<summary>Ver el recorrido con los comandos v3</summary>

---

## Escenario: el proyecto `hello-rapid`

Vamos a crear un directorio de trabajo aislado con un script básico en Python:

```text
hello-rapid/
├── app.py
└── README.md
```

---

## Paso 1: Crear el proyecto mínimo

Abre tu terminal y ejecuta los siguientes comandos para preparar el directorio:

```bash
mkdir hello-rapid
cd hello-rapid

# Crear un archivo Python inicial
echo 'def main():\n    print("Hello from Rapid OS governed project")\n\nif __name__ == "__main__":\n    main()' > app.py

# Crear un archivo README básico
echo '# Hello Rapid Project\nProyecto de demostración para Rapid OS.' > README.md
```

---

## Paso 2: Inicializar RAPID OS (alternativa: `rapid init`)

Si no usaste `/rapid-init`, ejecuta el comando de inicialización en la raíz del proyecto:

```bash
rapid init --archetype mvp --no-scan
```

*(También puedes ejecutar simplemente `rapid init` para utilizar el asistente interactivo).*

Además de los estándares, `rapid init` te pregunta por cuatro documentos del proyecto (`docs/PRODUCT_BRIEF.md`, `docs/BUSINESS_RULES.md`, `docs/DATA_MODEL.md` y `docs/ARCHITECTURE.md`). Para cada uno puedes: 1) importar un archivo, 2) escribirlo ahí mismo (termina con dos líneas vacías), 3) dejarlo para tu agente (`/rapid-init`) u 4) omitirlo. Con `--yes` quedan pendientes, y puedes pasar `--business-file <ruta>` para importar las reglas de negocio o `--skip-docs` para omitir los cuatro. Si quedan pendientes, `init` termina con `Completa la documentación con /rapid-init o rapid setup next`.

### ¿Qué ocurre internamente?
Rapid OS genera la estructura fundamental de gobernanza y archivos de contexto para los principales agentes de IA:

```text
hello-rapid/
├── .rapid-os/
│   ├── config.json              # Configuración del proyecto y stack
│   └── standards/
│       ├── tech-stack.md        # Definición del stack tecnológico
│       ├── topology.md          # Topología y arquitectura
│       └── ...
├── .cursorrules                 # Reglas de contexto para Cursor IDE
├── CLAUDE.md                    # Instrucciones de contexto para Claude / Anthropic
├── .agent/rules/constitution.md # Constitución para Antigravity
├── INSTRUCTIONS.md              # Estándares generales para coding agents
└── AGENTS.md                    # Mapeo de roles de agentes
```

:::note Respaldo automático con .bak
Si alguno de estos archivos ya existía previamente, Rapid OS crea una copia de seguridad con extensión `.bak` para evitar pérdida accidental de información.
:::

---

## Paso 3: Analizar el proyecto en modo lectura (`rapid scan`)

Ejecuta un escaneo determinista del repositorio:

```bash
rapid scan --verbose
```

### Conceptos clave del escaneo:
- **`ProjectModel`:** El modelo de datos resultante que unifica el conocimiento del repositorio.
- **`ProjectFact`:** Cada hecho técnico identificado (lenguaje Python detectado, estructura de archivos, etc.).
- **`Evidence`:** Procedencia demostrable de cada hecho (archivo leído, motivo de detección y nivel de confianza asignado).
- **Modo solo lectura:** `rapid scan` no modifica ningún archivo del repositorio a menos que se le indique explícitamente.

---

## Paso 4: Persistir Project Intelligence (`rapid scan --write`)

Para que los siguientes comandos del ciclo puedan consumir la inteligencia del proyecto sin volver a escanear el disco cada vez, persiste la instantánea:

```bash
rapid scan --write
```

Este comando escribe el archivo `.rapid-os/project.json` (`schema_version = 1`), que servirá como base de conocimiento estática e inmutable para la compilación de contexto y los contratos de ejecución.

---

## Paso 5: Crear tu primera especificación (`rapid spec create`)

En lugar de escribir un prompt suelto en un chat, define una especificación formal para la tarea: *"Implementar una función que valide nombres de usuario alfanuméricos"*:

```bash
rapid spec create \
  --id validate-username \
  --title "Validate Username Function" \
  --mode feature \
  --objective "Validar formato seguro de nombres de usuario" \
  --problem "Actualmente el sistema no valida caracteres especiales en nombres de usuario" \
  --scope "Crear función validate_username(username) que permita sólo caracteres alfanuméricos y guiones" \
  --acceptance "validate_username('juan_123') retorna True" \
  --acceptance "validate_username('juan@123') retorna False" \
  --task "Implementar función validate_username en app.py" \
  --status ready
```

### ¿Qué se generó?
Rapid OS crea el directorio `.rapid-os/specs/validate-username/` con:
- `spec.json`: Metadatos del registro.
- `revisions/0001.json`: La revisión inmutable congelada en estado `ready` con su correspondiente digest SHA-256 (`content_digest`).

---

## Paso 6: Consultar la especificación

Comprueba que la especificación esté registrada:

```bash
rapid spec list
```

**Salida esperada:**
Muestra la lista de specs registradas con su ID (`validate-username`), modo (`feature`), revisión actual (`0001`) y estado (`ready`).

Para ver los detalles completos de la especificación:
```bash
rapid spec show validate-username
```

---

## Paso 7: Compilar contexto para el agente (`rapid context`)

Ahora compilaremos el contexto exacto y presupuestado que entregaremos al coding harness (por ejemplo, Codex, Claude o Cursor):

```bash
rapid context \
  --mode feature \
  --spec validate-username \
  --harness codex \
  --manifest
```

### ¿Qué hace el compilador de contexto?
1. **Filtra por modo:** Selecciona únicamente los estándares y hechos del `ProjectModel` relevantes para una tarea de tipo `feature`.
2. **Incorpora la Spec:** Incluye la especificación `validate-username` en estado `ready`.
3. **Aplica presupuesto:** Asegura que el texto resultante no supere el límite de tokens/caracteres.
4. **Genera `ContextManifest`:** Describe las fuentes incluidas, sus tamaños y sus hashes SHA-256.
5. **Es 100% de solo lectura:** Emite el Markdown estructurado en `stdout` listo para ser consumido por el agente.

---

## Paso 8: Validar la integridad del proyecto (`rapid validate`)

Antes de iniciar la ejecución de código, verifica que la gobernanza del proyecto esté libre de discrepancias:

```bash
rapid validate
```

**Salida esperada:**
```text
==> Rapid OS Validation Report

Results:
  PASS - Project config: OK
  PASS - Standards: OK
  PASS - Project model snapshot: OK
  PASS - Spec registry: OK

Summary: 0 errors, 0 warnings. All registries valid.
```

Exit code: `0`. El proyecto cuenta con integridad total verificada.

---

## Paso 9: El siguiente paso en el Governance Loop

¡Has completado las primeras etapas de gobernanza! En este punto, el desarrollador o el harness implementa el cambio (`app.py`).

El ciclo continúa de la siguiente manera:

```mermaid
flowchart LR
    A[Spec + Context] --> B[rapid policy / run]
    B --> C[rapid harness resolve]
    C --> D[Implementación externa]
    D --> E[rapid evidence add]
    E --> F[rapid eval run]
```

- **Policy y Run:** Congelan el `ExecutionContract` con los requisitos de gates y riesgo.
- **Harness:** Valida que la herramienta declare soporte para las capabilities requeridas.
- **Evidence:** Custodia la salida del comando de prueba (`python -m unittest`) con su SHA-256.
- **Eval:** Evalúa deterministamente si el run pasa (`PASS`).

Continúa explorando:
- [Gobernar un proyecto existente](./existing-project.md)
- [Ciclo de gobernanza completo](../governance-loop.md)
- [Referencia de CLI](../cli.md)

</details>
