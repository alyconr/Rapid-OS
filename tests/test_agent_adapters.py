import io
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from rapid_os.adapters.agents import DEFAULT_AGENT_REGISTRY, create_default_agent_registry
from rapid_os.domain.agents import (
    generate_agent_contexts,
    generate_antigravity_config,
    generate_claude_config,
    generate_cursor_rules,
    generate_vscode_instructions,
)


REPO_ROOT = Path(__file__).resolve().parents[1]


def workspace_tempdir():
    return tempfile.TemporaryDirectory(dir=REPO_ROOT)


def generate_quietly(func, *args):
    with redirect_stdout(io.StringIO()):
        func(*args)


class AgentAdapterTests(unittest.TestCase):
    def test_default_registry_contains_supported_v2_agents(self):
        registry = create_default_agent_registry()

        self.assertEqual(
            registry.ids(),
            ("cursor", "claude", "antigravity", "vscode"),
        )

    def test_adapters_declare_output_files_and_metadata(self):
        self.assertEqual(
            DEFAULT_AGENT_REGISTRY.get("cursor").output_files,
            (Path(".cursorrules"),),
        )
        self.assertEqual(
            DEFAULT_AGENT_REGISTRY.get("claude").output_files,
            (Path("CLAUDE.md"),),
        )
        self.assertEqual(
            DEFAULT_AGENT_REGISTRY.get("antigravity").output_files,
            (Path(".agent") / "rules" / "constitution.md",),
        )
        self.assertEqual(
            DEFAULT_AGENT_REGISTRY.get("vscode").output_files,
            (Path("INSTRUCTIONS.md"),),
        )
        self.assertIn("activation", DEFAULT_AGENT_REGISTRY.get("cursor").metadata)

    def test_legacy_wrappers_render_existing_file_contents(self):
        with workspace_tempdir() as tmp:
            current_dir = Path(tmp)
            context = "project context"

            generate_quietly(generate_cursor_rules, context, current_dir)
            generate_quietly(generate_claude_config, context, current_dir)
            generate_quietly(generate_antigravity_config, context, current_dir)
            generate_quietly(generate_vscode_instructions, context, current_dir)

            self.assertEqual(
                (current_dir / ".cursorrules").read_text(encoding="utf-8"),
                "# RAPID OS - SYSTEM CONTEXT\n"
                "# DO NOT EDIT. Generated automatically.\n\n"
                "project context",
            )
            self.assertEqual(
                (current_dir / "CLAUDE.md").read_text(encoding="utf-8"),
                "# PROJECT MEMORY\n"
                "# SOURCE OF TRUTH FOR AI.\n\n"
                "project context",
            )
            self.assertEqual(
                (current_dir / ".agent" / "rules" / "constitution.md").read_text(
                    encoding="utf-8"
                ),
                "# PROJECT CONSTITUTION\n"
                "# ACTIVATION: ALWAYS_ON\n\n"
                "# IMMUTABLE TRUTH FOR GEMINI AGENTS.\n"
                "project context",
            )
            self.assertEqual(
                (current_dir / "INSTRUCTIONS.md").read_text(encoding="utf-8"),
                "# AI INSTRUCTIONS (COPILOT)\n\n"
                "project context",
            )

    def test_generate_agent_contexts_uses_registered_agents_and_ignores_unknown_tools(self):
        with workspace_tempdir() as tmp:
            current_dir = Path(tmp)

            generate_quietly(
                generate_agent_contexts,
                "project context",
                ["context7", "vscode", "firecrawl", "cursor", "codex"],
                current_dir,
            )

            self.assertTrue((current_dir / ".cursorrules").exists())
            self.assertTrue((current_dir / "INSTRUCTIONS.md").exists())
            self.assertFalse((current_dir / "CLAUDE.md").exists())
            self.assertFalse(
                (current_dir / ".agent" / "rules" / "constitution.md").exists()
            )

    def test_adapter_activation_keeps_backup_behavior(self):
        with workspace_tempdir() as tmp:
            current_dir = Path(tmp)
            target = current_dir / ".cursorrules"
            target.write_text("old", encoding="utf-8")

            generate_quietly(generate_cursor_rules, "new", current_dir)

            backups = list(current_dir.glob(".cursorrules.*.bak"))
            self.assertEqual(len(backups), 1)
            self.assertEqual(backups[0].read_text(encoding="utf-8"), "old")


if __name__ == "__main__":
    unittest.main()
