"""Runtime for `rapid hook stop|pre-tool`: project resolution, loop-guard state and log.

The decisions themselves are pure (`rapid_os.orchestration.hooks`). Everything that can go wrong
here is swallowed: a hook must never break the agent, so internal errors become "exit 0, no
output" plus a line in `.rapid-os/scratch/hooks.log`.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import time
from typing import Mapping

from rapid_os.core.config import load_project_config
from rapid_os.core.filesystem import safe_write_text
from rapid_os.core.paths import RAPID_HOME
from rapid_os.orchestration.hooks import (
    DEFAULT_MAX_STOP_BLOCKS,
    StopGuard,
    decide_pre_tool,
    decide_stop,
    parse_payload,
    pre_tool_output,
)
from rapid_os.orchestration.lifecycle import execute_next
from rapid_os.orchestration.session import load_session

RAPID_DIR_NAME = ".rapid-os"
GUARD_FILE = "hooks.json"
LOG_FILE = "hooks.log"
LOG_MAX_BYTES = 256_000
GUARD_MAX_SESSIONS = 20


@dataclass(frozen=True)
class HookProject:
    root: Path  # repository that owns the ledger (.rapid-os/)
    workspace: Path | None = None  # the run's isolated worktree, when the hook runs inside it

    @property
    def rapid_dir(self) -> Path:
        return self.root / RAPID_DIR_NAME

    @property
    def protected_dirs(self) -> tuple[str, ...]:
        dirs = [self.rapid_dir.resolve().as_posix()]
        if self.workspace is not None:
            dirs.append((self.workspace / RAPID_DIR_NAME).resolve().as_posix())
        return tuple(dirs)


def _same_path(a: Path, b: Path) -> bool:
    try:
        return os.path.normcase(str(a.resolve())) == os.path.normcase(str(b.resolve()))
    except OSError:
        return False


def _main_repo_of_worktree(directory: Path) -> Path | None:
    """If `directory` is a git linked worktree (its `.git` is a file), return the main repo root."""
    git_entry = directory / ".git"
    if not git_entry.is_file():
        return None
    try:
        text = git_entry.read_text(encoding="utf-8").strip()
    except OSError:
        return None
    if not text.startswith("gitdir:"):
        return None
    gitdir = Path(text[len("gitdir:"):].strip())
    if not gitdir.is_absolute():
        gitdir = (directory / gitdir).resolve()
    # <main>/.git/worktrees/<name>
    if gitdir.parent.name != "worktrees" or gitdir.parent.parent.name != ".git":
        return None
    return gitdir.parent.parent.parent


def find_project(cwd: str | os.PathLike | None) -> HookProject | None:
    """Walk up from `cwd` to the directory owning `.rapid-os/`.

    Inside a worktree created by `rapid start --worktree` (recorded as `workspace_path` in the
    main repository's session.json) the ledger of the main repository is used.
    """
    if not cwd:
        return None
    start = Path(cwd)
    try:
        start = start.resolve()
    except OSError:
        return None
    for directory in (start, *start.parents):
        main = _main_repo_of_worktree(directory)
        if main is not None and (main / RAPID_DIR_NAME / "session.json").is_file():
            session = load_session(main / RAPID_DIR_NAME)
            if session and session.workspace_path and _same_path(Path(session.workspace_path), directory):
                return HookProject(root=main, workspace=directory)
        candidate = directory / RAPID_DIR_NAME
        # ~/.rapid-os is the Rapid OS installation (RAPID_HOME), not a project ledger.
        if candidate.is_dir() and not _same_path(candidate, Path(RAPID_HOME)):
            return HookProject(root=directory)
    return None


# ------------------------------------------------------------------------------ files


def _scratch(project: HookProject) -> Path:
    return project.rapid_dir / "scratch"


def log_event(project: HookProject | None, event: str, message: str) -> None:
    if project is None:
        return
    try:
        scratch = _scratch(project)
        scratch.mkdir(parents=True, exist_ok=True)
        log = scratch / LOG_FILE
        if log.exists() and log.stat().st_size > LOG_MAX_BYTES:
            os.replace(log, scratch / (LOG_FILE + ".1"))
        stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        with open(log, "a", encoding="utf-8") as handle:
            handle.write(f"{stamp} [{event}] {message}\n")
    except OSError:
        pass


def _read_guards(project: HookProject) -> dict:
    path = _scratch(project) / GUARD_FILE
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    sessions = data.get("sessions") if isinstance(data, dict) else None
    return sessions if isinstance(sessions, dict) else {}


def _write_guards(project: HookProject, sessions: dict) -> None:
    newest = sorted(sessions.items(), key=lambda kv: kv[1].get("t", 0), reverse=True)[:GUARD_MAX_SESSIONS]
    payload = json.dumps({"sessions": dict(newest)}, indent=2, sort_keys=True) + "\n"
    safe_write_text(_scratch(project) / GUARD_FILE, payload, encoding="utf-8", create_parents=True)


def max_stop_blocks(project: HookProject) -> int:
    """`hooks.max_stop_blocks` in .rapid-os/config.json (default 3; 0 disables blocking)."""
    config = load_project_config(project.rapid_dir / "config.json")
    hooks = config.get("hooks") if isinstance(config, dict) else None
    value = hooks.get("max_stop_blocks") if isinstance(hooks, dict) else None
    if isinstance(value, int) and not isinstance(value, bool) and value >= 0:
        return value
    if value is not None:
        log_event(project, "config", f"ignoring invalid hooks.max_stop_blocks={value!r}")
    return DEFAULT_MAX_STOP_BLOCKS


# ------------------------------------------------------------------------------ hooks


def _handle_stop(payload, project: HookProject, templates_dir) -> str:
    session = load_session(project.rapid_dir)
    key = payload.session_id or "default"
    sessions = _read_guards(project)
    if session is None:
        if key in sessions:
            sessions.pop(key)
            _write_guards(project, sessions)
        return ""

    code, action = execute_next(
        project.root,
        project.rapid_dir,
        config_file=project.rapid_dir / "config.json",
        templates_dir=templates_dir,
    )
    if code != 0:
        return ""

    entry = sessions.get(key)
    guard = StopGuard(str(entry["key"]), int(entry["count"])) if isinstance(entry, dict) and "key" in entry else None
    output, new_guard = decide_stop(payload, action, guard, max_stop_blocks(project))

    changed = False
    if new_guard is None:
        changed = sessions.pop(key, None) is not None
    elif guard != new_guard:
        sessions[key] = {"key": new_guard.key, "count": new_guard.count, "t": int(time.time())}
        changed = True
    if changed:
        _write_guards(project, sessions)
    return json.dumps(output) if output else ""


def _handle_pre_tool(payload, project: HookProject) -> str:
    decision = decide_pre_tool(payload, project.protected_dirs)
    return json.dumps(pre_tool_output(decision)) if decision else ""


def run_hook(event: str, raw_stdin: str, env: Mapping[str, str], templates_dir=None) -> tuple[int, str]:
    """Run one hook invocation. Always exits 0; returns (exit_code, stdout_text)."""
    project: HookProject | None = None
    try:
        try:
            data = json.loads(raw_stdin)
        except ValueError:
            project = find_project(env.get("CLAUDE_PROJECT_DIR") or os.getcwd())
            log_event(project, event, "stdin is not valid JSON; ignored")
            return 0, ""
        payload = parse_payload(data)
        project = find_project(payload.cwd or env.get("CLAUDE_PROJECT_DIR"))
        if project is None:
            return 0, ""
        if event == "stop":
            return 0, _handle_stop(payload, project, templates_dir)
        if event == "pre-tool":
            return 0, _handle_pre_tool(payload, project)
        return 0, ""
    except Exception as exc:  # noqa: BLE001 - a hook must never break the agent
        log_event(project, event, f"internal error: {type(exc).__name__}: {exc}")
        return 0, ""
