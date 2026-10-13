from pathlib import Path
from typing import Mapping, Sequence

from rapid_os.adapters.agents.base import AgentAdapter, AgentOutput
from rapid_os.adapters.agents.shortcut_render import (
    context_step,
    document,
    simple_skill_outputs,
    skill_frontmatter,
    yaml_string,
)
from rapid_os.domain.shortcuts import ShortcutTemplate


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

    def shortcut_outputs(
        self, shortcuts: Sequence[ShortcutTemplate]
    ) -> Mapping[Path, str]:
        # Cursor skills: .cursor/skills/<name>/SKILL.md (supports disable-model-invocation).
        # https://cursor.com/docs/context/skills
        return simple_skill_outputs(
            shortcuts, (".cursor", "skills"), with_disable_model_invocation=True
        )


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

    def shortcut_outputs(
        self, shortcuts: Sequence[ShortcutTemplate]
    ) -> Mapping[Path, str]:
        # Claude Code skills: .claude/skills/<name>/SKILL.md. The only harness that runs
        # !`command` before the prompt is sent; a failing command aborts the skill.
        # https://code.claude.com/docs/en/skills
        outputs = {}
        for template in shortcuts:
            frontmatter = skill_frontmatter(template)
            if template.argument_hint:
                frontmatter.append(("argument-hint", yaml_string(template.argument_hint)))
            if template.allowed_commands:
                allowed = " ".join(f"Bash(rapid {sub} *)" for sub in template.allowed_commands)
                frontmatter.append(("allowed-tools", allowed))
            if template.disable_model_invocation:
                frontmatter.append(("disable-model-invocation", "true"))
            body = template.render_body(context_step(template, inline=True))
            outputs[Path(".claude") / "skills" / template.name / "SKILL.md"] = document(
                frontmatter, body
            )
        return outputs


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

    def shortcut_outputs(
        self, shortcuts: Sequence[ShortcutTemplate]
    ) -> Mapping[Path, str]:
        # Antigravity skills: .agents/skills/<name>/SKILL.md, invoked with /<name>.
        # Same folder and content as Codex so a project selecting both writes it once.
        # https://antigravity.google/docs/skills
        return simple_skill_outputs(
            shortcuts, (".agents", "skills"), with_disable_model_invocation=False
        )


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

    def shortcut_outputs(
        self, shortcuts: Sequence[ShortcutTemplate]
    ) -> Mapping[Path, str]:
        # VS Code prompt files: .github/prompts/<name>.prompt.md, invoked with /<name>.
        # https://code.visualstudio.com/docs/copilot/customization/prompt-files
        outputs = {}
        for template in shortcuts:
            frontmatter = [
                ("description", yaml_string(template.description)),
                ("name", template.name),
            ]
            if template.argument_hint:
                frontmatter.append(("argument-hint", yaml_string(template.argument_hint)))
            frontmatter.append(("agent", "agent"))
            body = template.render_body(context_step(template, inline=False))
            outputs[Path(".github") / "prompts" / f"{template.name}.prompt.md"] = document(
                frontmatter, body
            )
        return outputs


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

    def shortcut_outputs(
        self, shortcuts: Sequence[ShortcutTemplate]
    ) -> Mapping[Path, str]:
        # Codex skills: .agents/skills/<name>/SKILL.md, invoked with $<name> or from /skills.
        # Same folder and content as Antigravity so a project selecting both writes it once.
        # https://developers.openai.com/codex/skills
        return simple_skill_outputs(
            shortcuts, (".agents", "skills"), with_disable_model_invocation=False
        )


SUPPORTED_AGENT_ADAPTERS = (
    CursorAdapter,
    ClaudeAdapter,
    AntigravityAdapter,
    VSCodeAdapter,
    CodexAdapter,
)
