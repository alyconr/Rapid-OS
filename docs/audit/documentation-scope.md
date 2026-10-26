---
title: Documentation Coverage Audit
description: Initial coverage of the documentation against the capabilities implemented in Rapid OS v3.
---

# Documentation Coverage Audit

This page summarizes the first documentation audit carried out on Rapid OS v3. Its purpose is to maintain an explicit relationship between the **implemented product** and the **documented product**.

## Audited baseline

The first version of the portal was built against the release state of Rapid OS v3.0.0, which includes:

- PEP 517/518 packaging;
- global `rapid` CLI;
- v2 compatibility;
- Project Intelligence;
- Context Compiler;
- Spec Registry;
- Execution Policy and Run Registry;
- Harness Capability Registry;
- Evidence Engine;
- Behavioral Evals;
- validation and diagnostics;
- stable installers;
- Python 3.10–3.13 CI matrix.

## Coverage by area

| Implemented area | Main document | Status |
| --- | --- | --- |
| Product purpose and boundaries | [What is Rapid OS](../concepts/what-is-rapid-os) | Covered |
| Installation and requirements | [Getting Started](../getting-started) | Covered |
| Use cases | [Use cases](../guides/use-cases) | Covered |
| End-to-end flow | [Governance Loop](../governance-loop) | Covered |
| Project Intelligence | [Architecture v3](../architecture/rapid-os-v3) | Covered technically |
| Context Compiler | [Architecture v3](../architecture/rapid-os-v3) | Covered technically |
| Spec Registry | [CLI](../cli) + [Architecture v3](../architecture/rapid-os-v3) | Covered |
| Execution Policy / Runs | [CLI](../cli) + [Governance Loop](../governance-loop) | Covered |
| Harness profiles and capabilities | [Capabilities and permissions](../guides/permissions-capabilities) | Covered |
| Evidence Engine | [Governance Loop](../governance-loop) + [CLI](../cli) | Covered |
| Behavioral Evals | [Governance Loop](../governance-loop) + [CLI](../cli) | Covered |
| File structure | [File structure](../guides/project-layout) | Covered |
| RAPIDxxx diagnostics | [CLI](../cli) | Covered |
| Release v3.0.0 | [Release v3.0.0](../release-v3.0.0) | Covered |
| Release checklist | [Release checklist](../release-checklist) | Covered |
| Portal maintenance | [Maintaining the documentation](../contributing/documentation) | Covered |

## Main findings

### 1. The existing documentation was technically rich, but repository-oriented

The architecture and CLI documents describe internal contracts, diagnostics, and entities well, but a new user needed an earlier layer that answered:

- what Rapid OS is;
- what it is for;
- when to use it;
- what it does not do;
- how to get started;
- which files it modifies;
- how to interpret "permissions" and capabilities.

The new information architecture covers that layer.

### 2. "Permissions" required a product definition

Rapid OS does not implement an operating-system authorization system. The equivalent concept within the product is the **Harness Capability Registry**. The documentation now separates:

- declared capability;
- harness compatibility;
- contract requirement;
- observable evidence;
- evaluation verdict.

### 3. The documentation source had to be single

The Docusaurus portal uses `docs/` directly as its source. There is no second content folder inside `website/`.

This reduces drift between the documentation visible on GitHub and the published documentation.

### 4. The portal must fail when the documentation breaks

The configuration treats broken links as an error, and the CI workflow runs:

```bash
npm ci
npm run typecheck
npm run build
```

A PR that breaks navigation or documentation compilation must fail before merge.

## Recommended next coverage

The next iteration should go deeper into operational tutorials, not just reference:

1. a complete "first governed project" tutorial;
2. recipes per mode: feature, bugfix, refactor, hardening, and research;
3. complete `evidence.json` examples for each `EvidenceKind`;
4. a cookbook for `.rapid-os/policy.json` policies;
5. a `HarnessProfile` cookbook;
6. troubleshooting per `RAPIDxxx` diagnostic;
7. CI/CD integration;
8. official deployment of the documentation portal.
