---
title: Behavioral Evaluations (Behavioral Evals)
description: Cookbook for the deterministic evaluation of contracts, gates and evidence in RAPID OS.
---

# Behavioral Evaluations (Behavioral Evals)

The RAPID OS **Behavioral Evaluation** engine (`BehavioralEvaluator`) performs offline, deterministic audits of a run's execution. It evaluates the contract (`ExecutionContract`), the lifecycle state (`RunState`) and the set of immutable evidence (`RunEvidence[]`) against a set of canonical rules (`BehavioralRuleset`).

---

## Product Truth: The nature of the Evaluation

> **Product Truth Principle**:
> 1. RAPID OS does **not** invoke LLM models to evaluate code ("LLM-as-a-judge"). The evaluation is **100% mathematical, logical and reproducible**.
> 2. A state declaration (e.g. `GateDisposition.ACKNOWLEDGED`) is a user assertion; if it has no observable evidence backing it, the evaluator marks it as `UNVERIFIED`.
> 3. The `PASS` verdict certifies that the rules and gates required by the policy are satisfied by the recorded evidence. It **does not mathematically guarantee that the software is free of defects**.

---

## 1. The four Evaluation verdicts (`EvaluationVerdict`)

| Verdict | Meaning | CI requirement (`--require-pass`) |
| :--- | :--- | :--- |
| **`pass`** | All mandatory gates and requirements have valid evidence that satisfies them 100%. | **Passes** (Exit code `0`) |
| **`pass_with_waivers`** | All gates are satisfied, but one or more waivable gates were formally exempted with a justified waiver. | **Passes** (Exit code `0`) |
| **`unverified`** | There are acknowledged gates in the state that lack the corresponding observable evidence record. | **Fails** (Exit code `1`, diagnostic `RAPID1225`) |
| **`fail`** | At least one mandatory gate was rejected or skipped, or a test failed according to the recorded evidence. | **Fails** (Exit code `1`, diagnostic `RAPID1226`) |

---

## 2. Running the Evaluation (`rapid eval run`)

By default, the evaluation runs in read-only mode so you can inspect the result in the terminal:

```bash
# In-memory evaluation (Read-only)
rapid eval run --run my-run-001

# Evaluation in JSON format
rapid eval run --run my-run-001 --json
```

### Persist the evaluation report (`--write`)
To record the immutable report at `.rapid-os/evals/<run-id>/reports/eval_report_0001.json`:

```bash
rapid eval run --run my-run-001 --write
```

### Strict mode for continuous integration (`--require-pass`)
In CI/CD flows or pre-merge hooks, you can require the command to fail if the verdict is not `pass` or `pass_with_waivers`:

```bash
rapid eval run --run my-run-001 --require-pass
```

---

## 3. Inspection and Semantic Replay

RAPID OS lets you query the history of evaluation reports generated for a run:

```bash
# List generated reports
rapid eval list --run my-run-001

# Inspect the detail of a report revision
rapid eval show --run my-run-001 --revision 1
```

### Protection against manual tampering
Every time a report is loaded (`rapid eval show` or `rapid validate`), RAPID OS performs a **mandatory semantic replay**: it recomputes the assertions over the contract, the state and the actual evidence on disk. If someone manually altered the report file to change a `FAIL` into a `PASS`, the system detects the discrepancy and emits the diagnostic `RAPID1223`.

---

## 4. Structure of an Evaluation Report (`EvaluationReport`)

A generated report contains the following fundamental blocks:

```json
{
  "schema_version": 1,
  "run_id": "my-run-001",
  "revision": 1,
  "verdict": "pass",
  "ruleset_version": 1,
  "ruleset_digest": "3a4b5c6d...",
  "contract_digest": "e1f2a3b4...",
  "state_digest": "9f8e7d6c...",
  "evidence_set_digest": "4c3b2a1f...",
  "summary": {
    "total_assertions": 8,
    "satisfied": 8,
    "waived": 0,
    "unverified": 0,
    "failed": 0
  },
  "assertions": [
    {
      "id": "A001_contract_integrity",
      "category": "contract",
      "status": "satisfied",
      "target": "ExecutionContract",
      "reason": "Digest matches and spec is in ready state"
    },
    {
      "id": "A002_gate_implementation_tests",
      "category": "gate",
      "status": "satisfied",
      "target": "implementation_tests",
      "reason": "Evidence E001 (test_result) certifies 42 passing tests"
    }
  ]
}
```

---

## 5. Ruleset Versions: v1 vs v2 comparison

Starting with Rapid OS v3.2, the evaluation engine supports multiple rule versions (`BehavioralRuleset`):

| Feature | Ruleset v1 | Ruleset v2 (Default) |
| :--- | :--- | :--- |
| **Default version** | Compatible with historical runs | Active rule by default in `rapid eval run` |
| **Human Gates (`GateKind`)** | Accepted reviews issued by any producer (including `harness:*`) | **Rejects** `harness:*` producers for human review gates (`peer_review`, `security_review`, `migration_review`, `manual_approval`, `final_verification`). They stay `UNVERIFIED` if signed by a harness |
| **Automatic / Machine Gates** | Accepts `harness:*` and tools | Accepts `harness:*` and tools |
| **Expected Failures (`expectation: "fail"`)** | Evaluated as regular failures | Supported for defect reproduction verification (TDD/Bugfix); the evaluator produces `reproduction.<task-id>` assertions |
| **CLI `--ruleset`** | `--ruleset 1` | `--ruleset 2` |

> [!IMPORTANT]
> Reports saved with `--write` record their `ruleset_version`. When running `rapid eval show` or `rapid validate`, the semantic replay uses exactly the version declared in the report to guarantee immutable historical reproducibility.
