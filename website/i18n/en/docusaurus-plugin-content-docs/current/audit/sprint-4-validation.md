---
title: Sprint 4 Validation and Closure
description: Audit of reproducible labs, tutorials, harness integrations, and product truth.
---

# Sprint 4 Validation and Closure

Sprint 4 turned Rapid OS v3 knowledge into practical and reproducible learning materials.

## Scope

The sprint delivered six guided labs: first governed project, feature, bugfix, refactor, hardening, and research; six standard-library-only example projects with starter and solution states; and integration guides for Claude Code, Codex, Cursor, VS Code, and Google Antigravity. It also documented troubleshooting and the boundary between governance and external execution.

Examples cover a task tracker, booking collision prevention, discount division by zero, payroll deduction refactoring, constant-time token comparison, and deterministic LRU/FIFO cache benchmarking.

## Product truth and architecture

No runtime code under `rapid_os/` was changed. Evidence authoring JSON omits generated `id`, `schema_version`, and `run_id`; the CLI and domain assign IDs and bind evidence to the run. Payloads use only canonical `EvidenceKind` fields. Post-execution gates require tasks to be `done`; baseline and test gates require non-empty artifact lists. Rapid OS is not a code runner: the developer or external harness edits files, executes tests, captures logs, and registers evidence.

## Automated validation recorded

The source audit describes checks for required documents, lab structure, starter/solution behavior, CLI commands in tutorial code blocks, governance semantics, and authoring contracts. It recorded six automated checks for the lab suite. These results describe the sprint baseline and should not be read as current CI evidence.
