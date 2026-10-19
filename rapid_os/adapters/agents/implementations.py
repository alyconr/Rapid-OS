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
    skills_root = (".cursor", "skills")
    # "User-level (global) on the local machine": ~/.agents/skills/ and ~/.cursor/skills/
    # https://cursor.com/docs/context/skills
    global_skills_root = (".cursor", "skills")
    global_docs_url = "https://cursor.com/docs/context/skills"
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
    skills_root = (".claude", "skills")
    # "Personal skills live at ~/.claude/skills/<skill-name>/SKILL.md"
    # https://code.claude.com/docs/en/skills
    global_skills_root = (".claude", "skills")
    global_docs_url = "https://code.claude.com/docs/en/skills"
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
    skills_root = (".agents", "skills")
    # Global skills "available across all projects on your workstation": the Antigravity App and
    # IDE read ~/.gemini/config/skills/ (the Antigravity CLI reads ~/.gemini/antigravity-cli/skills/,
    # which --global does not write).
    # https://antigravity.google/docs/skills
    global_skills_root = (".gemini", "config", "skills")
    global_docs_url = "https://antigravity.google/docs/skills"
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
    skills_root = (".github", "prompts")
    # No user-level folder to write: the documentation says user prompt files live in "Your user
    # data (specific to your VS Code profile)" without naming a path, so --global is unsupported.
    # https://code.visualstudio.com/docs/copilot/customization/prompt-files
    global_skills_root = None
    global_docs_url = "https://code.visualstudio.com/docs/copilot/customization/prompt-files"
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
    skills_root = (".agents", "skills")
    # The USER row of the skill locations table is $HOME/.agents/skills
    # https://learn.chatgpt.com/docs/build-skills (formerly https://developers.openai.com/codex/skills)
    global_skills_root = (".agents", "skills")
    global_docs_url = "https://learn.chatgpt.com/docs/build-skills"
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
