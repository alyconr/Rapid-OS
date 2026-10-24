# Laboratorio 5: Research & Spike Engineering Lab

Haz un spike: compara JSON y SQLite para guardar preferencias y deja el aprendizaje registrado. En tu agente escribes tres cosas; en la terminal solo preparas el ejemplo y apruebas.

## Con shortcuts

### 1. Prepara el proyecto de ejemplo

```bash
cp -r ~/.rapid-os/examples/research-lab/starter storage-spike && cd storage-spike
git init -b main && git add . && git commit -m "starter"
```

En Windows PowerShell, la copia es `Copy-Item -Recurse $HOME\.rapid-os\examples\research-lab\starter storage-spike`. Si instalaste Rapid OS con `pip`, el ejemplo está en [`examples/research-lab/starter`](https://github.com/alyconr/Rapid-OS/tree/main/examples/research-lab/starter).

### 2. Configura el proyecto

Abre tu agente en la carpeta y escribe `/rapid-init` (en Codex, `$rapid-init`). Detecta Python y propone `python -m unittest discover` como comando de tests: acéptalo. Los documentos del proyecto puedes omitirlos en este laboratorio.

### 3. Pide el trabajo

```text
/rapid-research comparar JSON y SQLite para guardar las preferencias
```

Un spike no exige baseline ni tests: el agente prueba las dos opciones y registra cada hallazgo como evidencia del run (`rapid attach <ruta> --label "…"`).

### 4. Aprueba en tu terminal

Cuando el agente termina, se detiene y te da el comando exacto. Ejecútalo en **otra terminal**, fuera del agente, por ejemplo:

```bash
rapid approve gate.final-verification
```

Vuelve al agente y escribe `/rapid-next` para cerrar el run.

**Resultado:** Una comparación con los datos medidos, registrada en el run, y un veredicto `pass`.

¿No tienes los shortcuts? Una sola vez: `rapid shortcuts install --global --harness claude`, o dentro de la carpeta `rapid init --shortcuts`. Detalle en la [guía de shortcuts](../guides/shortcuts.md).

---

## Modo avanzado

No lo necesitas para hacer el laboratorio. Es el mismo recorrido con los comandos v3, para entender qué registra cada paso y para CI y auditoría.

<details>
<summary>Ver el laboratorio con comandos v3</summary>

## 1. Overview

- **Nombre:** Spike Comparativo de Estrategias de Almacenamiento Local.
- **Problema:** El equipo debe decidir entre persistencia en archivo JSON plano vs base de datos relacional embebida SQLite de la biblioteca estándar para un nuevo componente.
- **Objetivo:** Ejecutar un spike bajo el modo `research` (clasificación mínima `spike`, riesgo `low`), recopilando evidencia empírica con artefactos reproducibles sin introducir dependencias pesadas de producción.
- **Nivel de dificultad:** Intermedio.
- **Conocimientos previos:** Filosofía minimalista (YAGNI / Ponytail) y modos de RAPID OS.
- **Dependencias:** Python 3.10+ (biblioteca estándar `sqlite3` y `json`).
- **Archivos de referencia:** [`examples/research-lab/`](https://github.com/alyconr/Rapid-OS/tree/main/examples/research-lab).

---

## 2. Learning Outcomes

1. Configurar especificaciones de tipo `research`.
2. Comprender la clasificación `spike` en la política de RAPID OS.
3. Registrar evidencia de tipo `artifact` acompañada de hashes criptográficos SHA-256 reales.
4. Documentar conclusiones técnicas medibles sin simular métricas artificiales.
5. Cerrar el ciclo de investigación dejando evidencia auditable en `.rapid-os/evals/`.

---

## 3. Initial State

```text
storage-spike/
├── experiment.py
└── tests/
    ├── __init__.py
    └── test_experiment.py
```

En la versión inicial (`starter`):
`StorageExperiment` contiene únicamente la firma de método sin lógica ejecutable.

---

## 4. Engineering Requirements

1. **Implementación de JSON:** Escribir y leer 50 registros estructurados mediante `json.dump` / `json.loads`.
2. **Implementación de SQLite:** Crear tabla relacional, insertar y consultar los mismos 50 registros utilizando `sqlite3`.
3. **Métricas deterministas:** Contabilizar registros verificados y tamaño del archivo resultante en bytes.
4. **Cero dependencias:** No añadir paquetes externos de ORM ni frameworks de benchmarks.

---

## 5. Guided Procedure

### Paso 1: Crear la Spec en Modo Research

```bash
rapid spec create \
  --id spec-storage-strategy-spike \
  --title "Spike comparativo entre almacenamiento plano JSON y SQLite stdlib" \
  --mode research \
  --status ready
```

### Paso 2: Crear el Run

```bash
rapid context --manifest
rapid run create --spec spec-storage-strategy-spike --harness antigravity
```

Para un modo `research` sin rutas protegidas, la política asigna nivel de riesgo `low` y la compuerta básica `gate.final-verification`.

---

## 6. External Execution

Implementa el experimento en `experiment.py` y genera el reporte de resultados `research_report.md`:

```python
import json
from pathlib import Path
import sqlite3

class StorageExperiment:
    @staticmethod
    def run_json_storage(work_dir: Path, record_count: int = 50) -> dict[str, object]:
        file_path = work_dir / "records.json"
        data = [{"id": i, "name": f"item_{i}", "val": i * 10} for i in range(record_count)]
        file_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
        loaded = json.loads(file_path.read_text(encoding="utf-8"))
        return {
            "strategy": "json",
            "records_written": len(loaded),
            "file_size_bytes": file_path.stat().st_size,
        }

    @staticmethod
    def run_sqlite_storage(work_dir: Path, record_count: int = 50) -> dict[str, object]:
        db_path = work_dir / "records.db"
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()
        cursor.execute("CREATE TABLE records (id INTEGER PRIMARY KEY, name TEXT, val INTEGER)")
        cursor.executemany(
            "INSERT INTO records (id, name, val) VALUES (?, ?, ?)",
            [(i, f"item_{i}", i * 10) for i in range(record_count)]
        )
        conn.commit()
        cursor.execute("SELECT COUNT(*) FROM records")
        row_count = cursor.fetchone()[0]
        conn.close()
        return {
            "strategy": "sqlite",
            "records_written": row_count,
            "file_size_bytes": db_path.stat().st_size,
        }
```

Ejecuta el experimento de forma reproducible:

```bash
python -m unittest discover -s tests -t .
```

---

## 7. Evidence Collection

1. Actualizar el estado del run:
```bash
rapid run status spec-storage-strategy-spike-r1-run-001 active
rapid run task spec-storage-strategy-spike-r1-run-001 T001 in_progress
```

2. Registrar evidencia de cambios en el código (`file_change`).

3. Registrar evidencia de los tests del spike (`test_result`):
```json
{
  "kind": "test_result",
  "producer": "harness:antigravity",
  "summary": "Ejecución automatizada de ambos escenarios de persistencia",
  "task_ids": ["T001"],
  "gate_ids": ["gate.final-verification"],
  "capability_ids": ["tests.execute"],
  "payload": {
    "suite": "tests/test_experiment.py",
    "exit_code": 0,
    "passed": 2,
    "failed": 0,
    "skipped": 0
  }
}
```

```bash
rapid evidence add --run spec-storage-strategy-spike-r1-run-001 --input evidence_tests.json
rapid run gate spec-storage-strategy-spike-r1-run-001 gate.final-verification acknowledged
rapid run task spec-storage-strategy-spike-r1-run-001 T001 done
rapid run status spec-storage-strategy-spike-r1-run-001 finished
```

---

## 8. Evaluation

```bash
rapid eval run --run spec-storage-strategy-spike-r1-run-001 --write --require-pass
```

---

## 9. Validation

```bash
rapid validate
```

---

## 10. Assessment

- [x] Spike investigativo completado sin dependencias externas pesadas.
- [x] Evidencia verificada deterministamente.
- [x] Conclusiones respaldadas por ejecuciones reales de la suite.
- [x] Veredicto `pass` obtenido.

</details>
