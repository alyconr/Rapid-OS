---
title: Research Mode
description: Run technical spikes, evaluate alternatives, and build proofs of concept with Rapid OS.
---

# Research Mode

**Research** mode is for technical spikes, library evaluations, proofs of concept (PoCs), and benchmarks. The goal is to answer a design or feasibility question, not to immediately deliver production code.

## With the `/rapid-research` shortcut

```text
/rapid-research compare JSON and SQLite for storing preferences
```

In Codex, use `$rapid-research ...`. The shortcut guides the full run; see the [shortcuts guide](../shortcuts.md) for installation and harness invocation.

The playbook (`templates/modes/research.json` and the Conductor rules) works as follows:

- A spike is low risk and requires only `gate.final-verification`; there is no baseline or required test suite.
- Record findings with `rapid attach <path> --label "..."` (an `artifact` evidence item produced by `rapid:attach`), linked to the current task or to one specified with `--task`.
- Close tasks with `rapid task done T00N --no-check` because there are no tests to run.

The remaining guide describes the same workflow with v3 commands (**Advanced Mode**), useful for CI, debugging, and auditing.

## Research mode philosophy

- **Low friction:** Classified as `ExecutionClass.SPIKE` with low risk (`RiskLevel.LOW = 10`).
- **Flexible gates:** Allows justified waivers for test or comprehensive review gates.
- **Knowledge-focused deliverable:** Primary evidence is usually a benchmark document, comparison report, or experimental prototype (`artifact`).

## Step-by-step workflow

```mermaid
flowchart LR
    Idea[Technical question / alternatives] --> Spec[Create research spec]
    Spec --> Context[Compile research context]
    Context --> Run[Create spike run]
    Run --> Spike[Explore and benchmark]
    Spike --> Evidence[Register artifact evidence]
    Evidence --> Eval[Evaluate run]
```

### 1. Specify the spike

```bash
rapid spec create \
  --title "Compare JSON serializers under high concurrency" \
  --mode research \
  --objective "Evaluate performance and memory use of orjson and msgspec versus standard json" \
  --scope "Isolated benchmarks in scripts/benchmarks/" \
  --acceptance "Quantitative report with p99 latency and migration recommendations" \
  --task "1. Create a reproducible benchmark harness" \
  --task "2. Measure latency with 10KB and 1MB payloads" \
  --task "3. Write a report of technical findings" \
  --status ready
```

### 2. Compile research context

```bash
rapid context \
  --spec compare-json-serializers-spike \
  --harness cursor \
  --mode research \
  --objective "Explore alternative libraries without changing production code" \
  --manifest
```

### 3. Create a spike run

```bash
rapid run create --spec compare-json-serializers-spike --harness cursor --classification spike --risk low
```

Because this is a low-risk spike, the default policy minimizes required gates and allows results to be delivered quickly.

### 4. Capture finding evidence (`artifact`)

Generate a report file (for example, `reports/benchmark.json`) and an evidence authoring file (`benchmark-evidence.json`):

```json
{
  "kind": "artifact",
  "producer": "bench-harness",
  "summary": "Quantitative comparative benchmark report",
  "artifacts": ["reports/benchmark.json"],
  "payload": {"label": "benchmark-summary"}
}
```

Register the evidence:
```bash
rapid evidence add --run compare-json-serializers-spike-r1-run-001 --input benchmark-evidence.json
```

### 5. Close and move to production work

Evaluate the run to close it formally:
```bash
rapid eval run --run compare-json-serializers-spike-r1-run-001 --write
```

After a successful research spike, the team can promote recommendations into a [`feature`](./feature.md) or [`refactor`](./refactor.md) spec for governed implementation.
