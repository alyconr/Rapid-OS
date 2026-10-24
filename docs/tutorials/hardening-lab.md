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

## Modo avanzado

No lo necesitas para hacer el laboratorio. Es el mismo recorrido con los comandos v3, para entender qué registra cada paso y para CI y auditoría.

<details>
<summary>Ver el laboratorio con comandos v3</summary>

## 1. Overview

- **Nombre:** Endurecimiento de Fronteras y Validación Defensiva.
- **Problema:** Una aplicación acepta entradas arbitrarias sin límites de tamaño, verificación de formato ni protección contra bytes nulos.
- **Objetivo:** Implementar validación defensiva estricta, gobernar gates de seguridad y documentar políticas de workspace.
- **Nivel de dificultad:** Avanzado.
- **Conocimientos previos:** Gestión de riesgos y gates de seguridad en RAPID OS.
- **Dependencias:** Python 3.10+ (biblioteca estándar).
- **Archivos de referencia:** [`examples/hardening-lab/`](https://github.com/alyconr/Rapid-OS/tree/main/examples/hardening-lab).

---

## 2. Learning Outcomes

1. Configurar una especificación en modo `hardening` con etiquetas de seguridad.
2. Reconocer compuertas de seguridad (`gate.security-review`, `gate.workspace-isolation` si el riesgo se eleva a `high`).
3. Registrar evidencia de aislamiento de workspace (`workspace: { "mode": "isolated" }`).
4. Registrar evidencia de revisión especializada de seguridad (`review: { "review_type": "security" }`).
5. Blindar código Python contra vectores de inyección y sobrecarga de memoria sin dependencias externas.

---

## 3. Initial State

```text
user-profiles/
├── profile_mgr.py
└── tests/
    ├── __init__.py
    └── test_profile_mgr.py
```

En la versión inicial (`starter`):
`UserProfileManager.register_user(username, email, bio)` almacena cualquier tipo de cadena sin validación alguna.

---

## 4. Engineering Requirements

1. **Username:** Expresión regular `^[a-zA-Z0-9_-]{3,32}$`.
2. **Email:** Validación estricta con regex y formato estándar.
3. **Bio:** Longitud máxima de 200 caracteres y prohibición explícita de caracteres nulos (`\x00`).
4. **Excepciones:** Lanzar `ValidationError` (derivado de `ValueError`) ante cualquier violación de frontera.

---

## 5. Guided Procedure

### Paso 1: Crear la Spec en Modo Hardening

```bash
rapid spec create \
  --id spec-user-profile-hardening \
  --title "Validación defensiva de perfiles de usuario" \
  --mode hardening \
  --status ready
```

### Paso 2: Crear el Run con Nivel de Riesgo Evaluado

```bash
rapid context --manifest
rapid run create --spec spec-user-profile-hardening --harness antigravity
```

---

## 6. External Execution

Implementa `profile_mgr.py` defensivo:

```python
import re

USERNAME_RE = re.compile(r"^[a-zA-Z0-9_-]{3,32}$")
EMAIL_RE = re.compile(r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$")
MAX_BIO_LENGTH = 200

class ValidationError(ValueError):
    """Raised when input validation fails."""

class UserProfileManager:
    def __init__(self):
        self.profiles: dict[str, dict[str, object]] = {}

    def register_user(self, username: str, email: str, bio: str) -> dict[str, object]:
        if not isinstance(username, str) or not USERNAME_RE.match(username):
            raise ValidationError("Invalid username.")
        if not isinstance(email, str) or not EMAIL_RE.match(email):
            raise ValidationError("Invalid email format.")
        if not isinstance(bio, str) or len(bio) > MAX_BIO_LENGTH or "\x00" in bio:
            raise ValidationError("Invalid bio payload.")

        profile = {
            "username": username,
            "email": email,
            "bio": bio.strip(),
        }
        self.profiles[username] = profile
        return profile
```

---

## 7. Evidence Collection

1. Registrar evidencia de espacio de trabajo seguro:
```json
{
  "kind": "workspace",
  "producer": "harness:antigravity",
  "summary": "Confirmación de ejecución en entorno de trabajo seguro",
  "task_ids": ["T001"],
  "gate_ids": [],
  "capability_ids": ["workspace.current"],
  "payload": {
    "mode": "current"
  }
}
```

Ingiérela:
```bash
rapid run status spec-user-profile-hardening-r1-run-001 active
rapid run task spec-user-profile-hardening-r1-run-001 T001 in_progress
rapid evidence add --run spec-user-profile-hardening-r1-run-001 --input evidence_workspace.json
```

2. Registrar evidencia de cambios en el código (`file_change`).

3. Registrar evidencia de revisión de seguridad:
```json
{
  "kind": "review",
  "producer": "harness:antigravity",
  "summary": "Auditoría de seguridad y validación de expresiones regulares aprobada",
  "task_ids": ["T001"],
  "gate_ids": [],
  "capability_ids": [],
  "payload": {
    "review_type": "security",
    "outcome": "approved",
    "reviewer": "sec-ops"
  }
}
```

```bash
rapid evidence add --run spec-user-profile-hardening-r1-run-001 --input evidence_sec_review.json
```

4. Registrar evidencia de pruebas de seguridad y casos límite:
```json
{
  "kind": "test_result",
  "producer": "harness:antigravity",
  "summary": "Pruebas de frontera y rechazo de vectores maliciosos aprobadas",
  "task_ids": ["T001"],
  "gate_ids": ["gate.final-verification"],
  "capability_ids": ["tests.execute"],
  "payload": {
    "suite": "tests/test_profile_mgr.py",
    "exit_code": 0,
    "passed": 4,
    "failed": 0,
    "skipped": 0
  }
}
```

```bash
rapid evidence add --run spec-user-profile-hardening-r1-run-001 --input evidence_tests.json
rapid run gate spec-user-profile-hardening-r1-run-001 gate.final-verification acknowledged
rapid run task spec-user-profile-hardening-r1-run-001 T001 done
rapid run status spec-user-profile-hardening-r1-run-001 finished
```

---

## 8. Evaluation

```bash
rapid eval run --run spec-user-profile-hardening-r1-run-001 --write --require-pass
```

---

## 9. Validation

```bash
rapid validate
```

---

## 10. Assessment

- [x] Frontera de entrada sanitizada contra vectores arbitrarios.
- [x] Evidencia de revisión de tipo `security` ingestada.
- [x] Todas las compuertas obligatorias verificadas.
- [x] Veredicto `pass` emitido deterministamente.

</details>
