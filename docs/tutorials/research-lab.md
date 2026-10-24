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

## Detalles del laboratorio

### Estado inicial

```text
storage-spike/
├── experiment.py
└── tests/
    ├── __init__.py
    └── test_experiment.py
```

En la versión inicial (`starter`):
`StorageExperiment` contiene únicamente la firma de método sin lógica ejecutable.

### Requisitos

1. **Implementación de JSON:** Escribir y leer 50 registros estructurados mediante `json.dump` / `json.loads`.
2. **Implementación de SQLite:** Crear tabla relacional, insertar y consultar los mismos 50 registros utilizando `sqlite3`.
3. **Métricas deterministas:** Contabilizar registros verificados y tamaño del archivo resultante en bytes.
4. **Cero dependencias:** No añadir paquetes externos de ORM ni frameworks de benchmarks.

---

## Modo avanzado

No lo necesitas para hacer el laboratorio. El mismo tipo de trabajo hecho a mano con los comandos v3 (spec, run, evidencia y evaluación), para CI o auditoría, está en el [recorrido manual (Bajo el capó)](first-governed-project.md) y en el [ciclo de gobernanza v3](../governance-loop.md).
