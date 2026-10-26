# Laboratorio 1: Feature Engineering Lab

Añade una funcionalidad a un sistema de reservas: que rechace reservas que se solapen en el mismo horario. En tu agente escribes tres cosas; en la terminal solo preparas el ejemplo y apruebas.

## Con shortcuts

### 1. Prepara el proyecto de ejemplo

```bash
cp -r ~/.rapid-os/examples/feature-lab/starter booking-app && cd booking-app
git init -b main && git add . && git commit -m "starter"
```

En Windows PowerShell, la copia es `Copy-Item -Recurse $HOME\.rapid-os\examples\feature-lab\starter booking-app`. Si instalaste Rapid OS con `pip`, el ejemplo está en [`examples/feature-lab/starter`](https://github.com/alyconr/Rapid-OS/tree/main/examples/feature-lab/starter).

### 2. Configura el proyecto

Abre tu agente en la carpeta y escribe `/rapid-init` (en Codex, `$rapid-init`). Detecta Python y propone `python -m unittest discover` como comando de tests: acéptalo. Los documentos del proyecto puedes omitirlos en este laboratorio.

### 3. Pide el trabajo

```text
/rapid-feature añadir control de disponibilidad: rechazar reservas que se solapen en el mismo horario
```

El agente redacta la spec, comprueba que los tests del ejemplo pasan antes de tocar nada (baseline), implementa la validación con sus tests y los ejecuta con `rapid check`.

### 4. Aprueba en tu terminal

Cuando el agente termina, se detiene y te da el comando exacto. Ejecútalo en **otra terminal**, fuera del agente, por ejemplo:

```bash
rapid approve gate.final-verification
```

Vuelve al agente y escribe `/rapid-next` para cerrar el run.

**Resultado:** Reservar un horario ocupado lanza un error, la suite queda en verde y el run termina con veredicto `pass`.

¿No tienes los shortcuts? Una sola vez: `rapid shortcuts install --global --harness claude`, o dentro de la carpeta `rapid init --shortcuts`. Detalle en la [guía de shortcuts](../guides/shortcuts.md).

---

## Detalles del laboratorio

### Estado inicial

```text
booking-app/
├── booking.py
└── tests/
    ├── __init__.py
    └── test_booking.py
```

En la versión inicial (`starter`), `BookingSystem.create_booking(user_id, slot)` guarda cualquier reserva sin verificar si el horario ya fue ocupado previamente.

### Requisitos

1. **Detección de colisiones:** Lanzar `SlotAlreadyBookedError` si el horario solicitado ya se encuentra registrado.
2. **Saneamiento:** Limpiar espacios en blanco en `user_id` y `slot`.
3. **Casos borde:** Rechazar cadenas vacías o compuestas únicamente de espacios en blanco.
4. **Preservación:** Las reservas válidas deben continuar registrándose con normalidad.

---

## Modo avanzado

No lo necesitas para hacer el laboratorio. El mismo tipo de trabajo hecho a mano con los comandos v3 (spec, run, evidencia y evaluación), para CI o auditoría, está en el [recorrido manual (Bajo el capó)](first-governed-project.md) y en el [ciclo de gobernanza v3](../governance-loop.md).
