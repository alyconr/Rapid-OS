# Rapid OS Documentation Site

The Docusaurus application lives in `website/` while the canonical documentation content remains in the repository-level `docs/` directory.

This avoids maintaining two copies of the same technical documentation.

## Requirements

- Node.js 20+
- npm

## Local development

```bash
cd website
npm ci
npm run start
```

## Production build

```bash
cd website
npm ci
npm run typecheck
npm run build
```

The static output is generated in `website/build/`.

## Documentation source

Docusaurus is configured with:

```text
website/docusaurus.config.ts
    docs.path = ../docs
```

Add product documentation to `docs/`, then place the document in `website/sidebars.ts` when it should appear in the curated navigation.

## Languages

English is the default locale and the source in `docs/`. Spanish lives under `website/i18n/es/` and is selected from the language dropdown in the navbar. Pages missing from the Spanish locale fall back to English.
