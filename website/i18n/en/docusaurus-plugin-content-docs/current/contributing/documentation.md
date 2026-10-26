---
title: Maintaining the Documentation
description: Rapid OS documentation architecture and rules for preventing drift between the product, CLI, and site.
---

# Maintaining the Documentation

Rapid OS public documentation uses **Docusaurus** for presentation and keeps canonical Markdown content in `docs/`.

## Structure

```text
docs/                         # canonical content
website/
├── docusaurus.config.ts       # site configuration
├── sidebars.ts                # navigation structure
├── src/css/custom.css         # theme
└── package.json               # dependencies and scripts
```

Docusaurus reads `../docs` directly. Do not create a second copy of the same documents in `website/docs`.

## Product truth rule

Documentation should describe only behavior that can be verified in the parser, domain, tests, or release contracts.

Before documenting a new capability:

1. Confirm it exists in code.
2. Confirm the actual commands and flags.
3. Confirm whether the command is read-only or writes state.
4. Document the files it creates or modifies.
5. Document relevant exit codes and diagnostics.
6. Distinguish declared capability, evidence, and verdict.
7. Build the Docusaurus site.

## Local development

```bash
cd website
npm install
npm run start
```

## Production build

```bash
cd website
npm install
npm run build
```

Broken links must be treated as build errors.
