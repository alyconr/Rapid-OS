"""Writes of the onboarding: the decisions, the documents and the application of both to the project.

Shared by `rapid setup` and `rapid init`, so both leave the same files. Nothing here calls
`sys.exit` or prints: every expected failure is a `SetupApplyError` with a RAPID code, and the
CLI decides how to report it.

Order of authority: a document's frontmatter says whether it is confirmed; `setup.json` is
updated in the same operation and never contradicts it.
"""

from __future__ import annotations

import shlex
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Mapping, Sequence

from rapid_os.adapters.setup_store import derive_state
from rapid_os.core.config import inspect_project_config_file, save_project_config
from rapid_os.core.context import compose_project_context
from rapid_os.core.filesystem import (
    ensure_path_within_root,
    safe_append_text,
    safe_copy_file,
    safe_write_text,
    resolve_child_path,
)
from rapid_os.core.identifiers import validate_identifier
from rapid_os.domain.agents import generate_agent_contexts
from rapid_os.domain.catalog import (
    CUSTOM_STACK_ID,
    DOC_SITE_TOPOLOGY,
    GENERIC_STACK_ID,
    Catalog,
    SetupDocBank,
    build_generic_stack,
    missing_custom_stack_sections,
)
from rapid_os.domain.project import ProjectModel
from rapid_os.domain.project_docs import (
    DOC_SOURCES,
    parse_doc_frontmatter,
    prepare_body,
    body_sha256,
    is_managed,
    render_managed_doc,
    validate_doc_body,
    with_doc_status,
)
from rapid_os.domain.setup import ARCHETYPES, DocState, SetupAction, SetupActionKind, SetupState, StackChoice

DECISION_KEYS = ("stack", "topology", "archetype", "agents", "test-command")
NO_TEST_COMMAND = "none"
GITIGNORE_ENTRIES = (
    ".rapid-os/session.json",
    ".rapid-os/scratch/",
    ".rapid-os/backups/",
    # Tool artifacts: not writes of the project (see rapid_os.domain.file_changes).
    "__pycache__/",
    "*.pyc",
    ".pytest_cache/",
)


class SetupApplyError(ValueError):
    """An expected failure with a RAPID14xx code; `lines` are the full report lines."""

    def __init__(self, code: str, message: str, *, extra: Sequence[str] = ()):
        self.code = code
        self.lines = (f"{code} {message}", *extra)
        super().__init__("\n".join(self.lines))


def _fail(code: str, message: str) -> SetupApplyError:
    return SetupApplyError(code, message)


@dataclass(frozen=True)
class ApplyResult:
    written: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()


# --- decisions (pure) -----------------------------------------------------------------------


def allowed_topologies(catalog: Catalog, stack_id: str) -> tuple[str, ...]:
    """Topologies a stack accepts; a stack outside the catalog accepts all but doc-site."""
    compatible = catalog.compatible_topologies(stack_id)
    if compatible is None:
        return tuple(t for t in catalog.topology_ids if t != DOC_SITE_TOPOLOGY)
    return compatible


def _identifier(value: str, label: str) -> str:
    try:
        return validate_identifier(value, label)
    except ValueError as exc:
        raise _fail("RAPID1413", str(exc)) from exc


def set_decision(
    state: SetupState,
    key: str,
    value: str | None,
    catalog: Catalog,
    agent_ids: Sequence[str],
) -> tuple[SetupState, tuple[str, ...]]:
    """Apply `rapid setup set <key> <value>` to the state. Returns the new state and notes."""
    if key not in DECISION_KEYS:
        raise _fail("RAPID1413", f"Unknown setup key '{key}'. Use one of: {', '.join(DECISION_KEYS)}.")
    if value is None or not value.strip():
        raise _fail("RAPID1413", f"Missing value for 'rapid setup set {key}'.")
    value = value.strip()
    notes: list[str] = []

    if key == "stack":
        stack_id = _identifier(value, "stack")
        if stack_id == CUSTOM_STACK_ID:
            raise _fail(
                "RAPID1413",
                "The 'custom' stack comes from your own file: use 'rapid setup stack --custom --file -'.",
            )
        if stack_id in catalog.stacks:
            source = "generic" if stack_id == GENERIC_STACK_ID else "catalog"
        elif stack_id in catalog.sidecarless_stacks:
            source = "custom"
        else:
            known = sorted({*catalog.stacks, *catalog.sidecarless_stacks})
            raise _fail("RAPID1413", f"Unknown stack '{stack_id}'. Known stacks: {', '.join(known)}.")
        topology = state.topology
        if topology is not None and topology not in allowed_topologies(catalog, stack_id):
            notes.append(
                f"Topology '{topology}' does not fit stack '{stack_id}'; it is undecided again."
            )
            topology = None
        return replace(state, stack=StackChoice(stack_id, source), topology=topology, finished=False), tuple(notes)

    if key == "topology":
        topology_id = _identifier(value, "topology")
        if topology_id not in catalog.topology_ids:
            raise _fail(
                "RAPID1413",
                f"Unknown topology '{topology_id}'. Known topologies: {', '.join(catalog.topology_ids)}.",
            )
        if state.stack is not None and topology_id not in allowed_topologies(catalog, state.stack.id):
            raise _fail(
                "RAPID1402",
                f"Stack '{state.stack.id}' and topology '{topology_id}' are incompatible. "
                f"Compatible topologies: {', '.join(allowed_topologies(catalog, state.stack.id))}.",
            )
        return replace(state, topology=topology_id, finished=False), ()

    if key == "archetype":
        archetype = value.lower()
        if archetype not in ARCHETYPES:
            raise _fail("RAPID1413", f"Unknown archetype '{value}'. Use one of: {', '.join(ARCHETYPES)}.")
        return replace(state, archetype=archetype, finished=False), ()

    if key == "agents":
        agents: list[str] = []
        for part in value.split(","):
            agent = part.strip().lower()
            if not agent:
                continue
            if agent not in agent_ids:
                raise _fail("RAPID1413", f"Unknown agent '{agent}'. Use: {', '.join(agent_ids)}.")
            if agent not in agents:
                agents.append(agent)
        if not agents:
            raise _fail("RAPID1413", f"Missing agents. Use a comma-separated list of: {', '.join(agent_ids)}.")
        return replace(state, agents=tuple(agents), finished=False), ()

    # test-command
    if value.lower() == NO_TEST_COMMAND:
        return replace(state, test_command=(), finished=False), ()
    try:
        command = tuple(shlex.split(value))
    except ValueError as exc:
        raise _fail("RAPID1413", f"Invalid test command: {exc}") from exc
    if not command:
        raise _fail("RAPID1413", "Missing test command (use 'none' for a project without one).")
    return replace(state, test_command=command, finished=False), ()


def ensure_finishable(action: SetupAction) -> None:
    """RAPID1407 unless every decision is taken (the next action is `finish` or `done`)."""
    if action.kind in (SetupActionKind.FINISH, SetupActionKind.DONE):
        return
    command = " ".join(action.payload.get("command", ()))
    hint = f" Next: {command}" if command else ""
    raise _fail("RAPID1407", f"Setup cannot finish: the decision '{action.kind.value}' is still open.{hint}")


# --- custom stack ---------------------------------------------------------------------------


def write_custom_stack(
    rapid_dir: Path, state: SetupState, catalog: Catalog, text: str
) -> SetupState:
    """Store the tech-stack.md the harness wrote (it needs Runtime, Framework and Testing)."""
    body = prepare_body(text)
    if not body:
        raise _fail("RAPID1413", "The custom stack is empty.")
    missing = missing_custom_stack_sections(body)
    if missing:
        raise _fail(
            "RAPID1409",
            f"The custom tech-stack.md is missing the section(s): {', '.join(missing)} "
            "(a '## ' heading or a '- **Name:**' line for each of Runtime, Framework and Testing).",
        )
    safe_write_text(Path(rapid_dir) / "standards" / "tech-stack.md", body, encoding="utf-8", backup=True)
    topology = state.topology
    if topology is not None and topology not in allowed_topologies(catalog, CUSTOM_STACK_ID):
        topology = None
    return replace(state, stack=StackChoice(CUSTOM_STACK_ID, "custom"), topology=topology, finished=False)


# --- documents ------------------------------------------------------------------------------


def _doc_path(project_root: Path, bank: SetupDocBank) -> Path:
    try:
        return ensure_path_within_root(project_root, Path(project_root) / bank.file)
    except ValueError as exc:
        raise _fail("RAPID1413", str(exc)) from exc


def _read_existing(path: Path) -> str | None:
    try:
        return path.read_text(encoding="utf-8") if path.is_file() else None
    except (OSError, UnicodeDecodeError):
        return ""  # it exists but is not ours to read: treat it as someone's content


def _with_doc(state: SetupState, doc_id: str, doc: DocState) -> SetupState:
    return replace(state, docs={**state.docs, doc_id: doc})


def write_doc(
    project_root: Path,
    state: SetupState,
    bank: SetupDocBank,
    *,
    source: str,
    text: str,
    replace_existing: bool = False,
) -> SetupState:
    """Write `docs/<FILE>.md` with frontmatter. provided => confirmed, drafted => draft."""
    if source not in DOC_SOURCES:
        raise _fail("RAPID1413", f"Invalid source '{source}'. Use one of: {', '.join(DOC_SOURCES)}.")
    body = prepare_body(text)
    if not body:
        raise _fail("RAPID1413", f"The body of '{bank.id}' is empty.")
    if source == "drafted":
        # What a person provides is stored as is; what the agent drafts must fit the bank.
        issues = validate_doc_body(body, bank)
        if issues:
            raise SetupApplyError(
                issues[0].code,
                issues[0].message,
                extra=[f"{issue.code} {issue.message}" for issue in issues[1:]],
            )
    path = _doc_path(project_root, bank)
    existing = _read_existing(path)
    if source == "drafted" and not replace_existing and existing is not None and existing.strip():
        fields, _body = parse_doc_frontmatter(existing)
        if not (is_managed(fields, bank.id) and fields["source"] == "drafted"):
            raise _fail(
                "RAPID1405",
                f"{bank.file} already holds content from a person; a draft would replace it. "
                "Pass --replace to do it (the previous file is kept as .bak).",
            )
    status = "confirmed" if source == "provided" else "draft"
    safe_write_text(path, render_managed_doc(bank.id, source, status, body), encoding="utf-8", backup=True)
    doc = DocState(source, source == "provided", body_sha256(body))
    return _with_doc(state, bank.id, doc)


def import_legacy_business(
    project_root: Path, rapid_dir: Path, state: SetupState, bank: SetupDocBank, *, replace_existing: bool = False
) -> SetupState:
    """Import `standards/business.md` as a provided doc; the original is not touched."""
    if bank.id != "business":
        raise _fail("RAPID1413", "--from-legacy only applies to the 'business' document.")
    legacy = Path(rapid_dir) / "standards" / "business.md"
    text = _read_existing(legacy)
    if text is None or not text.strip():
        raise _fail("RAPID1413", "There is no .rapid-os/standards/business.md with content to import.")
    if not replace_existing and (Path(project_root) / bank.file).exists():
        raise _fail("RAPID1413", f"{bank.file} already exists. Pass --replace to import over it.")
    return write_doc(project_root, state, bank, source="provided", text=text, replace_existing=True)


def confirm_doc(project_root: Path, state: SetupState, bank: SetupDocBank) -> SetupState:
    """A person confirms a draft: only `status` changes, the body is not touched."""
    path = _doc_path(project_root, bank)
    existing = _read_existing(path)
    fields, _body = parse_doc_frontmatter(existing or "")
    if not is_managed(fields, bank.id):
        raise _fail("RAPID1413", f"There is no document written by rapid in {bank.file} to confirm.")
    if fields.get("status") != "confirmed":
        safe_write_text(path, with_doc_status(existing, "confirmed"), encoding="utf-8", backup=True)
    return _with_doc(state, bank.id, DocState(fields["source"], True, fields.get("sha256", "")))


def skip_doc(project_root: Path, state: SetupState, bank: SetupDocBank) -> SetupState:
    existing = _read_existing(_doc_path(project_root, bank))
    fields, _body = parse_doc_frontmatter(existing or "")
    if is_managed(fields, bank.id):
        raise _fail(
            "RAPID1413",
            f"{bank.file} is already written; rapid never deletes it. Edit it or write it again instead of skipping.",
        )
    return _with_doc(state, bank.id, DocState("skipped", False, ""))


def reopen_doc(project_root: Path, state: SetupState, bank: SetupDocBank) -> SetupState:
    """skipped => pending; a confirmed draft => draft again (the person must review it again)."""
    current = state.doc(bank.id)
    if current.status == "skipped":
        return _with_doc(state, bank.id, DocState())
    path = _doc_path(project_root, bank)
    existing = _read_existing(path)
    fields, _body = parse_doc_frontmatter(existing or "")
    if is_managed(fields, bank.id):
        if fields["source"] == "provided":
            raise _fail(
                "RAPID1413",
                f"{bank.file} was provided by a person; write it again with 'rapid setup doc {bank.id} --source provided'.",
            )
        if fields.get("status") == "confirmed":
            safe_write_text(path, with_doc_status(existing, "draft"), encoding="utf-8", backup=True)
        return _with_doc(state, bank.id, DocState("drafted", False, fields.get("sha256", "")))
    return state  # pending already: nothing to reopen


# --- application to the project -------------------------------------------------------------


def project_has_standards(rapid_dir: Path, config_file: Path) -> bool:
    """True when the project can already have agent files: standards plus agents in the config."""
    standards = Path(rapid_dir) / "standards"
    if not (standards / "tech-stack.md").is_file():
        return False
    result = inspect_project_config_file(config_file)
    tools = result.config.get("tools") if result.is_valid and Path(config_file).exists() else None
    return bool(tools)


def regenerate_agent_context(project_root: Path, rapid_dir: Path, config_file: Path) -> tuple[str, ...]:
    """Recompile the standards and rewrite the agent files for the configured tools."""
    result = inspect_project_config_file(config_file)
    warnings = ()
    if not result.is_valid:
        warnings = (f"Configuracion invalida en {config_file} ({result.status}): {result.error}",)
    full_context = compose_project_context(rapid_dir, project_root)
    generate_agent_contexts(full_context, result.config.get("tools", []), project_root)
    return warnings


def update_gitignore(project_root: Path) -> list[str]:
    """Append the session and scratch entries to an existing .gitignore. Returns what was added."""
    path = Path(project_root) / ".gitignore"
    if not path.exists():
        return []
    try:
        lines = [line.strip() for line in path.read_text(encoding="utf-8").splitlines()]
        missing = [
            entry
            for entry in GITIGNORE_ENTRIES
            if entry not in lines and entry.rstrip("/") not in lines
        ]
        if missing:
            safe_append_text(path, "\n" + "\n".join(missing) + "\n", encoding="utf-8")
        return missing
    except (OSError, UnicodeDecodeError):
        return []


def _copy_template(source: Path, target: Path, label: str) -> None:
    try:
        safe_copy_file(source, target, backup=True)
    except (OSError, ValueError) as exc:
        raise _fail("RAPID1413", f"No se pudo copiar {label}: {exc}") from exc


def apply_setup(
    project_root: Path,
    rapid_dir: Path,
    config_file: Path,
    templates_dir: Path,
    state: SetupState,
    catalog: Catalog,
    *,
    scan_model: ProjectModel | None = None,
    scanned: bool = True,
    extra_tools: Sequence[str] = (),
    only_changes: bool = False,
    regenerate: bool = True,
) -> ApplyResult:
    """Copy stack, topology, archetype and security to standards, save the config, rebuild context.

    With `only_changes`, a standard whose decision the files on disk already express is left as
    it is (`rapid setup finish` must not overwrite what the person edited). `rapid init` writes
    everything, as it always did.
    """
    from rapid_os.adapters.agents import DEFAULT_AGENT_REGISTRY

    project_root, rapid_dir, templates_dir = Path(project_root), Path(rapid_dir), Path(templates_dir)
    if state.stack is None or state.archetype is None or not state.agents:
        raise _fail("RAPID1407", "Setup cannot be applied: stack, archetype and agents must be decided.")
    standards = rapid_dir / "standards"
    standards.mkdir(parents=True, exist_ok=True)
    on_disk = (
        derive_state(project_root, rapid_dir, Path(config_file), templates_dir, catalog, {})
        if only_changes
        else None
    )
    written: list[str] = []

    def rel(path: Path) -> str:
        try:
            return path.relative_to(project_root).as_posix()
        except ValueError:
            return path.as_posix()

    # Stack
    stack = state.stack
    if on_disk is None or on_disk.stack is None or on_disk.stack.id != stack.id:
        target = standards / "tech-stack.md"
        try:
            template = resolve_child_path(templates_dir / "stacks", f"{_identifier(stack.id, 'stack')}.md", single_segment=True)
        except ValueError as exc:
            raise _fail("RAPID1413", str(exc)) from exc
        if stack.id == GENERIC_STACK_ID and not template.exists():
            model = scan_model if scan_model is not None else ProjectModel(root=project_root)
            safe_write_text(
                target, build_generic_stack(model, scanned=scanned), encoding="utf-8", backup=True, create_parents=True
            )
        elif stack.id == CUSTOM_STACK_ID:
            if not target.is_file():
                raise _fail(
                    "RAPID1413",
                    "The custom stack has no tech-stack.md: run 'rapid setup stack --custom --file -'.",
                )
        elif template.exists():
            _copy_template(template, target, f"el stack '{stack.id}'")
        else:
            raise _fail("RAPID1413", f"Template de stack no encontrado: {stack.id} ({template})")
        written.append(rel(target))

    # Topology
    topology = state.topology
    if topology is not None and (on_disk is None or on_disk.topology != topology):
        try:
            source = resolve_child_path(
                templates_dir / "topologies", f"{_identifier(topology, 'topology')}.md", single_segment=True
            )
        except ValueError as exc:
            raise _fail("RAPID1413", str(exc)) from exc
        _copy_template(source, standards / "topology.md", f"la topologia '{topology}'")
        written.append(rel(standards / "topology.md"))

    # Archetype and security
    if state.archetype not in ARCHETYPES and (on_disk is None or on_disk.archetype != state.archetype):
        raise _fail("RAPID1413", f"Arquetipo no soportado: '{state.archetype}'. Usa 'mvp' o 'corporate'.")
    if on_disk is None or on_disk.archetype != state.archetype:
        try:
            archetype_dir = resolve_child_path(templates_dir / "archetypes", state.archetype, single_segment=True)
            rules_src = resolve_child_path(archetype_dir, "coding-rules.md", single_segment=True)
            sec_src = resolve_child_path(archetype_dir, "security.md", single_segment=True)
            minimal_security = resolve_child_path(
                templates_dir / "archetypes", "default-security.md", single_segment=True
            )
        except ValueError as exc:
            raise _fail("RAPID1413", str(exc)) from exc
        if rules_src.exists():
            _copy_template(rules_src, standards / "coding-rules.md", "las reglas de codigo")
            written.append(rel(standards / "coding-rules.md"))
        if sec_src.exists():
            _copy_template(sec_src, standards / "security.md", "el estandar de seguridad")
            written.append(rel(standards / "security.md"))
        elif not (standards / "security.md").exists() and minimal_security.exists():
            # `rapid start hardening` requires a security standard: start from a minimal template.
            _copy_template(minimal_security, standards / "security.md", "el estandar de seguridad minimo")
            written.append(rel(standards / "security.md"))

    # Config
    existing = inspect_project_config_file(config_file)
    previous = dict(existing.config) if existing.is_valid and Path(config_file).exists() else {}
    data = dict(previous)
    known_agents = set(DEFAULT_AGENT_REGISTRY.ids())
    tools = list(state.agents)
    for tool in [*previous.get("tools", []), *extra_tools]:
        if isinstance(tool, str) and tool not in tools and (tool not in known_agents or tool in extra_tools):
            tools.append(tool)
    data["tools"] = tools
    if state.test_command:
        data["test_command"] = list(state.test_command)
    elif state.test_command is not None:
        data.pop("test_command", None)
    if not only_changes or data != previous or not Path(config_file).exists():
        save_project_config(data, rapid_dir, config_file)
        written.append(rel(Path(config_file)))

    warnings: tuple[str, ...] = ()
    if regenerate:
        warnings = regenerate_agent_context(project_root, rapid_dir, Path(config_file))
    return ApplyResult(tuple(written), warnings)
