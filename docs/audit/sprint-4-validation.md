---
title: Sprint 4 Validation and Closure
description: Technical audit, reproducible lab coverage matrix, Product Truth validation, and Definition of Done for RAPID OS Sprint 4.
---

# Sprint 4 Validation and Closure

This document formally records the technical audit, pedagogical coverage, and deterministic verification of **Sprint 4: Hands-on Tutorials, Reproducible Labs & Coding Harness Integration** of the RAPID OS v3.0.0 documentation platform.

---

## 1. Sprint 4 Scope and Objectives

The primary goal of Sprint 4 was to turn the theoretical and normative knowledge of RAPID OS v3 into practical, reproducible learning experiences that software engineers and AI agents can run directly:

1. **Canonical Hands-on Labs**: Create 6 complete guided tutorials covering the full spectrum of engineering modes (`first-governed-project`, `feature`, `bugfix`, `refactor`, `hardening`, `research`).
2. **Reproducible Example Projects**: Provide 6 directories in `examples/` with a canonical structure (`starter/`, `solution/`, `tests/`, `README.md`) using **only the Python standard library** (zero external dependencies).
3. **Coding Harness Integration Guides**: Design realistic operational guides for the 5 main execution environments (`Claude Code`, `Codex / OpenAI CLI`, `Cursor`, `VS Code`, `Google Antigravity`).
4. **Strict External Execution Boundary**: Establish unambiguously the separation between the governance plane (RAPID OS) and the external execution plane (developer / coding harness).
5. **Product Truth and E2E Automation**: Validate every tutorial, example, CLI command, and JSON authoring contract through automated tests (`tests/test_documentation_labs.py`).

---

## 2. Deliverables Matrix

### 2.1 Canonical Documentation (`docs/`)

| Category | Document Path | Description / Purpose |
| :--- | :--- | :--- |
| **Tutorials** | `docs/tutorials/index.md` | Lab catalog, recommended progression, and prerequisites. |
| **Tutorials** | `docs/tutorials/first-governed-project.md` | Lab 1: First Governed Project (Task Tracker CLI, full Governance Loop). |
| **Tutorials** | `docs/tutorials/feature-lab.md` | Lab 2: Feature Lab (Booking Service, duplicate booking prevention). |
| **Tutorials** | `docs/tutorials/bugfix-lab.md` | Lab 3: Bugfix Lab (Discount Calculator, division by zero, mandatory regression tests). |
| **Tutorials** | `docs/tutorials/refactor-lab.md` | Lab 4: Refactor Lab (Payroll Processor, tax deduplication with strict baseline). |
| **Tutorials** | `docs/tutorials/hardening-lab.md` | Lab 5: Hardening Lab (Auth Token Manager, timing attack and SAST remediation). |
| **Tutorials** | `docs/tutorials/research-lab.md` | Lab 6: Research Lab (Cache Eviction Spike, LRU vs FIFO benchmark and decision artifact). |
| **Troubleshooting** | `docs/troubleshooting/tutorials.md` | Diagnostic guide and resolution of common lab errors. |
| **Integrations** | `docs/integrations/index.md` | Overview of coding harness integration and the execution boundary. |
| **Integrations** | `docs/integrations/claude-code.md` | Operational integration with Claude Code (interactive terminal, governance hooks). |
| **Integrations** | `docs/integrations/codex.md` | Integration with OpenAI Codex CLI (non-interactive batch execution). |
| **Integrations** | `docs/integrations/cursor.md` | Integration with the Cursor AI IDE (Agent mode, compiled context prompts). |
| **Integrations** | `docs/integrations/vscode.md` | Integration with VS Code and GitHub Copilot (extensions and integrated terminal). |
| **Integrations** | `docs/integrations/antigravity.md` | Integration with Google Antigravity (Advanced Agentic Coding, subagents). |
| **Audit** | `docs/audit/sprint-4-validation.md` | This validation document, coverage matrix, and DoD. |

### 2.2 Reproducible Example Projects (`examples/`)

| Lab | Directory | Problem Description | Test Suites |
| :--- | :--- | :--- | :--- |
| **Lab 1** | `examples/first-governed-project/` | Task Tracker CLI: adding `high`/`medium`/`low` priority. | `tests/test_app.py` |
| **Lab 2** | `examples/feature-lab/` | Booking Service: time slot collision validation. | `tests/test_booking.py` |
| **Lab 3** | `examples/bugfix-lab/` | Discount Calculator: division-by-zero fix and regression test. | `tests/test_discount.py` |
| **Lab 4** | `examples/refactor-lab/` | Payroll Processor: extracting the tax deduction calculation without altering the baseline. | `tests/test_payroll.py` |
| **Lab 5** | `examples/hardening-lab/` | Auth Token Manager: using `hmac.compare_digest` to neutralize timing attacks. | `tests/test_auth.py` |
| **Lab 6** | `examples/research-lab/` | Cache Eviction Spike: deterministic benchmark comparing hits/misses between LRU and FIFO. | `tests/test_cache.py` |
| **Catalog** | `examples/README.md` | Example index, execution guide, and reproducible verification. | — |

All projects include independent `starter/` folders (with the initial state or failing tests) and `solution/` folders (with the complete solution and passing tests), plus `__init__.py` for standard `unittest` discovery.

---

## 3. Product Truth Verification and Architectural Constraints

In strict alignment with RAPID OS's guiding principles and the lessons learned from Issue #40:

### 3.1 Zero Runtime Modifications (`rapid_os/`)
- No file in `rapid_os/cli/`, `rapid_os/domain/`, `rapid_os/adapters/`, or `rapid_os/core/` was altered.
- All functionality exercised in the labs uses the real behavior of the already-implemented `3.0.0` release.

### 3.2 Evidence Authoring Format (Evidence Authoring vs RunEvidence)
- It is strictly respected that the inputs for `rapid evidence add --input <file>` are an **authoring** file, so they must **NOT** contain `id`, `schema_version`, or `run_id`. The CLI and the domain assign the ID sequentially (`E001`, `E002`, etc.) and bind the evidence to the active Run's contract.
- All documented payloads contain only the keys allowed by each canonical `EvidenceKind`.

### 3.3 Deterministic Gate Acknowledgement Order
- It is documented and verified that post-execution gates (`gate.tests`, `gate.final-verification`) require the Run's tasks to have reached the `done` state (`rapid run task update ... --status done`). Acknowledging gates before completing tasks triggers `RAPID1014` (Precondition failed).
- It is documented that gates such as `gate.baseline` and `gate.tests` require evidence with a non-empty list of artifacts (`artifacts: ["..."]`).

### 3.4 External Execution Boundary
- All tutorials and integrations emphasize that RAPID OS **is not a model executor or a code runner**.
- The developer or the coding harness is the only actor responsible for creating files, running `python -m unittest`, generating output logs, and then invoking the RAPID OS CLI to record the evidence produced.

---

## 4. Automated Test Matrix (`tests/test_documentation_labs.py`)

A comprehensive suite of 6 automated tests was implemented to verify the full integrity of the Sprint 4 material:

1. `test_sprint4_mandatory_documents_exist`:
   - Verifies the physical existence on disk of the 6 tutorials, the 5 integration guides, the troubleshooting guide, the examples README, and the audit document.
2. `test_all_tutorial_labs_follow_canonical_pedagogical_template`:
   - Validates that all 6 labs contain **all** of the mandatory pedagogical sections.
3. `test_all_example_labs_starters_and_solutions_pass_tests`:
   - Checks the exact execution of the suites of the 6 examples: it deliberately verifies that `bugfix-lab/starter` fails with exit code 1, isolating the regression in `test_regression_expected_discount`, and that `bugfix-lab/solution` together with all the other starters and solutions pass cleanly with exit code 0.
4. `test_documented_cli_commands_in_tutorials_match_argparse`:
   - Extracts all `bash` code blocks in the tutorials via regex and validates that every invoked command and subcommand formally exists in the RAPID OS CLI's `argparse` parser tree.
5. `test_governance_e2e_full_lifecycle_in_temp_project`:
   - Runs a real E2E process in a temporary directory (`tempfile.TemporaryDirectory`), capturing authentic logs through subprocesses (`base.log` and `tests.log`) with real output and counters, verifying evidence ingestion, task completion, and evaluation with a deterministic **PASS** verdict.
6. `test_bugfix_lifecycle_and_gate_order_e2e`:
   - Runs the full Bugfix mode lifecycle in a temporary directory: validates that attempting to transition to `active` before acknowledging `gate.baseline` fails with `RAPID1014`, captures authentic baseline logs, acknowledges `gate.baseline` in the `prepared` state, transitions to `active`, implements the fix, validates that attempting to acknowledge `POST_EXECUTION` gates before marking the task as `done` fails with `RAPID1014`, and concludes with a deterministic **PASS** evaluation and full validation.

---

## 5. Quality Gate Results

| Quality Gate | Tool / Command | Result | Status |
| :--- | :--- | :--- | :--- |
| **Python Unit & Contract Tests** | `python -m unittest discover tests` | **322 tests passed**, 0 failures, 0 errors (37.6s) | ✅ PASS |
| **Docusaurus TypeScript Types** | `npm run typecheck` in `website/` | 0 TypeScript errors | ✅ PASS |
| **Docusaurus Static Build** | `npm run build` in `website/` | Successful HTML build, **0 broken links** | ✅ PASS |
| **Git Working Tree Hygiene** | `git status --short` | Only Sprint 4 docs, examples, sidebars, and test files | ✅ PASS |

---

## 6. PR #43 Findings Remediation

The four identified technical findings were resolved exhaustively:

1. **P0 — Authentic E2E evidence**: In `tests/test_documentation_labs.py`, all hardcoded simulated texts (`Ran 2 tests`, `OK`) were removed. The output of `subprocess.run` (including stdout, stderr, returncode, and real counters) was captured directly in `base.log` and `tests.log`, and its content verified before linking them as artifacts in the evidence.
2. **P0 — Correct Bugfix gate order**: In `docs/tutorials/bugfix-lab.md`, the execution sequence was updated to faithfully reflect the domain constraints: the `gate.baseline` gate (`PRE_EXECUTION`) is acknowledged while the Run is in the `prepared` state, before moving to `active` (avoiding `RAPID1014`). Afterwards, the `POST_EXECUTION` gates (`gate.tests`, `gate.final-verification`) are acknowledged after completing the contractual task (`T001 -> done`).
3. **P1 — Real regression in the Bugfix Starter**: In `examples/bugfix-lab/`, the defect characterization (`test_defect_characterization`, which documents the current anomalous behavior) was separated from the regression test (`test_regression_expected_discount`, which deliberately fails, proving the genuine existence of the bug). The CI suite in `test_documentation_labs.py` explicitly verifies the failure with exit code 1 in the starter and the clean 100% pass in the solution.
4. **P1 — Canonical Antigravity JSON**: In `docs/integrations/antigravity.md`, the `delegation` evidence JSON block was cleaned up, removing persisted internal state fields (`schema_version`, `id`, `run_id`) so that it strictly conforms to a valid authoring document for `rapid evidence add --input`.

---

## 7. Definition of Done (DoD) Checklist

- [x] The 6 hands-on tutorials implemented following the canonical pedagogical structure.
- [x] The 6 example projects implemented with `starter/`, `solution/`, `tests/`, and `README.md`.
- [x] All examples use only standard Python with no external libraries.
- [x] The 5 coding harness integration guides completed with a clear delimitation of responsibilities.
- [x] Lab-specific troubleshooting documented in `docs/troubleshooting/tutorials.md`.
- [x] Docusaurus navigation updated in `website/sidebars.ts` with intuitive categories.
- [x] Zero functional modifications to the `rapid_os/` runtime.
- [x] Automated test suite `tests/test_documentation_labs.py` added and passing 100% (6 exhaustive tests, 322 tests total in the repo).
- [x] Feature and Bugfix E2E cycles validated in a real environment with a deterministic `PASS` verdict.
- [x] Audit document `docs/audit/sprint-4-validation.md` updated with findings remediation.
- [x] No secrets, API keys, or private data exposed in documentation or code.
- [x] Branch `docs/sprint-4-hands-on-tutorials` ready for a Pull Request to `develop`.
