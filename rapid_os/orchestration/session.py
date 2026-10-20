"""Session management for Rapid OS porcelain layer.

Manages `.rapid-os/session.json` which tracks the currently active run,
execution mode, harness identifier, and starting git HEAD commit.
"""

from __future__ import annotations

import json
import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable

from rapid_os.adapters.run_registry import RunRegistry
from rapid_os.core.filesystem import safe_write_text
from rapid_os.domain.execution import RunStatus
from rapid_os.domain.file_changes import is_tool_artifact, normalize_path
from rapid_os.domain.validation import ERROR, WARNING, Diagnostic, ValidationReport


SESSION_FILE_NAME = "session.json"
SESSION_SCHEMA_VERSION = 1


@dataclass(frozen=True)
class Session:
    active_run_id: str
    mode: str
    harness: str
    start_head: str | None = None
    schema_version: int = SESSION_SCHEMA_VERSION
    # Untracked files that already existed when the run started (None = not recorded).
    start_untracked: tuple[str, ...] | None = None
    # Isolated git worktree of the run (absolute path); the ledger stays in the main repo.
    workspace_path: str | None = None

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "schema_version": self.schema_version,
            "active_run_id": self.active_run_id,
            "mode": self.mode,
            "harness": self.harness,
            "start_head": self.start_head,
        }
        if self.start_untracked is not None:
            payload["start_untracked"] = list(self.start_untracked)
        if self.workspace_path is not None:
            payload["workspace_path"] = self.workspace_path
        return payload

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Session:
        if not isinstance(data, dict):
            raise ValueError(f"Session data must be a dictionary, got {type(data).__name__}.")
        schema_version = data.get("schema_version", SESSION_SCHEMA_VERSION)
        active_run_id = data.get("active_run_id")
        if not active_run_id or not isinstance(active_run_id, str):
            raise ValueError("Session data missing or invalid 'active_run_id'.")
        mode = data.get("mode")
        if not mode or not isinstance(mode, str):
            raise ValueError("Session data missing or invalid 'mode'.")
        harness = data.get("harness")
        if not harness or not isinstance(harness, str):
            raise ValueError("Session data missing or invalid 'harness'.")
        start_head = data.get("start_head")
        if start_head is not None and not isinstance(start_head, str):
            raise ValueError("Session 'start_head' must be a string or None.")
        raw_untracked = data.get("start_untracked")
        start_untracked: tuple[str, ...] | None = None
        if raw_untracked is not None:
            if not isinstance(raw_untracked, list) or not all(
                isinstance(item, str) for item in raw_untracked
            ):
                raise ValueError("Session 'start_untracked' must be a list of strings or None.")
            start_untracked = tuple(raw_untracked)
        workspace_path = data.get("workspace_path")
        if workspace_path is not None and not isinstance(workspace_path, str):
            raise ValueError("Session 'workspace_path' must be a string or None.")
        return cls(
            schema_version=schema_version,
            active_run_id=active_run_id,
            mode=mode,
            harness=harness,
            start_head=start_head,
            start_untracked=start_untracked,
            workspace_path=workspace_path,
        )


def resolve_git_untracked(cwd: Path | str | None = None) -> tuple[str, ...] | None:
    """List untracked, non-ignored files (`git ls-files --others --exclude-standard`).

    Artifacts that tools create (`__pycache__`, `*.pyc`, `.pytest_cache`...) are left out even
    when the project has no `.gitignore` for them (see `rapid_os.domain.file_changes`).

    Returns None when git is unavailable or `cwd` is not a repository, so callers can tell
    "nothing untracked" (empty tuple) from "unknown".
    """
    try:
        proc = subprocess.run(
            ["git", "ls-files", "--others", "--exclude-standard"],
            cwd=str(cwd) if cwd else None,
            capture_output=True,
            text=True,
            check=False,
            shell=False,
        )
    except Exception:
        return None
    if proc.returncode != 0:
        return None
    return tuple(
        sorted(
            path
            for path in (normalize_path(line) for line in proc.stdout.splitlines())
            if path and not is_tool_artifact(path)
        )
    )


def observed_changes(
    cwd: Path | str,
    start_head: str,
    pre_existing_untracked: Iterable[str] = (),
) -> list[str]:
    """Files the run changed in the project: `git diff` since `start_head` plus the files that
    are untracked now and were not before, without `.rapid-os/` and without tool artifacts.

    The one place that decides this, so `rapid start` (which records what was already untracked)
    and `rapid finish` (which subtracts it) agree. Returns [] when git cannot answer.
    """
    already = set(pre_existing_untracked)
    try:
        proc = subprocess.run(
            ["git", "diff", "--name-only", start_head],
            cwd=str(cwd),
            capture_output=True,
            text=True,
            check=False,
            shell=False,
        )
        untracked = resolve_git_untracked(cwd) or ()
    except Exception:
        return []
    changed: list[str] = []
    for path in [normalize_path(line) for line in proc.stdout.splitlines()] + [
        u for u in untracked if u not in already
    ]:
        if (
            path
            and not path.startswith(".rapid-os/")
            and not is_tool_artifact(path)
            and path not in changed
        ):
            changed.append(path)
    return changed


def resolve_git_head(cwd: Path | str | None = None) -> str | None:
    """Safely resolve current git HEAD commit hash, returning None if not in git or on error."""
    try:
        proc = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=str(cwd) if cwd else None,
            capture_output=True,
            text=True,
            check=False,
            shell=False,
        )
        if proc.returncode == 0:
            commit = proc.stdout.strip()
            if commit:
                return commit
    except Exception:
        pass
    return None


def get_session_file_path(project_rapid_dir: Path | str) -> Path:
    return Path(project_rapid_dir) / SESSION_FILE_NAME


def load_session(project_rapid_dir: Path | str) -> Session | None:
    session_path = get_session_file_path(project_rapid_dir)
    if not session_path.exists() or not session_path.is_file():
        return None
    try:
        content = session_path.read_text(encoding="utf-8")
        data = json.loads(content)
        return Session.from_dict(data)
    except Exception:
        return None


def save_session(project_rapid_dir: Path | str, session: Session) -> Path:
    session_path = get_session_file_path(project_rapid_dir)
    payload = json.dumps(session.to_dict(), indent=2, sort_keys=True) + "\n"
    safe_write_text(
        session_path,
        payload,
        encoding="utf-8",
        allow_overwrite=True,
        create_parents=True,
    )
    return session_path


def clear_session(project_rapid_dir: Path | str) -> bool:
    session_path = get_session_file_path(project_rapid_dir)
    if session_path.exists():
        try:
            session_path.unlink()
            return True
        except OSError:
            return False
    return False


def validate_session(
    project_rapid_dir: Path,
    current_dir: Path | None = None,
) -> ValidationReport:
    """Validate `.rapid-os/session.json` against the project RunRegistry."""
    session_path = get_session_file_path(project_rapid_dir)
    if not session_path.exists():
        return ValidationReport()

    diagnostics: list[Diagnostic] = []
    session = load_session(project_rapid_dir)
    if session is None:
        # Invalid format or unreadable
        diagnostics.append(
            Diagnostic(
                ERROR,
                "RAPID1304",
                f"Session file '{session_path.name}' is invalid or cannot be parsed.",
                path=session_path,
                hint="Delete or recreate .rapid-os/session.json with a valid active run session.",
            )
        )
        return ValidationReport(tuple(diagnostics))

    root = current_dir if current_dir is not None else project_rapid_dir.parent
    run_registry = RunRegistry(root, project_rapid_dir)

    try:
        run_record = run_registry.get(session.active_run_id)
    except Exception:
        diagnostics.append(
            Diagnostic(
                ERROR,
                "RAPID1304",
                f"Active run '{session.active_run_id}' referenced in session.json does not exist in RunRegistry.",
                path=session_path,
                hint="Ensure active_run_id exists in .rapid-os/runs or clear session.json.",
            )
        )
        return ValidationReport(tuple(diagnostics))

    # Check terminal status
    try:
        run_state = run_registry.get_state(session.active_run_id)
        terminal_statuses = {
            RunStatus.FINISHED,
            RunStatus.FAILED,
            RunStatus.CANCELLED,
        }
        if run_state.status in terminal_statuses:
            diagnostics.append(
                Diagnostic(
                    WARNING,
                    "RAPID1305",
                    f"Active run '{session.active_run_id}' referenced in session.json has reached terminal status '{run_state.status.value}'.",
                    path=session_path,
                    hint="A new run should be started or session.json cleared.",
                )
            )
    except Exception:
        pass

    return ValidationReport(tuple(diagnostics))
