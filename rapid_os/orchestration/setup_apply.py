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
from rapid_os.domain.security import (
    CI_WORKFLOW_PATH,
    ci_language,
    effective_ai,
    has_api,
    is_ai_stack,
    render_ci_workflow,
    render_security_standard,
)
from rapid_os.domain.architecture import default_config as default_architecture_config
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
from rapid_os.domain.setup import ARCHETYPES, DocState, SetupAction, SetupActionKind, SetupState, StackChoice

DECISION_KEYS = ("stack", "topology", "archetype", "ai", "agents", "test-command")
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

    if key == "ai":
        answer = value.strip().lower()
        if answer not in AI_ANSWERS:
            raise _fail("RAPID1413", f"Invalid value '{value}' for 'ai': use yes or no.")
        uses_ai = AI_ANSWERS[answer]
        if not uses_ai and state.stack is not None and is_ai_stack(state.stack.id):
            notes.append(
                f"El stack '{state.stack.id}' es de IA: el estándar de seguridad incluye siempre la sección de IA."
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
        if has_lost_characters(body):
            raise _fail("RAPID1415", LOST_CHARACTERS_MESSAGE)
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
    templates_dir: Path, standards: Path, archetype: str, stack_id: str, uses_ai: bool
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
        Path(templates_dir), standards, state.archetype, state.stack.id, effective_ai(state.stack.id, state.ai)
    )
    warnings = (warning,) if warning else ()
    if project_has_standards(Path(rapid_dir), Path(config_file)):
        warnings = (*warnings, *regenerate_agent_context(Path(project_root), Path(rapid_dir), Path(config_file)))
    return warnings


def planned_ci_workflow(project_root: Path, stack_id: str | None, scan_model: ProjectModel | None = None) -> str | None:
    """The CI workflow `setup finish` would write, or None. Only in an empty repository without one."""
    from rapid_os.domain.scanner import is_empty_repository

    root = Path(project_root)
    if (root / CI_WORKFLOW_PATH).exists() or not is_empty_repository(root):
        return None
    languages = scan_model.values("language") if scan_model is not None else ()
    return CI_WORKFLOW_PATH if ci_language(stack_id, languages) else None


def _write_ci_workflow(
    project_root: Path, templates_dir: Path, archetype: str, stack_id: str, scan_model: ProjectModel | None
) -> str | None:
    """Write `.github/workflows/rapid-security.yml` from `templates/ci/<language>-security.yml`.

    Rapid OS writes it, not the agent. Only in an empty repository and never over a workflow that
    already exists. Returns its path relative to the project, or None."""
    if planned_ci_workflow(project_root, stack_id, scan_model) is None:
        return None
    language = ci_language(stack_id, scan_model.values("language") if scan_model is not None else ())
    try:
        source = resolve_child_path(templates_dir / "ci", f"{language}-security.yml", single_segment=True)
    except ValueError as exc:
        raise _fail("RAPID1413", str(exc)) from exc
    if not source.is_file():
        return None
    try:
        body = render_ci_workflow(source.read_text(encoding="utf-8"), archetype=archetype)
    except (OSError, UnicodeDecodeError) as exc:
        raise _fail("RAPID1413", f"No se pudo leer el workflow de seguridad: {exc}") from exc
    safe_write_text(
        Path(project_root) / CI_WORKFLOW_PATH, body, encoding="utf-8", backup=False, create_parents=True, allow_overwrite=False
    )
    return CI_WORKFLOW_PATH


def render_architecture_standard(text: str, stack_id: str) -> str:
    """The modular-monolith standard for one stack: the rule plus only the tree of that stack.

    The template has a `### ...` subsection per group of stacks under `## Estructura por stack`
    (the heading names the stacks it is for); the others are dropped.
    """
    lines = text.splitlines(keepends=True)
    kept: list[str] = []
    in_stacks = False
    keep_subsection = True
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("## "):
            in_stacks = stripped == _STACK_SECTION_HEADING
            keep_subsection = True
        elif in_stacks and stripped.startswith("### "):
            keep_subsection = stack_id in re.split(r"[^a-z0-9-]+", stripped[4:].lower())
            if not keep_subsection:
                continue
        elif in_stacks and not keep_subsection:
            continue
        kept.append(line)
    return "".join(kept)


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
    uses_ai = effective_ai(stack.id, state.ai)
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
        or has_api(on_disk.stack.id) != has_api(stack.id)
    )
    # Only a standard Rapid OS wrote follows its decisions: a security.md the person wrote is theirs
    # (`rapid setup set archetype <id> --refresh` replaces it on request, keeping a backup).
    security_changed = not security_file.exists() or (decision_changed and is_rapid_security(security_file))
    security_warning: str | None = None
    if security_changed:
        security_path, security_warning = _write_security(templates_dir, standards, state.archetype, stack.id, uses_ai)
        if security_path is not None:
            written.append(rel(security_path))

    # Architecture: a backend starts as a modular monolith. The text goes to the agent as a
    # standard and the machine form is what `rapid arch check` and `gate.architecture` read.
    architecture = default_architecture_config(stack.id)
    architecture_warning: str | None = None
    if architecture:
        stack_changed = on_disk is None or on_disk.stack is None or on_disk.stack.id != stack.id
        arch_md, arch_json = standards / "architecture.md", standards / "architecture.json"
        template = None
        if stack_changed or not arch_md.exists() or not arch_json.exists():
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
                arch_md, render_architecture_standard(body, stack.id), encoding="utf-8", backup=True, create_parents=True
            )
            safe_write_text(
                arch_json,
                json.dumps(architecture, indent=2, ensure_ascii=False) + "\n",
                encoding="utf-8",
                backup=True,
                create_parents=True,
            )
            written.extend([rel(arch_md), rel(arch_json)])

    # CI: the security scans run from the first PR, written by Rapid OS in a new repository.
    ci_workflow = _write_ci_workflow(project_root, templates_dir, state.archetype, stack.id, scan_model)
    if ci_workflow is not None:
        written.append(ci_workflow)

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

    warnings = tuple(w for w in (architecture_warning, security_warning) if w)
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
