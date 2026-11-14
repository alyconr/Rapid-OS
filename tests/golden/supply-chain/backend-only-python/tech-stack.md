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
