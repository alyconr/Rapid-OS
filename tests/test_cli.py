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


if __name__ == "__main__":
    unittest.main()
