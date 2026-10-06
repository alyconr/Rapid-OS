from pathlib import Path

from rapid_os.core.filesystem import (
    ensure_path_within_root,
    resolve_child_path,
    safe_write_text,
)
from rapid_os.domain.policy import (
    DEFAULT_EXECUTION_POLICY,
    ExecutionError,
    ExecutionPolicy,
    InvalidExecutionPolicyError,
    UnsafeRunPathError,
)


POLICY_FILENAME = "policy.json"


def resolve_execution_policy_path(
    project_root: Path,
    project_rapid_dir: Path | None = None,
) -> tuple[Path, Path, Path]:
    """Return `(root, rapid_dir, policy_file)` with containment verification."""
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
        policy_file = resolve_child_path(
            contained_rapid,
            POLICY_FILENAME,
            single_segment=True,
        )
        ensure_path_within_root(root, policy_file)
    except ValueError as exc:
        raise UnsafeRunPathError(
            str(exc),
            path=rapid_dir / POLICY_FILENAME,
        ) from exc

    return root, contained_rapid, policy_file


def load_execution_policy(
    project_root: Path = Path("."),
    project_rapid_dir: Path | None = None,
) -> tuple[ExecutionPolicy, str]:
    """Load `.rapid-os/policy.json` if present, or return `(DEFAULT_EXECUTION_POLICY, 'default')` without silent fallback on corruption."""
    _, _, policy_file = resolve_execution_policy_path(
        project_root,
        project_rapid_dir,
    )

    if policy_file.is_symlink():
        raise UnsafeRunPathError(
            f"Execution policy file '{policy_file}' cannot be a symlink.",
            path=policy_file,
        )

    if not policy_file.exists():
        return DEFAULT_EXECUTION_POLICY, "default"

    if not policy_file.is_file():
        raise UnsafeRunPathError(
            f"Execution policy path '{policy_file}' is not a regular file.",
            path=policy_file,
        )

    try:
        raw_content = policy_file.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        raise UnsafeRunPathError(
            f"Execution policy file '{policy_file}' could not be read as UTF-8: {exc}",
            path=policy_file,
        ) from exc

    try:
        policy = ExecutionPolicy.from_json(raw_content)
    except ExecutionError as exc:
        raise type(exc)(str(exc), code=exc.code, path=policy_file) from exc

    return policy, ".rapid-os/policy.json"


def write_default_execution_policy(
    project_root: Path = Path("."),
    project_rapid_dir: Path | None = None,
) -> Path:
    """Write `DEFAULT_EXECUTION_POLICY` to `.rapid-os/policy.json`, failing explicitly if it already exists."""
    root, rapid_dir, policy_file = resolve_execution_policy_path(
        project_root,
        project_rapid_dir,
    )
    if rapid_dir.is_symlink() or policy_file.is_symlink():
        raise UnsafeRunPathError(
            f"Cannot write execution policy to symlink path '{policy_file}'.",
            path=policy_file,
        )
    if policy_file.exists():
        raise InvalidExecutionPolicyError(
            f"Execution policy file '{policy_file}' already exists; refusing to overwrite.",
            path=policy_file,
        )
    ensure_path_within_root(root, policy_file)
    safe_write_text(
        policy_file,
        DEFAULT_EXECUTION_POLICY.to_json(indent=2) + "\n",
        encoding="utf-8",
        backup=False,
        create_parents=True,
    )
    return policy_file
