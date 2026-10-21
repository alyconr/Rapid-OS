---
description: "Conduce el onboarding de Rapid OS: stack, topología, arquetipo, agentes, comando de test y documentos del proyecto."
argument-hint: "[descripción del proyecto]"
context-command: rapid setup next --json
allowed-commands: setup
---
# Rapid OS: onboarding del proyecto

{{context_step}}

Conduces el onboarding de Rapid OS con `rapid setup`. La descripción del proyecto es lo que la persona escribió al invocar este comando. Sigue este bucle:

1. Ejecuta `rapid setup next --json` y sigue `action.kind` en bucle hasta `done`. Usa `action.command` (y `action.alt_command`) tal cual, sustituyendo solo los valores entre `<` y `>`; no inventes comandos.
2. `choose_stack` y `choose_topology`:
   - Si hay `recommended`, propónlo con una o dos razones (de `fits` y `avoid_if` de la opción) y una alternativa.
   - Si no hay `recommended`, haz las `questions` de la acción (máximo 5, de a 2 por mensaje) y recomienda según las respuestas.
   - Si ninguna opción encaja, redacta un stack custom (secciones `Runtime`, `Framework` y `Testing`), muéstralo completo a la persona y, con su visto bueno, envíalo por stdin con `action.alt_command`.
   - Si la salida de un comando trae `notes`, explícalas a la persona.
3. `choose_archetype`, `choose_agents` y `set_test_command`: propón `recommended` si existe, explica en una frase la diferencia entre las opciones y ejecuta `action.command` con la decisión de la persona. Para un proyecto sin comando de test, el valor es `none`.
4. `resolve_doc`: ofrece a la persona tres caminos (pegar el contenido, que lo redactes tú u omitirlo) y, si la acción trae `legacy_source`, un cuarto: importar el documento anterior con `rapid setup doc business --from-legacy`.
   - Si lo redactas: haz las `questions` de la acción, muestra el borrador completo, aplica los cambios que pida la persona y envíalo por stdin (heredoc) con `--source drafted`. En Windows PowerShell no envíes el documento por tubería: escríbelo en un archivo temporal UTF-8 fuera de .rapid-os (`Set-Content -Encoding utf8 $env:TEMP\rapid-<id>.md`) y usa `--file <ruta>`; la tubería de PowerShell 5.1 convierte los acentos y la ñ en `?`. Respeta `required_sections` y `max_chars`; si el comando rechaza el borrador, corrígelo y reenvíalo.
   - Ejecuta `rapid setup doc <id> --confirm` SOLO si la persona dice explícitamente que lo confirma. Un borrador sin confirmar queda como supuesto.
   - Si la persona pega el contenido: envíalo tal cual con `--source provided`, sin reescribirlo.
   - Si lo omite: ejecuta `rapid setup doc <id> --skip`.
5. Usa la descripción del usuario para no repetir preguntas que ya respondió.
6. Nunca edites `.rapid-os/` ni `docs/` directamente: todo se escribe con `rapid setup`. Nunca ejecutes la inicialización interactiva de Rapid OS: exige la terminal de la persona.
7. Cuando `action.kind` sea `done`: resume lo decidido, lista `unconfirmed_docs` si los hay (siguen como supuestos hasta que la persona los confirme) y ofrece `/rapid-feature` con la primera historia sin marcar del brief (en Codex el shortcut se invoca como `$rapid-feature`; en Codex CLI, `/` no lista los skills). Si la salida de `rapid setup finish` dijo «Repositorio git creado», cuéntaselo a la persona: Rapid OS creó el repositorio (sin commits) porque observa los cambios de los runs con git, y no tiene que ejecutar `git init`. Si la salida trae `person_actions`, muéstralas tal cual con su explicación (`why`) y pídele a la persona que las ejecute en su propia terminal; no las ejecutes tú.
