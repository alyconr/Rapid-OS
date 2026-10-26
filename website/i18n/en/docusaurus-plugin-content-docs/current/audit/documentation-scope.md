---
title: Documentation Coverage Audit
description: Initial coverage of Rapid OS documentation against implemented v3 capabilities.
---

# Documentation Coverage Audit

This page records the first audit of the Rapid OS v3 portal and keeps an explicit link between implemented and documented product behavior.

## Audited baseline

The first portal version targeted Rapid OS v3.0.0, including PEP 517/518 packaging, the global `rapid` CLI, v2 compatibility, Project Intelligence, Context Compiler, Spec Registry, Execution Policy and Run Registry, Harness Capability Registry, Evidence Engine, Behavioral Evals, validation and diagnostics, stable installers, and Python 3.10–3.13 CI.

## Coverage

| Implemented area | Main documentation | Status |
| --- | --- | --- |
| Purpose and product boundaries | [What is Rapid OS](../concepts/what-is-rapid-os) | Covered |
| Installation and requirements | [Getting Started](../getting-started) | Covered |
| Use cases | [Use cases](../guides/use-cases) | Covered |
| End-to-end workflow | [Governance Loop](../governance-loop) | Covered |
| Project Intelligence and Context Compiler | [Architecture v3](../architecture/rapid-os-v3) | Technically covered |
| Spec Registry and execution policy | [CLI](../cli), [Architecture v3](../architecture/rapid-os-v3), [Governance Loop](../governance-loop) | Covered |
| Harness profiles and capabilities | [Capabilities and permissions](../guides/permissions-capabilities) | Covered |
| Evidence and behavioral evaluations | [Governance Loop](../governance-loop), [CLI](../cli) | Covered |
| File layout | [Project layout](../guides/project-layout) | Covered |
| RAPIDxxx diagnostics | [CLI](../cli) | Covered |
| Releases | [Release v3.0.0](../release-v3.0.0), [Release checklist](../release-checklist) | Covered |
| Portal maintenance | [Documentation maintenance](../contributing/documentation) | Covered |

## Findings

The original architecture and CLI material was technically rich but repository-oriented. New users also needed explanations of what Rapid OS does, when to use it, what files it changes, and what it does not do. The information architecture now addresses those questions.

Rapid OS does not provide operating-system authorization. Its related product concept is the **Harness Capability Registry**. Documentation distinguishes declared capability, harness compatibility, contract requirements, observable evidence, and evaluation verdict.

Docusaurus reads directly from `docs/`; there is no second content source under `website/`. Broken links are configured to fail, and CI runs `npm ci`, `npm run typecheck`, and `npm run build`.

## Recommended next coverage

Continue with operational tutorials, recipes for each mode, examples for each `EvidenceKind`, policy and `HarnessProfile` cookbooks, diagnostics troubleshooting, CI/CD integration, and the official documentation deployment process.
