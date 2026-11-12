"""Isolated git worktrees for runs whose contract requires `isolated_required`.

The ledger (`.rapid-os/`, session.json) always stays in the main repository; only the
working files live in the worktree at `../<repo>-<run-id>` on branch `rapid/<run-id>`.
"""

from __future__ import annotations

import os
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
    return run_git(cwd, "-c", "core.longpaths=true", *args)


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
            f"git worktree add failed for branch '{branch}': {detail[-1] if detail else 'unknown error'}"
            + (
                " Enable long paths for your Windows checkout with 'git config core.longpaths true' and retry."
                if "filename too long" in "\n".join(detail).lower()
                else ""
            ),
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


FOREIGN_WORKTREE_CODE = "RAPID1450"
# `reproduction.check_reproduction` creates its baseline worktree in a temporary `rapid-repro-*` directory.
REPRODUCTION_WORKTREE_PREFIX = "rapid-repro-"


def _same_dir(a: Path, b: Path) -> bool:
    try:
        return os.path.normcase(str(Path(a).resolve())) == os.path.normcase(str(Path(b).resolve()))
    except OSError:
        return False


def _worktree_entries(cwd: Path) -> list[dict[str, str]] | None:
    """`git worktree list --porcelain` as dicts (`worktree`, `branch`, `bare`), main checkout first."""
    proc = _git(cwd, "worktree", "list", "--porcelain")
    if proc.returncode != 0:
        return None
    entries: list[dict[str, str]] = []
    current: dict[str, str] = {}
    for line in proc.stdout.splitlines():
        if not line.strip():
            if current:
                entries.append(current)
            current = {}
            continue
        key, _, value = line.partition(" ")
        current[key] = value.strip()
    if current:
        entries.append(current)
    return entries


def _is_run_worktree(main: Path, toplevel: Path, branch: str | None) -> bool:
    """A worktree Rapid OS created for a run: the active run's `workspace_path`, or `../<repo>-<id>` on `rapid/<id>`."""
    rapid_dir = main / ".rapid-os"
    try:
        session = load_session(rapid_dir) if (rapid_dir / "session.json").is_file() else None
    except (OSError, ValueError):
        session = None
    if session is not None and session.workspace_path and _same_dir(Path(session.workspace_path), toplevel):
        return True
    prefix = "refs/heads/rapid/"
    if branch and branch.startswith(prefix):
        run_id = branch[len(prefix):]
        return bool(run_id) and _same_dir(worktree_path_for(main, run_id), toplevel)
    return False


def foreign_worktree_message(cwd: Path) -> str | None:
    """RAPID1450 when `cwd` is in a linked git worktree that is not the worktree of a Rapid OS run.

    The run state lives in the checkout where `rapid start` runs, and the run's worktree is created
    next to it: started from a worktree a harness made for itself (Codex, for instance), the run
    would live outside the person's checkout. None in the main checkout, in a run worktree, outside
    git, or when git cannot answer (this guard never blocks a project it cannot inspect).
    """
    base = Path(cwd)
    try:
        proc = _git(base, "rev-parse", "--git-dir", "--git-common-dir", "--show-toplevel")
    except OSError:
        return None
    lines = [line.strip() for line in proc.stdout.splitlines() if line.strip()]
    if proc.returncode != 0 or len(lines) != 3:
        return None
    git_dir, common_dir, toplevel = (Path(p) if Path(p).is_absolute() else base / p for p in lines)
    if _same_dir(git_dir, common_dir):
        return None
    try:
        entries = _worktree_entries(base)
    except OSError:
        return None
    if not entries or "bare" in entries[0] or not entries[0].get("worktree"):
        # A bare repository has no main checkout to send the person to.
        return None
    main = Path(entries[0]["worktree"])
    if _same_dir(main, toplevel):
        return None
    if toplevel.parent.name.startswith(REPRODUCTION_WORKTREE_PREFIX):
        return None  # the temporary baseline worktree of a bugfix reproduction check (H-67)
    branch = next(
        (e.get("branch") for e in entries if e.get("worktree") and _same_dir(Path(e["worktree"]), toplevel)),
        None,
    )
    if _is_run_worktree(main, toplevel, branch):
        return None
    return (
        f"{FOREIGN_WORKTREE_CODE} Este directorio está en un worktree de git ({toplevel}) que no es el de un run "
        f"de Rapid OS. El estado del run vive en el checkout principal y Rapid OS crea allí al lado el worktree "
        f"del run: ejecuta los comandos de Rapid OS desde el checkout principal, {main} "
        f"(cd \"{main}\"). Si el run exige un workspace aislado, lo crea Rapid OS con "
        f"'rapid start --resume --worktree'; no uses el worktree del harness. Esto no escribió nada."
    )
