"""Isolated git worktrees for runs whose contract requires `isolated_required`.

The ledger (`.rapid-os/`, session.json) always stays in the main repository; only the
working files live in the worktree at `../<repo>-<run-id>` on branch `rapid/<run-id>`.
"""

from __future__ import annotations

from pathlib import Path
import subprocess

from rapid_os.orchestration.git import run_git

from rapid_os.orchestration.session import load_session


class WorkspaceError(ValueError):
    """Expected workspace failure; the message already carries its RAPID code."""

    def __init__(self, code: str, message: str):
        super().__init__(f"{code} {message}")
        self.code = code


def worktree_path_for(project_root: Path, run_id: str) -> Path:
    root = Path(project_root).resolve()
    return root.parent / f"{root.name}-{run_id}"


def _git(cwd: Path, *args: str) -> subprocess.CompletedProcess:
    return run_git(cwd, *args)


def _registered_worktrees(project_root: Path) -> set[str]:
    proc = _git(project_root, "worktree", "list", "--porcelain")
    if proc.returncode != 0:
        return set()
    return {
        str(Path(line[len("worktree "):].strip()).resolve())
        for line in proc.stdout.splitlines()
        if line.startswith("worktree ")
    }


def create_run_worktree(project_root: Path, run_id: str) -> Path:
    """Create (or reuse) `../<repo>-<run-id>` on branch `rapid/<run-id>` from HEAD."""
    root = Path(project_root).resolve()
    target = worktree_path_for(root, run_id)
    branch = f"rapid/{run_id}"

    try:
        inside = _git(root, "rev-parse", "--is-inside-work-tree")
    except OSError as exc:
        raise WorkspaceError("RAPID1334", f"git is not available to create the worktree: {exc}") from exc
    if inside.returncode != 0 or inside.stdout.strip() != "true":
        raise WorkspaceError(
            "RAPID1334", "An isolated workspace requires a git repository with at least one commit."
        )

    if target.exists():
        if str(target.resolve()) in _registered_worktrees(root):
            return target
        raise WorkspaceError(
            "RAPID1334",
            f"Cannot create worktree: '{target}' already exists and is not a worktree of this repository.",
        )

    proc = _git(root, "worktree", "add", "-b", branch, str(target), "HEAD")
    if proc.returncode != 0:
        detail = (proc.stderr or proc.stdout).strip().splitlines()
        raise WorkspaceError(
            "RAPID1334",
            f"git worktree add failed for branch '{branch}': {detail[-1] if detail else 'unknown error'}",
        )
    return target


def resolve_workspace_cwd(project_root: Path, project_rapid_dir: Path) -> Path:
    """Directory where run commands execute: the run's worktree when it has one."""
    session = load_session(project_rapid_dir)
    if session is None or not session.workspace_path:
        return Path(project_root)
    workspace = Path(session.workspace_path)
    if not workspace.is_dir():
        raise WorkspaceError(
            "RAPID1335",
            f"Workspace '{workspace}' of run '{session.active_run_id}' no longer exists. "
            "Restore it with 'git worktree add' or run 'rapid abort'.",
        )
    return workspace
