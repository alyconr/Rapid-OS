---
title: Rapid OS 3.2.0.dev0 Technical Audit
description: Findings and release-readiness assessment for the audited development checkout.
---

# Rapid OS 3.2.0.dev0 Technical Audit

## Scope and verdict

Audited revision: `570382dd` on `main` (`docs: sync the documentation with 3.2.0.dev0`). The CLI reported `Rapid OS 3.2.0.dev0`; the audit found no corresponding local release tag. This review concerns a development checkout, not a certified published artifact.

The move toward governed engineering is implemented, but the audit recommended against promoting this revision as stable evidence that the delivered tree was verified. It found gaps between valid ledger evidence and evidence about the current code. The review combined implementation reading, documentation comparison, existing tests, and temporary-directory reproductions. It was not exhaustive across all stacks, deployments, or harnesses; priorities are engineering severity, not CVSS scores.

## Findings

| ID | Priority | Finding | Validation recorded |
| --- | --- | --- | --- |
| A1 | High | Any successful command can provide passing architecture evidence. | Real execution and evidence registration |
| A2 | High | Earlier passing evidence survives code changes and later failed checks. | Ledger reproduction and `finish` review |
| A3 | High | A worktree can replace the governing architecture rule. | Existing test and resolver review |
| A4 | Medium | Tracked changes from before a run are attributed to it. | Git reproduction |
| A5 | Medium | Skipped `unittest` cases can be counted as passed. | Parser reproduction |

### A1: Architecture gate lacks verifier identity

The evaluator accepted any successful `COMMAND_RESULT` with an artifact for `ARCHITECTURE_CHECK`; `run_check` could attach that gate to an arbitrary command. The audit reproduced this with a no-op command. Recommended fix: dedicated verifier evidence containing verifier identity, rule version/digest, analyzed sources, and structured result; generic commands should not satisfy the gate.

### A2: Evidence is not tied to the code snapshot

Evidence binds to governance state, not a complete code snapshot. `finish` records changed paths but does not rerun checks or compare the delivered tree with the verified tree. Ordinary failed checks return no ledger evidence, so prior success may still classify as passing. Recommended fix: bind checks and reviews to a tree digest, invalidate on changes, record failed attempts, and define supersession so corrected failures can recover.

### A3: Worktree policy can override the governing rule

The resolver preferred a worktree-local `architecture.json`, allowing a relaxed rule to replace the main project's expectation. The audit cited an existing test that intentionally demonstrates this behavior. Recommended fix: pin the rule digest in the run contract or require explicit policy review.

### A4: Pre-run changes can be attributed to the run

The start snapshot records HEAD and untracked names, not the full working-tree/index contents. A later diff from HEAD includes earlier tracked edits; changed contents of pre-existing untracked files may be excluded. Recommended fix: capture and compare a content/state manifest or require a clean tree where strict attribution is needed.

### A5: Skipped tests can inflate pass counts

The parser handled skipped tests in failure summaries but treated `OK (skipped=N)` as all passing. Recommended fix: parse successful unittest summaries, distinguish passed and skipped, and define expected-failure handling.

## Strengths recorded

The audit found clear domain/adapter/orchestration separation, deterministic evaluation without an LLM, distinctions between declarations, capabilities, evidence, and verdicts, digest-backed artifacts and replay checks, honest documentation of human approval limits, argv-based checks without a shell, and architecture guidance extending governance beyond prompts.

## Tests and limits recorded

The full `python -m unittest discover -s tests` run timed out after 200 seconds and was not certified. A directed suite recorded 101 passing tests; a worktree priority test passed and confirmed finding A3; a reproduction script confirmed A1, A2, A4, and A5; and `python -m rapid_os --version` reported 3.2.0.dev0. The audit did not run clean wheel/sdist builds, external scanners, deployments, every runner, or a full OS matrix.

## Release priorities

Before stable promotion, address A1–A3 and make each machine gate establish which verifier applied which rule to which code snapshot. Next address A4–A5, add adversarial end-to-end cases, Windows CI, and a complete suite/package run. Then align documentation and versioning, harden the repository's supply chain, and add structured evidence adapters for test runners.

Rapid OS is a useful local governed-engineering layer for cooperative agents, but the audit says it should not be presented as an adversarial-agent security boundary or proof that the delivered tree exactly matches the verified tree. Its proposed chain is policy → verifier → code snapshot → evidence → approval.
