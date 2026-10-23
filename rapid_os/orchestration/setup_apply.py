"""Writes of the onboarding: the decisions, the documents and the application of both to the project.

Shared by `rapid setup` and `rapid init`, so both leave the same files. Nothing here calls
`sys.exit` or prints: every expected failure is a `SetupApplyError` with a RAPID code, and the
CLI decides how to report it.

Order of authority: a document's frontmatter says whether it is confirmed; `setup.json` is
updated in the same operation and never contradicts it.
"""

from __future__ import annotations

import json
import re
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
from rapid_os.domain.services import (
    COMPOSE_FILE_NAMES,
    DEFAULT_COMPOSE_FILE,
    ENV_EXAMPLE_FILE,
    ServiceInputError,
    active_conditions,
    check_stack_compatibility,
    merge_compose,
    merge_env_example,
    parse_services,
    render_compose,
    render_env_example,
    render_tech_stack,
    services_now,
    stack_language,
)
from rapid_os.domain.security import (
    CI_WORKFLOW_PATH,
    ci_language,
    ci_languages,
    ci_workflow_path,
    effective_ai,
    has_api,
    is_ai_stack,
    render_ci_workflow,
    render_security_standard,
)
from rapid_os.domain.architecture import architecture_document, render_architecture_markdown, rules_for
from rapid_os.domain.stack_aliases import LEGACY_STACKS
from rapid_os.domain.catalog import (
    COMPONENTS,
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
    LOST_CHARACTERS_MESSAGE,
    has_lost_characters,
    parse_doc_frontmatter,
    prepare_body,
    body_sha256,
    is_managed,
    mark_story_done,
    render_managed_doc,
    validate_doc_body,
    with_doc_status,
)
from rapid_os.orchestration.git import run_git
from rapid_os.orchestration.session import git_trust_command, git_work_tree_state
from rapid_os.domain.setup import (
    ARCHETYPES,
    STACK_COMPONENTS,
    DocState,
    SetupAction,
    SetupActionKind,
    SetupState,
    StackChoice,
)

DECISION_KEYS = ("stack", "topology", "archetype", "ai", "services", "agents", "test-command")
NO_TEST_COMMAND = "none"
AI_ANSWERS = {"yes": True, "y": True, "si": True, "sí": True, "true": True, "no": False, "n": False, "false": False}
SECURITY_TEMPLATE = ("security", "baseline.md")
BASELINE_TITLE = "# SEGURIDAD: BASE OBLIGATORIA"
MINIMAL_SECURITY_TITLE = "SECURITY STANDARD (MINIMAL)"
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


@dataclass(frozen=True)
class StackResolution:
    """What `rapid setup set stack <id> [--component c]` fills: the stack of each component it covers."""

    stacks: dict[str, StackChoice]
    ai: bool = False
    notes: tuple[str, ...] = ()


def resolve_stack(
    stack_id: str, catalog: Catalog, *, component: str | None = None, topology: str | None = None
) -> StackResolution:
    """The components a stack id fills. A stack id of before the component catalog (`python-api`,
    `web-modern`...) maps to the stacks that replace it; `--component` restricts a stack that covers
    several components to one of them."""
    # A Markdown template without a sidecar is a stack of its own, even when its name is an old id.
    legacy = LEGACY_STACKS.get(stack_id) if stack_id not in catalog.sidecarless_stacks else None
    if legacy is not None:
        stacks = {
            c: StackChoice(sid, "catalog", legacy.profile if c == "frontend" else None)
            for c, sid in legacy.stacks.items()
        }
        covers = tuple(stacks)
        notes = (f"'{stack_id}' is a stack id of before the component catalog: it maps to {', '.join(f'{c} {s.id}' for c, s in stacks.items())}.",)
    elif stack_id == CUSTOM_STACK_ID:
        raise _fail(
            "RAPID1413",
            "The 'custom' stack comes from your own file: use 'rapid setup stack --custom --file -'.",
        )
    else:
        entry = catalog.stacks.get(stack_id)
        if entry is not None:
            source = "generic" if stack_id == GENERIC_STACK_ID else "catalog"
            covers = entry.covers or ((entry.component,) if entry.component else COMPONENTS)
        elif stack_id in catalog.sidecarless_stacks:
            source, covers = "custom", COMPONENTS
        else:
            known = sorted({*catalog.stacks, *catalog.sidecarless_stacks})
            raise _fail("RAPID1413", f"Unknown stack '{stack_id}'. Known stacks: {', '.join(known)}.")
        stacks = {c: StackChoice(stack_id, source) for c in covers}
        notes = ()
    if component is not None:
        if component not in COMPONENTS:
            raise _fail("RAPID1413", f"Unknown component '{component}'. Use one of: {', '.join(COMPONENTS)}.")
        if component not in stacks:
            raise _fail(
                "RAPID1413",
                f"Stack '{stack_id}' cannot fill the component '{component}'; it fills: {', '.join(covers)}.",
            )
        return StackResolution({component: stacks[component]}, bool(legacy and legacy.ai), notes)
    wanted = catalog.components_of(topology)
    fills = tuple(c for c in covers if c in wanted) or tuple(covers)
    return StackResolution({c: stacks[c] for c in fills}, bool(legacy and legacy.ai), notes)


def set_decision(
    state: SetupState,
    key: str,
    value: str | None,
    catalog: Catalog,
    agent_ids: Sequence[str],
    component: str | None = None,
) -> tuple[SetupState, tuple[str, ...]]:
    """Apply `rapid setup set <key> <value>` to the state. Returns the new state and notes."""
    if key not in DECISION_KEYS:
        raise _fail("RAPID1413", f"Unknown setup key '{key}'. Use one of: {', '.join(DECISION_KEYS)}.")
    if value is None or not value.strip():
        raise _fail("RAPID1413", f"Missing value for 'rapid setup set {key}'.")
    value = value.strip()
    notes: list[str] = []

    if component is not None and key != "stack":
        raise _fail("RAPID1413", "--component only goes with 'rapid setup set stack <id>'.")

    if key == "stack":
        stack_id = _identifier(value, "stack")
        resolution = resolve_stack(stack_id, catalog, component=component, topology=state.topology)
        stacks = {**state.stacks, **resolution.stacks}
        notes.extend(resolution.notes)
        topology = state.topology
        ids = {choice.id for choice in stacks.values()}
        if topology is not None and not all(topology in allowed_topologies(catalog, sid) for sid in ids):
            notes.append(f"Topology '{topology}' does not fit stack '{stack_id}'; it is undecided again.")
            topology = None
        updated = replace(
            state,
            stacks=stacks,
            topology=topology,
            ai=True if resolution.ai else state.ai,
            finished=False,
        )
        services = state.services
        if services:
            try:
                check_stack_compatibility(services, updated.stack.id if updated.stack else None, catalog)
            except ServiceInputError:
                notes.append(f"The services do not fit stack '{stack_id}'; they are undecided again.")
                services = None
        return replace(updated, services=services), tuple(notes)

    if key == "topology":
        topology_id = _identifier(value, "topology")
        if topology_id not in catalog.topology_ids:
            raise _fail(
                "RAPID1413",
                f"Unknown topology '{topology_id}'. Known topologies: {', '.join(catalog.topology_ids)}.",
            )
        for decided in state.stack_ids:
            if topology_id not in allowed_topologies(catalog, decided):
                raise _fail(
                    "RAPID1402",
                    f"Stack '{decided}' and topology '{topology_id}' are incompatible. "
                    f"Compatible topologies: {', '.join(allowed_topologies(catalog, decided))}.",
                )
        return replace(state, topology=topology_id, finished=False), ()

    if key == "archetype":
        archetype = value.lower()
        if archetype not in ARCHETYPES:
            raise _fail("RAPID1413", f"Unknown archetype '{value}'. Use one of: {', '.join(ARCHETYPES)}.")
        return replace(state, archetype=archetype, finished=False), ()

    if key == "services":
        try:
            choices = parse_services(value, catalog)
            check_stack_compatibility(choices, state.stack.id if state.stack else None, catalog)
        except ServiceInputError as exc:
            raise _fail(exc.code, exc.message) from exc
        return replace(state, services=choices, finished=False), ()

    if key == "ai":
        answer = value.strip().lower()
        if answer not in AI_ANSWERS:
            raise _fail("RAPID1413", f"Invalid value '{value}' for 'ai': use yes or no.")
        uses_ai = AI_ANSWERS[answer]
        if not uses_ai and is_ai_stack(state.stack_ids):
            notes.append(
                f"El stack '{', '.join(state.stack_ids)}' es de IA: el estándar de seguridad incluye siempre la sección de IA."
            )
        return replace(state, ai=uses_ai, finished=False), tuple(notes)

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


REVIEW_NOTHING_LEFT = "Todos los borradores quedaron confirmados; no hay nada más que revisar"


def has_unconfirmed_drafts(state: SetupState) -> bool:
    return any(doc.status == "drafted" and not doc.confirmed for doc in state.docs.values())


def mark_drafts_reviewed(state: SetupState) -> SetupState:
    """`rapid setup review --done`: the person went through the drafts. Nothing is confirmed here:
    what they did not confirm one by one stays a draft.

    With no unconfirmed draft left (the person confirmed them all) there is nothing to record:
    the state is returned as it is, so the command succeeds without writing anything."""
    if not has_unconfirmed_drafts(state):
        return state
    return replace(state, drafts_reviewed=True)


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
    custom = StackChoice(CUSTOM_STACK_ID, "custom")
    return replace(
        state, stacks={c: custom for c in STACK_COMPONENTS}, topology=topology, finished=False
    )


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
        if has_lost_characters(body):
            raise _fail("RAPID1415", LOST_CHARACTERS_MESSAGE)
        issues = validate_doc_body(body, bank, active_conditions(state.services))
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
    new_state = _with_doc(state, bank.id, doc)
    # A new draft is something the person has not seen yet: the review is due again.
    return replace(new_state, drafts_reviewed=False) if source == "drafted" else new_state


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
        reopened = _with_doc(state, bank.id, DocState("drafted", False, fields.get("sha256", "")))
        return replace(reopened, drafts_reviewed=False)
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


@dataclass(frozen=True)
class GitSetup:
    """What `ensure_git_repository` did: a note when it created the repository, a warning when
    git is missing, neither when the folder already is inside one."""

    note: str | None = None
    warning: str | None = None


DEFAULT_GIT_BRANCH = "main"
GIT_MISSING_WARNING = "Instala git: los runs de Rapid OS lo necesitan para observar los cambios"


def ensure_git_repository(project_root: Path) -> GitSetup:
    """Give the project a git repository, because Rapid OS observes a run's changes with git.

    Nothing happens inside an existing work tree (a parent repository counts: repositories are
    never nested). Otherwise `git init`, then `symbolic-ref HEAD` to the branch before the first
    commit (it works on every git version, unlike `git init -b`). It makes no commit. Without
    git installed it only warns: the onboarding does not fail.
    """
    root = Path(project_root)
    state = git_work_tree_state(root)
    if state == "inside":
        return GitSetup()
    if state == "missing":
        return GitSetup(warning=GIT_MISSING_WARNING)
    if state == "untrusted":
        # There is a repository git does not trust: `git init` would not fix it.
        return GitSetup(
            warning=f"git no confía en esta carpeta (dubious ownership). Ejecuta: {git_trust_command(root)}"
        )
    # Always `main`, whatever `init.defaultBranch` says: Git for Windows and the harness sandbox user
    # may carry `master` in a config the person never chose, and the runs' branches start from `main`.
    branch = DEFAULT_GIT_BRANCH
    try:
        # `-c` keeps `git init` from reading any `init.defaultBranch` of the machine.
        init = run_git(root, "-c", f"init.defaultBranch={branch}", "init", "-q")
        if init.returncode != 0:
            detail = init.stderr.strip() or "git init falló"
            return GitSetup(warning=f"No se pudo crear el repositorio git ({detail})")
        head = run_git(root, "symbolic-ref", "HEAD", f"refs/heads/{branch}")
    except OSError:
        return GitSetup(warning=GIT_MISSING_WARNING)
    if head.returncode != 0:
        # The repository exists: say what was created and what failed, not "could not create".
        detail = head.stderr.strip() or "git symbolic-ref HEAD falló"
        return GitSetup(
            warning=(
                f"Se creó el repositorio git (git init), pero no se pudo fijar la rama {branch} ({detail}); "
                "HEAD quedó en la rama que eligió git"
            )
        )
    return GitSetup(
        note=f"Repositorio git creado en la rama {branch} (Rapid OS observa los cambios con git)"
    )


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


ARCHITECTURE_TEMPLATE = "modular-monolith.md"
_STACK_SECTION_HEADING = "## Estructura por stack"


def is_rapid_security(path: Path) -> bool:
    """True when `security.md` is one Rapid OS generated: the baseline or the minimal standard."""
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return False
    return BASELINE_TITLE in text or MINIMAL_SECURITY_TITLE in text


def services_stack_entry(state: SetupState, catalog: Catalog):
    """The catalog entry of the stack the services are judged against: the project's primary stack."""
    return catalog.entry(state.stack.id) if state.stack else None


def _services_text(text: str, stack_id: str, state: SetupState, catalog: Catalog) -> str:
    """Rewrite the database lines of a stack's `tech-stack.md` from the services decision."""
    entry = catalog.entry(stack_id)
    if state.services is None or not catalog.services or (entry is not None and entry.service_roles == ()):
        return text  # undecided (`rapid init`), no catalog, or a static site: the template stays as it is
    return render_tech_stack(text, stack_language(catalog, stack_id), state.services, catalog, entry)


def render_tech_stack_file(
    state: SetupState,
    catalog: Catalog,
    templates_dir: Path,
    *,
    model: ProjectModel,
    scanned: bool,
) -> str | None:
    """The whole `tech-stack.md` of the decided stacks (one block each, the backend's first), or None
    when a stack the person wrote is among them (its file is the person's)."""
    blocks: list[str] = []
    primary = state.stack.id if state.stack else None
    for stack_id in state.stack_ids:
        choice = next(c for comp in ("backend", "frontend", "baas", "docs") if (c := state.stacks.get(comp)) and c.id == stack_id)
        if stack_id == CUSTOM_STACK_ID:
            return None
        entry = catalog.stacks.get(stack_id)
        if stack_id == GENERIC_STACK_ID and (entry is None or not (templates_dir / "stacks" / f"{entry.template}.md").exists()):
            block = build_generic_stack(model, scanned=scanned).rstrip("\n")
        elif entry is not None or stack_id in catalog.sidecarless_stacks:
            try:
                template = resolve_child_path(
                    templates_dir / "stacks", f"{entry.template if entry is not None else _identifier(stack_id, 'stack')}.md"
                )
            except ValueError as exc:
                raise _fail("RAPID1413", str(exc)) from exc
            if not template.is_file():
                raise _fail("RAPID1413", f"Template de stack no encontrado: {stack_id} ({template})")
            block = template.read_text(encoding="utf-8").rstrip("\n")
            fragments = []
            if state.ai:
                fragments.append(template.with_name(f"{template.stem}.ai.md"))
            if choice.profile:
                fragments.append(template.with_name(f"{template.stem}.{choice.profile}.md"))
            for fragment in fragments:
                if fragment.is_file():
                    block += "\n" + fragment.read_text(encoding="utf-8").strip("\n")
            if stack_id == primary:
                block = _services_text(block, stack_id, state, catalog)
        else:
            raise _fail("RAPID1413", f"Template de stack no encontrado: {stack_id}")
        components = [c for c in ("backend", "frontend", "baas", "docs") if state.stacks.get(c) and state.stacks[c].id == stack_id]
        marker = " ".join(f"{c}={stack_id}" for c in components)
        blocks.append(f"{block}\n<!-- rapid-stack: {marker} -->")
    return "\n\n".join(blocks) + "\n"


def find_compose_file(project_root: Path) -> Path | None:
    for name in COMPOSE_FILE_NAMES:
        if (Path(project_root) / name).is_file():
            return Path(project_root) / name
    return None


def planned_local_environment(
    project_root: Path, state: SetupState, catalog: Catalog, scan_model: ProjectModel | None = None
) -> list[str]:
    """The files `setup finish` is going to write for the `@now` services (empty repository only)."""
    from rapid_os.domain.scanner import is_empty_repository

    if not services_now(state.services) or find_compose_file(project_root) is not None:
        return []
    if not is_empty_repository(Path(project_root)):
        return []
    return [DEFAULT_COMPOSE_FILE, ENV_EXAMPLE_FILE]


def _ensure_env_ignored(project_root: Path) -> None:
    path = Path(project_root) / ".gitignore"
    try:
        lines = path.read_text(encoding="utf-8").splitlines() if path.is_file() else []
    except (OSError, UnicodeDecodeError):
        return
    if ".env" in (line.strip() for line in lines):
        return
    body = "\n".join(lines).rstrip("\n")
    safe_write_text(path, (body + "\n" if body else "") + ".env\n", encoding="utf-8", backup=False)


def write_local_environment(
    project_root: Path, state: SetupState, catalog: Catalog, scan_model: ProjectModel | None = None
) -> tuple[list[str], list[str]]:
    """`compose.yaml`, `.env.example` and `.env` in `.gitignore` for the `@now` services.

    Rapid OS writes them, not the agent. In an empty repository they are created; where a compose
    file already exists only the missing `@now` services are added (and the missing variables), and
    nothing that is there changes: a compose file it cannot read as YAML is left alone with a warning.
    Returns the files written (relative paths) and the warnings."""
    root = Path(project_root)
    choices = state.services or ()
    if not services_now(choices) or not catalog.services:
        return [], []
    languages = scan_model.values("language") if scan_model is not None else ()
    language = stack_language(catalog, state.stack.id if state.stack else None, ci_language_or_default(state, languages))
    stack = services_stack_entry(state, catalog)
    written: list[str] = []
    warnings: list[str] = []
    compose = find_compose_file(root)
    if compose is None:
        if not planned_local_environment(root, state, catalog, scan_model):
            return [], []
        safe_write_text(root / DEFAULT_COMPOSE_FILE, render_compose(choices, catalog), encoding="utf-8", backup=False)
        written.append(DEFAULT_COMPOSE_FILE)
    else:
        try:
            existing = compose.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            return [], [f"No se pudo leer {compose.name}: Rapid OS no lo toca."]
        merged = merge_compose(existing, choices, catalog)
        if merged.warning:
            return [], [f"{compose.name}: {merged.warning}"]
        if not merged.added:
            return [], []
        safe_write_text(compose, merged.text, encoding="utf-8", backup=True)
        written.append(compose.name)
    env_path = root / ENV_EXAMPLE_FILE
    if env_path.is_file():
        try:
            current = env_path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            current = None
        if current is not None:
            updated = merge_env_example(current, choices, catalog, language, stack)
            if updated != current:
                safe_write_text(env_path, updated, encoding="utf-8", backup=True)
                written.append(ENV_EXAMPLE_FILE)
    else:
        safe_write_text(env_path, render_env_example(choices, catalog, language, stack), encoding="utf-8", backup=False)
        written.append(ENV_EXAMPLE_FILE)
    _ensure_env_ignored(root)
    return written, warnings


def ci_language_or_default(state: SetupState, languages) -> str:
    """The language of the connection URLs for a stack the catalog does not know (generic, custom)."""
    return ci_language(state.stack.id if state.stack else None, languages) or "typescript"


def _write_coding_rules(templates_dir: Path, standards: Path, archetype: str) -> list[Path]:
    """Copy the archetype's coding rules (with backup). Returns the files written."""
    try:
        archetype_dir = resolve_child_path(templates_dir / "archetypes", archetype, single_segment=True)
        rules_src = resolve_child_path(archetype_dir, "coding-rules.md", single_segment=True)
    except ValueError as exc:
        raise _fail("RAPID1413", str(exc)) from exc
    if not rules_src.exists():
        return []
    _copy_template(rules_src, standards / "coding-rules.md", "las reglas de codigo")
    return [standards / "coding-rules.md"]


def _write_security(
    templates_dir: Path, standards: Path, archetype: str, stack_id: "str | Sequence[str]", uses_ai: bool
) -> tuple[Path | None, str | None]:
    """`standards/security.md`: the security baseline at the archetype's level (with backup).

    Returns the file written and a warning when the baseline template is missing and the minimal
    standard (which `rapid start hardening` requires) stands in."""
    target = standards / "security.md"
    try:
        baseline = resolve_child_path(templates_dir / SECURITY_TEMPLATE[0], SECURITY_TEMPLATE[1], single_segment=True)
        minimal = resolve_child_path(templates_dir / "archetypes", "default-security.md", single_segment=True)
    except ValueError as exc:
        raise _fail("RAPID1413", str(exc)) from exc
    if baseline.is_file():
        try:
            body = render_security_standard(
                baseline.read_text(encoding="utf-8"), archetype=archetype, stack_id=stack_id, ai=uses_ai
            )
        except (OSError, UnicodeDecodeError) as exc:
            raise _fail("RAPID1413", f"No se pudo leer la base de seguridad: {exc}") from exc
        safe_write_text(target, body, encoding="utf-8", backup=True, create_parents=True)
        return target, None
    if not target.exists() and minimal.is_file():
        _copy_template(minimal, target, "el estandar de seguridad minimo")
        return target, (
            f"No se encontró templates/{SECURITY_TEMPLATE[0]}/{SECURITY_TEMPLATE[1]}: "
            "se usó el estándar de seguridad mínimo."
        )
    return None, None


def refresh_archetype_files(
    project_root: Path, rapid_dir: Path, config_file: Path, templates_dir: Path, state: SetupState
) -> tuple[str, ...]:
    """`rapid setup set archetype <x> --refresh`: regenerate `security.md` and `coding-rules.md`
    from the current templates (the previous copies are kept as backups) and the agent files.

    This is how a project initialized before the security baseline gets it."""
    if state.stack is None or state.archetype not in ARCHETYPES:
        raise _fail("RAPID1413", "--refresh needs the stack and the archetype decided.")
    standards = Path(rapid_dir) / "standards"
    standards.mkdir(parents=True, exist_ok=True)
    _write_coding_rules(Path(templates_dir), standards, state.archetype)
    _path, warning = _write_security(
        Path(templates_dir), standards, state.archetype, state.stack_ids, effective_ai(state.stack_ids, state.ai)
    )
    warnings = (warning,) if warning else ()
    if project_has_standards(Path(rapid_dir), Path(config_file)):
        warnings = (*warnings, *regenerate_agent_context(Path(project_root), Path(rapid_dir), Path(config_file)))
    return warnings


def planned_ci_workflows(
    project_root: Path, stack_ids: "str | Sequence[str] | None", scan_model: ProjectModel | None = None
) -> list[tuple[str, str]]:
    """`(path, language)` of the CI workflows `setup finish` would write: one per language of the
    project (the backend's first), only in an empty repository and never over one that exists."""
    from rapid_os.domain.scanner import is_empty_repository

    root = Path(project_root)
    if not is_empty_repository(root):
        return []
    ids = [stack_ids] if isinstance(stack_ids, str) else list(stack_ids or ())
    languages = scan_model.values("language") if scan_model is not None else ()
    planned = []
    for index, language in enumerate(ci_languages(ids, languages)):
        path = ci_workflow_path(language, index)
        if not (root / path).exists():
            planned.append((path, language))
    return planned


def planned_ci_workflow(project_root: Path, stack_id: "str | Sequence[str] | None", scan_model: ProjectModel | None = None) -> str | None:
    """The first CI workflow `setup finish` would write, or None."""
    planned = planned_ci_workflows(project_root, stack_id, scan_model)
    return planned[0][0] if planned else None


def _write_ci_workflows(
    project_root: Path, templates_dir: Path, archetype: str, stack_ids: Sequence[str], scan_model: ProjectModel | None
) -> list[str]:
    """Write `.github/workflows/rapid-security.yml` (and one more per extra language) from
    `templates/ci/<language>-security.yml`.

    Rapid OS writes them, not the agent. Only in an empty repository and never over a workflow that
    already exists. Returns the paths relative to the project."""
    written: list[str] = []
    for path, language in planned_ci_workflows(project_root, stack_ids, scan_model):
        try:
            source = resolve_child_path(templates_dir / "ci", f"{language}-security.yml", single_segment=True)
        except ValueError as exc:
            raise _fail("RAPID1413", str(exc)) from exc
        if not source.is_file():
            continue
        try:
            body = render_ci_workflow(
                source.read_text(encoding="utf-8"), archetype=archetype, primary=path == CI_WORKFLOW_PATH
            )
        except (OSError, UnicodeDecodeError) as exc:
            raise _fail("RAPID1413", f"No se pudo leer el workflow de seguridad: {exc}") from exc
        safe_write_text(
            Path(project_root) / path, body, encoding="utf-8", backup=False, create_parents=True, allow_overwrite=False
        )
        written.append(path)
    return written


def render_architecture_standard(text: str, stack_id: str) -> str:
    """The modular-monolith standard for the stack ids of a project (accepts the ids of before
    the component catalog): the language-neutral rule plus the structure of each stack."""
    from rapid_os.domain.architecture import stacks_of_legacy

    return render_architecture_markdown(text, rules_for(stacks_of_legacy(stack_id)))


def _stack_key(state: SetupState) -> tuple:
    """What identifies the stack decision on disk: each component's stack id and profile."""
    return tuple(
        (c, state.stacks[c].id, state.stacks[c].profile) for c in STACK_COMPONENTS if c in state.stacks
    )


def _stacks_differ(on_disk: SetupState, state: SetupState, tech_stack_file: Path) -> bool:
    """Whether `tech-stack.md` must be rewritten for the decided stacks.

    A file Rapid OS wrote carries its markers and says every component it covers. A file from before
    the component catalog, or one the person edited, only says what it says: a component it does not
    mention does not make it stale (the person's file is not rewritten to add it)."""
    try:
        marked = "rapid-stack:" in tech_stack_file.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        marked = True
    if marked:
        return _stack_key(on_disk) != _stack_key(state)
    return any(
        (choice.id, choice.profile)
        != ((state.stacks[c].id, state.stacks[c].profile) if c in state.stacks else None)
        for c, choice in on_disk.stacks.items()
    )


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
    services_changed: bool = False,
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
    target = standards / "tech-stack.md"
    stacks_changed = on_disk is None or _stacks_differ(on_disk, state, target)
    if stacks_changed or services_changed:
        if CUSTOM_STACK_ID in state.stack_ids and not target.is_file():
            raise _fail(
                "RAPID1413",
                "The custom stack has no tech-stack.md: run 'rapid setup stack --custom --file -'.",
            )
        model = scan_model if scan_model is not None else ProjectModel(root=project_root)
        text = render_tech_stack_file(state, catalog, templates_dir, model=model, scanned=scanned)
        if text is not None:
            if target.is_file() and text == target.read_text(encoding="utf-8"):
                pass  # nothing to rewrite
            else:
                safe_write_text(target, text, encoding="utf-8", backup=True, create_parents=True)
                written.append(rel(target))
        elif stacks_changed:
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
    uses_ai = effective_ai(state.stack_ids, state.ai)
    archetype_changed = on_disk is None or on_disk.archetype != state.archetype
    if archetype_changed:
        written.extend(rel(path) for path in _write_coding_rules(templates_dir, standards, state.archetype))
    # The security baseline follows the archetype (level), the stack (API) and the AI answer; a
    # standard the person edited is only rewritten when one of those decisions changed.
    security_file = standards / "security.md"
    decision_changed = (
        archetype_changed
        or on_disk.ai != uses_ai
        or on_disk.stack is None
        or has_api(on_disk.stack_ids) != has_api(state.stack_ids)
    )
    # Only a standard Rapid OS wrote follows its decisions: a security.md the person wrote is theirs
    # (`rapid setup set archetype <id> --refresh` replaces it on request, keeping a backup).
    security_changed = not security_file.exists() or (decision_changed and is_rapid_security(security_file))
    security_warning: str | None = None
    if security_changed:
        security_path, security_warning = _write_security(templates_dir, standards, state.archetype, state.stack_ids, uses_ai)
        if security_path is not None:
            written.append(rel(security_path))

    # Architecture: a backend starts as a modular monolith. The text goes to the agent as a
    # standard and the machine form is what `rapid arch check` and `gate.architecture` read.
    wanted = state.stacks
    architecture = architecture_document({c: choice.id for c, choice in wanted.items()})
    architecture_warning: str | None = None
    if architecture:
        arch_md, arch_json = standards / "architecture.md", standards / "architecture.json"
        template = None
        if stacks_changed or not arch_md.exists() or not arch_json.exists():
            try:
                template = resolve_child_path(templates_dir / "architecture", ARCHITECTURE_TEMPLATE, single_segment=True)
            except ValueError as exc:
                raise _fail("RAPID1413", f"No se pudo leer la regla de arquitectura: {exc}") from exc
            if not template.is_file():
                # A templates folder without the rule (a trimmed copy): the project goes without it.
                architecture_warning = (
                    f"No se encontró templates/architecture/{ARCHITECTURE_TEMPLATE}: "
                    "el proyecto queda sin regla de arquitectura."
                )
                template = None
        if template is not None:
            try:
                body = template.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError) as exc:
                raise _fail("RAPID1413", f"No se pudo leer la regla de arquitectura: {exc}") from exc
            safe_write_text(
                arch_md,
                render_architecture_markdown(body, rules_for({c: choice.id for c, choice in wanted.items()})),
                encoding="utf-8",
                backup=True,
                create_parents=True,
            )
            safe_write_text(
                arch_json,
                json.dumps(architecture, indent=2, ensure_ascii=False) + "\n",
                encoding="utf-8",
                backup=True,
                create_parents=True,
            )
            written.extend([rel(arch_md), rel(arch_json)])

    # Local services: the containers to test the data model from the first feature.
    env_written, env_warnings = write_local_environment(project_root, state, catalog, scan_model)
    written.extend(env_written)

    # CI: the security scans run from the first PR, written by Rapid OS in a new repository.
    written.extend(_write_ci_workflows(project_root, templates_dir, state.archetype, state.stack_ids, scan_model))

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

    warnings = tuple(w for w in (architecture_warning, security_warning, *env_warnings) if w)
    if regenerate:
        warnings = (*warnings, *regenerate_agent_context(project_root, rapid_dir, Path(config_file)))
    return ApplyResult(tuple(written), warnings)


# --- ticking a story of the brief ----------------------------------------------------------


@dataclass(frozen=True)
class StoryTick:
    """What `tick_story` did: `marked`, `already_done`, `not_found` or `unmanaged`."""

    outcome: str
    story_id: str
    file: str
    warnings: tuple[str, ...] = ()


def tick_story(
    project_root: Path, rapid_dir: Path, config_file: Path, bank: SetupDocBank, story_id: str
) -> StoryTick:
    """Tick `- [ ] <ID>:` in the brief once a run that cites the story passed.

    The one line changes and nothing else: `source` and `status` stay (a draft stays a draft),
    the frontmatter `sha256` follows the body, the previous file goes to `.rapid-os/backups`,
    and the agent files are rebuilt. A brief without `rapid-doc` frontmatter is not touched.
    """
    from rapid_os.adapters.agents.base import AGENT_BACKUP_DIR, AGENT_BACKUPS_KEPT
    from rapid_os.adapters.setup_store import load_setup_file, write_setup

    path = _doc_path(project_root, bank)
    existing = _read_existing(path)
    fields, _body = parse_doc_frontmatter(existing or "")
    if not existing or not is_managed(fields, bank.id):
        return StoryTick("unmanaged", story_id, bank.file)
    new_text, outcome, written_id = mark_story_done(existing, bank, story_id)
    if outcome != "marked":
        return StoryTick(outcome, written_id, bank.file)
    safe_write_text(
        path,
        new_text,
        encoding="utf-8",
        backup=True,
        backup_dir=Path(project_root) / AGENT_BACKUP_DIR,
        keep_backups=AGENT_BACKUPS_KEPT,
    )
    # setup.json keeps the digest of each document; a derived state reads it from the file.
    new_fields, _ = parse_doc_frontmatter(new_text)
    persisted = load_setup_file(rapid_dir)
    if persisted is not None and bank.id in persisted.docs:
        current = persisted.doc(bank.id)
        write_setup(
            rapid_dir,
            _with_doc(persisted, bank.id, replace(current, sha256=new_fields.get("sha256", ""))),
        )
    warnings: tuple[str, ...] = ()
    if project_has_standards(rapid_dir, config_file):
        warnings = regenerate_agent_context(project_root, rapid_dir, config_file)
    return StoryTick("marked", written_id, bank.file, warnings)
