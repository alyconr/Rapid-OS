from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

from rapid_os.core.filesystem import create_backup
from rapid_os.core.output import print_success


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

    @property
    def output_files(self):
        return tuple(output.relative_path for output in self.outputs)

    @abstractmethod
    def render(self, context: str) -> Mapping[Path, str]:
        """Return generated content keyed by relative output path."""

    def activate(self, context: str, current_dir: Path) -> None:
        """Render and place the adapter outputs in a project directory."""
        rendered_outputs = self.render(context)

        for output in self.outputs:
            relative_path = output.relative_path
            if relative_path not in rendered_outputs:
                raise KeyError(
                    f"Adapter '{self.id}' did not render '{relative_path.as_posix()}'."
                )

            target = current_dir / relative_path
            target.parent.mkdir(parents=True, exist_ok=True)
            create_backup(target)
            target.write_text(rendered_outputs[relative_path], encoding=output.encoding)
            print_success(output.success_message)
