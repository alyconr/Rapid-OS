---
title: Research Mode
description: Exploratory spikes, evaluation of technical alternatives, and proofs of concept with RAPID OS.
---

# Research Mode

**Research** mode is aimed at technical spikes, library evaluations, proofs of concept (PoC), and benchmarks where the goal is not to deliver production code right away but to answer a design or feasibility question.

---

## With the `/rapid-research` shortcut

```text
/rapid-research compare JSON and SQLite for storing the preferences
```

(In Codex: `$rapid-research …`.) The shortcut drives the whole run; installation and per-harness invocation are in the [shortcuts guide](../shortcuts.md).

What its playbook does (`templates/modes/research.json` and the Conductor's rules):

- A spike is low risk: only `gate.final-verification` remains; there is no baseline or mandatory tests.
- Findings are recorded with `rapid attach <path> --label "…"` (an `artifact` evidence, producer `rapid:attach`), linked to the task in progress (or to the one you indicate with `--task`).
- Tasks are closed with `rapid task done T00N --no-check`, because there are no tests to run.

The rest of this guide describes the same cycle with v3 commands (**Advanced mode**), useful for CI, debugging, and auditing.

---

## Philosophy of Research mode

- **Low friction**: Classified as `ExecutionClass.SPIKE` with low risk (`RiskLevel.LOW = 10`).
- **Flexible gates**: Allows justified waivers on test gates or exhaustive reviews.
- **Knowledge-centered deliverable**: The primary evidence is usually a benchmark document, a comparative report, or an experimental prototype (`artifact`).

---

## Step-by-step flow

```mermaid
flowchart LR
    Idea["Technical question / Alternatives"] --> Spec["rapid spec create --mode research"]
    Spec --> Context["rapid context --mode research"]
    Context --> Run["rapid run create --classification spike"]
    Run --> Spike["Exploration & Benchmarks"]
    Spike --> Evidence["Record Evidence (artifact)"]
    Evidence --> Eval["rapid eval run"]
```

---

## 1. Spike specification

```bash
rapid spec create \
  --title "Comparative spike of JSON serializers for high concurrency" \
  --mode research \
  --objective "Evaluate performance and memory consumption of orjson and msgspec versus standard json" \
  --scope "Isolated benchmarks in scripts/benchmarks/" \
  --acceptance "Quantitative report with 99th percentile latency and migration recommendations" \
  --task "1. Create a reproducible benchmark harness" \
  --task "2. Measure latency with 10KB and 1MB payloads" \
  --task "3. Generate a report of technical findings" \
  --status ready
```

---

## 2. Compile the research context

```bash
rapid context \
  --spec comparative-spike-of-json-serializers \
  --harness cursor \
  --mode research \
  --objective "Exploration of alternative libraries without modifying production code" \
  --manifest
```

---

## 3. Create the run classified as a spike

```bash
rapid run create \
  --spec comparative-spike-of-json-serializers \
  --harness cursor \
  --classification spike \
  --risk low
```

Since it is a low-risk spike, the default policy minimizes the mandatory gates and allows agile delivery of results.

---

## 4. Capture the finding's evidence (`artifact`)

Generate the report file (for example `reports/benchmark.json`) and create the evidence authoring document (`benchmark-evidence.json`):

```json
{
  "kind": "artifact",
  "producer": "bench-harness",
  "summary": "Quantitative report of comparative benchmarking",
  "artifacts": [
    "reports/benchmark.json"
  ],
  "payload": {
    "label": "benchmark-summary"
  }
}
```

Record the evidence in the run:

```bash
rapid evidence add \
  --run comparative-spike-of-json-serializers-r1-run-001 \
  --input benchmark-evidence.json
```

---

## 5. Closing and transition to the production cycle

Run the evaluation to formally close the run:

```bash
rapid eval run \
  --run comparative-spike-of-json-serializers-r1-run-001 \
  --write
```

Once the research spike concludes with a satisfactory verdict, the team can promote the recommendations to a specification in [`feature`](./feature.md) or [`refactor`](./refactor.md) mode for governed implementation in the system.
