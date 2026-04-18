import argparse
import json
import os
import subprocess
import sys
import unittest
from pathlib import Path

from rapid_os.cli.main import create_parser, parse_agent_selection


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


if __name__ == "__main__":
    unittest.main()
