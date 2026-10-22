"""Reads `.rapid-os/standards/architecture.json` and the sources the architecture check looks at."""

from __future__ import annotations

import json
from pathlib import Path

from rapid_os.domain.architecture import (
    ARCHITECTURE_CODE,
    SOURCE_SUFFIXES,
    ArchitectureConfig,
    ArchitectureConfigError,
)

CONFIG_FILE_NAME = "architecture.json"
_SKIPPED_DIRS = frozenset({"__pycache__", "node_modules"})


def config_path(project_rapid_dir: Path | str) -> Path:
    return Path(project_rapid_dir) / "standards" / CONFIG_FILE_NAME


def has_architecture_rule(project_rapid_dir: Path | str) -> bool:
    return config_path(project_rapid_dir).is_file()


def load_config(project_rapid_dir: Path | str) -> ArchitectureConfig | None:
    """The rule, or None when the project has none. An unreadable one raises
    `ArchitectureConfigError` (RAPID1420)."""
    path = config_path(project_rapid_dir)
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ArchitectureConfigError(
            f"{ARCHITECTURE_CODE} architecture.json inválido: no se puede leer como JSON ({exc})."
        ) from exc
    return ArchitectureConfig.from_dict(data)


def collect_sources(project_root: Path | str, config: ArchitectureConfig) -> dict[str, str]:
    """Source text of every file under `modules_root` and `shared_root`, keyed by posix path
    relative to the project root. Hidden folders, `__pycache__` and `node_modules` are left out."""
    root = Path(project_root)
    suffixes = SOURCE_SUFFIXES[config.language]
    sources: dict[str, str] = {}
    for base in (config.modules_root, config.shared_root):
        folder = root / base
        if not folder.is_dir():
            continue
        for path in sorted(folder.rglob("*")):
            relative = path.relative_to(root)
            if not path.is_file() or path.suffix not in suffixes or path.name.endswith(".d.ts"):
                continue
            if any(part in _SKIPPED_DIRS or part.startswith(".") for part in relative.parts[:-1]):
                continue
            try:
                sources[relative.as_posix()] = path.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                continue
    return sources
