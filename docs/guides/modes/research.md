---
title: Modo Research
description: Spikes exploratorios, evaluación de alternativas técnicas y pruebas de concepto con RAPID OS.
---

# Modo Research

El modo **Research** está orientado a spikes técnicos, evaluación de bibliotecas, pruebas de concepto (PoC) y benchmarks donde el objetivo no es entregar código productivo inmediato, sino responder una duda de diseño o viabilidad.

---

## Filosofía del modo Research

- **Baja fricción**: Clasificado como `ExecutionClass.SPIKE` con riesgo bajo (`RiskLevel.LOW = 10`).
- **Compuertas flexibles**: Permite waivers justificados en compuertas de pruebas o revisiones exhaustivas.
- **Entregable centrado en conocimiento**: La evidencia primaria suele ser un documento de benchmark, informe comparativo o prototipo experimental (`artifact`).

---

## Flujo paso a paso

```mermaid
flowchart LR
    Idea["Pregunta técnica / Alternativas"] --> Spec["rapid spec create --mode research"]
    Spec --> Context["rapid context --mode research"]
    Context --> Run["rapid run create --classification spike"]
    Run --> Spike["Exploración & Benchmarks"]
    Spike --> Evidence["Registrar Evidencia (artifact)"]
    Evidence --> Eval["rapid eval run"]
```

---

## 1. Especificación del Spike

```bash
rapid spec create \
  --title "Spike comparativo de serializadores JSON para alta concurrencia" \
  --mode research \
  --objective "Evaluar rendimiento y consumo de memoria entre orjson y msgspec frente a json estándar" \
  --scope "Benchmarks aislados en scripts/benchmarks/" \
  --acceptance "Reporte cuantitativo con latencia percentil 99 y recomendaciones de migración" \
  --task "1. Crear harness de benchmark reproducible" \
  --task "2. Medir latencia con payloads de 10KB y 1MB" \
  --task "3. Generar informe de hallazgos técnicos" \
  --status ready
```

---

## 2. Compilar el Contexto de Investigación

```bash
rapid context \
  --spec spike-comparativo-de-serializadores-json \
  --harness cursor \
  --mode research \
  --objective "Exploración de librerías alternativas sin modificar código de producción" \
  --manifest
```

---

## 3. Crear el Run clasificado como Spike

```bash
rapid run create \
  --spec spike-comparativo-de-serializadores-json \
  --harness cursor \
  --classification spike \
  --risk low
```

Al ser un spike de riesgo bajo, la política por defecto minimiza las compuertas obligatorias y permite la entrega ágil de resultados.

---

## 4. Capturar Evidencia del Hallazgo (`artifact`)

Genera el archivo del informe (por ejemplo `reports/benchmark.json`) y crea el documento de autoría de la evidencia (`benchmark-evidence.json`):

```json
{
  "kind": "artifact",
  "producer": "bench-harness",
  "summary": "Reporte cuantitativo de benchmarking comparativo",
  "artifacts": [
    "reports/benchmark.json"
  ],
  "payload": {
    "label": "benchmark-summary"
  }
}
```

Registra la evidencia en el run:

```bash
rapid evidence add \
  --run spike-comparativo-de-serializadores-json-r1-run-001 \
  --input benchmark-evidence.json
```

---

## 5. Cierre y Transición al Ciclo Productivo

Ejecuta la evaluación para cerrar formalmente el run:

```bash
rapid eval run \
  --run spike-comparativo-de-serializadores-json-r1-run-001 \
  --write
```

Una vez concluido el spike de investigación con veredicto satisfactorio, el equipo puede promover las recomendaciones a una especificación de modo [`feature`](./feature.md) o [`refactor`](./refactor.md) para su implementación gobernada en el sistema.
