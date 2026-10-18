"""Stack and topology catalog read from JSON sidecars (RAPID1401 on invalid data)."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from rapid_os.domain.project import ProjectModel

CATALOG_SCHEMA_VERSION = 1
GENERIC_STACK_ID = "generic"
GENERIC_STACK_TITLE = "# 🧩 TECH STACK: GENERIC"
GENERIC_STACK_RULE = "Follow the existing conventions of the repository."


class CatalogError(ValueError):
    """Invalid catalog sidecar (RAPID1401)."""

    code = "RAPID1401"


@dataclass(frozen=True)
class StackEntry:
    id: str
    summary: str
    language: str
    fits: tuple[str, ...]
    avoid_if: tuple[str, ...]
    compatible_topologies: tuple[str, ...]
    default_topology: str


@dataclass(frozen=True)
class TopologyEntry:
    id: str
    summary: str
    fits: tuple[str, ...]
    avoid_if: tuple[str, ...]


@dataclass(frozen=True)
class Catalog:
    stacks: dict[str, StackEntry]
    topologies: dict[str, TopologyEntry]

    def default_topology_for_stack(self, stack_id: str) -> str | None:
        entry = self.stacks.get(stack_id)
        return entry.default_topology if entry else None

    def is_compatible(self, stack_id: str, topology_id: str) -> bool | None:
        """True/False for known stacks, None when the stack is not in the catalog."""
        entry = self.stacks.get(stack_id)
        if entry is None:
            return None
        return topology_id in entry.compatible_topologies


def _fail(path: Path, message: str) -> CatalogError:
    return CatalogError(f"RAPID1401 Invalid catalog sidecar '{path.name}': {message}")


def _read_sidecar(path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise _fail(path, f"cannot be read as JSON ({exc}).") from exc
    if not isinstance(data, dict):
        raise _fail(path, "must contain a JSON object.")
    version = data.get("schema_version")
    if isinstance(version, bool) or version != CATALOG_SCHEMA_VERSION:
        raise _fail(path, f"schema_version must be {CATALOG_SCHEMA_VERSION}.")
    if data.get("id") != path.stem:
        raise _fail(path, f"id '{data.get('id')}' does not match the file name '{path.stem}'.")
    return data


def _text(path: Path, data: dict, field: str) -> str:
    value = data.get(field)
    if not isinstance(value, str) or not value.strip():
        raise _fail(path, f"missing or empty field '{field}'.")
    return value


def _text_list(path: Path, data: dict, field: str, *, non_empty: bool = False) -> tuple[str, ...]:
    value = data.get(field)
    if not isinstance(value, list) or not all(
        isinstance(item, str) and item.strip() for item in value
    ):
        raise _fail(path, f"field '{field}' must be a list of non-empty strings.")
    if non_empty and not value:
        raise _fail(path, f"field '{field}' must not be empty.")
    return tuple(value)


def _load_topology(path: Path) -> TopologyEntry:
    data = _read_sidecar(path)
    return TopologyEntry(
        id=data["id"],
        summary=_text(path, data, "summary"),
        fits=_text_list(path, data, "fits"),
        avoid_if=_text_list(path, data, "avoid_if"),
    )


def _load_stack(path: Path, topology_ids: set[str]) -> StackEntry:
    data = _read_sidecar(path)
    compatible = _text_list(path, data, "compatible_topologies", non_empty=True)
    default = _text(path, data, "default_topology")
    unknown = [item for item in compatible if item not in topology_ids]
    if unknown:
        raise _fail(path, f"compatible_topologies references unknown topology: {', '.join(unknown)}.")
    if default not in compatible:
        raise _fail(path, f"default_topology '{default}' is not listed in compatible_topologies.")
    return StackEntry(
        id=data["id"],
        summary=_text(path, data, "summary"),
        language=_text(path, data, "language"),
        fits=_text_list(path, data, "fits"),
        avoid_if=_text_list(path, data, "avoid_if"),
        compatible_topologies=compatible,
        default_topology=default,
    )


def _require_sidecars(directory: Path, paths: list[Path]) -> None:
    """Every Markdown template must have a sidecar next to it."""
    for markdown in sorted(directory.glob("*.md")):
        if markdown.with_suffix(".json") not in paths:
            raise _fail(markdown.with_suffix(".json"), f"missing sidecar for template '{markdown.name}'.")


def load_catalog(templates_dir: Path) -> Catalog:
    templates_dir = Path(templates_dir)
    topology_dir = templates_dir / "topologies"
    stack_dir = templates_dir / "stacks"
    topology_paths = sorted(topology_dir.glob("*.json"))
    stack_paths = sorted(stack_dir.glob("*.json"))
    _require_sidecars(topology_dir, topology_paths)
    _require_sidecars(stack_dir, stack_paths)

    topologies = {}
    for path in topology_paths:
        entry = _load_topology(path)
        topologies[entry.id] = entry
    stacks = {}
    for path in stack_paths:
        entry = _load_stack(path, set(topologies))
        stacks[entry.id] = entry
    return Catalog(stacks=stacks, topologies=topologies)


_LANGUAGE_NAMES = {
    "python": "Python",
    "typescript": "TypeScript",
    "javascript": "JavaScript",
    "go": "Go",
    "rust": "Rust",
    "java": "Java",
    "csharp": "C#",
    "php": "PHP",
    "ruby": "Ruby",
}


def _display(category: str, value: str) -> str:
    if category == "language":
        return _LANGUAGE_NAMES.get(value.lower(), value)
    return value


def _detected(model: ProjectModel, category: str) -> str:
    seen: list[str] = []
    for value in model.values(category):
        shown = _display(category, value)
        if shown not in seen:
            seen.append(shown)
    return ", ".join(seen) if seen else "not detected"


def build_generic_stack(model: ProjectModel) -> str:
    """Render a tech-stack.md from what the scanner detected (pure)."""
    lines = [
        GENERIC_STACK_TITLE,
        f"- **Language:** {_detected(model, 'language')}.",
        f"- **Package manager:** {_detected(model, 'package_manager')}.",
        f"- **Framework:** {_detected(model, 'framework')}.",
        f"- **Testing:** {_detected(model, 'testing')}.",
        f"- **Convention:** {GENERIC_STACK_RULE}",
        "- **Version Control:** Git.",
    ]
    return "\n".join(lines) + "\n"


SETUP_DOC_IDS = ("brief", "business", "data-model", "architecture")
_CONTEXT_PRIORITIES = {"low", "medium", "high", "critical"}


@dataclass(frozen=True)
class SetupQuestion:
    id: str
    text: str
    required: bool = True
    options: tuple[str, ...] = ()


@dataclass(frozen=True)
class SetupDocBank:
    id: str
    file: str
    title: str
    questions: tuple[SetupQuestion, ...]
    required_sections: tuple[str, ...]
    max_chars: int
    context_priority: str


def _questions(path: Path, data: dict) -> tuple[SetupQuestion, ...]:
    raw = data.get("questions")
    if not isinstance(raw, list) or not raw:
        raise _fail(path, "field 'questions' must be a non-empty list.")
    questions = []
    for item in raw:
        if not isinstance(item, dict):
            raise _fail(path, "each question must be an object.")
        required = item.get("required", True)
        if not isinstance(required, bool):
            raise _fail(path, "question 'required' must be a boolean.")
        options = item.get("options", [])
        if not isinstance(options, list) or not all(isinstance(o, str) and o for o in options):
            raise _fail(path, "question 'options' must be a list of non-empty strings.")
        questions.append(
            SetupQuestion(_text(path, item, "id"), _text(path, item, "text"), required, tuple(options))
        )
    return tuple(questions)


def load_setup_doc_banks(templates_dir: Path) -> dict[str, SetupDocBank]:
    directory = Path(templates_dir) / "setup" / "docs"
    banks = {}
    for doc_id in SETUP_DOC_IDS:
        path = directory / f"{doc_id}.json"
        data = _read_sidecar(path)
        max_chars = data.get("max_chars")
        if isinstance(max_chars, bool) or not isinstance(max_chars, int) or max_chars <= 0:
            raise _fail(path, "field 'max_chars' must be a positive integer.")
        priority = _text(path, data, "context_priority")
        if priority not in _CONTEXT_PRIORITIES:
            raise _fail(path, f"context_priority must be one of {sorted(_CONTEXT_PRIORITIES)}.")
        banks[doc_id] = SetupDocBank(
            id=doc_id,
            file=_text(path, data, "file"),
            title=_text(path, data, "title"),
            questions=_questions(path, data),
            required_sections=_text_list(path, data, "required_sections", non_empty=True),
            max_chars=max_chars,
            context_priority=priority,
        )
    return banks


def load_stack_questions(templates_dir: Path) -> tuple[SetupQuestion, ...]:
    path = Path(templates_dir) / "setup" / "stack-questions.json"
    return _questions(path, _read_sidecar(path))
