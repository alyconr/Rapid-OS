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
- **El plumbing no ejecuta nada del repositorio; el porcelain ejecuta solo lo que se le pide:** `rapid scan`, `rapid context`, `rapid spec`, `rapid policy`, `rapid run`, `rapid harness`, `rapid evidence`, `rapid eval` y `rapid validate` operan de forma estática sobre archivos y registros. El porcelain ejecuta solo el `test_command` de `.rapid-os/config.json` (en la baseline de `rapid start` y en `rapid task done`) o el argv que se pasa a `rapid check -- <comando>`, sin shell, y comandos `git` de lectura (`rev-parse`, `diff`, `ls-files`, `config user.name`) para registrar los cambios del run; con `rapid start --worktree` añade `git worktree add`. No ejecuta ningún otro comando del proyecto.
- **Nunca aprueba gates humanos:** `rapid approve` lo ejecuta una persona en su terminal. Rapid OS nunca aprueba, dispensa ni rechaza un gate humano por su cuenta, y tampoco lo hace un shortcut, un hook o una evidencia producida por un harness.
- **No crea automáticamente branches o worktrees de Git:** Cuando una política exige `workspace.isolated`, Rapid OS declara la necesidad en el contrato y `rapid start` se detiene en `blocked`. Solo `rapid start --worktree`, ejecutado por el operador o su harness, crea el worktree aislado (`../<repo>-<run-id>`, rama `rapid/<run-id>`); `rapid abort` nunca lo elimina. Para el resto de casos la creación efectiva del entorno aislado o rama corresponde al operador o al harness.
- **Todos sus comandos git pasan por una sola puerta:** `rapid_os/orchestration/git.py` ejecuta git con `-c safe.directory=<raíz del proyecto>` (solo esa carpeta, nunca `*`) y `-c core.fsmonitor=false`, para no depender de quién es el dueño de la carpeta (sandbox de Codex en Windows) y para que un repositorio ajeno no ejecute programas al leerse. La excepción para el git de la persona, que solo ella puede conceder, se le entrega como `person_actions`; Rapid OS nunca modifica la configuración de git de la persona.
- **Solo crea un repositorio git para poder observar los runs:** `rapid setup finish` y `rapid init` ejecutan `git init` (y fijan la rama inicial con `git symbolic-ref HEAD`, siempre `main`) únicamente cuando la carpeta no está dentro de un repositorio. Nunca anida repositorios, nunca hace commits y, sin git instalado, solo avisa. `rapid start` en una carpeta sin repositorio falla con `RAPID1416` sin escribir nada.
- **La arquitectura se verifica leyendo imports, no ejecutando código:** `rapid arch check` lee el texto de los archivos bajo `modules_root` y `shared_root` (Python con `ast`, TypeScript y JavaScript con expresiones regulares) y solo informa; nunca edita el código ni migra un proyecto existente. Rapid OS escribe la regla (`architecture.md` y `architecture.json`) únicamente para los stacks `python-api`, `python-ai`, `nodejs-ai` y `web-modern`, y no sobrescribe un archivo existente. Ver [Arquitectura de referencia](./architecture.md).
- **Los hooks deniegan herramientas al agente, pero Rapid OS no invoca agentes:** `rapid hook stop|pre-tool` los ejecuta Claude Code cuando el agente intenta detenerse o usar una herramienta; solo devuelven un bloqueo de parada o una denegación (reservan `rapid approve`, `rapid abort` y las escrituras en `.rapid-os/` a la persona) y nunca lanzan al agente. Solo `rapid shortcuts install --hooks` o `rapid init --hooks` los escriben en `.claude/settings.json`, sin tocar los hooks del usuario, y la detección de comandos es de mejor esfuerzo.
- **No instala shortcuts de harness por su cuenta:** `rapid shortcuts install` (o `rapid init --shortcuts`) es la única vía que escribe los comandos `/rapid-<modo>` (y `/rapid-init`) en `.claude/skills`, `.agents/skills`, `.cursor/skills` o `.github/prompts`, y `rapid shortcuts install --global` la única que los escribe fuera del proyecto, en la carpeta de skills de tu usuario (solo para los harnesses con carpeta documentada; `install.sh` e `install.ps1` lo ofrecen como opción y nunca por defecto); `rapid shortcuts remove` borra solo los archivos que llevan el marcador `generated by rapid shortcuts`. Los shortcuts nunca aprueban gates humanos.
- **No confirma por la persona ni crea documentación por su cuenta:** `rapid setup doc` y `rapid init` son los únicos comandos que escriben `docs/PRODUCT_BRIEF.md`, `docs/BUSINESS_RULES.md`, `docs/DATA_MODEL.md` y `docs/ARCHITECTURE.md` (con frontmatter `rapid-doc`, `source`, `status` y `sha256`, y un `.bak` del archivo anterior); `rapid setup finish` y `rapid init` son los únicos que copian stack, topología, arquetipo y seguridad a `.rapid-os/standards/`. Un documento redactado por el agente se guarda como `source: drafted` y `status: draft`, entra al contexto como supuesto y solo `rapid setup doc <id> --confirm` lo confirma. `rapid init` ya no crea el andamiaje `TODO` de `docs/`.
- **Solo marca la historia que el run cerró, y no llena la raíz de backups:** cuando `rapid finish` termina en PASS y la spec lleva el tag `story:<ID>`, cambia en `docs/PRODUCT_BRIEF.md` esa única línea `- [ ] <ID>:` a `- [x] <ID>:` (copia previa en `.rapid-os/backups/`, `source` y `status` sin cambios: un borrador sigue siendo borrador); si el veredicto no es PASS, si pasas `--no-tick` o si el brief no es un documento de Rapid OS, solo sugiere la historia. Un run cubre una historia. Los archivos de agente que Rapid OS regenera guardan su copia anterior en `.rapid-os/backups/` (solo si cambió el contenido, 5 por archivo), no en la raíz del proyecto.
- **No es una sandbox de sistema operativo:** Las "capabilities" en Rapid OS son declaraciones de capacidades de software, no jaulas de seguridad de kernel o contenedores forzados.
- **No garantiza matemáticamente ausencia de defectos:** Un veredicto `PASS` certifica que las reglas del contrato y la evidencia registrada fueron satisfechas. No equivale a una prueba formal de corrección matemática de todo el software ni sustituye el criterio de los ingenieros.

---

## Qué SÍ hace Rapid OS

- Conduce un run gobernado de principio a fin con el porcelain (`rapid start`, `rapid next`, `rapid check`, `rapid task`, `rapid attach`, `rapid finish`) y genera los shortcuts `/rapid-<modo>` de cada harness (`rapid shortcuts`).
- Analiza repositorios de forma determinista y extrae hechos con procedencia (`rapid scan`).
- Mantiene especificaciones de software con revisiones inmutables (`rapid spec`).
- Compila contexto estructurado respetando presupuestos estrictos de caracteres (`rapid context`).
- Modela políticas de riesgo y gates de control (`rapid policy`).
- Emite contratos inmutables de ejecución vinculados por digests SHA-256 (`rapid run`).
- Modela y valida capabilities declaradas por herramientas de codificación (`rapid harness`).
- Registra y custodia artefactos de evidencia de ejecución (`rapid evidence`).
- Evalúa evidencia física offline mediante reglas reproducibles (`rapid eval`).
- Audita la integridad cruzada completa del proyecto (`rapid validate`).

---

## Fronteras en compuertas humanas y defensa en capas

Un principio fundamental de gobernanza en Rapid OS es que **las compuertas de revisión humana nunca se reconocen automáticamente**.

Para mitigar que agentes o subprocesos auto-aprueben compuertas humanas:
- `rapid approve` exige una terminal interactiva (TTY), solicita confirmación textual explícita (`aprobar <gate-id>`) y rechaza la ejecución si detecta marcadores de sesión de agente hijo (`CLAUDE_CODE_CHILD_SESSION == "1"`).
- Además recorre la cadena de procesos padre y rechaza la ejecución (`RAPID1310`) si algún ancestro es un harness de agente. Hoy solo se reconoce Claude Code (el binario `claude`/`claude.exe`, el paquete npm `@anthropic-ai/claude-code` y el directorio `~/.local/share/claude/versions/` del instalador nativo), porque son los únicos nombres confirmados en su documentación oficial o en una instalación real; Codex y Cursor no se reconocen porque su nombre de proceso no está confirmado. La detección por ascendencia es de **mejor esfuerzo**: un proceso que se desacopla de su padre (doble fork, `setsid`, `nohup … &`) pasa a colgar de `init` y deja de tener a `claude` como ancestro. Junto al `claude.exe` renombrado y el pid reutilizado de un padre ya muerto, es un límite conocido. La regla sigue siendo que una persona apruebe en su propia terminal. Si la ascendencia no se puede leer (Linux: `/proc`; macOS: `ps`; Windows: `CreateToolhelp32Snapshot`), `rapid approve` **no** rechaza por ello y `rapid doctor` registra el motivo (`RAPID1319`). Una persona que usa su propia terminal, aunque sea la integrada de un IDE, no tiene un proceso `claude` entre sus ancestros; tampoco puede aprobar desde el modo `!` de Claude Code, porque ahí `claude` sí es el ancestro.
- Es importante destacar que la confirmación por TTY se puede emular externamente (mediante comandos como `script` o emuladores `pty`), por lo que actúa como **defensa en capas** y fricción deliberada, no como una garantía criptográfica o infalible. Rapid OS no atestigua criptográficamente quién aprueba: la identidad del revisor es la que se declara (`--reviewer` o `git config user.name`).

