---
title: Documentation Maintenance and Operations
description: Ongoing maintenance guidelines for the accuracy, security, and health of the Rapid OS v3 documentation site.
---

# Documentation Maintenance and Operations

This document sets operating guidelines to keep the **Rapid OS v3** documentation site technically healthy, secure, accurate, and current.

## 1. Maintenance schedule

### Monthly: link and dependency audit

1. **Update Node.js dependencies:** Check vulnerabilities with `npm audit` and update minor/patch versions while respecting pinned Docusaurus versions:
   ```bash
   cd website
   npm audit
   npm update
   ```
2. **Check for broken links:** Docusaurus configuration (`onBrokenLinks: 'throw'`) blocks internal broken links during every build. Periodically audit external links to repositories and coding harness tools.

### Quarterly: SEO and metadata audit

1. Verify that Open Graph and Twitter Card tags render correctly in preview tools (for example, opengraph.xyz).
2. Inspect `sitemap.xml` to ensure new site pages are indexed.
3. Check screen-reader compatibility and WCAG 2.1 AA accessibility with Lighthouse audits.

## 2. Documentation versioning strategy

### Canonical principle: documentation tracks the product

Rapid OS documentation evolves in sync with the product lifecycle:

- **Active version (`v3.1.1`):** `docs/` accurately reflects the current CLI release and deterministic v3 architecture.
- **Development branch (`develop`):** Holds changes pending release; CI builds and validates it, but it is **not published** to GitHub Pages until merged into `main`.

### New major/minor versions (Docusaurus versioning)

When a new minor or major product version ships (for example, Rapid OS v3.1.0 or v4.0.0):

1. **Snapshot the previous version:** Docusaurus has built-in documentation snapshotting:
   ```bash
   cd website
   npm run docusaurus docs:version 3.0.0
   ```
   This freezes the current content in `website/versioned_docs/version-3.0.0` and `website/versioned_sidebars/version-3.0.0-sidebars.json`.
2. **Update `docs/`:** The root `docs/` directory becomes the development (`Next`) version and reflects upcoming release features.
3. **Enable the version selector** in `website/docusaurus.config.ts`:
   ```ts
   navbar: {
     items: [
       { type: 'docsVersionDropdown', position: 'right' },
       // ...
     ],
   }
   ```
4. **Product truth for snapshots:** *Do not fabricate historical versions before v3.0.0.* Versions before the unified v3 architecture did not have this documentation set; artificial snapshots would misrepresent the product.

## 3. Contribution and review policy

- **Single source of truth:** Make documentation changes only in `docs/`. Do not duplicate or edit content in `website/build/` or create parallel folders in `website/docs/`.
- **Required automated verification:** Any PR affecting documentation must pass without warnings or errors:
  - `npm ci`
  - `npm run typecheck`
  - `npm run build`
  - Python documentation tests (`tests/test_documentation_labs.py`, `tests/test_documentation_deployment.py`).

## 4. The `site/` directory was removed

The repository used to contain a `site/` directory with the default Docusaurus template (`README.md`, `blog/`, `debug_rapid_config.py`, `docusaurus.config.ts`, and others). No workflow, test, packaging config, or document used it: the site is built and published **only** from `website/` (`docs.path = '../docs'`). It was removed to avoid having two Docusaurus projects. If you need the template, consult Git history; do not recreate `site/`. Documentation belongs in `docs/`, and navigation belongs in `website/sidebars.ts`.
