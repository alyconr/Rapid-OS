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

        for output in self.outputs:
            relative_path = output.relative_path
            if relative_path not in rendered_outputs:
                raise KeyError(
                    f"Adapter '{self.id}' did not render '{relative_path.as_posix()}'."
                )

            target = resolve_child_path(current_dir, relative_path)
            safe_write_text(
                target,
                rendered_outputs[relative_path],
                encoding=output.encoding,
                backup=True,
                create_parents=True,
            )
            print_success(output.success_message)
