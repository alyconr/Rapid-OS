"""Access to the onboarding state (`.rapid-os/setup.json`).

Reading never writes: when `setup.json` does not exist, a project initialized before the setup
flow gets a state derived from what is already on disk. `write_setup` is the only writer.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

from rapid_os.adapters.agents import DEFAULT_AGENT_REGISTRY
from rapid_os.adapters.project_commands import propose_test_command
from rapid_os.core.config import inspect_project_config_file
from rapid_os.core.filesystem import safe_write_text
from rapid_os.core.harness_detect import detect_harness
from rapid_os.domain.catalog import Catalog, SetupDocBank
from rapid_os.domain.project_docs import is_managed, parse_doc_frontmatter
from rapid_os.domain.project import ProjectModel
from rapid_os.domain.security import security_has_ai_section
from rapid_os.domain.stack_aliases import LEGACY_STACKS
from rapid_os.domain.setup import (
    ARCHETYPES,
    STACK_COMPONENTS,
    DocState,
    SetupState,
    SetupStateError,
    StackChoice,
)

SETUP_FILE_NAME = "setup.json"
ORIGIN_FILE = "setup.json"
ORIGIN_DERIVED = "derived"
ORIGIN_EMPTY = "empty"


@dataclass(frozen=True)
class SetupSnapshot:
    state: SetupState
    origin: str
    # Inputs for the pure conductor that need the filesystem or the environment.
    proposed_test_command: tuple[str, ...] | None = None
    detected_agent: str | None = None


def read_setup(
    project_root: Path,
    rapid_dir: Path,
    config_file: Path,
    templates_dir: Path,
    catalog: Catalog,
    doc_banks: Mapping[str, SetupDocBank],
    project_model: ProjectModel | None = None,
) -> SetupSnapshot:
    """Return the persisted state, a state derived from disk, or the empty state."""
    setup_file = rapid_dir / SETUP_FILE_NAME
    if setup_file.exists() or setup_file.is_symlink():
        state, origin = _load_file(setup_file), ORIGIN_FILE
    elif not rapid_dir.is_dir():
        state, origin = SetupState(), ORIGIN_EMPTY
    else:
        state = _derive_state(project_root, rapid_dir, config_file, templates_dir, catalog, doc_banks)
        origin = ORIGIN_DERIVED

    proposed = propose_test_command(project_root, project_model) if project_model is not None else None
    return SetupSnapshot(
        state,
        origin,
        proposed_test_command=tuple(proposed) if proposed else None,
        detected_agent=_detect_agent(config_file),
    )


def read_setup_file(rapid_dir: Path) -> tuple[SetupState | None, str | None]:
    """`(state, None)` when `setup.json` is valid, `(None, None)` when absent, `(None, error)` when not."""
    setup_file = rapid_dir / SETUP_FILE_NAME
    if not (setup_file.exists() or setup_file.is_symlink()):
        return None, None
    try:
        return _load_file(setup_file), None
    except SetupStateError as exc:
        return None, str(exc)


def load_setup_file(rapid_dir: Path) -> SetupState | None:
    """The persisted state, or None when `.rapid-os/setup.json` does not exist."""
    setup_file = Path(rapid_dir) / SETUP_FILE_NAME
    return _load_file(setup_file) if setup_file.exists() else None


def write_setup(rapid_dir: Path, state: SetupState) -> Path:
    """Atomically write `setup.json`, creating `.rapid-os/` when it does not exist."""
    return safe_write_text(
        rapid_dir / SETUP_FILE_NAME,
        json.dumps(state.to_dict(), indent=2) + "\n",
        encoding="utf-8",
        backup=False,
        create_parents=True,
    )


def derive_state(
    project_root: Path,
    rapid_dir: Path,
    config_file: Path,
    templates_dir: Path,
    catalog: Catalog,
    doc_banks: Mapping[str, SetupDocBank],
) -> SetupState:
    """The state that the files on disk already express (what `rapid setup` would derive)."""
    return _derive_state(project_root, rapid_dir, config_file, templates_dir, catalog, doc_banks)


def _detect_agent(config_file: Path) -> str | None:
    """The harness named by the environment or the config; the cursor fallback is not a detection."""
    config = inspect_project_config_file(config_file)
    try:
        detection = detect_harness(None, os.environ, config.config if config.is_valid else {})
    except ValueError:
        return None
    return None if detection.source == "fallback" else detection.harness_id


def _load_file(path: Path) -> SetupState:
    try:
        raw = path.read_text(encoding="utf-8")
        data = json.loads(raw)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise SetupStateError(f"RAPID1406 Invalid setup state '{path.name}': cannot be read as JSON ({exc}).") from exc
    return SetupState.from_dict(data)


def _read_text(path: Path) -> str | None:
    try:
        return path.read_text(encoding="utf-8") if path.is_file() else None
    except (OSError, UnicodeDecodeError):
        return None


def _derive_state(
    project_root: Path,
    rapid_dir: Path,
    config_file: Path,
    templates_dir: Path,
    catalog: Catalog,
    doc_banks: Mapping[str, SetupDocBank],
) -> SetupState:
    standards = rapid_dir / "standards"
    config = inspect_project_config_file(config_file)
    config_data = config.config if config.is_valid and config_file.exists() else {}

    tools = config_data.get("tools", [])
    known_agents = set(DEFAULT_AGENT_REGISTRY.ids())
    agents = tuple(t for t in tools if isinstance(t, str) and t in known_agents)

    test_command = config_data.get("test_command")
    if not (isinstance(test_command, list) and all(isinstance(t, str) for t in test_command)):
        test_command = None

    return SetupState(
        stacks=_derive_stacks(_read_text(standards / "tech-stack.md"), catalog),
        topology=_derive_topology(_read_text(standards / "topology.md")),
        archetype=_derive_archetype(_read_text(standards / "coding-rules.md"), templates_dir),
        agents=agents,
        test_command=None if test_command is None else tuple(test_command),
        docs={doc_id: _derive_doc(project_root, doc_id, bank) for doc_id, bank in doc_banks.items()},
        ai=_derive_ai(_read_text(standards / "security.md")),
    )


_STACK_MARKER = re.compile(r"<!--\s*rapid-stack:\s*([^>]*?)\s*-->")


def _derive_stacks(content: str | None, catalog: Catalog) -> dict[str, StackChoice]:
    """The stack of each component a `tech-stack.md` says. Rapid OS marks every block it writes
    (`<!-- rapid-stack: backend=go -->`); a file from before the component catalog is read by its
    title (`python-api` maps to backend `python-fastapi`...)."""
    if content is None:
        return {}
    stacks: dict[str, StackChoice] = {}
    for marker in _STACK_MARKER.finditer(content):
        for pair in marker.group(1).split():
            component, _, stack_id = pair.partition("=")
            if component in STACK_COMPONENTS and stack_id:
                source = "generic" if stack_id == "generic" else "catalog" if stack_id in catalog.stacks else "custom"
                profile = "creative" if stack_id == "react-vite" and "React Three Fiber" in content else None
                stacks[component] = StackChoice(stack_id, source, profile)
    if stacks:
        return stacks
    from rapid_os.domain.validation import infer_stack  # lazy: validation imports the adapters

    stack_id = infer_stack(content)
    if stack_id is None:
        return {component: StackChoice("custom", "custom") for component in STACK_COMPONENTS}
    if stack_id == "generic":
        return {component: StackChoice("generic", "generic") for component in STACK_COMPONENTS}
    legacy = LEGACY_STACKS.get(stack_id)
    if legacy is not None:
        return {
            component: StackChoice(new_id, "catalog", legacy.profile if component == "frontend" else None)
            for component, new_id in legacy.stacks.items()
        }
    if stack_id == "docs-modern":
        return {"docs": StackChoice(stack_id, "catalog")}
    source = "catalog" if stack_id in catalog.stacks else "custom"
    return {component: StackChoice(stack_id, source) for component in STACK_COMPONENTS}


def _derive_topology(content: str | None) -> str | None:
    if content is None:
        return None
    from rapid_os.domain.validation import infer_topology  # lazy: validation imports the adapters

    return infer_topology(content) or "custom"


def _derive_archetype(content: str | None, templates_dir: Path) -> str | None:
    """`rapid init` copies the archetype's coding rules; match them to name the archetype."""
    if content is None:
        return None
    for archetype in ARCHETYPES:
        template = _read_text(templates_dir / "archetypes" / archetype / "coding-rules.md")
        if template is not None and template == content:
            return archetype
    return "custom"


def _derive_ai(security: str | None) -> bool | None:
    """With a security standard on disk the answer is known: it has the AI section or it does not."""
    if security is None:
        return None
    return security_has_ai_section(security)


def _derive_doc(project_root: Path, doc_id: str, bank: SetupDocBank) -> DocState:
    """A doc counts only when it carries the `rapid-doc` frontmatter written by `rapid setup doc`."""
    text = _read_text(project_root / bank.file)
    if text is None:
        return DocState()
    fields, _body = parse_doc_frontmatter(text)
    if not is_managed(fields, doc_id):
        return DocState()
    return DocState(
        status=fields["source"],
        confirmed=fields.get("status") == "confirmed",
        sha256=fields.get("sha256", ""),
    )
