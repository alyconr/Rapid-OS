"""Install and remove the Rapid OS hooks in the project's `.claude/settings.json`.

Settings schema (verified): https://code.claude.com/docs/en/hooks
  {"hooks": {"<Event>": [{"matcher": "...", "hooks": [{"type": "command", "command": "rapid",
                                                       "args": ["hook", "stop"], "timeout": 15}]}]}}

The handlers use the *exec form* (`command` + `args`): Claude Code resolves `rapid` on PATH and
spawns it without a shell, so the same entry works on Linux, macOS and Windows (pip installs a
real `rapid.exe` launcher there). If `rapid` is not on PATH the hook cannot start, which Claude
Code treats as a non-blocking error; `rapid doctor` warns about that (RAPID1339).

Ownership: a handler is ours when it is `rapid` with exactly the `hook stop` / `hook pre-tool`
arguments. Merging replaces only those handlers and `remove` deletes only those, leaving every
other key and hook of the file untouched.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
import json
from pathlib import Path

from rapid_os.adapters.shortcut_installer import ShortcutError
from rapid_os.core.filesystem import create_backup, resolve_child_path, safe_write_text

SETTINGS_PATH = Path(".claude") / "settings.json"
HOOK_COMMAND = "rapid"
HOOK_TIMEOUT_S = 15
PRE_TOOL_MATCHER = "Bash|PowerShell|Write|Edit|MultiEdit|NotebookEdit"

# event -> (args, matcher, spinner message)
OWN_HOOKS = {
    "Stop": (("hook", "stop"), None, "Rapid OS: checking the run state"),
    "PreToolUse": (("hook", "pre-tool"), PRE_TOOL_MATCHER, "Rapid OS: checking the command"),
}


def desired_handler(event: str) -> dict:
    args, _, message = OWN_HOOKS[event]
    return {
        "type": "command",
        "command": HOOK_COMMAND,
        "args": list(args),
        "timeout": HOOK_TIMEOUT_S,
        "statusMessage": message,
    }


def is_ours(handler: object, event: str) -> bool:
    return (
        isinstance(handler, dict)
        and handler.get("command") == HOOK_COMMAND
        and handler.get("args") == list(OWN_HOOKS[event][0])
    )


def _settings_error(path: Path, detail: str) -> ShortcutError:
    return ShortcutError("RAPID1338", f"Cannot merge Claude Code hooks into {path.as_posix()}: {detail}")


def read_settings(project_root: Path) -> tuple[Path, dict | None]:
    """Return (target path, parsed settings or None when the file does not exist)."""
    try:
        target = resolve_child_path(project_root, SETTINGS_PATH)
    except ValueError as exc:
        raise _settings_error(SETTINGS_PATH, str(exc)) from exc
    if not target.exists():
        return target, None
    try:
        data = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, ValueError) as exc:
        raise _settings_error(SETTINGS_PATH, f"the file is not valid JSON ({exc})") from exc
    if not isinstance(data, dict):
        raise _settings_error(SETTINGS_PATH, "the root must be a JSON object")
    return target, data


def merge_hooks(settings: dict) -> dict:
    """Return a copy of `settings` with the Rapid OS hooks present and up to date."""
    merged = deepcopy(settings)
    hooks = merged.setdefault("hooks", {})
    if not isinstance(hooks, dict):
        raise _settings_error(SETTINGS_PATH, "'hooks' must be an object")
    for event, (_, matcher, _) in OWN_HOOKS.items():
        groups = hooks.setdefault(event, [])
        if not isinstance(groups, list):
            raise _settings_error(SETTINGS_PATH, f"'hooks.{event}' must be a list")
        handler = desired_handler(event)
        placed = False
        for group in groups:
            inner = group.get("hooks") if isinstance(group, dict) else None
            if not isinstance(inner, list):
                continue
            for idx, existing in enumerate(inner):
                if is_ours(existing, event):
                    inner[idx] = handler
                    if len(inner) == 1 and matcher is not None:
                        group["matcher"] = matcher
                    placed = True
                    break
            if placed:
                break
        if not placed:
            new_group: dict = {"hooks": [handler]}
            if matcher is not None:
                new_group = {"matcher": matcher, "hooks": [handler]}
            groups.append(new_group)
    return merged


def strip_hooks(settings: dict) -> dict:
    """Return a copy of `settings` without the Rapid OS handlers (and any group left empty)."""
    stripped = deepcopy(settings)
    hooks = stripped.get("hooks")
    if not isinstance(hooks, dict):
        return stripped
    for event in OWN_HOOKS:
        groups = hooks.get(event)
        if not isinstance(groups, list):
            continue
        kept = []
        for group in groups:
            inner = group.get("hooks") if isinstance(group, dict) else None
            if isinstance(inner, list):
                remaining = [h for h in inner if not is_ours(h, event)]
                if len(remaining) != len(inner):
                    if not remaining:
                        continue
                    group = {**group, "hooks": remaining}
            kept.append(group)
        if kept:
            hooks[event] = kept
        else:
            hooks.pop(event)
    if not hooks:
        stripped.pop("hooks")
    return stripped


def hooks_installed(project_root: Path) -> bool:
    try:
        _, settings = read_settings(project_root)
    except ShortcutError:
        return False
    if not settings:
        return False
    hooks = settings.get("hooks")
    if not isinstance(hooks, dict):
        return False
    for event in OWN_HOOKS:
        for group in hooks.get(event, []) if isinstance(hooks.get(event), list) else []:
            inner = group.get("hooks") if isinstance(group, dict) else None
            if isinstance(inner, list) and any(is_ours(h, event) for h in inner):
                return True
    return False


@dataclass(frozen=True)
class HooksPlan:
    path: Path  # relative
    action: str  # create | update | unchanged | remove | absent
    settings: dict | None  # content to write (None = delete the file / nothing to write)

    def to_dict(self) -> dict:
        return {
            "path": self.path.as_posix(),
            "action": self.action,
            "events": list(OWN_HOOKS),
        }


def plan_install(project_root: Path) -> HooksPlan:
    _, current = read_settings(project_root)
    merged = merge_hooks(current or {})
    if current is None:
        return HooksPlan(SETTINGS_PATH, "create", merged)
    if merged == current:
        return HooksPlan(SETTINGS_PATH, "unchanged", merged)
    return HooksPlan(SETTINGS_PATH, "update", merged)


def plan_remove(project_root: Path) -> HooksPlan:
    _, current = read_settings(project_root)
    if current is None or not hooks_installed(project_root):
        return HooksPlan(SETTINGS_PATH, "absent", current)
    return HooksPlan(SETTINGS_PATH, "remove", strip_hooks(current))


def apply_plan(project_root: Path, plan: HooksPlan) -> bool:
    """Write the plan; returns True when the filesystem changed."""
    if plan.action in ("unchanged", "absent"):
        return False
    target = resolve_child_path(project_root, plan.path)
    try:
        if plan.action == "remove" and not plan.settings:
            create_backup(target)
            target.unlink()
            return True
        text = json.dumps(plan.settings, indent=2, ensure_ascii=False) + "\n"
        safe_write_text(target, text, encoding="utf-8", backup=True, create_parents=True)
    except OSError as exc:
        raise ShortcutError("RAPID1338", f"Cannot write {plan.path.as_posix()}: {exc}") from exc
    return True
