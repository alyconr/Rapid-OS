from pathlib import Path
from typing import Mapping

from rapid_os.adapters.agents.base import AgentAdapter, AgentOutput


class CursorAdapter(AgentAdapter):
    id = "cursor"
    name = "Cursor"
    metadata = {"activation": "Project root .cursorrules"}
    outputs = (
        AgentOutput(Path(".cursorrules"), "Generado: .cursorrules"),
    )

    def render(self, context: str) -> Mapping[Path, str]:
        return {
            Path(".cursorrules"): (
                "# RAPID OS - SYSTEM CONTEXT\n"
                "# DO NOT EDIT. Generated automatically.\n\n"
                f"{context}"
            )
        }


class ClaudeAdapter(AgentAdapter):
    id = "claude"
    name = "Claude Code"
    metadata = {"activation": "Project root CLAUDE.md"}
    outputs = (
        AgentOutput(Path("CLAUDE.md"), "Generado: CLAUDE.md"),
    )

    def render(self, context: str) -> Mapping[Path, str]:
        return {
            Path("CLAUDE.md"): (
                "# PROJECT MEMORY\n"
                "# SOURCE OF TRUTH FOR AI.\n\n"
                f"{context}"
            )
        }


class AntigravityAdapter(AgentAdapter):
    id = "antigravity"
    name = "Google Antigravity"
    metadata = {"activation": "Always-on project constitution rule"}
    outputs = (
        AgentOutput(
            Path(".agent") / "rules" / "constitution.md",
            "Generado: .agent/rules/constitution.md",
        ),
    )

    def render(self, context: str) -> Mapping[Path, str]:
        relative_path = Path(".agent") / "rules" / "constitution.md"
        return {
            relative_path: (
                "# PROJECT CONSTITUTION\n"
                "# ACTIVATION: ALWAYS_ON\n\n"
                "# IMMUTABLE TRUTH FOR GEMINI AGENTS.\n"
                f"{context}"
            )
        }


class VSCodeAdapter(AgentAdapter):
    id = "vscode"
    name = "VS Code / Copilot"
    metadata = {"activation": "Project root INSTRUCTIONS.md"}
    outputs = (
        AgentOutput(Path("INSTRUCTIONS.md"), "Generado: INSTRUCTIONS.md"),
    )

    def render(self, context: str) -> Mapping[Path, str]:
        return {
            Path("INSTRUCTIONS.md"): (
                "# AI INSTRUCTIONS (COPILOT)\n\n"
                f"{context}"
            )
        }


class CodexAdapter(AgentAdapter):
    id = "codex"
    name = "Codex"
    metadata = {
        "activation": "Project root AGENTS.md",
        "scope": "repository",
        "agent": "Codex",
    }
    outputs = (
        AgentOutput(Path("AGENTS.md"), "Generado: AGENTS.md"),
    )

    def render(self, context: str) -> Mapping[Path, str]:
        return {
            Path("AGENTS.md"): (
                "# RAPID OS - CODEX PROJECT INSTRUCTIONS\n"
                "# SOURCE OF TRUTH FOR CODEX.\n\n"
                f"{context}"
            )
        }


SUPPORTED_AGENT_ADAPTERS = (
    CursorAdapter,
    ClaudeAdapter,
    AntigravityAdapter,
    VSCodeAdapter,
    CodexAdapter,
)
