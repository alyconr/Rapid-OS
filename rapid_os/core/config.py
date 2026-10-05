import json
from dataclasses import dataclass
from pathlib import Path

from rapid_os.core.filesystem import safe_write_text
from rapid_os.core.paths import CONFIG_FILE, PROJECT_RAPID_DIR


DEFAULT_PROJECT_CONFIG = {"tools": ["cursor", "claude", "antigravity", "vscode"]}
INVALID_PROJECT_CONFIG = {"tools": []}

CONFIG_STATUS_MISSING = "missing"
CONFIG_STATUS_VALID = "valid"
CONFIG_STATUS_INVALID_JSON = "invalid_json"
CONFIG_STATUS_INVALID_SCHEMA = "invalid_schema"
CONFIG_STATUS_IO_ERROR = "io_error"


class ProjectConfigError(ValueError):
    """Raised when project configuration is corrupt or unreadable in strict mode."""

    def __init__(self, status: str, path: Path, message: str):
        super().__init__(f"{message} ({path})")
        self.status = status
        self.path = Path(path)
        self.detail = message


@dataclass(frozen=True)
class ProjectConfigLoadResult:
    status: str
    config: dict
    path: Path
    error: str | None = None

    @property
    def is_valid(self) -> bool:
        return self.status in (CONFIG_STATUS_MISSING, CONFIG_STATUS_VALID)


def inspect_project_config_file(config_file=CONFIG_FILE) -> ProjectConfigLoadResult:
    """Inspect and classify `.rapid-os/config.json` without collapsing error states."""
    path = Path(config_file)
    if not path.exists():
        return ProjectConfigLoadResult(
            status=CONFIG_STATUS_MISSING,
            config={"tools": list(DEFAULT_PROJECT_CONFIG["tools"])},
            path=path,
        )

    if path.is_dir():
        return ProjectConfigLoadResult(
            status=CONFIG_STATUS_IO_ERROR,
            config={"tools": []},
            path=path,
            error="Project config path is a directory, not a file.",
        )

    try:
        raw = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        return ProjectConfigLoadResult(
            status=CONFIG_STATUS_IO_ERROR,
            config={"tools": []},
            path=path,
            error=str(exc),
        )

    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        return ProjectConfigLoadResult(
            status=CONFIG_STATUS_INVALID_JSON,
            config={"tools": []},
            path=path,
            error=exc.msg,
        )

    if not isinstance(payload, dict):
        return ProjectConfigLoadResult(
            status=CONFIG_STATUS_INVALID_SCHEMA,
            config={"tools": []},
            path=path,
            error="Project config root must be a JSON object.",
        )

    tools = payload.get("tools", [])
    if not isinstance(tools, list):
        return ProjectConfigLoadResult(
            status=CONFIG_STATUS_INVALID_SCHEMA,
            config={"tools": []},
            path=path,
            error="Project config field 'tools' must be a list.",
        )

    if any(not isinstance(item, str) for item in tools):
        return ProjectConfigLoadResult(
            status=CONFIG_STATUS_INVALID_SCHEMA,
            config={"tools": [item for item in tools if isinstance(item, str)]},
            path=path,
            error="Tool ids in project config must be strings.",
        )

    normalized = dict(payload)
    normalized["tools"] = list(tools)
    return ProjectConfigLoadResult(
        status=CONFIG_STATUS_VALID,
        config=normalized,
        path=path,
    )


def save_project_config(
    config_data,
    project_rapid_dir=PROJECT_RAPID_DIR,
    config_file=CONFIG_FILE,
):
    """Guarda la configuracion del proyecto de forma atomica con backup."""
    Path(project_rapid_dir).mkdir(parents=True, exist_ok=True)
    serialized = json.dumps(config_data, indent=2) + "\n"
    return safe_write_text(
        config_file,
        serialized,
        encoding="utf-8",
        backup=True,
        create_parents=True,
    )


def load_project_config(config_file=CONFIG_FILE, *, strict: bool = False):
    """Carga la configuracion. Si no existe, devuelve defaults. En modo strict lanza ProjectConfigError."""
    result = inspect_project_config_file(config_file)
    if result.is_valid:
        return result.config
    if strict:
        raise ProjectConfigError(
            result.status,
            result.path,
            result.error or "Invalid project configuration.",
        )
    return INVALID_PROJECT_CONFIG.copy()
