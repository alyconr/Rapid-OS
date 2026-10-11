# Examples Catalog — RAPID OS Hands-on Labs

Este directorio contiene proyectos de ejemplo reproducibles y autocontenidos para los laboratorios prácticos de RAPID OS v3.

## Estructura

Cada laboratorio cuenta con:
- `starter/`: Estado inicial del ejercicio (código base y suite de pruebas inicial).
- `solution/`: Solución canónica de referencia que satisface todos los criterios de aceptación.
- `README.md`: Instrucciones específicas del ejercicio y comandos de validación.

## Catálogo de laboratorios

1. [`first-governed-project/`](first-governed-project/README.md) — Task Tracker CLI (Tutorial: [first-governed-project.md](../docs/tutorials/first-governed-project.md)).
2. [`feature-lab/`](feature-lab/README.md) — Sistema de Reservas en memoria con control de disponibilidad (Tutorial: [feature-lab.md](../docs/tutorials/feature-lab.md)).
3. [`bugfix-lab/`](bugfix-lab/README.md) — Corrección de cálculo de descuentos en facturación (Tutorial: [bugfix-lab.md](../docs/tutorials/bugfix-lab.md)).
4. [`refactor-lab/`](refactor-lab/README.md) — Desacoplamiento de cálculo de comisiones (Tutorial: [refactor-lab.md](../docs/tutorials/refactor-lab.md)).
5. [`hardening-lab/`](hardening-lab/README.md) — Endurecimiento y validación estricta de entradas (Tutorial: [hardening-lab.md](../docs/tutorials/hardening-lab.md)).
6. [`research-lab/`](research-lab/README.md) — Spike comparativo: JSON vs SQLite (Tutorial: [research-lab.md](../docs/tutorials/research-lab.md)).

## Principio de diseño: Cero dependencias externas

Todos los ejemplos utilizan exclusivamente la biblioteca estándar de Python (`unittest`, `json`, `sqlite3`, `pathlib`, `sys`). No requieren instalación de paquetes externos ni conexión a redes.
