---
title: Core Concepts
description: Concepts, models, and entities in the Rapid OS v3 governance loop.
---

# Core Concepts

Rapid OS organizes engineering governance around structured entities, immutable contracts, and SHA-256 cryptographic digests. This guide introduces the system's core concepts.

## 1. Project Intelligence (`ProjectModel`)

`ProjectModel` represents Rapid OS's deterministic knowledge about a repository. `rapid scan` generates it as a collection of normalized facts (`ProjectFact`). Each fact includes a category (language, framework, testing, database, packaging, Docker, monorepo, and others), detected values and versions, and evidence identifying the source file (such as `pyproject.toml` or `package.json`), reason, and confidence. `rapid scan --write` explicitly saves it to `.rapid-os/project.json`.

## 2. Context Compiler (`CompiledContext`)

`rapid context` extracts and assembles only the information a coding harness needs for a specific task.

- **Task mode:** `feature`, `bugfix`, `refactor`, `hardening`, `research`, or `general`.
- **Strict budget (`--max-chars`):** Limits generated Markdown so it does not overwhelm the LLM context window.
- **Relevance:** Prioritizes project standards, scan facts relevant to the mode, and specs marked ready.
- **Traceability (`ContextManifest`):** Records the SHA-256 digest of each included fragment, showing exactly what the agent received.
- **Read-only:** `rapid context` never modifies repository files.

## 3. Specification Registry (`SpecRecord` and `SpecRevision`)

Rapid OS replaces ephemeral notes with a formal spec registry under `.rapid-os/specs/<spec-id>/`.

- **Authoring states:** `draft` (in progress), `ready` (frozen and ready for a run), and `archived` (retired or completed).
- **Immutable revisions:** Each edit creates a new revision (`0001.json`, `0002.json`, ...) with its own SHA-256 `content_digest`. A running run stays permanently bound to one specific revision, so later spec changes cannot silently alter it.

## 4. Execution Policy (`ExecutionPolicy`)

Stored in `.rapid-os/policy.json`, the execution policy defines team operating rules: risk levels (`low`, `medium`, `high`, `critical`), whether work can use the current workspace or needs isolation, and required gates (such as `gate.tests`, `gate.lint`, and `gate.review`).

## 5. Execution Contract (`ExecutionContract`)

Created by `rapid run create`, the execution contract is the foundational record of a run. It immutably freezes the exact spec and revision, compiled context and manifest, project snapshot, applicable policy, designated harness, and assigned tasks (`T001`, `T002`, ...). Its `contract_digest` is the cryptographic root for the rest of the lifecycle.

## 6. Run State Ledger (`RunState`)

`.rapid-os/runs/<run-id>/states/` is an append-only ledger. Each transition creates a sequentially numbered file (`0001.json`, `0002.json`, ...).

- **Run states:** `prepared` → `active` → `finished` (or `failed`, `cancelled`, or `blocked`).
- **Task states:** `pending` → `in_progress` → `done` (or `skipped` or `blocked`).
- **Gate disposition:** `pending` → `acknowledged` (declared by the operator) or `waived` (waived with a recorded reason).

## 7. Harness Capabilities (`HarnessProfile`)

Rapid OS does not grant operating-system permissions; it models capabilities a harness declares it supports:

- `supported`: The profile explicitly declares support.
- `unsupported`: The profile explicitly declares no support.
- `unknown`: There is no declaration; Rapid OS does **not** assume support.

Before authorizing work, `rapid harness resolve` compares contract requirements with the profile.

## 8. Run Evidence (`RunEvidence`)

`rapid evidence` ingests records of observed execution:

- Command output and exit codes.
- Test-suite results (`TEST_RESULT`).
- Version-control diffs (`GIT_RESULT`).
- Generated files copied to `.rapid-os/evidence/<run-id>/artifacts/` with size and SHA-256 hash.

Every evidence item is anchored to a state revision (`state_revision`) and a specific contract digest.

## 9. Behavioral Evaluations (`EvaluationReport`)

`rapid eval run` is a deterministic local engine independent of any LLM. It applies `BehavioralRuleset` v1 to collected evidence and returns:

- `PASS`: All requirements and gates have satisfactory valid evidence.
- `PASS_WITH_WAIVERS`: Requirements pass and gates were validly waived under policy.
- `UNVERIFIED`: Evidence is missing for a task or gate.
- `FAIL`: A test failed or a contract rule was violated.

## 10. Integrity Validation (`rapid validate`)

`rapid validate` checks referential and cryptographic integrity across `.rapid-os/` directories and files, detecting manual tampering, schema inconsistencies, or breaks in the SHA-256 provenance chain.

## 11. Porcelain layer: session, NextAction, playbook, shortcut, producer, and human gate

Above the governance engine (the *plumbing*: specs, runs, evidence, evaluation), Rapid OS provides an intent layer (the *porcelain*: `rapid start`, `next`, `check`, `finish`, `approve`, and others). See the complete [orchestration architecture](../architecture/orchestration.md).

- **Session (`.rapid-os/session.json`):** Remembers the active run, mode, harness, and repository state at start (`start_head`). It is local and unversioned; porcelain commands use it so you do not need to provide the run ID.
- **`NextAction`:** Deterministic response from `rapid next --json`. It includes `action.kind` (`author_spec`, `run_baseline`, `activate`, `implement_task`, `verify`, `await_human_approval`, `finish`, `done`, or `blocked`), the command, missing requirements, and progress. A pure function calculates it from the contract, state, and evidence, using the behavioral evaluator as an oracle.
- **Playbook (`templates/modes/<mode>.json`):** A mode template (`feature`, `bugfix`, `refactor`, `hardening`, `research`) with the `spec_template` and instructions for each action.
- **Shortcut:** A file that teaches a harness the workflow for a mode (`/rapid-feature`, and others), generated from `templates/shortcuts/` by `rapid shortcuts install`.
- **Porcelain producer:** The evidence `producer` field identifies who recorded it: `rapid:check`, `rapid:start`, `rapid:finish`, `rapid:attach`, `user`, or `harness:<id>`. Review evidence produced by `harness:*` cannot close a human gate.
- **Human gate:** `gate.peer_review`, `security_review`, `migration_review`, `manual_approval`, and `final_verification` are never acknowledged automatically. A person runs `rapid approve <gate>` in their terminal (with a TTY and no agent as an ancestor). This is best-effort protection; see [Product Boundaries](./product-boundaries.md).
