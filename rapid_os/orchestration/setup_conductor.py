"""Pure conductor for the onboarding: which decision comes next.

Mirrors `orchestration/conductor.py` for runs: it reads state and returns an action, and never
touches the filesystem. Reading the state is the adapter's job (`adapters/setup_store.py`).
"""

from __future__ import annotations

import re
from typing import Sequence

from rapid_os.domain.catalog import (
    DOC_SITE_TOPOLOGY,
    Catalog,
    SetupDocBank,
    SetupQuestion,
    StackEntry,
)
from rapid_os.domain.project import ProjectModel
from rapid_os.domain.scanner import suggest_init_choices
from rapid_os.domain.security import is_ai_stack
from rapid_os.domain.setup import (
    ARCHETYPES,
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
    """Order: stack, topology, archetype, ai, agents, test command, docs, finish, done.

    Everything that needs the filesystem or the environment (the proposed test command, the
    detected harness) arrives as an argument: this function reads nothing.
    """
    if state.stack is None:
        return _choose_stack(project_model, catalog, stack_questions)
    if state.topology is None:
        return _choose_topology(state, project_model, catalog)
    if state.archetype is None:
        return _action(
            SetupActionKind.CHOOSE_ARCHETYPE,
            options=[{"id": a, "summary": ARCHETYPE_SUMMARIES[a]} for a in ARCHETYPES],
            recommended=None,
            command=list(ARCHETYPE_COMMAND),
        )
    if state.ai is None and not is_ai_stack(state.stack.id):
        # python-ai and nodejs-ai are AI products by definition: they are not asked.
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
        return _action(
            SetupActionKind.SET_TEST_COMMAND,
            recommended=list(proposed_test_command) if proposed_test_command else None,
            command=list(TEST_COMMAND_COMMAND),
        )
    for doc_id in SETUP_DOC_ORDER:
        if state.doc(doc_id).status == "pending":
            return _resolve_doc(doc_id, doc_banks[doc_id], legacy_business)
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


def _choose_stack(
    model: ProjectModel, catalog: Catalog, questions: Sequence[SetupQuestion]
) -> SetupAction:
    options = [
        {
            "id": entry.id,
            "source": "generic" if entry.id == "generic" else "catalog",
            "summary": entry.summary,
            "language": entry.language,
            "score": _stack_score(entry, model),
            "fits": list(entry.fits),
            "avoid_if": list(entry.avoid_if),
            "compatible_topologies": list(entry.compatible_topologies),
        }
        for entry in catalog.stacks.values()
    ]
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

    suggestion = suggest_init_choices(model).stack
    recommended = suggestion.value if suggestion and any(o["id"] == suggestion.value for o in options) else None
    facts = sorted({(f.category, f.value) for f in model.facts})
    return _action(
        SetupActionKind.CHOOSE_STACK,
        facts=[{"category": c, "value": v} for c, v in facts],
        options=options,
        recommended=recommended,
        questions=[] if recommended else [_question(q) for q in questions],
        command=list(STACK_COMMAND),
        alt_command=list(STACK_CUSTOM_COMMAND),
    )


def _question(question: SetupQuestion) -> dict:
    data = {"id": question.id, "text": question.text, "required": question.required}
    if question.options:
        data["options"] = list(question.options)
    return data


def _choose_topology(state: SetupState, model: ProjectModel, catalog: Catalog) -> SetupAction:
    stack_id = state.stack.id
    compatible = catalog.compatible_topologies(stack_id)
    if compatible is None:
        compatible = tuple(t for t in catalog.topology_ids if t != DOC_SITE_TOPOLOGY)
    ids = sorted(compatible)
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
        options=options,
        recommended=recommended,
        command=list(TOPOLOGY_COMMAND),
    )


def _resolve_doc(doc_id: str, bank: SetupDocBank, legacy_business: str | None) -> SetupAction:
    command = [doc_id if token == "<id>" else token for token in DOC_COMMAND]
    extra = {"legacy_source": legacy_business} if doc_id == "business" and legacy_business else {}
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
