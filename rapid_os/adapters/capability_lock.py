from pathlib import Path

from rapid_os.adapters.harness_registry import HarnessRegistry
from rapid_os.core.filesystem import (
    ensure_path_within_root,
    resolve_child_path,
    safe_write_text,
)
from rapid_os.domain.capabilities import (
    CAPABILITY_LOCK_SCHEMA_VERSION,
    CapabilityLock,
    HarnessCapabilityError,
    InvalidCapabilityLockError,
    LockedHarnessProfile,
    UnsafeHarnessPathError,
)


CAPABILITY_LOCK_FILENAME = "capabilities.lock"


def resolve_capability_lock_path(
    project_root: Path,
    project_rapid_dir: Path | None = None,
) -> tuple[Path, Path, Path]:
    """Return `(root, rapid_dir, lock_file)` with containment verification."""
    raw_first = Path(project_root)
    if project_rapid_dir is None and raw_first.name == ".rapid-os":
        rapid_dir = raw_first
        root = rapid_dir.parent
    else:
        root = raw_first
        rapid_dir = (
            Path(project_rapid_dir)
            if project_rapid_dir is not None
            else (root / ".rapid-os")
        )

    try:
        contained_rapid = ensure_path_within_root(root, rapid_dir)
        lock_file = resolve_child_path(
            contained_rapid,
            CAPABILITY_LOCK_FILENAME,
            single_segment=True,
        )
        ensure_path_within_root(root, lock_file)
    except ValueError as exc:
        raise UnsafeHarnessPathError(
            str(exc),
            path=rapid_dir / CAPABILITY_LOCK_FILENAME,
        ) from exc

    return root, contained_rapid, lock_file


def build_capability_lock(registry: HarnessRegistry) -> CapabilityLock:
    """Build a deterministic `CapabilityLock` snapshot from all active profiles in `registry`."""
    active_profiles = registry.list_profiles()
    locked_entries = tuple(
        LockedHarnessProfile(
            id=item.id,
            source=item.source,
            profile_digest=item.profile_digest,
            profile=item.profile,
        )
        for item in active_profiles
    )
    return CapabilityLock(
        schema_version=CAPABILITY_LOCK_SCHEMA_VERSION,
        profiles=locked_entries,
    )


def write_capability_lock(
    project_root: Path = Path("."),
    project_rapid_dir: Path | None = None,
    *,
    registry: HarnessRegistry | None = None,
) -> tuple[CapabilityLock, Path]:
    """Deterministically generate and atomically write `.rapid-os/capabilities.lock`."""
    root, rapid_dir, lock_file = resolve_capability_lock_path(
        project_root,
        project_rapid_dir,
    )
    if rapid_dir.is_symlink() or lock_file.is_symlink():
        raise UnsafeHarnessPathError(
            f"Cannot write capabilities.lock to symlink path '{lock_file}'.",
            path=lock_file,
        )

    active_registry = registry or HarnessRegistry(root, rapid_dir)
    lock = build_capability_lock(active_registry)

    ensure_path_within_root(root, lock_file)
    safe_write_text(
        lock_file,
        lock.to_json(indent=2) + "\n",
        encoding="utf-8",
        backup=False,
        create_parents=True,
    )
    return lock, lock_file


def load_capability_lock(
    project_root: Path = Path("."),
    project_rapid_dir: Path | None = None,
) -> CapabilityLock:
    """Load and validate `.rapid-os/capabilities.lock`, failing explicitly if missing or corrupt."""
    _, rapid_dir, lock_file = resolve_capability_lock_path(
        project_root,
        project_rapid_dir,
    )
    if rapid_dir.is_symlink() or lock_file.is_symlink():
        raise UnsafeHarnessPathError(
            f"Capabilities lock file '{lock_file}' cannot be a symlink.",
            path=lock_file,
        )
    if not lock_file.exists():
        raise InvalidCapabilityLockError(
            f"Capabilities lock '{lock_file}' does not exist; run 'rapid harness lock' first.",
            path=lock_file,
        )
    if not lock_file.is_file():
        raise UnsafeHarnessPathError(
            f"Capabilities lock path '{lock_file}' is not a regular file.",
            path=lock_file,
        )

    try:
        raw = lock_file.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        raise UnsafeHarnessPathError(
            f"Capabilities lock '{lock_file}' could not be read as UTF-8: {exc}",
            path=lock_file,
        ) from exc

    try:
        return CapabilityLock.from_json(raw, verify_digest=True)
    except HarnessCapabilityError as exc:
        raise InvalidCapabilityLockError(
            str(exc),
            code="RAPID1111",
            path=lock_file,
        ) from exc
