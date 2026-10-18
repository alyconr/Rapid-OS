"""Project commands inferred from the repository (reads files; the domain never does)."""

from __future__ import annotations

import json
from pathlib import Path

from rapid_os.domain.project import ProjectModel


def propose_test_command(project_root: Path, model: ProjectModel) -> list[str] | None:
    """Test command to suggest, or None. Used by `rapid init` and `rapid setup`.

    Order: `package.json` with `scripts.test`; pytest; a tests directory in a Python project.
    """
    if _has_npm_test_script(Path(project_root) / "package.json"):
        return ["npm", "test"]
    testing = set(model.values("testing"))
    if "pytest" in testing:
        return ["python", "-m", "pytest"]
    if "tests-directory" in testing and "python" in set(model.values("language")):
        return ["python", "-m", "unittest", "discover"]
    return None


def _has_npm_test_script(package_json: Path) -> bool:
    try:
        data = json.loads(package_json.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return False
    scripts = data.get("scripts") if isinstance(data, dict) else None
    return isinstance(scripts, dict) and "test" in scripts
