"""The stack ids of Rapid OS before the component catalog, and the stacks they map to. Pure: no I/O.

A project initialized before `templates/stacks/<component>/` names its stack with one of these ids
(`python-api`, `web-modern`...). They are still accepted everywhere a stack id is read: the state
file, `rapid setup set stack`, and the content of an existing `tech-stack.md`. Nothing is rewritten
until the person changes the decision.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping


@dataclass(frozen=True)
class LegacyStack:
    """What an old stack id means now: the stack of each component, an AI answer and a profile."""

    stacks: Mapping[str, str]
    ai: bool = False
    profile: str | None = None
    # The topologies the old id accepted: they keep validating the content of an existing project.
    topologies: tuple[str, ...] = ()
    order: tuple[str, ...] = field(default=("backend", "frontend"))

    def primary_id(self) -> str:
        for component in self.order:
            if component in self.stacks:
                return self.stacks[component]
        return next(iter(self.stacks.values()))


LEGACY_STACKS: Mapping[str, LegacyStack] = {
    "python-api": LegacyStack(
        {"backend": "python-fastapi"}, topologies=("fullstack-baas", "fullstack-separated")
    ),
    "python-ai": LegacyStack(
        {"backend": "python-fastapi"}, ai=True, topologies=("fullstack-baas", "fullstack-separated")
    ),
    "nodejs-ai": LegacyStack(
        {"backend": "node-fastify"}, ai=True, topologies=("fullstack-baas", "fullstack-separated")
    ),
    "web-modern": LegacyStack(
        {"frontend": "nextjs", "backend": "nextjs"},
        topologies=("front-end-only", "fullstack-baas", "fullstack-separated"),
    ),
    "frontend-creative": LegacyStack(
        {"frontend": "react-vite"}, profile="creative",
        topologies=("front-end-only", "fullstack-baas", "fullstack-separated"),
    ),
}


def is_legacy_stack(stack_id: str | None) -> bool:
    return stack_id in LEGACY_STACKS
