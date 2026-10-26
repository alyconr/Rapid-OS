---
title: Behavioral Evaluations
description: A cookbook for deterministic evaluation of contracts, gates, and evidence in Rapid OS.
---

# Behavioral Evaluations

Rapid OS's `BehavioralEvaluator` performs offline, deterministic audits of a run. It evaluates the `ExecutionContract`, `RunState`, and immutable `RunEvidence[]` against a `BehavioralRuleset`.

## What evaluation means

Rapid OS does not use an LLM as a judge. Evaluation is logical, mathematical, and reproducible. A state declaration such as `GateDisposition.ACKNOWLEDGED` is a claim; without observable supporting evidence it is `UNVERIFIED`. `PASS` means the required policy rules and gates are satisfied by recorded evidence. It does not prove that software is defect-free.

## Verdicts

| Verdict | Meaning | `--require-pass` |
| --- | --- | --- |
| `pass` | All required gates and requirements have valid supporting evidence. | Exit 0 |
| `pass_with_waivers` | Requirements pass, with one or more permitted, justified waivers. | Exit 0 |
| `unverified` | Acknowledged gates lack corresponding observable evidence. | Exit 1, `RAPID1225` |
| `fail` | A required gate failed, was rejected or skipped, or evidence reports a failed test. | Exit 1, `RAPID1226` |

## Run evaluation

Evaluation is read-only by default:

```bash
rapid eval run --run my-run-001
rapid eval run --run my-run-001 --json
```

Persist an immutable report with `--write`, or require a passing verdict in CI with `--require-pass`:

```bash
rapid eval run --run my-run-001 --write
rapid eval run --run my-run-001 --require-pass
```

## Inspect and replay reports

```bash
rapid eval list --run my-run-001
rapid eval show --run my-run-001 --revision 1
```

When a report is loaded, including during `rapid validate`, Rapid OS performs semantic replay against the actual contract, state, and evidence on disk. Manual edits that change a `FAIL` to `PASS` are detected as `RAPID1223`.

An `EvaluationReport` includes schema version, run and revision, verdict, ruleset version and digest, contract/state/evidence digests, summary counts, and individual assertions with status, target, and reason.

## Ruleset versions

Rapid OS v3.2 supports ruleset versions 1 and 2. Version 2 is the default. Version 1 remains for historical runs. Both accept harness evidence for machine gates; v2 rejects `harness:*` evidence for human review gates, leaving them unverified. Version 2 supports `expectation: "fail"` for bug reproduction and emits `reproduction.<task-id>` assertions. Select a version with `--ruleset 1` or `--ruleset 2`. Saved reports record their ruleset version, and semantic replay uses that version for historical reproducibility.
