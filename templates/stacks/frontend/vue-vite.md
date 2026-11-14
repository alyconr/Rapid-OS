# 💚 TECH STACK: VUE VITE
- **Runtime:** Node.js 24 (Active LTS), TypeScript strict.
- **Framework:** Vue 3 (`<script setup>`) + Vite (SPA).
- **Routing:** Vue Router.
- **State:** Pinia.
- **Testing:** Vitest + @vue/test-utils.
- **Linting:** ESLint + Prettier.
- **Package manager:** pnpm.
- **Supply chain:** `pnpm-workspace.yaml` sets `minimumReleaseAge: 10080` (seven days, in minutes; pnpm 10.16), `trustPolicy: no-downgrade` (pnpm 10.21) and `blockExoticSubdeps: true` (pnpm 10.26), so pnpm 10.26 or later. If the project has no `pnpm-workspace.yaml` yet, create it with these three settings when scaffolding (a single package needs no `packages` field). Without them semgrep `p/owasp-top-ten` fails the security workflow. Sources: https://pnpm.io/settings, https://github.com/pnpm/pnpm/releases/tag/v10.16.0, https://github.com/pnpm/pnpm/releases/tag/v10.21.0, https://github.com/pnpm/pnpm/releases/tag/v10.26.0.
- **Version Control:** Git.
