import argparse
import contextlib
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from argparse import Namespace
from pathlib import Path
from unittest.mock import patch

from rapid_os.cli import main as cli_main
from rapid_os.cli.main import create_parser, parse_agent_selection, refine_standard
from rapid_os.core.text import read_text_best_effort


class CliSmokeTests(unittest.TestCase):
    def test_parser_preserves_existing_command_names(self):
        parser = create_parser()
        subparsers = next(
            action
            for action in parser._actions
            if isinstance(action, argparse._SubParsersAction)
        )

        self.assertEqual(
            set(subparsers.choices),
            {
                "init",
                "skill",
                "scope",
                "deploy",
                "vision",
                "mcp",
                "refine",
                "prompt",
                "validate",
                "doctor",
                "inspect-context",
                "guide",
            },
        )

    def test_agent_selection_default_remains_cursor_only(self):
        self.assertEqual(parse_agent_selection(""), ["cursor"])
        self.assertEqual(parse_agent_selection("   "), ["cursor"])

    def test_agent_selection_includes_codex_when_explicitly_selected(self):
        self.assertEqual(
            parse_agent_selection("1, 5"),
            ["cursor", "codex"],
        )

    def test_scope_command_remains_available(self):
        parser = create_parser()
        subparsers = next(
            action
            for action in parser._actions
            if isinstance(action, argparse._SubParsersAction)
        )

        self.assertIn("scope", subparsers.choices)

    def test_skill_command_accepts_no_action_for_interactive_fallback(self):
        parser = create_parser()

        args = parser.parse_args(["skill"])

        self.assertEqual(args.command, "skill")
        self.assertIsNone(args.action)
        self.assertIsNone(args.name)

    def test_vision_command_accepts_no_path_for_interactive_fallback(self):
        parser = create_parser()

        args = parser.parse_args(["vision"])

        self.assertEqual(args.command, "vision")
        self.assertIsNone(args.path)

    def test_mcp_command_accepts_ide_and_scope_flags(self):
        parser = create_parser()

        args = parser.parse_args(["mcp", "--ide", "cursor", "--scope", "project"])

        self.assertEqual(args.command, "mcp")
        self.assertEqual(args.ide, "cursor")
        self.assertEqual(args.scope, "project")

    def test_rapid_help_smoke(self):
        repo_root = Path(__file__).resolve().parents[1]
        env = os.environ.copy()
        env["PYTHONDONTWRITEBYTECODE"] = "1"

        result = subprocess.run(
            [sys.executable, "rapid.py", "--help"],
            cwd=repo_root,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn(b"Rapid OS", result.stdout)

    def test_rapid_guide_smoke(self):
        repo_root = Path(__file__).resolve().parents[1]
        env = os.environ.copy()
        env["PYTHONDONTWRITEBYTECODE"] = "1"

        result = subprocess.run(
            [sys.executable, "rapid.py", "guide"],
            cwd=repo_root,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn(b"init", result.stdout)

    def test_validation_command_help_smoke(self):
        repo_root = Path(__file__).resolve().parents[1]
        env = os.environ.copy()
        env["PYTHONDONTWRITEBYTECODE"] = "1"

        for command in ("validate", "doctor", "inspect-context"):
            result = subprocess.run(
                [sys.executable, "rapid.py", command, "--help"],
                cwd=repo_root,
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn(command.encode(), result.stdout)

    def test_validate_json_exits_nonzero_for_current_uninitialized_project(self):
        repo_root = Path(__file__).resolve().parents[1]
        env = os.environ.copy()
        env["PYTHONDONTWRITEBYTECODE"] = "1"

        result = subprocess.run(
            [sys.executable, "rapid.py", "validate", "--json"],
            cwd=repo_root,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        self.assertEqual(result.returncode, 1)
        payload = json.loads(result.stdout.decode("utf-8"))
        self.assertFalse(payload["ok"])
        self.assertIn("diagnostics", payload)

    def test_doctor_json_exit_codes_cover_success_and_strict_warning(self):
        repo_root = Path(__file__).resolve().parents[1]
        env = os.environ.copy()
        env["PYTHONDONTWRITEBYTECODE"] = "1"

        relaxed = subprocess.run(
            [sys.executable, "rapid.py", "doctor", "--json"],
            cwd=repo_root,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        strict = subprocess.run(
            [sys.executable, "rapid.py", "doctor", "--json", "--strict"],
            cwd=repo_root,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        self.assertEqual(relaxed.returncode, 0, relaxed.stderr)
        self.assertEqual(strict.returncode, 1, strict.stderr)
        self.assertTrue(json.loads(relaxed.stdout.decode("utf-8"))["ok"])
        self.assertFalse(json.loads(strict.stdout.decode("utf-8"))["ok"])


class CliEncodingTests(unittest.TestCase):
    def test_read_text_best_effort_reads_cp1252_files(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "business.md"
            expected = "Descripción comercial"
            path.write_bytes(expected.encode("cp1252"))

            self.assertEqual(read_text_best_effort(path), expected)

    def test_refine_standard_handles_cp1252_files(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "business.md"
            content = "Descripción comercial"
            path.write_bytes(content.encode("cp1252"))
            output = io.StringIO()

            with contextlib.redirect_stdout(output):
                refine_standard(Namespace(file=str(path)))

            self.assertIn(content, output.getvalue())


class CliInteractiveUxTests(unittest.TestCase):
    def test_skill_without_action_opens_menu_and_runs_selected_flow(self):
        repo_root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory(dir=repo_root) as temp_dir:
            root = Path(temp_dir)
            templates_dir = root / "templates"
            templates_dir.mkdir()
            output = io.StringIO()

            with patch.object(cli_main, "TEMPLATES_DIR", templates_dir), patch(
                "builtins.input", return_value="1"
            ), contextlib.redirect_stdout(output):
                cli_main.manage_skills(Namespace(action=None, name=None))

            self.assertIn("SKILLS", output.getvalue())

    def test_visual_reference_cancel_does_not_write_references(self):
        repo_root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory(dir=repo_root) as temp_dir:
            root = Path(temp_dir)
            output = io.StringIO()

            with patch.object(cli_main, "CURRENT_DIR", root), patch(
                "builtins.input", return_value="0"
            ), contextlib.redirect_stdout(output):
                cli_main.add_visual_reference(Namespace(path=None))

            self.assertFalse((root / "references").exists())
            self.assertIn("cancelada", output.getvalue())

    def test_optional_docs_scaffold_creates_selected_docs_and_backup(self):
        repo_root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory(dir=repo_root) as temp_dir:
            root = Path(temp_dir)
            docs_dir = root / "docs"
            docs_dir.mkdir()
            existing = docs_dir / "BUSINESS_RULES.md"
            existing.write_text("old", encoding="utf-8")
            answers = iter(["y", "y", "n", "n", "n"])

            with patch.object(cli_main, "CURRENT_DIR", root), contextlib.redirect_stdout(
                io.StringIO()
            ):
                written = cli_main.create_optional_docs_scaffold(
                    input_fn=lambda _prompt: next(answers)
                )

            self.assertEqual([path.name for path in written], ["BUSINESS_RULES.md"])
            self.assertIn("## Purpose", existing.read_text(encoding="utf-8"))
            self.assertTrue(list(docs_dir.glob("BUSINESS_RULES.md.*.bak")))
            self.assertFalse((docs_dir / "SPECS.md").exists())

    def test_optional_docs_scaffold_cancel_writes_nothing(self):
        repo_root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory(dir=repo_root) as temp_dir:
            root = Path(temp_dir)

            with patch.object(cli_main, "CURRENT_DIR", root), contextlib.redirect_stdout(
                io.StringIO()
            ):
                written = cli_main.create_optional_docs_scaffold(
                    input_fn=lambda _prompt: "cancelar"
                )

            self.assertEqual(written, [])
            self.assertFalse((root / "docs").exists())


def _create_full_init_templates(root: Path) -> Path:
    templates = root / "templates"
    for dirname in ("stacks", "topologies", "archetypes", "business"):
        (templates / dirname).mkdir(parents=True)

    (templates / "stacks" / "web-modern.md").write_text(
        "# web-modern\n", encoding="utf-8"
    )
    (templates / "topologies" / "front-end-only.md").write_text(
        "# front-end-only\n", encoding="utf-8"
    )
    (templates / "archetypes" / "mvp").mkdir()
    (templates / "archetypes" / "mvp" / "coding-rules.md").write_text(
        "mvp coding rules", encoding="utf-8"
    )
    (templates / "archetypes" / "corporate").mkdir()
    (templates / "archetypes" / "corporate" / "coding-rules.md").write_text(
        "corporate coding rules", encoding="utf-8"
    )
    (templates / "archetypes" / "corporate" / "security.md").write_text(
        "corporate security rules", encoding="utf-8"
    )
    return templates


class CliArchetypeAndHardeningTests(unittest.TestCase):
    def test_parser_accepts_mvp_and_corporate_archetype_and_rejects_invalid(self):
        parser = create_parser()

        mvp_args = parser.parse_args(["init", "--archetype", "mvp"])
        corp_args = parser.parse_args(["init", "--archetype", "corporate"])

        self.assertEqual(mvp_args.archetype, "mvp")
        self.assertEqual(corp_args.archetype, "corporate")

        with contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit):
                parser.parse_args(["init", "--archetype", "enterprise"])

    def test_init_honors_archetype_corporate_without_prompting(self):
        repo_root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory(dir=repo_root) as temp_dir:
            root = Path(temp_dir)
            project = root / "project"
            project.mkdir()
            templates = _create_full_init_templates(root)

            # Notice: only topology, agents, research, import(n), manual business rules, optional docs(n)
            # No archetype prompt is consumed when --archetype corporate is passed.
            prompts_seen = []
            answers = iter(["1", "1", "", "n", "Regla 1", "n"])

            def fake_input(prompt=""):
                prompts_seen.append(prompt)
                return next(answers)

            args = Namespace(
                stack="web-modern",
                archetype="corporate",
                no_scan=True,
            )

            with patch.object(cli_main, "CURRENT_DIR", project), patch.object(
                cli_main, "PROJECT_RAPID_DIR", project / ".rapid-os"
            ), patch.object(
                cli_main, "CONFIG_FILE", project / ".rapid-os" / "config.json"
            ), patch.object(
                cli_main, "TEMPLATES_DIR", templates
            ), patch(
                "builtins.input", fake_input
            ), contextlib.redirect_stdout(io.StringIO()):
                cli_main.init_project(args)

            standards = project / ".rapid-os" / "standards"
            self.assertEqual(
                (standards / "coding-rules.md").read_text(encoding="utf-8"),
                "corporate coding rules",
            )
            self.assertEqual(
                (standards / "security.md").read_text(encoding="utf-8"),
                "corporate security rules",
            )

    def test_init_honors_archetype_mvp_without_prompting(self):
        repo_root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory(dir=repo_root) as temp_dir:
            root = Path(temp_dir)
            project = root / "project"
            project.mkdir()
            templates = _create_full_init_templates(root)

            answers = iter(["1", "1", "", "n", "Regla MVP", "n"])
            args = Namespace(
                stack="web-modern",
                archetype="mvp",
                no_scan=True,
            )

            with patch.object(cli_main, "CURRENT_DIR", project), patch.object(
                cli_main, "PROJECT_RAPID_DIR", project / ".rapid-os"
            ), patch.object(
                cli_main, "CONFIG_FILE", project / ".rapid-os" / "config.json"
            ), patch.object(
                cli_main, "TEMPLATES_DIR", templates
            ), patch(
                "builtins.input", lambda prompt="": next(answers)
            ), contextlib.redirect_stdout(io.StringIO()):
                cli_main.init_project(args)

            standards = project / ".rapid-os" / "standards"
            self.assertEqual(
                (standards / "coding-rules.md").read_text(encoding="utf-8"),
                "mvp coding rules",
            )
            self.assertFalse((standards / "security.md").exists())

    def test_init_interactive_archetype_fallback_when_flag_omitted(self):
        repo_root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory(dir=repo_root) as temp_dir:
            root = Path(temp_dir)
            project = root / "project"
            project.mkdir()
            templates = _create_full_init_templates(root)

            # "2" selects corporate interactively
            answers = iter(["1", "2", "1", "", "n", "", "n"])
            args = Namespace(
                stack="web-modern",
                archetype=None,
                no_scan=True,
            )

            with patch.object(cli_main, "CURRENT_DIR", project), patch.object(
                cli_main, "PROJECT_RAPID_DIR", project / ".rapid-os"
            ), patch.object(
                cli_main, "CONFIG_FILE", project / ".rapid-os" / "config.json"
            ), patch.object(
                cli_main, "TEMPLATES_DIR", templates
            ), patch(
                "builtins.input", lambda prompt="": next(answers)
            ), contextlib.redirect_stdout(io.StringIO()):
                cli_main.init_project(args)

            standards = project / ".rapid-os" / "standards"
            self.assertEqual(
                (standards / "coding-rules.md").read_text(encoding="utf-8"),
                "corporate coding rules",
            )
            self.assertTrue((standards / "security.md").exists())

    def test_init_creates_backups_for_existing_standards_and_deploy_backs_up_deploy_md(self):
        repo_root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory(dir=repo_root) as temp_dir:
            root = Path(temp_dir)
            project = root / "project"
            standards = project / ".rapid-os" / "standards"
            standards.mkdir(parents=True)
            for fname in ("tech-stack.md", "topology.md", "coding-rules.md", "business.md"):
                (standards / fname).write_text(f"old {fname}", encoding="utf-8")

            templates = _create_full_init_templates(root)
            (templates / "deploy").mkdir(parents=True)
            (templates / "deploy" / "aws.md").write_text("AWS guide", encoding="utf-8")

            answers = iter(["1", "1", "", "n", "New business", "n"])
            args = Namespace(
                stack="web-modern",
                archetype="mvp",
                no_scan=True,
            )

            with patch.object(cli_main, "CURRENT_DIR", project), patch.object(
                cli_main, "PROJECT_RAPID_DIR", project / ".rapid-os"
            ), patch.object(
                cli_main, "CONFIG_FILE", project / ".rapid-os" / "config.json"
            ), patch.object(
                cli_main, "TEMPLATES_DIR", templates
            ), patch(
                "builtins.input", lambda prompt="": next(answers)
            ), contextlib.redirect_stdout(io.StringIO()):
                cli_main.init_project(args)

            for fname in ("tech-stack.md", "topology.md", "coding-rules.md", "business.md"):
                self.assertTrue(list(standards.glob(f"{fname}.*.bak")), fname)

            deploy_file = project / "DEPLOY.md"
            deploy_file.write_text("old deploy", encoding="utf-8")
            with patch.object(cli_main, "CURRENT_DIR", project), patch.object(
                cli_main, "TEMPLATES_DIR", templates
            ), contextlib.redirect_stdout(io.StringIO()):
                cli_main.deploy_assistant(Namespace(target="aws"))

            self.assertTrue(list(project.glob("DEPLOY.md.*.bak")))

    def test_init_missing_stack_template_fails_explicitly(self):
        repo_root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory(dir=repo_root) as temp_dir:
            root = Path(temp_dir)
            project = root / "project"
            project.mkdir()
            templates = _create_full_init_templates(root)

            args = Namespace(
                stack="nonexistent-stack",
                archetype="mvp",
                no_scan=True,
            )

            with patch.object(cli_main, "CURRENT_DIR", project), patch.object(
                cli_main, "PROJECT_RAPID_DIR", project / ".rapid-os"
            ), patch.object(
                cli_main, "CONFIG_FILE", project / ".rapid-os" / "config.json"
            ), patch.object(
                cli_main, "TEMPLATES_DIR", templates
            ), contextlib.redirect_stdout(io.StringIO()):
                with self.assertRaises(SystemExit) as ctx:
                    cli_main.init_project(args)
                self.assertEqual(ctx.exception.code, 1)

    def test_parser_normalizes_archetype_case_insensitively(self):
        parser = cli_main.create_parser()
        parsed_mvp = parser.parse_args(["init", "--archetype", "MVP"])
        parsed_corporate = parser.parse_args(["init", "--archetype", "Corporate"])
        self.assertEqual(parsed_mvp.archetype, "mvp")
        self.assertEqual(parsed_corporate.archetype, "corporate")

    def test_deploy_assistant_uses_neutral_prompt_and_generic_fallback(self):
        repo_root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory(dir=repo_root) as temp_dir:
            root = Path(temp_dir)
            project = root / "project"
            project.mkdir()
            templates = root / "templates"
            (templates / "deploy").mkdir(parents=True)
            (templates / "deploy" / "aws.md").write_text(
                "AWS Guide Content",
                encoding="utf-8",
            )

            recorded_prompts = []

            def fake_input(prompt=""):
                recorded_prompts.append(prompt)
                return "customtarget"

            with patch.object(cli_main, "CURRENT_DIR", project), patch.object(
                cli_main, "TEMPLATES_DIR", templates
            ), patch("builtins.input", fake_input), contextlib.redirect_stdout(
                io.StringIO()
            ):
                cli_main.deploy_assistant(Namespace(target=None))

            self.assertEqual(recorded_prompts, ["Target (e.g. aws): "])
            self.assertEqual(
                (project / "DEPLOY.md").read_text(encoding="utf-8"),
                "# DEPLOY customtarget\nDeploy to customtarget",
            )


if __name__ == "__main__":
    unittest.main()
