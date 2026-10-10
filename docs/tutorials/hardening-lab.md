# Laboratorio 5: Hardening & Security Engineering Lab

Aprende a gobernar proyectos de endurecimiento y seguridad con RAPID OS, manejando elevación de nivel de riesgo, validación de fronteras de entrada y aislamiento de workspace.

---

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

