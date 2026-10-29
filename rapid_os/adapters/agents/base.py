import hashlib
import json
import sys
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Sequence

from rapid_os.core.filesystem import resolve_child_path, safe_write_text
from rapid_os.core.output import print_success
from rapid_os.domain.shortcuts import ShortcutTemplate


@dataclass(frozen=True)
class AgentOutput:
    """A file produced by an agent adapter."""

    relative_path: Path
    success_message: str
    encoding: str = "utf-8"


AGENT_BACKUP_DIR = Path(".rapid-os") / "backups"
AGENT_BACKUPS_KEPT = 5
# SHA-256 of each agent file as Rapid OS last wrote it, to tell a file that was edited by hand.
GENERATED_MANIFEST = Path(".rapid-os") / "generated.json"
HAND_EDITED_CODE = "RAPID1427"


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def read_generated_manifest(current_dir: Path) -> dict[str, str]:
    try:
        data = json.loads((Path(current_dir) / GENERATED_MANIFEST).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return {k: v for k, v in data.items() if isinstance(k, str) and isinstance(v, str)} if isinstance(data, dict) else {}


def write_generated_manifest(current_dir: Path, manifest: Mapping[str, str]) -> None:
    safe_write_text(
        Path(current_dir) / GENERATED_MANIFEST,
        json.dumps(dict(sorted(manifest.items())), indent=2) + "\n",
        encoding="utf-8",
        allow_overwrite=True,
        create_parents=True,
    )


class AgentAdapter(ABC):
    """Base contract for agents that consume Rapid OS project context."""

    id: str
    name: str
    metadata: Mapping[str, str] = {}
    outputs: tuple[AgentOutput, ...] = ()
    # Folder (relative to the project root) where `shortcut_outputs` writes, and the documented
    # user-level folder (relative to the home directory) with the page that documents it. A
    # harness without a documented user-level folder has `global_skills_root = None`.
    skills_root: tuple[str, ...] | None = None
    global_skills_root: tuple[str, ...] | None = None
    global_docs_url: str | None = None

    @property
    def output_files(self):
        return tuple(output.relative_path for output in self.outputs)

    @abstractmethod
    def render(self, context: str) -> Mapping[Path, str]:
        """Return generated content keyed by relative output path."""

    def shortcut_outputs(
        self, shortcuts: Sequence[ShortcutTemplate]
    ) -> Mapping[Path, str]:
        """Return `/rapid-<modo>` shortcut files keyed by relative path (none by default)."""
        return {}

    def global_shortcut_outputs(
        self, shortcuts: Sequence[ShortcutTemplate]
    ) -> Mapping[Path, str]:
        """The same shortcut files, keyed by path relative to the home directory."""
        if self.global_skills_root is None or self.skills_root is None:
            return {}
        project_root = self.skills_root
        remapped = {}
        for relative, content in self.shortcut_outputs(shortcuts).items():
            parts = relative.parts
            if parts[: len(project_root)] != project_root:
                raise ValueError(f"Shortcut path '{relative}' is outside '{'/'.join(project_root)}'.")
            remapped[Path(*self.global_skills_root, *parts[len(project_root):])] = content
        return remapped

    def activate(self, context: str, current_dir: Path) -> None:
        """Render and place the adapter outputs in a project directory."""
        rendered_outputs = self.render(context)
        manifest = read_generated_manifest(current_dir)
        manifest_changed = False

        for output in self.outputs:
            relative_path = output.relative_path
            if relative_path not in rendered_outputs:
                raise KeyError(
                    f"Adapter '{self.id}' did not render '{relative_path.as_posix()}'."
                )

            target = resolve_child_path(current_dir, relative_path)
            key = relative_path.as_posix()
            new_bytes = rendered_outputs[relative_path].encode(output.encoding)
            # The whole file is rewritten from the standards: if it differs from what Rapid OS wrote last time
            # (and from what it is about to write) somebody edited it. The previous copy goes to the backups.
            if target.is_file() and key in manifest:
                existing_bytes = target.read_bytes()
                if _sha256(existing_bytes) != manifest[key] and existing_bytes.replace(b"\r\n", b"\n") != new_bytes:
                    print(
                        f"WARNING {HAND_EDITED_CODE} {key} tiene cambios hechos a mano (difiere de lo último que generó "
                        f"Rapid OS) y se va a sobrescribir; la versión anterior queda en {AGENT_BACKUP_DIR.as_posix()}/. "
                        "Pasa lo que quieras conservar a los estándares de .rapid-os/standards/, que son la fuente.",
                        file=sys.stderr,
                    )
            # Regenerated on every change of the standards: the backups live in
            # .rapid-os/backups (not in the project root), the 5 latest per file, and none
            # when the content did not change.
            safe_write_text(
                target,
                rendered_outputs[relative_path],
                encoding=output.encoding,
                backup=True,
                create_parents=True,
                backup_dir=Path(current_dir) / AGENT_BACKUP_DIR,
                keep_backups=AGENT_BACKUPS_KEPT,
            )
            written = _sha256(target.read_bytes())
            if manifest.get(key) != written:
                manifest[key] = written
                manifest_changed = True
            print_success(output.success_message)
        if manifest_changed:
            write_generated_manifest(current_dir, manifest)
