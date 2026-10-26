# Laboratorio 4: Hardening & Security Engineering Lab

Endurece la seguridad de un registro de usuarios: validar y acotar las entradas de `register_user`. En tu agente escribes tres cosas; en la terminal solo preparas el ejemplo y apruebas.

## Con shortcuts

### 1. Prepara el proyecto de ejemplo

```bash
cp -r ~/.rapid-os/examples/hardening-lab/starter user-profiles && cd user-profiles
git init -b main && git add . && git commit -m "starter"
```

En Windows PowerShell, la copia es `Copy-Item -Recurse $HOME\.rapid-os\examples\hardening-lab\starter user-profiles`. Si instalaste Rapid OS con `pip`, el ejemplo está en [`examples/hardening-lab/starter`](https://github.com/alyconr/Rapid-OS/tree/main/examples/hardening-lab/starter).

### 2. Configura el proyecto

Abre tu agente en la carpeta y escribe `/rapid-init` (en Codex, `$rapid-init`). Detecta Python y propone `python -m unittest discover` como comando de tests: acéptalo. Los documentos del proyecto puedes omitirlos en este laboratorio. Cuando te pregunte el arquetipo, elige **Corporate** (`corporate`): es el que trae las reglas de seguridad más estrictas.

### 3. Pide el trabajo

```text
/rapid-hardening validar y acotar las entradas de register_user
```

El agente trabaja en una copia aislada del repositorio (`rapid start --resume --worktree` crea la carpeta `../<repo>-<run-id>` en la rama `rapid/<run-id>`), así tu rama `main` no cambia hasta que revises. Además de la verificación final te pide una revisión (`gate.review`), que puedes aprobar o dispensar.

### 4. Aprueba en tu terminal

Cuando el agente termina, se detiene y te da el comando exacto. Ejecútalo en **otra terminal**, fuera del agente, por ejemplo:

```bash
rapid approve gate.final-verification
```

Vuelve al agente y escribe `/rapid-next` para cerrar el run.

**Resultado:** `register_user` rechaza usuarios, correos y biografías fuera de los límites, con sus tests, y el run termina con veredicto `pass` (o `pass_with_waivers` si dispensaste la revisión).

¿No tienes los shortcuts? Una sola vez: `rapid shortcuts install --global --harness claude`, o dentro de la carpeta `rapid init --shortcuts`. Detalle en la [guía de shortcuts](../guides/shortcuts.md).

---

## Detalles del laboratorio

### Estado inicial

```text
user-profiles/
├── profile_mgr.py
└── tests/
    ├── __init__.py
    └── test_profile_mgr.py
```

En la versión inicial (`starter`):
`UserProfileManager.register_user(username, email, bio)` almacena cualquier tipo de cadena sin validación alguna.

### Requisitos

1. **Username:** Expresión regular `^[a-zA-Z0-9_-]{3,32}$`.
2. **Email:** Validación estricta con regex y formato estándar.
3. **Bio:** Longitud máxima de 200 caracteres y prohibición explícita de caracteres nulos (`\x00`).
4. **Excepciones:** Lanzar `ValidationError` (derivado de `ValueError`) ante cualquier violación de frontera.

---

## Modo avanzado

No lo necesitas para hacer el laboratorio. El mismo tipo de trabajo hecho a mano con los comandos v3 (spec, run, evidencia y evaluación), para CI o auditoría, está en el [recorrido manual (Bajo el capó)](first-governed-project.md) y en el [ciclo de gobernanza v3](../governance-loop.md).
