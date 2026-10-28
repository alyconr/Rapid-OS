"""Pure conductor for the onboarding: which decision comes next.

Mirrors `orchestration/conductor.py` for runs: it reads state and returns an action, and never
touches the filesystem. Reading the state is the adapter's job (`adapters/setup_store.py`).
"""

from __future__ import annotations

import re
from typing import Sequence

from rapid_os.domain.architecture import architecture_standard
from rapid_os.domain.catalog import (
    DOC_SITE_TOPOLOGY,
    SERVICE_ROLES,
    Catalog,
    SetupDocBank,
    SetupQuestion,
    StackEntry,
)
from rapid_os.domain.project import ProjectModel
from rapid_os.domain.scanner import suggest_init_choices
from rapid_os.domain.stack_aliases import LEGACY_STACKS
from rapid_os.domain.services import active_conditions, describe_services
from rapid_os.domain.setup import (
    ARCHETYPES,
    SERVICE_WHEN,
    SETUP_DOC_ORDER,
    SetupAction,
    SetupActionKind,
    SetupState,
)

LANGUAGE_MATCH_SCORE = 10
FRAMEWORK_MATCH_SCORE = 20
DOC_CHOICES = ("provided", "drafted", "skip")
DOC_COMMAND = ("rapid", "setup", "doc", "<id>", "--source", "<provided|drafted>", "--file", "-")
STACK_COMMAND = ("rapid", "setup", "set", "stack", "<id>")
STACK_INSTRUCTION = (
    "Haz las preguntas que el brief no responda. Recomienda una opción y una alternativa, y explica la "
    "diferencia con los factors del catálogo aplicados a este producto (p. ej. consumo de memoria y "
    "concurrencia frente a velocidad de desarrollo). No afirmes nada que el catálogo no diga. "
    "La persona decide."
)
STACK_CUSTOM_COMMAND = ("rapid", "setup", "stack", "--custom", "--file", "-")
TOPOLOGY_COMMAND = ("rapid", "setup", "set", "topology", "<id>")
ARCHETYPE_COMMAND = ("rapid", "setup", "set", "archetype", "<id>")
AGENTS_COMMAND = ("rapid", "setup", "set", "agents", "<id,id>")
TEST_COMMAND_COMMAND = ("rapid", "setup", "set", "test-command", "<cmd>")
FINISH_COMMAND = ("rapid", "setup", "finish")
REVIEW_DONE_COMMAND = ("rapid", "setup", "review", "--done")
CONFIRM_DOC_COMMAND = ("rapid", "setup", "doc", "<id>", "--confirm")
REVIEW_CONSEQUENCES = {
    "confirm": (
        "Pasa a ser una regla del proyecto: el agente la cumple en cada run sin cuestionarla. "
        "Puedes devolverla a borrador con rapid setup doc <id> --reopen."
    ),
    "keep_draft": (
        "Queda como supuesto: el agente la recibe bajo el aviso 'Supuestos redactados por el agente, "
        "no confirmados por la persona', puede cuestionarla y preguntarte, y cada run te recuerda que "
        "está sin confirmar (RAPID1408). La confirmas cuando quieras con rapid setup doc <id> --confirm."
    ),
}
ARCHETYPE_SUMMARIES = {
    "mvp": "Speed first; includes the security baseline (OWASP ASVS L1)",
    "corporate": "Security first; includes the security baseline at OWASP ASVS L2 and SLSA Build L2",
}
AI_COMMAND = ("rapid", "setup", "set", "ai", "<yes|no>")
SERVICES_COMMAND = ("rapid", "setup", "set", "services", "<role>:<engine>[@now|@later],...")
# The documents that come after the services decision (the agent needs the product first).
AFTER_SERVICES_DOCS = ("data-model", "architecture", "deployment")
SERVICES_INSTRUCTION = (
    "Propón los servicios a partir del brief y las reglas de negocio, con una línea de porqué por cada uno. "
    "Empieza por lo mínimo: una base de datos. Propón caché, colas o streaming solo si el brief lo justifica "
    "(p. ej. webhooks de pago con reintentos -> cola; notificaciones masivas por WhatsApp -> cola), y márcalos "
    "@later si no hacen falta para la primera historia. La persona decide; no fijes nada sin su respuesta."
)
STANDARD_INSTRUCTION = (
    "`standard` es la estructura que fijará .rapid-os/standards/architecture.md al terminar (aún no existe). "
    "Cita sus carpetas, su punto público (`public_entry`), sus capas y sus reglas de dependencia tal cual; "
    "no inventes otro punto público ni otras capas. Las reglas propias del producto se añaden, no sustituyen."
)
AI_QUESTION = (
    "¿El producto usará modelos de IA o agentes (por ejemplo, un asistente que responda por WhatsApp)?"
)


def next_setup_action(
    state: SetupState,
    project_model: ProjectModel,
    catalog: Catalog,
    doc_banks: dict[str, SetupDocBank],
    *,
    stack_questions: Sequence[SetupQuestion] = (),
    agent_ids: Sequence[str] = (),
    proposed_test_command: Sequence[str] | None = None,
    detected_agent: str | None = None,
    legacy_business: str | None = None,
) -> SetupAction:
    """Order: stack, topology, archetype, ai, agents, test command, docs (brief, business), services,
    docs (data-model, architecture, deployment), review of the drafts, finish, done.

    Everything that needs the filesystem or the environment (the proposed test command, the
    detected harness) arrives as an argument: this function reads nothing.
    """
    if state.stack is None:
        # A topology the person already chose says which component comes first; otherwise the
        # first stack can be of any component and the topology follows from it.
        components = [c for c in catalog.components_of(state.topology) if c != "baas"]
        return _choose_stack(project_model, catalog, stack_questions, components[0] if components else None, state)
    if state.topology is None:
        return _choose_topology(state, project_model, catalog)
    for component in catalog.components_of(state.topology):
        # A finished onboarding (a project from before the component catalog included) is not reopened
        # because its topology asks for a component it never had to decide.
        if component != "baas" and component not in state.stacks and not state.finished:
            return _choose_stack(project_model, catalog, stack_questions, component, state)
    if state.archetype is None:
        return _action(
            SetupActionKind.CHOOSE_ARCHETYPE,
            options=[{"id": a, "summary": ARCHETYPE_SUMMARIES[a]} for a in ARCHETYPES],
            recommended=None,
            command=list(ARCHETYPE_COMMAND),
        )
    if state.ai is None:
        # (`python-ai` and `nodejs-ai`, the ids of before the component catalog, set `ai` themselves.)
        return _action(
            SetupActionKind.CHOOSE_AI,
            question=AI_QUESTION,
            options=[{"id": "yes"}, {"id": "no"}],
            recommended=None,
            command=list(AI_COMMAND),
        )
    if not state.agents:
        return _action(
            SetupActionKind.CHOOSE_AGENTS,
            options=[{"id": agent_id} for agent_id in agent_ids],
            recommended=detected_agent if detected_agent in agent_ids else None,
            command=list(AGENTS_COMMAND),
        )
    if state.test_command is None:
        # What the repository already has (a `package.json` with a test script, pytest) wins; in an empty
        # repository the stacks decided say how each component is tested, from the folder it lives in.
        per_component = catalog_test_commands(state, catalog)
        extra = {}
        recommended = list(proposed_test_command) if proposed_test_command else None
        if recommended is None and per_component:
            recommended = combine_test_commands([item["command"] for item in per_component])
        if per_component:
            extra["components"] = per_component
        return _action(
            SetupActionKind.SET_TEST_COMMAND,
            recommended=recommended,
            command=list(TEST_COMMAND_COMMAND),
            **extra,
        )
    for doc_id in SETUP_DOC_ORDER:
        # A document that did not exist when the onboarding closed (`deployment`) reads as skipped: it can
        # be written whenever the person wants, but the finished onboarding does not ask for it.
        if state.finished and doc_id not in state.docs:
            continue
        if state.doc(doc_id).status == "pending":
            if doc_id in AFTER_SERVICES_DOCS and state.services is None:
                return _choose_services(state, catalog)
            return _resolve_doc(doc_id, doc_banks[doc_id], legacy_business, state, catalog)
    if state.services is None:
        return _choose_services(state, catalog)
    unconfirmed = _unconfirmed_docs(state)
    if unconfirmed and not state.drafts_reviewed and not state.finished:
        return _review_drafts(unconfirmed, doc_banks)
    if not state.finished:
        return _action(
            SetupActionKind.FINISH, unconfirmed_docs=unconfirmed, command=list(FINISH_COMMAND)
        )
    return _action(SetupActionKind.DONE, unconfirmed_docs=unconfirmed)


def _action(kind: SetupActionKind, **payload) -> SetupAction:
    return SetupAction(kind, payload)


def _review_drafts(unconfirmed: list[str], doc_banks: dict[str, SetupDocBank]) -> SetupAction:
    """The person decides, document by document, whether a draft becomes a rule."""
    return _action(
        SetupActionKind.REVIEW_DRAFTS,
        drafts=[
            {"doc": doc_id, "file": doc_banks[doc_id].file, "title": doc_banks[doc_id].title}
            for doc_id in unconfirmed
        ],
        consequences=dict(REVIEW_CONSEQUENCES),
        commands={"confirm": list(CONFIRM_DOC_COMMAND), "done": list(REVIEW_DONE_COMMAND)},
        command=list(REVIEW_DONE_COMMAND),
    )


def _unconfirmed_docs(state: SetupState) -> list[str]:
    return [
        doc_id
        for doc_id in SETUP_DOC_ORDER
        if state.doc(doc_id).status == "drafted" and not state.doc(doc_id).confirmed
    ]


def _norm(text: str) -> str:
    return re.sub(r"[^a-z0-9]", "", text.lower())


def _stack_score(entry: StackEntry, model: ProjectModel) -> int:
    haystack = _norm(" ".join([entry.id, entry.summary, *entry.fits]))
    score = 0
    languages = {_norm(v) for v in model.values("language")}
    if _norm(entry.language) in languages:
        score += LANGUAGE_MATCH_SCORE
    for framework in sorted(set(model.values("framework"))):
        if _norm(framework) and _norm(framework) in haystack:
            score += FRAMEWORK_MATCH_SCORE
    return score


def _stack_option(entry: StackEntry, model: ProjectModel) -> dict:
    option = {
        "id": entry.id,
        "source": "generic" if entry.id == "generic" else "catalog",
        "summary": entry.summary,
        "language": entry.language,
        "score": _stack_score(entry, model),
        "fits": list(entry.fits),
        "avoid_if": list(entry.avoid_if),
        "compatible_topologies": list(entry.compatible_topologies),
    }
    if entry.component:
        option.update(
            component=entry.component,
            covers=list(entry.covers),
            monolith=entry.monolith or len(entry.covers) > 1,
            factors=dict(entry.factors),
            factor_sources={k: list(v) for k, v in entry.factor_sources.items()},
            package_manager=entry.package_manager,
            default_test_command=list(entry.default_test_command),
            supported_services=sorted(entry.supported_services or {}),
        )
    return option


def _choose_stack(
    model: ProjectModel,
    catalog: Catalog,
    questions: Sequence[SetupQuestion],
    component: str | None = None,
    state: SetupState | None = None,
) -> SetupAction:
    """One stack per component of the topology (`component` names the one asked now)."""
    entries = catalog.options_for(component) if component else tuple(catalog.stacks.values())
    flat = [e for e in catalog.stacks.values() if not e.component and (component is None or component in e.covers)]
    unique = {}
    for entry in [*entries, *flat]:
        unique.setdefault(entry.id, entry)
    options = [_stack_option(entry, model) for entry in unique.values()]
    options += [
        {
            "id": stack_id,
            "source": "custom",
            "summary": "",
            "language": "",
            "score": 0,
            "fits": [],
            "avoid_if": [],
            "compatible_topologies": [],
        }
        for stack_id in catalog.sidecarless_stacks
    ]
    options.sort(key=lambda o: (-o["score"], o["source"] == "generic", o["id"]))

    suggestions = suggest_init_choices(model)
    suggestion = (suggestions.stacks or {}).get(component) if component else suggestions.stack
    suggested = suggestion.value if suggestion else None
    legacy = LEGACY_STACKS.get(suggested or "")
    if legacy is not None:
        suggested = legacy.stacks.get(component or "backend") or legacy.primary_id()
    recommended = suggested if suggested and any(o["id"] == suggested for o in options) else None
    facts = sorted({(f.category, f.value) for f in model.facts})
    command = list(STACK_COMMAND) + (["--component", component] if component else [])
    payload = dict(
        facts=[{"category": c, "value": v} for c, v in facts],
        options=options,
        recommended=recommended,
        questions=[_question(q) for q in questions],
        instruction=STACK_INSTRUCTION,
        command=command,
        alt_command=list(STACK_CUSTOM_COMMAND),
    )
    if component:
        payload["component"] = component
        payload["decided"] = {c: s.id for c, s in (state.stacks if state else {}).items()}
        if state is not None and state.topology is not None:
            payload["topology"] = state.topology
            payload["components"] = list(catalog.components_of(state.topology))
    return _action(SetupActionKind.CHOOSE_STACK, **payload)


def _question(question: SetupQuestion) -> dict:
    data = {"id": question.id, "text": question.text, "required": question.required}
    if question.options:
        data["options"] = list(question.options)
    return data


def _choose_topology(state: SetupState, model: ProjectModel, catalog: Catalog) -> SetupAction:
    stack_id = state.stack.id
    compatible = None
    for decided in state.stack_ids:
        allowed = catalog.compatible_topologies(decided)
        if allowed is None:
            allowed = tuple(t for t in catalog.topology_ids if t != DOC_SITE_TOPOLOGY)
        compatible = allowed if compatible is None else tuple(t for t in compatible if t in allowed)
    ids = sorted(compatible or ())
    suggestion = suggest_init_choices(model).topology
    recommended = catalog.default_topology_for_stack(
        stack_id, suggestion.value if suggestion else None, ids
    )
    options = []
    for topology_id in ids:
        entry = catalog.topologies.get(topology_id)
        options.append(
            {
                "id": topology_id,
                "summary": entry.summary if entry else "",
                "fits": list(entry.fits) if entry else [],
                "avoid_if": list(entry.avoid_if) if entry else [],
            }
        )
    return _action(
        SetupActionKind.CHOOSE_TOPOLOGY,
        stack=stack_id,
        stacks={c: choice.id for c, choice in state.stacks.items()},
        options=options,
        recommended=recommended,
        command=list(TOPOLOGY_COMMAND),
    )


def _choose_services(state: SetupState, catalog: Catalog) -> SetupAction:
    """The infrastructure services come from a recorded decision, not from the stack: the stack only
    suggests a minimum."""
    entry = catalog.entry(state.stack.id) if state.stack else None
    return _action(
        SetupActionKind.CHOOSE_SERVICES,
        roles=list(SERVICE_ROLES),
        catalog=[
            {
                "id": s.id,
                "role": s.role,
                "image": s.image,
                "ports": list(s.ports),
                "connection_env": s.connection_env,
            }
            for s in sorted(catalog.services.values(), key=lambda s: (SERVICE_ROLES.index(s.role), s.id))
        ],
        suggested_services=list(entry.suggested_services) if entry else [],
        suggestion_note="Una sugerencia mínima del stack, no una decisión: la persona decide.",
        when_values=list(SERVICE_WHEN),
        instruction=SERVICES_INSTRUCTION,
        command=list(SERVICES_COMMAND),
    )


def catalog_test_commands(state: SetupState, catalog: Catalog) -> list[dict]:
    """`{component, stack, root, command}` for each component that has tests, from the stack catalog.

    Two components in their own folders (`backend/`, `frontend/`) run from the project root with the
    folder in the command (`uv run --directory backend pytest`), so they work outside the agent's shell."""
    chosen = {c: choice.id for c, choice in state.stacks.items() if c in ("backend", "frontend")}
    separate = len(chosen) == 2 and len(set(chosen.values())) == 2
    items: list[dict] = []
    seen: set[str] = set()
    for component in ("backend", "frontend"):
        stack_id = chosen.get(component)
        entry = catalog.stacks.get(stack_id or "")
        if entry is None or stack_id in seen:
            continue
        seen.add(stack_id)
        root = component if separate else ""
        command = entry.test_command(root)
        if command:  # `generic` knows no test command
            items.append({"component": component, "stack": stack_id, "root": root, "command": command})
    return items


def combine_test_commands(commands: Sequence[Sequence[str]]) -> list[str]:
    """One argv for several test commands: it runs them all and fails when any fails (no shell needed)."""
    if len(commands) == 1:
        return list(commands[0])
    code = (
        "import subprocess, sys; "
        f"sys.exit(max(subprocess.call(c) for c in {[list(c) for c in commands]!r}))"
    )
    return ["python", "-c", code]


def _resolve_doc(
    doc_id: str,
    bank: SetupDocBank,
    legacy_business: str | None,
    state: SetupState | None = None,
    catalog: Catalog | None = None,
) -> SetupAction:
    command = [doc_id if token == "<id>" else token for token in DOC_COMMAND]
    extra = {"legacy_source": legacy_business} if doc_id == "business" and legacy_business else {}
    if doc_id in ("data-model", "architecture", "deployment") and state is not None and catalog is not None:
        # Only the decided services: the document describes them and invents no others.
        extra["services"] = describe_services(state.services, catalog)
        if bank.conditional_sections:
            extra["conditional_sections"] = [
                {"id": s.id, "titles": list(s.titles), "when": s.when}
                for s in bank.conditional_sections
                if s.when in active_conditions(state.services)
            ]
    if doc_id == "architecture" and state is not None:
        standard = architecture_standard({component: choice.id for component, choice in state.stacks.items()})
        if standard:
            # `standards/architecture.md` is only written by `finish`: the draft cites this, not an invention.
            extra["standard"] = standard
            extra["standard_instruction"] = STANDARD_INSTRUCTION
    return _action(
        SetupActionKind.RESOLVE_DOC,
        doc=doc_id,
        target=bank.file,
        choices=list(DOC_CHOICES),
        questions=[_question(q) for q in bank.questions],
        required_sections=[{"id": s.id, "titles": list(s.titles)} for s in bank.required_sections],
        max_chars=bank.max_chars,
        command=command,
        **extra,
    )
