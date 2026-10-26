---
title: Sprint 1 — Documentation Foundation Validation
description: Audit record and requirements to close the first Docusaurus sprint.
---

# Sprint 1 — Documentation Foundation Validation

## Objective and scope

Consolidate the Docusaurus portal without altering the capabilities of the Rapid OS Python core. This document records verifiable criteria, evidence, and limits of the initial audit.

### Baseline

- Product: Rapid OS v3.0.0, release-readiness PR #33.
- Documentation: PR #34, branch `docs/docusaurus-v3`.
- Canonical source: `docs/`.
- Site application: `website/`.
- Existing functional documentation: `docs/cli.md`, `docs/governance-loop.md`, `docs/architecture/rapid-os-v3.md`, and release guides.

## Implemented controls

| Control | Expected evidence |
| --- | --- |
| Single content source | `docs.path = '../docs'`, no `website/docs/` |
| Valid navigation | All sidebar IDs correspond to Markdown files |
| Internal links | Docusaurus `onBrokenLinks: 'throw'` and site build |
| CLI contract and product boundaries | `tests/test_documentation_contract.py` |
| Core compatibility | Existing Python tests workflow |
| Documentation build | Documentation workflow: `npm run typecheck` and `npm run build` |
| Release review | Documentation PR separate from the release PR |

## Gaps before publishing a stable portal version

1. **Reproducible lockfile**: generate and commit `website/package-lock.json` with npm, replace `npm install` with `npm ci`, and enable caching using `website/package-lock.json`. Do not manually create a lockfile without dependency resolution.
2. **Clean-environment validation**: verify the build after installing with the lockfile and repeat on the minimum declared Node.js.
3. **Rapid OS installation tests**: keep the Python/wheel/sdist release tests and the Docusaurus portal tests independent.
4. **Published version and domain**: the `url`/`baseUrl` value represents the intended GitHub Pages path; it is not evidence of deployment.
5. **Editorial consistency**: the documentation is now maintained in English only, with no divergent copies.
6. **Detailed content audit**: in later sprints, check every advanced example against the parser, schema, and tests, in addition to the minimal static check.

## Sprint 1 Definition of Done

- [x] Site and content separated into `website/` and `docs/`.
- [x] Portal with navigation organized by user goals.
- [x] Documentation of the product's purpose, use cases, capabilities, and limits.
- [x] Workflow dedicated to typecheck and build.
- [x] Broken internal link detection configured.
- [x] Static documentation-contract tests added to the repository.
- [x] `website/package-lock.json` generated and validated by npm.
- [x] CI with reproducible `npm ci` installation.
- [x] Final validation of the most recent review of PR #34.

**Closure criterion:** do not declare Sprint 1 finished until all boxes are verified in CI and the PR remains free of regressions.
