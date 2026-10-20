"""Which changed paths are the project's and which are artifacts that tools leave behind. Pure.

`file_change` evidence (capability `repository.write`) must say "the run changed the project",
not "running the tests created `__pycache__`". A project without a `.gitignore` entry for these
would otherwise count them as writes.
"""

from __future__ import annotations

from fnmatch import fnmatchcase

# Folder names (a whole path segment, never a substring) that tools create and nobody authors.
TOOL_ARTIFACT_DIRS: frozenset[str] = frozenset(
    {
        "__pycache__",
        ".pytest_cache",
        ".mypy_cache",
        ".ruff_cache",
        ".tox",
        ".nox",
        "node_modules",
        ".venv",
        "venv",
    }
)

# File-name patterns (matched against the last segment).
TOOL_ARTIFACT_FILES: tuple[str, ...] = ("*.pyc", "*.pyo", ".coverage", ".coverage.*")

TOOL_ARTIFACT_PATTERNS: tuple[str, ...] = (
    *(f"{name}/" for name in sorted(TOOL_ARTIFACT_DIRS)),
    *TOOL_ARTIFACT_FILES,
)


def normalize_path(path: str) -> str:
    return path.strip().replace("\\", "/")


def is_tool_artifact(path: str) -> bool:
    """True for a path inside a tool-artifact folder, or a tool-artifact file.

    Segments match exactly: `my__pycache__notes.md` is not an artifact. A folder named `venv`
    may or may not be a virtualenv (`pyvenv.cfg` cannot be checked here): the name decides.
    """
    segments = [segment for segment in normalize_path(path).split("/") if segment]
    if not segments:
        return False
    if any(segment in TOOL_ARTIFACT_DIRS for segment in segments[:-1]):
        return True
    last = segments[-1]
    return last in TOOL_ARTIFACT_DIRS or any(fnmatchcase(last, pattern) for pattern in TOOL_ARTIFACT_FILES)
