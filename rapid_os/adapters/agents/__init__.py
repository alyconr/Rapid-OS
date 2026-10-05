"""Agent adapters for Rapid OS generated context files."""

from rapid_os.adapters.agents.base import AgentAdapter, AgentOutput
from rapid_os.adapters.agents.registry import (
    DEFAULT_AGENT_REGISTRY,
    AgentRegistry,
    create_default_agent_registry,
)

__all__ = [
    "AgentAdapter",
    "AgentOutput",
    "AgentRegistry",
    "DEFAULT_AGENT_REGISTRY",
    "create_default_agent_registry",
]
