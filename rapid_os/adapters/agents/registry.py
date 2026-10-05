from collections import OrderedDict
from typing import Iterable

from rapid_os.adapters.agents.base import AgentAdapter
from rapid_os.adapters.agents.implementations import SUPPORTED_AGENT_ADAPTERS


class AgentRegistry:
    """Ordered registry for project-context agent adapters."""

    def __init__(self, adapters: Iterable[AgentAdapter] = ()):
        self._adapters = OrderedDict()
        for adapter in adapters:
            self.register(adapter)

    def register(self, adapter: AgentAdapter) -> None:
        if adapter.id in self._adapters:
            raise ValueError(f"Agent adapter already registered: {adapter.id}")
        self._adapters[adapter.id] = adapter

    def get(self, agent_id: str) -> AgentAdapter:
        return self._adapters[agent_id]

    def ids(self):
        return tuple(self._adapters.keys())

    def adapters(self):
        return tuple(self._adapters.values())

    def enabled(self, selected_ids: Iterable[str]):
        selected = set(selected_ids)
        return tuple(
            adapter
            for adapter_id, adapter in self._adapters.items()
            if adapter_id in selected
        )


def create_default_agent_registry() -> AgentRegistry:
    return AgentRegistry(adapter_cls() for adapter_cls in SUPPORTED_AGENT_ADAPTERS)


DEFAULT_AGENT_REGISTRY = create_default_agent_registry()
