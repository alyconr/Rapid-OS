import os
import re
import shutil
import tempfile
import time
from pathlib import Path, PurePosixPath, PureWindowsPath

from rapid_os.core.process import is_npx_available


WINDOWS_DRIVE_PATTERN = re.compile(r"^[A-Za-z]:")


def _is_explicitly_absolute_or_rooted(raw: str) -> bool:
    if raw.startswith(("/", "\\")):
        return True
    if WINDOWS_DRIVE_PATTERN.match(raw):
        return True
    win_path = PureWindowsPath(raw)
    posix_path = PurePosixPath(raw)
    return bool(
        win_path.is_absolute()
        or posix_path.is_absolute()
        or win_path.drive
        or win_path.root
        or posix_path.root
    )


def ensure_path_within_root(root, candidate_path) -> Path:
    """Resolve `root` and `candidate_path` and verify `candidate_path` is strictly inside `root`."""
    resolved_root = Path(root).resolve()
    resolved_candidate = Path(candidate_path).resolve()

    if resolved_candidate == resolved_root or not resolved_candidate.is_relative_to(
        resolved_root
    ):
        raise ValueError(
            f"Path '{candidate_path}' escapes root directory '{resolved_root}'."
        )
    return resolved_candidate


def resolve_child_path(root, user_value, *, single_segment: bool = False) -> Path:
    """Resolve a descendant path inside `root`, rejecting empty values, absolute paths, and traversal."""
    if user_value is None:
        raise ValueError("Path value cannot be None.")
    if not isinstance(user_value, (str, Path)):
        raise ValueError("Path value must be a string or Path.")

    raw = str(user_value).strip()
    if not raw:
        raise ValueError("Path value cannot be empty.")
    if "\x00" in raw:
        raise ValueError("Path value cannot contain null bytes.")

    if _is_explicitly_absolute_or_rooted(raw):
        raise ValueError(f"Absolute or rooted path is not allowed: '{user_value}'.")

    normalized = raw.replace("\\", "/")
    raw_segments = [segment for segment in normalized.split("/") if segment != ""]
    if not raw_segments:
        raise ValueError("Path value cannot be empty.")

    if single_segment and len(raw_segments) != 1:
        raise ValueError(
            f"Expected a single path segment, got '{user_value}'."
        )

    resolved_root = Path(root).resolve()
    relative_candidate = Path(*raw_segments)
    resolved_candidate = (resolved_root / relative_candidate).resolve()

    if resolved_candidate == resolved_root or not resolved_candidate.is_relative_to(
        resolved_root
    ):
        raise ValueError(
            f"Unsafe path '{user_value}' escapes root directory '{resolved_root}'."
        )

    if any(segment in {".", ".."} for segment in raw_segments):
        raise ValueError(
            f"Traversal segments are not allowed in path '{user_value}'."
        )

    return resolved_candidate


def safe_rmtree_child(root, target_path) -> None:
    """Delete a directory tree only after proving it is a strict child of `root`."""
    target = Path(target_path)
    resolved_root = Path(root).resolve()

    # Check both lexical parent/containment and symlink-resolved containment
    if target.is_symlink():
        raise ValueError(
            f"Refusing to remove symlinked skill target '{target}'."
        )

    resolved_target = ensure_path_within_root(resolved_root, target)
    if resolved_target.exists():
        shutil.rmtree(resolved_target)


def create_backup(file_path, timestamp=None):
    """Crea una copia de seguridad con timestamp si el archivo existe."""
    path = Path(file_path)
    if not path.exists():
        return None

    timestamp = int(time.time()) if timestamp is None else timestamp
    backup_path = path.parent / f"{path.name}.{timestamp}.bak"
    shutil.copy(path, backup_path)
    return backup_path


def safe_write_text(
    file_path,
    content: str,
    *,
    encoding: str = "utf-8",
    backup: bool = False,
    create_parents: bool = True,
    allow_overwrite: bool = True,
    timestamp=None,
) -> Path:
    """Atomically write UTF-8 text to `file_path` with optional overwrite protection, backup, and parent creation."""
    target = Path(file_path)
    if not allow_overwrite and (target.exists() or target.is_symlink()):
        raise FileExistsError(f"Refusing to overwrite existing file: {target}")
    if create_parents:
        target.parent.mkdir(parents=True, exist_ok=True)

    temp_path = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding=encoding,
            dir=target.parent,
            prefix=f".{target.name}.",
            suffix=".tmp",
            delete=False,
        ) as tmp_file:
            temp_path = Path(tmp_file.name)
            tmp_file.write(content)
            tmp_file.flush()
            os.fsync(tmp_file.fileno())

        if not allow_overwrite and (target.exists() or target.is_symlink()):
            raise FileExistsError(f"Refusing to overwrite existing file: {target}")

        if backup and target.exists():
            create_backup(target, timestamp=timestamp)

        os.replace(temp_path, target)
        temp_path = None
        return target
    finally:
        if temp_path is not None and temp_path.exists():
            try:
                temp_path.unlink()
            except OSError:
                pass


def safe_write_bytes(
    file_path,
    content: bytes,
    *,
    backup: bool = False,
    create_parents: bool = True,
    allow_overwrite: bool = True,
    timestamp=None,
) -> Path:
    """Atomically write bytes to `file_path` with optional overwrite protection, backup, and parent creation."""
    if not isinstance(content, (bytes, bytearray)):
        raise TypeError("safe_write_bytes requires bytes content.")
    target = Path(file_path)
    if not allow_overwrite and (target.exists() or target.is_symlink()):
        raise FileExistsError(f"Refusing to overwrite existing file: {target}")
    if create_parents:
        target.parent.mkdir(parents=True, exist_ok=True)

    temp_path = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="wb",
            dir=target.parent,
            prefix=f".{target.name}.",
            suffix=".tmp",
            delete=False,
        ) as tmp_file:
            temp_path = Path(tmp_file.name)
            tmp_file.write(bytes(content))
            tmp_file.flush()
            os.fsync(tmp_file.fileno())

        if not allow_overwrite and (target.exists() or target.is_symlink()):
            raise FileExistsError(f"Refusing to overwrite existing file: {target}")

        if backup and target.exists():
            create_backup(target, timestamp=timestamp)

        os.replace(temp_path, target)
        temp_path = None
        return target
    finally:
        if temp_path is not None and temp_path.exists():
            try:
                temp_path.unlink()
            except OSError:
                pass


def safe_copy_file(
    src_path,
    dest_path,
    *,
    backup: bool = False,
    create_parents: bool = True,
    timestamp=None,
) -> Path:
    """Atomically copy `src_path` to `dest_path` with optional backup and parent creation."""
    source = Path(src_path)
    if not source.exists() or not source.is_file():
        raise FileNotFoundError(f"Source file does not exist: {source}")

    target = Path(dest_path)
    if create_parents:
        target.parent.mkdir(parents=True, exist_ok=True)

    temp_path = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="wb",
            dir=target.parent,
            prefix=f".{target.name}.",
            suffix=".tmp",
            delete=False,
        ) as tmp_file:
            temp_path = Path(tmp_file.name)
            with open(source, "rb") as src_file:
                shutil.copyfileobj(src_file, tmp_file)
            tmp_file.flush()
            os.fsync(tmp_file.fileno())

        if backup and target.exists():
            create_backup(target, timestamp=timestamp)

        os.replace(temp_path, target)
        temp_path = None
        return target
    finally:
        if temp_path is not None and temp_path.exists():
            try:
                temp_path.unlink()
            except OSError:
                pass


def safe_append_text(
    file_path,
    content: str,
    *,
    encoding: str = "utf-8",
    create_parents: bool = True,
) -> Path:
    """Safely append text to `file_path` using an atomic write replacement."""
    target = Path(file_path)
    existing = target.read_text(encoding=encoding) if target.exists() else ""
    return safe_write_text(
        target,
        existing + content,
        encoding=encoding,
        backup=False,
        create_parents=create_parents,
    )


def check_node_installed():
    """Verifica si npx/node esta disponible."""
    return is_npx_available()
