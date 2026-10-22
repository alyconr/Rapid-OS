"""Setup (onboarding) state and next-action model. Pure data: no I/O."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Mapping

SETUP_SCHEMA_VERSION = 1
ARCHETYPES = ("mvp", "corporate")
STACK_SOURCES = ("catalog", "custom", "generic")
DOC_STATUSES = ("pending", "provided", "drafted", "skipped")
SETUP_DOC_ORDER = ("brief", "business", "data-model", "architecture")


class SetupStateError(ValueError):
    """Invalid setup state (RAPID1406)."""

    code = "RAPID1406"


def _fail(message: str) -> SetupStateError:
    return SetupStateError(f"RAPID1406 Invalid setup state: {message}")


@dataclass(frozen=True)
class StackChoice:
    id: str
    source: str

    def to_dict(self) -> dict[str, str]:
        return {"id": self.id, "source": self.source}


@dataclass(frozen=True)
class DocState:
    status: str = "pending"
    confirmed: bool = False
    sha256: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {"status": self.status, "confirmed": self.confirmed, "sha256": self.sha256}


@dataclass(frozen=True)
class SetupState:
    """Decisions taken so far. `None` means undecided; `test_command == ()` means "none"."""

    schema_version: int = SETUP_SCHEMA_VERSION
    stack: StackChoice | None = None
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

    def doc(self, doc_id: str) -> DocState:
        return self.docs.get(doc_id, DocState())

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "schema_version": self.schema_version,
            "stack": self.stack.to_dict() if self.stack else None,
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
        return payload

    @classmethod
    def from_dict(cls, data: object) -> "SetupState":
        if not isinstance(data, dict):
            raise _fail("the document must be a JSON object.")
        version = data.get("schema_version")
        if isinstance(version, bool) or version != SETUP_SCHEMA_VERSION:
            raise _fail(f"schema_version must be {SETUP_SCHEMA_VERSION}.")

        stack = None
        raw_stack = data.get("stack")
        if raw_stack is not None:
            if (
                not isinstance(raw_stack, dict)
                or not isinstance(raw_stack.get("id"), str)
                or not raw_stack["id"]
                or raw_stack.get("source") not in STACK_SOURCES
            ):
                raise _fail(f"stack must be null or {{id, source}} with source in {list(STACK_SOURCES)}.")
            stack = StackChoice(raw_stack["id"], raw_stack["source"])

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
        if ai is not None and not isinstance(ai, bool):
            raise _fail("ai must be null or a boolean.")

        return cls(
            schema_version=SETUP_SCHEMA_VERSION,
            stack=stack,
            topology=topology,
            archetype=archetype,
            agents=tuple(agents),
            test_command=None if test_command is None else tuple(test_command),
            docs=docs,
            finished=finished,
            drafts_reviewed=drafts_reviewed,
            ai=ai,
        )


class SetupActionKind(str, Enum):
    CHOOSE_STACK = "choose_stack"
    CHOOSE_TOPOLOGY = "choose_topology"
    CHOOSE_ARCHETYPE = "choose_archetype"
    CHOOSE_AI = "choose_ai"
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
