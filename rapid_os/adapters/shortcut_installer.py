"""Plan, install, list and remove generated `/rapid-<modo>` harness shortcuts.

Files never overwrite silently: identical content is not rewritten, different content is
backed up (`.bak`) first, and `remove` only deletes files carrying the generated marker.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Mapping, Sequence

from rapid_os.adapters.agents import DEFAULT_AGENT_REGISTRY, AgentRegistry
from rapid_os.core.filesystem import resolve_child_path, safe_write_text
from rapid_os.domain.shortcuts import (
    SHORTCUT_NAMES,
    ShortcutTemplate,
    ShortcutTemplateError,
    has_generated_marker,
    parse_template,
)
from rapid_os.orchestration.playbooks import PlaybookError, load_playbook


class ShortcutError(ValueError):
    """Expected shortcut failure, reported as `RAPIDxxxx message` with exit 1."""

    def __init__(self, code: str, message: str):
        super().__init__(f"{code} {message}")
        self.code = code


@dataclass(frozen=True)
class PlannedFile:
    path: Path
    content: str
    harnesses: tuple[str, ...]
    shortcut: str
    action: str  # create | update | unchanged


@dataclass(frozen=True)
class SkippedShortcut:
    shortcut: str
    mode: str
    code: str
    reason: str


@dataclass(frozen=True)
class InstallPlan:
    harnesses: tuple[str, ...]
    files: tuple[PlannedFile, ...]
    skipped: tuple[SkippedShortcut, ...]
    warnings: tuple[str, ...] = ()
    # The same warnings as objects ({code, message, ...}) for the JSON output.
    warning_objects: tuple[dict, ...] = ()


@dataclass(frozen=True)
class RemovalEntry:
    path: Path
    harnesses: tuple[str, ...]
    shortcut: str
    action: str  # remove | skip_unmarked | absent


@dataclass(frozen=True)
class ListEntry:
    harness: str
    shortcut: str
    path: Path
    state: str  # installed | outdated | missing | unmanaged


def load_templates(templates_dir: Path) -> tuple[ShortcutTemplate, ...]:
    templates = []
    for name in SHORTCUT_NAMES:
        path = Path(templates_dir) / "shortcuts" / f"{name}.md"
        try:
            text = path.read_text(encoding="utf-8")
        except OSError as exc:
            raise ShortcutError(
                "RAPID1313", f"Shortcut template '{name}' not readable at {path}: {exc}"
            ) from exc
        try:
            templates.append(parse_template(name, text))
        except ShortcutTemplateError as exc:
            raise ShortcutError("RAPID1313", str(exc).removeprefix("RAPID1313 ")) from exc
    return tuple(templates)


def split_available(
    templates: Sequence[ShortcutTemplate], templates_dir: Path
) -> tuple[tuple[ShortcutTemplate, ...], tuple[SkippedShortcut, ...]]:
    """Mode shortcuts need a playbook; utility shortcuts are always available."""
    available: list[ShortcutTemplate] = []
    skipped: list[SkippedShortcut] = []
    for template in templates:
        if template.mode is None:
            available.append(template)
            continue
        # The playbook must exist in the templates being installed from (load_playbook alone
        # also falls back to the packaged templates).
        has_playbook = (Path(templates_dir) / "modes" / f"{template.mode}.json").is_file()
        try:
            if not has_playbook:
                raise PlaybookError(f"Playbook for mode '{template.mode}' not found.")
            load_playbook(template.mode, templates_dir=templates_dir)
        except PlaybookError:
            skipped.append(
                SkippedShortcut(
                    shortcut=template.name,
                    mode=template.mode,
                    code="RAPID1315",
                    reason=(
                        f"No playbook templates/modes/{template.mode}.json; the shortcut "
                        "is generated once the mode playbook exists."
                    ),
                )
            )
        else:
            available.append(template)
    return tuple(available), tuple(skipped)


def resolve_harness_ids(
    explicit: Iterable[str] | None,
    config_tools: Iterable[str] | None,
    registry: AgentRegistry = DEFAULT_AGENT_REGISTRY,
) -> tuple[str, ...]:
    supported = registry.ids()
    if explicit:
        requested = list(explicit)
        unknown = sorted({h for h in requested if h not in supported})
        if unknown:
            raise ShortcutError(
                "RAPID1311",
                f"Unsupported harness for shortcuts: {', '.join(unknown)}. "
                f"Supported: {', '.join(supported)}.",
            )
    else:
        requested = [t for t in (config_tools or ()) if t in supported]
        if not requested:
            raise ShortcutError(
                "RAPID1312",
                "No harness selected: pass --harness <id> or list a supported harness in "
                f"'tools' of .rapid-os/config.json ({', '.join(supported)}).",
            )
    return tuple(h for h in supported if h in set(requested))


SCOPES = ("project", "global")


def select_templates(
    templates: Sequence[ShortcutTemplate], only: Iterable[str] | None
) -> tuple[ShortcutTemplate, ...]:
    """Keep only the named shortcuts (`--only`); an unknown name is RAPID1413."""
    if not only:
        return tuple(templates)
    wanted = list(dict.fromkeys(only))
    known = {t.name for t in templates}
    unknown = [name for name in wanted if name not in known]
    if unknown:
        raise ShortcutError(
            "RAPID1413",
            f"Unknown shortcut for --only: {', '.join(unknown)}. Known: {', '.join(sorted(known))}.",
        )
    return tuple(t for t in templates if t.name in set(wanted))


def ensure_global_supported(
    harness_ids: Sequence[str], registry: AgentRegistry = DEFAULT_AGENT_REGISTRY
) -> None:
    """`--global` needs a documented user-level folder; otherwise RAPID1413 and nothing is written."""
    unsupported = [h for h in harness_ids if registry.get(h).global_skills_root is None]
    if unsupported:
        details = "; ".join(
            f"{h}: no user-level folder is documented ({registry.get(h).global_docs_url})"
            for h in unsupported
        )
        raise ShortcutError(
            "RAPID1413",
            f"--global is not supported for {', '.join(unsupported)}. {details}. "
            "Install it in the project instead (without --global).",
        )


def _adapter_outputs(
    registry: AgentRegistry,
    harness_id: str,
    templates: Sequence[ShortcutTemplate],
    scope: str,
) -> Mapping[Path, str]:
    adapter = registry.get(harness_id)
    if scope == "global":
        return adapter.global_shortcut_outputs(templates)
    return adapter.shortcut_outputs(templates)


def _target(project_root: Path, relative: Path) -> Path:
    try:
        target = resolve_child_path(project_root, relative)
    except ValueError as exc:
        raise ShortcutError("RAPID1314", f"Unsafe shortcut path '{relative}': {exc}") from exc
    if Path(project_root, relative).is_symlink():
        raise ShortcutError("RAPID1314", f"Refusing symlinked shortcut path '{relative}'.")
    return target


def _read_existing(target: Path) -> str | None:
    if not target.exists():
        return None
    try:
        return target.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        raise ShortcutError("RAPID1314", f"Cannot read existing file {target}: {exc}") from exc


def _outputs_by_path(
    harness_ids: Sequence[str],
    templates: Sequence[ShortcutTemplate],
    registry: AgentRegistry,
    scope: str = "project",
) -> dict[Path, tuple[str, list[str], str]]:
    """Merge adapter outputs by path (Codex and Antigravity share `.agents/skills`)."""
    merged: dict[Path, tuple[str, list[str], str]] = {}
    by_name = {t.name: t for t in templates}
    ordered = [h for h in registry.ids() if h in set(harness_ids)]  # stable owner order
    for harness_id in ordered:
        rendered: Mapping[Path, str] = _adapter_outputs(registry, harness_id, templates, scope)
        for relative, content in rendered.items():
            shortcut = _shortcut_of(relative, by_name)
            if relative in merged:
                if merged[relative][0] != content:
                    raise ShortcutError(
                        "RAPID1314",
                        f"Harnesses render different content for '{relative.as_posix()}'.",
                    )
                merged[relative][1].append(harness_id)
            else:
                merged[relative] = (content, [harness_id], shortcut)
    return merged


def _shortcut_of(relative: Path, by_name: Mapping[str, ShortcutTemplate]) -> str:
    for name in by_name:
        if name in relative.parts or relative.name.startswith(f"{name}."):
            return name
    return relative.stem


@dataclass(frozen=True)
class ScopeDuplicate:
    """The same /rapid-* installed both for the user (home) and in the project, for one harness."""

    harness: str
    shortcuts: tuple[str, ...]
    user_folder: str
    project_folder: str

    @property
    def message(self) -> str:
        return (
            f"RAPID1321 {self.harness}: {len(self.shortcuts)} shortcut(s) /rapid-* están a la vez en tu usuario "
            f"(~/{self.user_folder}) y en este proyecto ({self.project_folder}) y se verán duplicados "
            f"({', '.join(self.shortcuts)}). Deja uno solo: `rapid shortcuts remove --harness {self.harness}` "
            f"quita los del proyecto; `rapid shortcuts remove --global --harness {self.harness}` quita los del usuario."
        )

    def to_dict(self) -> dict:
        return {
            "code": "RAPID1321",
            "message": self.message,
            "harness": self.harness,
            "shortcuts": list(self.shortcuts),
            "user_folder": self.user_folder,
            "project_folder": self.project_folder,
        }


def detect_scope_duplicates(
    home: Path,
    project_root: Path,
    harness_ids: Sequence[str],
    templates_dir: Path,
    registry: AgentRegistry = DEFAULT_AGENT_REGISTRY,
) -> list[ScopeDuplicate]:
    """/rapid-* files that exist in `home` and in `project_root` for the same harness (read-only)."""
    home, project_root = Path(home), Path(project_root)
    try:
        if home.resolve() == project_root.resolve():
            return []
    except OSError:
        return []
    templates = load_templates(templates_dir)
    by_name = {t.name: t for t in templates}
    found: list[ScopeDuplicate] = []
    for harness_id in dict.fromkeys(harness_ids):
        try:
            user_outputs = _adapter_outputs(registry, harness_id, templates, "global")
            project_outputs = _adapter_outputs(registry, harness_id, templates, "project")
        except (ShortcutError, NotImplementedError, AttributeError):
            continue  # the harness has no user-level shortcuts
        project_by_shortcut = {_shortcut_of(rel, by_name): rel for rel in project_outputs}
        shortcuts: list[str] = []
        user_folder = project_folder = ""
        for relative in user_outputs:
            name = _shortcut_of(relative, by_name)
            counterpart = project_by_shortcut.get(name)
            if counterpart is None:
                continue
            if (home / relative).is_file() and (project_root / counterpart).is_file():
                shortcuts.append(name)
                user_folder = user_folder or relative.parent.parent.as_posix()
                project_folder = project_folder or counterpart.parent.parent.as_posix()
        if shortcuts:
            found.append(ScopeDuplicate(harness_id, tuple(sorted(set(shortcuts))), user_folder, project_folder))
    return found


def build_plan(
    project_root: Path,
    harness_ids: Sequence[str],
    templates_dir: Path,
    registry: AgentRegistry = DEFAULT_AGENT_REGISTRY,
    *,
    scope: str = "project",
    only: Iterable[str] | None = None,
) -> InstallPlan:
    """With `scope="global"`, `project_root` is the home directory."""
    if scope == "global":
        ensure_global_supported(harness_ids, registry)
    templates = select_templates(load_templates(templates_dir), only)
    available, skipped = split_available(templates, templates_dir)
    merged = _outputs_by_path(harness_ids, available, registry, scope)

    files: list[PlannedFile] = []
    warnings: list[str] = []
    warning_objects: list[dict] = []
    for relative in sorted(merged, key=lambda p: p.as_posix()):
        content, owners, shortcut = merged[relative]
        existing = _read_existing(_target(project_root, relative))
        if existing is None:
            action = "create"
        elif existing == content:
            action = "unchanged"
        else:
            action = "update"
            if not has_generated_marker(existing):
                message = (
                    f"RAPID1316 {relative.as_posix()} exists without the generated marker; "
                    "it will be replaced and the previous content kept as .bak."
                )
                warnings.append(message)
                warning_objects.append(
                    {"code": "RAPID1316", "message": message, "path": relative.as_posix()}
                )
        files.append(PlannedFile(relative, content, tuple(owners), shortcut, action))
    for s in skipped:
        message = f"{s.code} {s.shortcut}: {s.reason}"
        warnings.append(message)
        warning_objects.append(
            {"code": s.code, "message": message, "shortcut": s.shortcut, "mode": s.mode}
        )
    return InstallPlan(tuple(harness_ids), tuple(files), skipped, tuple(warnings), tuple(warning_objects))


def apply_plan(project_root: Path, plan: InstallPlan) -> tuple[Path, ...]:
    """Write only files whose content differs; returns the relative paths written."""
    written: list[Path] = []
    for planned in plan.files:
        if planned.action == "unchanged":
            continue
        target = _target(project_root, planned.path)
        try:
            safe_write_text(target, planned.content, backup=True, create_parents=True)
        except OSError as exc:
            raise ShortcutError("RAPID1314", f"Cannot write {planned.path.as_posix()}: {exc}") from exc
        written.append(planned.path)
    return tuple(written)


def list_entries(
    project_root: Path,
    harness_ids: Sequence[str],
    templates_dir: Path,
    registry: AgentRegistry = DEFAULT_AGENT_REGISTRY,
    *,
    scope: str = "project",
    only: Iterable[str] | None = None,
) -> tuple[tuple[ListEntry, ...], tuple[SkippedShortcut, ...]]:
    if scope == "global":
        ensure_global_supported(harness_ids, registry)
    templates = select_templates(load_templates(templates_dir), only)
    available, skipped = split_available(templates, templates_dir)
    entries: list[ListEntry] = []
    for harness_id in harness_ids:
        by_name = {t.name: t for t in available}
        for relative, content in _adapter_outputs(registry, harness_id, available, scope).items():
            existing = _read_existing(_target(project_root, relative))
            if existing is None:
                state = "missing"
            elif existing == content:
                state = "installed"
            elif has_generated_marker(existing):
                state = "outdated"
            else:
                state = "unmanaged"
            entries.append(
                ListEntry(harness_id, _shortcut_of(relative, by_name), relative, state)
            )
    return tuple(entries), skipped


def plan_removal(
    project_root: Path,
    harness_ids: Sequence[str],
    templates_dir: Path,
    registry: AgentRegistry = DEFAULT_AGENT_REGISTRY,
    *,
    scope: str = "project",
    only: Iterable[str] | None = None,
) -> tuple[RemovalEntry, ...]:
    if scope == "global":
        ensure_global_supported(harness_ids, registry)
    # All templates, not only the available ones: modes whose playbook disappeared
    # must still be removable.
    templates = select_templates(load_templates(templates_dir), only)
    merged = _outputs_by_path(harness_ids, templates, registry, scope)
    entries: list[RemovalEntry] = []
    for relative in sorted(merged, key=lambda p: p.as_posix()):
        _, owners, shortcut = merged[relative]
        existing = _read_existing(_target(project_root, relative))
        if existing is None:
            action = "absent"
        elif has_generated_marker(existing):
            action = "remove"
        else:
            action = "skip_unmarked"
        entries.append(RemovalEntry(relative, tuple(owners), shortcut, action))
    return tuple(entries)


def apply_removal(project_root: Path, entries: Iterable[RemovalEntry]) -> tuple[Path, ...]:
    removed: list[Path] = []
    for entry in entries:
        if entry.action != "remove":
            continue
        target = _target(project_root, entry.path)
        try:
            target.unlink()
            if target.name == "SKILL.md":
                try:
                    target.parent.rmdir()  # only the empty <name>/ folder, never shared roots
                except OSError:
                    pass
        except OSError as exc:
            raise ShortcutError("RAPID1314", f"Cannot remove {entry.path.as_posix()}: {exc}") from exc
        removed.append(entry.path)
    return tuple(removed)
