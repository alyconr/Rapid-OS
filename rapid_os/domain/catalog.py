"""Stack and topology catalog read from JSON sidecars (RAPID1401 on invalid data)."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from rapid_os.domain.project import ProjectModel

CATALOG_SCHEMA_VERSION = 1
GENERIC_STACK_ID = "generic"
GENERIC_STACK_HEADER = "# TECH STACK: GENERIC"
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


DOC_SITE_TOPOLOGY = "doc-site"


@dataclass(frozen=True)
class Catalog:
    stacks: dict[str, StackEntry]
    topologies: dict[str, TopologyEntry]
    # Markdown templates without a sidecar (RAPID1412): still usable, compatible with every
    # topology except doc-site.
    sidecarless_stacks: tuple[str, ...] = ()
    sidecarless_topologies: tuple[str, ...] = ()

    @property
    def topology_ids(self) -> tuple[str, ...]:
        return tuple(sorted(set(self.topologies) | set(self.sidecarless_topologies)))

    def compatible_topologies(self, stack_id: str) -> tuple[str, ...] | None:
        """Compatible topologies for a known stack, None when the stack is not in the catalog."""
        entry = self.stacks.get(stack_id)
        if entry is not None:
            return entry.compatible_topologies
        if stack_id in self.sidecarless_stacks:
            return tuple(t for t in self.topology_ids if t != DOC_SITE_TOPOLOGY)
        return None

    def is_compatible(self, stack_id: str, topology_id: str) -> bool | None:
        """True/False for known stacks, None when the stack is not in the catalog."""
        compatible = self.compatible_topologies(stack_id)
        if compatible is None:
            return None
        return topology_id in compatible

    def default_topology_for_stack(
        self, stack_name: str, suggested_topology: str | None, topologies
    ) -> str | None:
        """Topology for `rapid init --yes` when nothing was asked: coherent with the stack.

        A stack that only fits doc-site gets it; any other stack never defaults to doc-site.
        A scanner suggestion is kept only when it does not contradict the chosen stack.
        """
        compatible = self.compatible_topologies(stack_name)
        if compatible == (DOC_SITE_TOPOLOGY,):
            return DOC_SITE_TOPOLOGY if DOC_SITE_TOPOLOGY in topologies else None
        if (
            suggested_topology in topologies
            and suggested_topology != DOC_SITE_TOPOLOGY
            and self.is_compatible(stack_name, suggested_topology) is not False
        ):
            return suggested_topology
        entry = self.stacks.get(stack_name)
        if entry is not None and entry.default_topology in topologies:
            return entry.default_topology
        for name in topologies:
            if name != DOC_SITE_TOPOLOGY:
                return name
        return None


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


def _sidecarless(directory: Path) -> tuple[str, ...]:
    """Ids of Markdown templates that have no .json sidecar next to them."""
    return tuple(
        markdown.stem
        for markdown in sorted(directory.glob("*.md"))
        if not markdown.with_suffix(".json").exists()
    )


def load_catalog(templates_dir: Path) -> Catalog:
    templates_dir = Path(templates_dir)
    topology_dir = templates_dir / "topologies"
    stack_dir = templates_dir / "stacks"
    sidecarless_topologies = _sidecarless(topology_dir)
    sidecarless_stacks = _sidecarless(stack_dir)

    topologies = {}
    for path in sorted(topology_dir.glob("*.json")):
        entry = _load_topology(path)
        topologies[entry.id] = entry
    known_topologies = set(topologies) | set(sidecarless_topologies)
    stacks = {}
    for path in sorted(stack_dir.glob("*.json")):
        entry = _load_stack(path, known_topologies)
        stacks[entry.id] = entry
    return Catalog(
        stacks=stacks,
        topologies=topologies,
        sidecarless_stacks=sidecarless_stacks,
        sidecarless_topologies=sidecarless_topologies,
    )


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


def is_generic_stack(content: str) -> bool:
    """True when the text carries the exact header written by build_generic_stack."""
    return any(line.strip() == GENERIC_STACK_HEADER for line in content.splitlines())


NOT_SCANNED = "not scanned (--no-scan)"


def build_generic_stack(model: ProjectModel, *, scanned: bool = True) -> str:
    """Render a tech-stack.md from what the scanner detected (pure).

    With `scanned=False` nothing was searched, so facts read "not scanned" instead of
    claiming "not detected".
    """

    def value(category: str) -> str:
        return _detected(model, category) if scanned else NOT_SCANNED

    lines = [
        GENERIC_STACK_HEADER,
        f"- **Language:** {value('language')}.",
        f"- **Package manager:** {value('package_manager')}.",
        f"- **Framework:** {value('framework')}.",
        f"- **Testing:** {value('testing')}.",
        f"- **Convention:** {GENERIC_STACK_RULE}",
        "- **Version Control:** Git.",
    ]
    return "\n".join(lines) + "\n"


SETUP_DOC_IDS = ("brief", "business", "data-model", "architecture")
_CONTEXT_PRIORITIES = {"LOW", "MEDIUM", "HIGH", "CRITICAL"}


@dataclass(frozen=True)
class SetupQuestion:
    id: str
    text: str
    required: bool = True
    options: tuple[str, ...] = ()


@dataclass(frozen=True)
class RequiredSection:
    """A section the drafted doc must contain; any of `titles` (aliases) satisfies it."""

    id: str
    titles: tuple[str, ...]


@dataclass(frozen=True)
class SetupDocBank:
    id: str
    file: str
    title: str
    questions: tuple[SetupQuestion, ...]
    required_sections: tuple[RequiredSection, ...]
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


def _required_sections(path: Path, data: dict) -> tuple[RequiredSection, ...]:
    raw = data.get("required_sections")
    if not isinstance(raw, list) or not raw:
        raise _fail(path, "field 'required_sections' must be a non-empty list.")
    sections = []
    for item in raw:
        if not isinstance(item, dict):
            raise _fail(path, "each required section must be an object with 'id' and 'titles'.")
        sections.append(
            RequiredSection(_text(path, item, "id"), _text_list(path, item, "titles", non_empty=True))
        )
    return tuple(sections)


def load_setup_doc_banks(templates_dir: Path) -> dict[str, SetupDocBank]:
    directory = Path(templates_dir) / "setup" / "docs"
    banks = {}
    for doc_id in SETUP_DOC_IDS:
        path = directory / f"{doc_id}.json"
        data = _read_sidecar(path)
        max_chars = data.get("max_chars")
        if isinstance(max_chars, bool) or not isinstance(max_chars, int) or max_chars <= 0:
            raise _fail(path, "field 'max_chars' must be a positive integer.")
        priority = _text(path, data, "context_priority").upper()
        if priority not in _CONTEXT_PRIORITIES:
            raise _fail(path, f"context_priority must be one of {sorted(_CONTEXT_PRIORITIES)}.")
        questions = _questions(path, data)
        sections = _required_sections(path, data)
        question_ids = {question.id for question in questions}
        missing = [section.id for section in sections if section.id not in question_ids]
        if missing:
            raise _fail(path, f"required sections without a question of the same id: {', '.join(missing)}.")
        banks[doc_id] = SetupDocBank(
            id=doc_id,
            file=_text(path, data, "file"),
            title=_text(path, data, "title"),
            questions=questions,
            required_sections=sections,
            max_chars=max_chars,
            context_priority=priority,
        )
    return banks


def load_stack_questions(templates_dir: Path) -> tuple[SetupQuestion, ...]:
    path = Path(templates_dir) / "setup" / "stack-questions.json"
    return _questions(path, _read_sidecar(path))
