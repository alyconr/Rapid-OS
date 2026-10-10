# Laboratorio 2: Feature Engineering Lab

Aprende a gobernar el desarrollo de una nueva funcionalidad en RAPID OS con criterios de aceptación rigurosos, gates de pruebas y resolución de capacidades.

---

## 1. Overview

- **Nombre:** Sistema de Reservas con Control de Disponibilidad.
- **Problema:** Un sistema de reservas en memoria permite duplicar reservas para un mismo horario por falta de validación de disponibilidad.
- **Objetivo:** Gobernar la adición de control de conflictos y validación de franjas horarias mediante una especificación formal de tipo `feature`.
- **Nivel de dificultad:** Intermedio.
- **Conocimientos previos:** Conceptos básicos del Governance Loop (Laboratorio 1).
- **Dependencias:** Python 3.10+ (biblioteca estándar).
- **Archivos de referencia:** [`examples/feature-lab/`](https://github.com/alyconr/Rapid-OS/tree/main/examples/feature-lab).

---

## 2. Learning Outcomes

1. Redactar especificaciones de tipo `feature` con criterios de aceptación verificables.
2. Reconocer compuertas `gate.tests` y `gate.final-verification`.
3. Validar capacidades de escritura y ejecución de pruebas del harness externo.
4. Generar evidencias `file_change` y `test_result` que satisfagan los criterios de la política.
5. Interpretar evaluaciones conductuales bajo condiciones de aceptación.

---

## 3. Initial State

```text
booking-app/
├── booking.py
└── tests/
    ├── __init__.py
    └── test_booking.py
```

En la versión inicial (`starter`), `BookingSystem.create_booking(user_id, slot)` guarda cualquier reserva sin verificar si el horario ya fue ocupado previamente.

---

## 4. Engineering Requirements

1. **Detección de colisiones:** Lanzar `SlotAlreadyBookedError` si el horario solicitado ya se encuentra registrado.
2. **Saneamiento:** Limpiar espacios en blanco en `user_id` y `slot`.
3. **Casos borde:** Rechazar cadenas vacías o compuestas únicamente de espacios en blanco.
4. **Preservación:** Las reservas válidas deben continuar registrándose con normalidad.

---

## 5. Guided Procedure

### Paso 1: Crear la Spec del Feature

```bash
rapid spec create \
  --id spec-booking-conflict-check \
  --title "Prevención de colisiones en reservas y validación de slots" \
  --mode feature \
  --status ready
```

### Paso 2: Compilar Contexto y Crear Run

```bash
rapid context --manifest
rapid run create --spec spec-booking-conflict-check --harness cursor
```

Esto generará el run `spec-booking-conflict-check-r1-run-001`.

### Paso 3: Consultar los Gates Requeridos

```bash
rapid run show spec-booking-conflict-check-r1-run-001
```

La política exige los gates asociados a la clasificación del feature (como `gate.baseline`, `gate.tests` y `gate.final-verification` según el nivel de riesgo).

---

## 6. External Execution

El harness o desarrollador actualiza `booking.py` agregando la clase de error y la validación:

```python
class SlotAlreadyBookedError(RuntimeError):
    """Raised when a time slot is already reserved."""

class BookingSystem:
    def __init__(self):
        self.bookings: list[dict[str, object]] = []

    def create_booking(self, user_id: str, slot: str) -> dict[str, object]:
        if not user_id or not user_id.strip() or not slot or not slot.strip():
            raise ValueError("user_id and slot must be non-empty strings.")
        clean_user = user_id.strip()
        clean_slot = slot.strip()

        if any(b["slot"] == clean_slot for b in self.bookings):
            raise SlotAlreadyBookedError(f"Slot '{clean_slot}' is already booked.")

        booking = {
            "id": len(self.bookings) + 1,
            "user_id": clean_user,
            "slot": clean_slot,
        }
        self.bookings.append(booking)
        return booking
```

Ejecuta la suite externa:

```bash
python -m unittest discover -s tests -t .
```

---

## 7. Evidence Collection

1. Actualizar el estado del run:
```bash
rapid run status spec-booking-conflict-check-r1-run-001 active
rapid run task spec-booking-conflict-check-r1-run-001 T001 in_progress
```

2. Registrar evidencia de cambios en el repositorio:
```json
{
  "kind": "file_change",
  "producer": "harness:cursor",
  "summary": "Implementación de SlotAlreadyBookedError y pruebas de conflicto",
  "task_ids": ["T001"],
  "gate_ids": [],
  "capability_ids": ["repository.write"],
  "payload": {
    "paths": ["booking.py", "tests/test_booking.py"]
  }
}
```

```bash
rapid evidence add --run spec-booking-conflict-check-r1-run-001 --input evidence_files.json
```

3. Registrar resultados de la prueba unitaria:
```json
{
  "kind": "test_result",
  "producer": "harness:cursor",
  "summary": "Suite de pruebas de colisión y casos borde aprobada",
  "task_ids": ["T001"],
  "gate_ids": ["gate.tests", "gate.final-verification"],
  "capability_ids": ["tests.execute"],
  "payload": {
    "suite": "tests/test_booking.py",
    "exit_code": 0,
    "passed": 4,
    "failed": 0,
    "skipped": 0
  }
}
```

```bash
rapid evidence add --run spec-booking-conflict-check-r1-run-001 --input evidence_tests.json
```

4. Agradecer y cerrar gates:
```bash
rapid run gate spec-booking-conflict-check-r1-run-001 gate.tests acknowledged
rapid run gate spec-booking-conflict-check-r1-run-001 gate.final-verification acknowledged
rapid run task spec-booking-conflict-check-r1-run-001 T001 done
rapid run status spec-booking-conflict-check-r1-run-001 finished
```

---

## 8. Evaluation

```bash
rapid eval run --run spec-booking-conflict-check-r1-run-001 --write --require-pass
```

---

## 9. Validation

```bash
rapid validate
```

---

## 10. Troubleshooting

- Si `rapid eval run` falla con `RAPID1225` (`unverified`), revisa si todas las compuertas obligatorias fueron reconocidas en el `RunState`.

---

## 11. Assessment

- [x] Intento de duplicación lanza `SlotAlreadyBookedError`.
- [x] Entradas en blanco rechazadas con `ValueError`.
- [x] Pruebas unitarias 100% aprobadas y reportadas en evidencia.

