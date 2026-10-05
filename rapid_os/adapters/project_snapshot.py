from pathlib import Path

from rapid_os.core.filesystem import resolve_child_path, safe_write_text
from rapid_os.domain.project import ProjectModel


PROJECT_SNAPSHOT_FILENAME = "project.json"


def resolve_project_snapshot_path(project_rapid_dir: Path) -> Path:
    """Resolve `.rapid-os/project.json` safely within `project_rapid_dir`."""
    return resolve_child_path(
        Path(project_rapid_dir),
        PROJECT_SNAPSHOT_FILENAME,
        single_segment=True,
    )


def write_project_snapshot(
    model: ProjectModel,
    project_rapid_dir: Path,
    *,
    backup: bool = True,
) -> Path:
    """Persist a canonical `ProjectModel` snapshot to `.rapid-os/project.json`."""
    if not isinstance(model, ProjectModel):
        raise TypeError("Expected a ProjectModel instance to persist.")
    target = resolve_project_snapshot_path(project_rapid_dir)
    serialized = model.to_json(indent=2) + "\n"
    return safe_write_text(
        target,
        serialized,
        encoding="utf-8",
        backup=backup,
        create_parents=True,
    )


def read_project_snapshot(
    project_rapid_dir: Path,
    project_root: Path | None = None,
) -> ProjectModel:
    """Read and validate `.rapid-os/project.json` into a `ProjectModel`."""
    target = resolve_project_snapshot_path(project_rapid_dir)
    raw_content = target.read_text(encoding="utf-8")
    root = Path(project_root) if project_root is not None else Path(project_rapid_dir).parent
    return ProjectModel.from_json(raw_content, root=root)
