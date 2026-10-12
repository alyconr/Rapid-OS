from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Mapping

from rapid_os.core.paths import resolve_paths
from rapid_os.orchestration.actions import ActionKind


class PlaybookError(ValueError):
    """Domain error for orchestration playbooks (RAPID1303)."""

    code = "RAPID1303"

    def __init__(self, message: str, *, code: str = "RAPID1303", path: Path | str | None = None):
        super().__init__(f"{code} {message}" if not message.startswith("RAPID") else message)
        self.code = code
        self.path = path


@dataclass(frozen=True)
class Playbook:
    schema_version: int
    mode: str
    spec_template: dict[str, object]
    instructions: dict[str, str]

    def get_instruction(self, kind: ActionKind | str) -> str:
        coerced = ActionKind.coerce(kind)
        return self.instructions.get(coerced.value, "")


def _find_mode_file(mode: str, templates_dir: Path | None = None) -> Path | None:
    if templates_dir is not None:
        candidate = Path(templates_dir) / f"{mode}.json"
        if candidate.exists():
            return candidate
        candidate_subdir = Path(templates_dir) / "modes" / f"{mode}.json"
        if candidate_subdir.exists():
            return candidate_subdir

    resolved_templates = resolve_paths().templates_dir
    candidate = resolved_templates / "modes" / f"{mode}.json"
    if candidate.exists():
        return candidate
    candidate_root = resolved_templates / f"{mode}.json"
    if candidate_root.exists():
        return candidate_root

    # Source checkout fallback relative to this file
    repo_candidate = Path(__file__).resolve().parents[2] / "templates" / "modes" / f"{mode}.json"
    if repo_candidate.exists():
        return repo_candidate

    return None


def load_playbook(mode: str, templates_dir: Path | None = None) -> Playbook:
    """Load and validate an orchestration playbook from templates/modes/<mode>.json."""
    if not isinstance(mode, str) or not mode.strip():
        raise PlaybookError("Mode identifier must be a non-empty string.")

    cleaned_mode = mode.strip().lower()
    path = _find_mode_file(cleaned_mode, templates_dir)
    if path is None or not path.is_file():
        expected = (templates_dir or (resolve_paths().templates_dir / "modes")) / f"{cleaned_mode}.json"
        raise PlaybookError(
            f"Playbook for mode '{cleaned_mode}' not found at {expected}",
            path=expected,
        )

    try:
        content = path.read_text(encoding="utf-8")
        data = json.loads(content)
    except Exception as exc:
        raise PlaybookError(
            f"Failed to read or parse playbook at {path}: {exc}",
            path=path,
        ) from exc

    if not isinstance(data, Mapping):
        raise PlaybookError(f"Playbook at {path} must be a JSON object.", path=path)

    schema_version = data.get("schema_version")
    if schema_version != 1:
        raise PlaybookError(
            f"Unsupported playbook schema_version '{schema_version}': expected 1.",
            path=path,
        )

    mode_val = data.get("mode")
    if not isinstance(mode_val, str) or mode_val.lower() != cleaned_mode:
        raise PlaybookError(
            f"Playbook mode '{mode_val}' does not match requested mode '{cleaned_mode}'.",
            path=path,
        )

    spec_template = data.get("spec_template")
    if not isinstance(spec_template, Mapping):
        raise PlaybookError(
            "Playbook 'spec_template' must be a JSON object.",
            path=path,
        )

    instructions = data.get("instructions")
    if not isinstance(instructions, Mapping):
        raise PlaybookError(
            "Playbook 'instructions' must be a JSON mapping.",
            path=path,
        )

    norm_instructions = {str(k): str(v) for k, v in instructions.items()}

    return Playbook(
        schema_version=int(schema_version),
        mode=cleaned_mode,
        spec_template=dict(spec_template),
        instructions=norm_instructions,
    )
