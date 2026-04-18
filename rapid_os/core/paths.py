from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class RapidPaths:
    rapid_home: Path
    script_dir: Path
    templates_dir: Path
    current_dir: Path
    project_rapid_dir: Path
    config_file: Path


def resolve_paths(
    current_dir=None,
    script_dir=None,
    rapid_home=None,
):
    """Resolve runtime paths using the same source/install template precedence."""
    rapid_home = Path(rapid_home) if rapid_home else Path.home() / ".rapid-os"
    script_dir = Path(script_dir) if script_dir else Path(__file__).resolve().parents[2]
    current_dir = Path(current_dir) if current_dir else Path.cwd()

    if (script_dir / "templates").exists():
        templates_dir = script_dir / "templates"
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

