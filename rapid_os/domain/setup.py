"""Setup (onboarding) state and next-action model. Pure data: no I/O."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Mapping

from rapid_os.domain.stack_aliases import LEGACY_STACKS

SETUP_SCHEMA_VERSION = 1
# The components a project can ask a stack for (`rapid_os.domain.catalog.COMPONENTS`).
STACK_COMPONENTS = ("frontend", "backend", "baas", "docs")
ARCHETYPES = ("mvp", "corporate")
STACK_SOURCES = ("catalog", "custom", "generic")
DOC_STATUSES = ("pending", "provided", "drafted", "skipped")
SETUP_DOC_ORDER = ("brief", "business", "data-model", "architecture", "deployment")
SERVICE_WHEN = ("now", "later")


class SetupStateError(ValueError):
    """Invalid setup state (RAPID1406)."""

    code = "RAPID1406"


def _fail(message: str) -> SetupStateError:
    return SetupStateError(f"RAPID1406 Invalid setup state: {message}")


@dataclass(frozen=True)
class StackChoice:
    id: str
    source: str
    # A variant of the stack's `tech-stack.md` (react-vite with the creative profile).
    profile: str | None = None

    def to_dict(self) -> dict[str, str]:
        data = {"id": self.id, "source": self.source}
        if self.profile:
            data["profile"] = self.profile
        return data


@dataclass(frozen=True)
class DocState:
    status: str = "pending"
    confirmed: bool = False
    sha256: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {"status": self.status, "confirmed": self.confirmed, "sha256": self.sha256}


@dataclass(frozen=True)
class ServiceChoice:
    """One infrastructure service the person chose: its role, engine and when it is needed."""

    role: str
    engine: str
    when: str = "now"

    def to_dict(self) -> dict[str, str]:
        return {"role": self.role, "engine": self.engine, "when": self.when}


@dataclass(frozen=True)
class SetupState:
    """Decisions taken so far. `None` means undecided; `test_command == ()` means "none"."""

    schema_version: int = SETUP_SCHEMA_VERSION
    # The stack of each component of the topology. A stack that covers several components is
    # stored under each of them (Next.js under `frontend` and `backend`).
    stacks: Mapping[str, StackChoice] = field(default_factory=dict)
    topology: str | None = None
    archetype: str | None = None
    agents: tuple[str, ...] = ()
    test_command: tuple[str, ...] | None = None
    docs: Mapping[str, DocState] = field(default_factory=dict)
    finished: bool = False
    # The person went through the unconfirmed drafts (`rapid setup review --done`); what they
    # did not confirm stays a draft. Omitted from the JSON while False.
    drafts_reviewed: bool = False
    # Does the product use models or agents? `None` is undecided. AI stacks do not ask (see
    # `rapid_os.domain.security.effective_ai`).
    ai: bool | None = None
    # Infrastructure services. `None` is undecided; `()` is "none" (a project without services).
    services: tuple[ServiceChoice, ...] | None = None

    def doc(self, doc_id: str) -> DocState:
        return self.docs.get(doc_id, DocState())

    @property
    def stack(self) -> StackChoice | None:
        """The stack that stands for the project where one is enough: the backend's, else the first."""
        for component in ("backend", "frontend", "baas", "docs"):
            if component in self.stacks:
                return self.stacks[component]
        return next(iter(self.stacks.values()), None)

    def stack_for(self, component: str) -> StackChoice | None:
        return self.stacks.get(component)

    @property
    def stack_ids(self) -> tuple[str, ...]:
        """Distinct stack ids, in component order."""
        seen: list[str] = []
        for component in ("backend", "frontend", "baas", "docs"):
            choice = self.stacks.get(component)
            if choice is not None and choice.id not in seen:
                seen.append(choice.id)
        return tuple(seen)

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "schema_version": self.schema_version,
            "stacks": {c: self.stacks[c].to_dict() for c in STACK_COMPONENTS if c in self.stacks},
            "topology": self.topology,
            "archetype": self.archetype,
            "agents": list(self.agents),
            "test_command": None if self.test_command is None else list(self.test_command),
            "docs": {doc_id: self.docs[doc_id].to_dict() for doc_id in sorted(self.docs)},
            "finished": self.finished,
        }
        if self.drafts_reviewed:
            payload["drafts_reviewed"] = True
        if self.ai is not None:
            payload["ai"] = self.ai
        if self.services is not None:
            payload["services"] = [s.to_dict() for s in self.services]
        return payload

    @classmethod
    def from_dict(cls, data: object) -> "SetupState":
        if not isinstance(data, dict):
            raise _fail("the document must be a JSON object.")
        version = data.get("schema_version")
        if isinstance(version, bool) or version != SETUP_SCHEMA_VERSION:
            raise _fail(f"schema_version must be {SETUP_SCHEMA_VERSION}.")

        stacks = _read_stacks(data)

        topology = data.get("topology")
        if topology is not None and (not isinstance(topology, str) or not topology):
            raise _fail("topology must be null or a non-empty string.")
        archetype = data.get("archetype")
        if archetype is not None and (not isinstance(archetype, str) or not archetype):
            raise _fail("archetype must be null or a non-empty string.")

        agents = data.get("agents", [])
        if not isinstance(agents, list) or not all(isinstance(a, str) and a for a in agents):
            raise _fail("agents must be a list of non-empty strings.")

        test_command = data.get("test_command")
        if test_command is not None and (
            not isinstance(test_command, list) or not all(isinstance(t, str) for t in test_command)
        ):
            raise _fail("test_command must be null or a list of strings.")

        raw_docs = data.get("docs", {})
        if not isinstance(raw_docs, dict):
            raise _fail("docs must be an object keyed by document id.")
        docs: dict[str, DocState] = {}
        for doc_id, raw in raw_docs.items():
            if doc_id not in SETUP_DOC_ORDER:
                raise _fail(f"unknown document id '{doc_id}'.")
            if (
                not isinstance(raw, dict)
                or raw.get("status") not in DOC_STATUSES
                or not isinstance(raw.get("confirmed"), bool)
                or not isinstance(raw.get("sha256", ""), str)
            ):
                raise _fail(f"docs.{doc_id} must be {{status, confirmed, sha256}} with status in {list(DOC_STATUSES)}.")
            docs[doc_id] = DocState(raw["status"], raw["confirmed"], raw.get("sha256", ""))

        finished = data.get("finished", False)
        if not isinstance(finished, bool):
            raise _fail("finished must be a boolean.")
        drafts_reviewed = data.get("drafts_reviewed", False)
        if not isinstance(drafts_reviewed, bool):
            raise _fail("drafts_reviewed must be a boolean.")
        # A file without the field is undecided, unless the setup is already finished: then it is no.
        ai = data.get("ai", False if finished else None)
        if "ai" not in data and "stacks" not in data and LEGACY_STACKS.get(_legacy_id(data), None) is not None:
            legacy = LEGACY_STACKS[_legacy_id(data)]
            if legacy.ai:
                ai = True  # python-ai and nodejs-ai are AI products by definition
        if ai is not None and not isinstance(ai, bool):
            raise _fail("ai must be null or a boolean.")
        # Like `ai`: a file without the field is undecided, unless the setup is finished (then: none).
        raw_services = data.get("services", [] if finished else None)
        services = None
        if raw_services is not None:
            if not isinstance(raw_services, list):
                raise _fail("services must be null or a list of {role, engine, when}.")
            parsed = []
            for item in raw_services:
                if (
                    not isinstance(item, dict)
                    or not isinstance(item.get("role"), str)
                    or not item["role"]
                    or not isinstance(item.get("engine"), str)
                    or not item["engine"]
                    or item.get("when", "now") not in SERVICE_WHEN
                ):
                    raise _fail(f"each service must be {{role, engine, when}} with when in {list(SERVICE_WHEN)}.")
                parsed.append(ServiceChoice(item["role"], item["engine"], item.get("when", "now")))
            services = tuple(parsed)

        return cls(
            schema_version=SETUP_SCHEMA_VERSION,
            stacks=stacks,
            topology=topology,
            archetype=archetype,
            agents=tuple(agents),
            test_command=None if test_command is None else tuple(test_command),
            docs=docs,
            finished=finished,
            drafts_reviewed=drafts_reviewed,
            ai=ai,
            services=services,
        )


def _legacy_id(data: dict) -> str | None:
    raw = data.get("stack")
    return raw.get("id") if isinstance(raw, dict) and isinstance(raw.get("id"), str) else None


def _stack_choice(raw: object, where: str) -> StackChoice:
    if (
        not isinstance(raw, dict)
        or not isinstance(raw.get("id"), str)
        or not raw["id"]
        or raw.get("source") not in STACK_SOURCES
        or not (raw.get("profile") is None or (isinstance(raw["profile"], str) and raw["profile"]))
    ):
        raise _fail(f"{where} must be {{id, source}} with source in {list(STACK_SOURCES)}.")
    return StackChoice(raw["id"], raw["source"], raw.get("profile"))


def _read_stacks(data: dict) -> dict[str, StackChoice]:
    """`stacks` {component: {id, source}}; a file written before the component catalog has `stack`
    {id, source} instead, which maps to the stacks of each component (`python-api` -> backend
    `python-fastapi`...). Any other id covered every part of the project, as `generic` does."""
    raw_stacks = data.get("stacks")
    if raw_stacks is not None:
        if not isinstance(raw_stacks, dict):
            raise _fail("stacks must be an object keyed by component.")
        stacks: dict[str, StackChoice] = {}
        for component, raw in raw_stacks.items():
            if component not in STACK_COMPONENTS:
                raise _fail(f"unknown component '{component}' in stacks (use {list(STACK_COMPONENTS)}).")
            stacks[component] = _stack_choice(raw, f"stacks.{component}")
        return stacks
    raw_stack = data.get("stack")
    if raw_stack is None:
        return {}
    choice = _stack_choice(raw_stack, "stack")
    legacy = LEGACY_STACKS.get(choice.id)
    if legacy is not None:
        return {
            component: StackChoice(stack_id, "catalog", legacy.profile if component == "frontend" else None)
            for component, stack_id in legacy.stacks.items()
        }
    if choice.id == "docs-modern":
        return {"docs": choice}
    return {component: choice for component in STACK_COMPONENTS}


class SetupActionKind(str, Enum):
    CHOOSE_STACK = "choose_stack"
    CHOOSE_TOPOLOGY = "choose_topology"
    CHOOSE_ARCHETYPE = "choose_archetype"
    CHOOSE_AI = "choose_ai"
    CHOOSE_SERVICES = "choose_services"
    CHOOSE_AGENTS = "choose_agents"
    SET_TEST_COMMAND = "set_test_command"
    RESOLVE_DOC = "resolve_doc"
    REVIEW_DRAFTS = "review_drafts"
    FINISH = "finish"
    DONE = "done"


@dataclass(frozen=True)
class SetupAction:
    kind: SetupActionKind
    payload: Mapping[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Stable shape: `schema_version`, `kind`, then the payload keys in insertion order."""
        return {"schema_version": SETUP_SCHEMA_VERSION, "kind": self.kind.value, **self.payload}
