import argparse
import os
import subprocess
import sys
import unittest
from pathlib import Path

from rapid_os.cli.main import create_parser


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
                "guide",
            },
        )

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


if __name__ == "__main__":
    unittest.main()
