import shutil
import subprocess
import time
from pathlib import Path


def create_backup(file_path, timestamp=None):
    """Crea una copia de seguridad con timestamp si el archivo existe."""
    path = Path(file_path)
    if not path.exists():
        return None

    timestamp = int(time.time()) if timestamp is None else timestamp
    backup_path = path.parent / f"{path.name}.{timestamp}.bak"
    shutil.copy(path, backup_path)
    return backup_path


def check_node_installed():
    """Verifica si npx/node esta disponible."""
    try:
        subprocess.run(
            ["npx", "--version"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            shell=True,
        )
        return True
    except Exception:
        return False

