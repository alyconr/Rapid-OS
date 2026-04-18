import json

from rapid_os.core.paths import CONFIG_FILE, PROJECT_RAPID_DIR


DEFAULT_PROJECT_CONFIG = {"tools": ["cursor", "claude", "antigravity", "vscode"]}
INVALID_PROJECT_CONFIG = {"tools": []}


def save_project_config(config_data, project_rapid_dir=PROJECT_RAPID_DIR, config_file=CONFIG_FILE):
    """Guarda la configuracion del proyecto."""
    project_rapid_dir.mkdir(parents=True, exist_ok=True)
    with open(config_file, "w", encoding="utf-8") as f:
        json.dump(config_data, f, indent=2)


def load_project_config(config_file=CONFIG_FILE):
    """Carga la configuracion. Si no existe, devuelve defaults."""
    if not config_file.exists():
        return DEFAULT_PROJECT_CONFIG.copy()
    try:
        with open(config_file, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return INVALID_PROJECT_CONFIG.copy()
