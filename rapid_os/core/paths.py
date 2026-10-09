from dataclasses import dataclass
from importlib import resources
from pathlib import Path


@dataclass(frozen=True)
class RapidPaths:
    rapid_home: Path
    script_dir: Path
    templates_dir: Path
    current_dir: Path
    project_rapid_dir: Path
    config_file: Path


def _resolve_packaged_templates_dir() -> Path | None:
    """Locate templates bundled inside the installed `rapid_os` package, if present."""
    try:
        traversable = resources.files("rapid_os").joinpath("templates")
        candidate = Path(str(traversable))
        if candidate.exists() and candidate.is_dir():
            return candidate
    except Exception:
        pass

    package_candidate = Path(__file__).resolve().parents[1] / "templates"
    if package_candidate.exists() and package_candidate.is_dir():
        return package_candidate
    return None


def resolve_paths(
    current_dir=None,
    script_dir=None,
    rapid_home=None,
):
    """Resolve runtime paths using source checkout, packaged resource, or user install template precedence."""
    explicit_script_dir = script_dir is not None
    rapid_home = Path(rapid_home) if rapid_home else Path.home() / ".rapid-os"
    script_dir = Path(script_dir) if script_dir else Path(__file__).resolve().parents[2]
    current_dir = Path(current_dir) if current_dir else Path.cwd()

    if (script_dir / "templates").exists():
        templates_dir = script_dir / "templates"
    elif not explicit_script_dir and (packaged := _resolve_packaged_templates_dir()) is not None:
        templates_dir = packaged
    else:
        templates_dir = rapid_home / "templates"

    project_rapid_dir = current_dir / ".rapid-os"
    config_file = project_rapid_dir / "config.json"

    return RapidPaths(
        rapid_home=rapid_home,
        script_dir=script_dir,
        templates_dir=templates_dir,
        current_dir=current_dir,
        project_rapid_dir=project_rapid_dir,
        config_file=config_file,
    )


DEFAULT_PATHS = resolve_paths()

RAPID_HOME = DEFAULT_PATHS.rapid_home
SCRIPT_DIR = DEFAULT_PATHS.script_dir
TEMPLATES_DIR = DEFAULT_PATHS.templates_dir
CURRENT_DIR = DEFAULT_PATHS.current_dir
PROJECT_RAPID_DIR = DEFAULT_PATHS.project_rapid_dir
CONFIG_FILE = DEFAULT_PATHS.config_file

