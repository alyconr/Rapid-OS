# 🐍 TECH STACK: PYTHON FASTAPI
- **Runtime:** Python 3.12 (taken from .python-version; edit this line if the project targets another version).
- **Framework:** FastAPI (Async).
- **Validation:** Pydantic V2 (Strict).
- **Testing:** pytest + httpx (AsyncClient).
- **Linting:** Ruff.
- **Package manager:** uv.
- **Supply chain:** `pyproject.toml` sets `exclude-newer = "7 days"` under `[tool.uv]` (a relative duration needs uv 0.9.17 or later): uv does not resolve versions published in the last seven days. Add it when scaffolding; semgrep `p/owasp-top-ten` fails the security workflow on a `[tool.uv]` table without it. Source: https://docs.astral.sh/uv/concepts/resolution/#dependency-cooldowns.
- **Database:** none (no database service was decided).
- **Version Control:** Git.
<!-- rapid-stack: backend=python-fastapi -->

# 🅰️ TECH STACK: ANGULAR
- **Runtime:** Node.js 24 (Active LTS), TypeScript strict.
- **Framework:** Angular 22 (standalone components, signals).
- **Routing:** Angular Router.
- **Data:** HttpClient.
- **Testing:** Vitest (default in new projects) with `ng test`.
- **Linting:** ESLint + angular-eslint.
- **Package manager:** pnpm.
- **Supply chain:** `pnpm-workspace.yaml` sets `minimumReleaseAge: 10080` (seven days, in minutes; pnpm 10.16), `trustPolicy: no-downgrade` (pnpm 10.21) and `blockExoticSubdeps: true` (pnpm 10.26), so pnpm 10.26 or later. If the project has no `pnpm-workspace.yaml` yet, create it with these three settings when scaffolding (a single package needs no `packages` field). Without them semgrep `p/owasp-top-ten` fails the security workflow. Sources: https://pnpm.io/settings, https://github.com/pnpm/pnpm/releases/tag/v10.16.0, https://github.com/pnpm/pnpm/releases/tag/v10.21.0, https://github.com/pnpm/pnpm/releases/tag/v10.26.0.
- **Version Control:** Git.
<!-- rapid-stack: frontend=angular -->
