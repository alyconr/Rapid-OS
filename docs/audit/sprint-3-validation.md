---
title: Sprint 3 Validation and Closure
description: Coverage audit, validation matrix, and Definition of Done for Sprint 3 of the RAPID OS Documentation Platform.
---

# Sprint 3 Validation and Closure

This document formally records the technical audit and coverage of **Sprint 3: Governance Guides, Engineering Modes & Diagnostic Cookbooks** of the RAPID OS v3.0.0 documentation platform.

---

## 1. Sprint 3 Scope and Objectives

Sprint 3 aimed to go deeper into the advanced operational aspects of RAPID OS:
- Document the **5 engineering modes** (`feature`, `bugfix`, `refactor`, `hardening`, `research`) in detail.
- Provide **practical cookbooks** with real payloads for policies, contracts, harness profiles, the 9 evidence types, and behavioral evaluations.
- Compile an **exhaustive catalog of `RAPIDxxx` diagnostics** with explanations and remediation steps.
- Document **CI/CD pipeline integration** (GitHub Actions, exit codes, and strict validation).

---

## 2. Delivered Files Matrix

| Category | Document Path | Description / Purpose |
| :--- | :--- | :--- |
| **Engineering Modes** | `docs/guides/modes/index.md` | Overview of modes, relationship with the Context Compiler and Policy. |
| **Engineering Modes** | `docs/guides/modes/feature.md` | Full cycle for governed new-feature development. |
| **Engineering Modes** | `docs/guides/modes/bugfix.md` | Reproduction flow, mandatory regression test, and resolution. |
| **Engineering Modes** | `docs/guides/modes/refactor.md` | Refactoring with a mandatory baseline and 100% test parity. |
| **Engineering Modes** | `docs/guides/modes/hardening.md` | Security, CVEs, SAST analysis, and high-risk gates. |
| **Engineering Modes** | `docs/guides/modes/research.md` | Exploratory spikes (`ExecutionClass.SPIKE`), benchmarks, and artifacts. |
| **Cookbooks** | `docs/cookbooks/policies-and-contracts.md` | Configuration of `.rapid-os/policy.json`, gates, risks, and waivers. |
| **Cookbooks** | `docs/cookbooks/harness-profiles.md` | Built-in profiles, project profiles, and `capabilities.lock`. |
| **Cookbooks** | `docs/cookbooks/evidence-engine.md` | Real JSON formats for the 9 evidence types and verification. |
| **Cookbooks** | `docs/cookbooks/behavioral-evaluations.md` | Deterministic evaluations, verdicts, and semantic replay protection. |
| **Troubleshooting** | `docs/troubleshooting/diagnostics.md` | Catalog of `RAPID100` to `RAPID1229` diagnostics and remediation. |
| **CI/CD** | `docs/guides/ci-cd-integration.md` | Integration with GitHub Actions, pre-commit, and strict validation. |
| **Audit** | `docs/audit/sprint-3-validation.md` | Compliance matrix and Definition of Done for Sprint 3. |

---

## 3. Product Truth Verification

While producing all the Sprint 3 material, the following product-truth boundaries were rigorously verified:

1. **No autonomous LLM execution**: It was emphasized that RAPID OS does not invoke agents or models on its own; it governs specifications, context, and contracts.
2. **Offline, deterministic evaluation**: It was explicitly clarified that `rapid eval run` does not use "LLM-as-a-judge", but logical and mathematical rules over state and evidence.
3. **Capabilities as declarations**: It was reinforced that a harness capability is a declaration of tool compatibility, not a guarantee of correct execution nor operating-system sandboxing.
4. **PASS verdict without absolute claims**: It was clarified that `EvaluationVerdict.PASS` certifies that the gates and evidence rules are satisfied, but does not mathematically guarantee the total absence of bugs in the software.

---

## 4. Definition of Done (DoD) Checklist

- [x] All new documentation pages have valid frontmatter (`title`, `description`).
- [x] Flow diagrams use standard Mermaid syntax (`mermaid`).
- [x] Code blocks reflect the real v3.0.0 CLI interface with no fictitious flags.
- [x] Navigation integrated in `website/sidebars.ts` with an intuitive hierarchy.
- [x] `tests/test_documentation_contract.py` updated with validations for the new slugs and contracts.
- [x] `npm run typecheck` passes with 0 TypeScript errors.
- [x] `npm run build` passes with 0 broken links (`onBrokenLinks: 'throw'`).
- [x] Full Python test suite executed and passing at 100%.

---

## 5. Post-Merge Product Truth Remediation — Issue #40

After Sprint 3 was merged into `main` (PR #38), a later audit identified technical discrepancies in documentation examples that the original unit tests did not catch. A comprehensive remediation (Issue #40) was carried out on the `fix/docs-sprint3-product-truth` branch.

### 5.1 Findings and Root Cause

1. **Evidence Engine CLI (`rapid evidence add`)**:
   - *Discrepancy*: Fictitious flags such as `--kind`, `--producer`, `--summary` were documented.
   - *Cause*: The CLI only supports `--run <id>`, `--input <file>`, and `--json`.
   - *Remediation*: Complete rewrite of the `docs/cookbooks/evidence-engine.md` cookbook and the mode guides (`feature.md`, `bugfix.md`, `refactor.md`, `hardening.md`, `research.md`) to structure JSON authoring files and pass them via `--input <file>`.

2. **Evidence Authoring Schema and Strict Validation**:
   - *Discrepancy*: Example documents included fields not allowed in `payload`, or gate identifiers based on enums (`implementation_tests`) instead of the contract's canonical IDs (`gate.tests`, `gate.baseline`, `gate.review`).
   - *Cause*: `RunEvidence.from_dict` and `PAYLOAD_REQUIRED_KEYS` enforce strict closed-key validation (`RAPID1206`, `RAPID1207`).
   - *Remediation*: Precise documentation of the 9 canonical `EvidenceKind` types with minimal, exact schemas.

3. **Harness Profiles Schema and Capability Catalog**:
   - *Discrepancy*: `harness-profiles.md` presented `capabilities` as a dictionary with a nonexistent `conditional` status and invented capabilities (`terminal.execute`, `filesystem.write`).
   - *Cause*: `HarnessProfile` requires a list of `CapabilitySupportDeclaration` objects (`capability_id`, `status`, `reason`). The only valid statuses are `supported`, `unsupported`, `unknown` (`CapabilitySupportStatus`).
   - *Remediation*: Full alignment with the canonical catalog of 11 capabilities (`CANONICAL_CAPABILITY_IDS`).

4. **Diagnostics Catalog**:
   - *Discrepancy*: `RAPID1101` and `RAPID1106` listed fictitious IDs and `conditional` statuses.
   - *Remediation*: Update of `docs/troubleshooting/diagnostics.md` to canonical IDs and statuses.

5. **CI/CD Integration**:
   - *Discrepancy*: The example pipeline blindly iterated over `.rapid-os/runs/*/` with `--require-pass`, breaking active runs or concurrent branches.
   - *Remediation*: Separation into the 3 independent CI checks (`rapid validate --strict`, `rapid harness resolve`, `rapid eval run`), removal of "production-ready" claims, and addition of minimal permissions (`contents: read`).

### 5.2 Automated Contract Tests Added

`tests/test_sprint3_remediation_contract.py` was added (11 rigorous automated tests) validating:
- Absence of invalid flags in the `rapid evidence add` CLI parser.
- Strict validation, with no silent omissions, of the cookbook's 9 JSON blocks against `PAYLOAD_REQUIRED_KEYS`.
- Strict rejection (`RAPID1206`) of unknown fields in evidence payloads.
- Deserialization and serialization validation of `HarnessProfile` with a list of `CapabilitySupportDeclaration`.
- Rejection of non-canonical statuses (such as `conditional`) in harness profiles.
- Consistency of the 11-capability catalog in the documentation against `CANONICAL_CAPABILITY_IDS`.
- Isolation governance semantics: an explicit test confirming that `mode: "current"` produces `FAIL` for the `gate.workspace-isolation` gate (`rule.gate.workspace_isolation.v1`), requiring `mode: "isolated"`.
- Direct docs-to-fixtures link: the end-to-end test directly ingests the 9 JSON blocks extracted from `evidence-engine.md` with no intermediaries or duplication, validating ingestion and verification of the 9 types via the CLI (`rapid evidence verify`).

### 5.3 Quality Gates Verification

- **Python Tests**: 316/316 tests passing (`discover tests`).
- **Docusaurus TypeScript**: 0 type errors (`npm run typecheck`).
- **Docusaurus Build**: Clean build, 0 broken links (`npm run build`).
