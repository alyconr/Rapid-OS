"""The onboarding and run findings of the rc.2 end-to-end run on Windows with Codex (H-40 to H-50)."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class Sandbox(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.base = Path(tmp.name)
        self.root = self.base / "project"
        self.root.mkdir()
        gitconfig = self.base / "gitconfig"
        gitconfig.write_text("[user]\n\tname = T\n\temail = t@example.com\n[init]\n\tdefaultBranch = main\n", encoding="utf-8")
        home = self.base / "home"
        home.mkdir()
        self.env = {
            **{k: v for k, v in os.environ.items() if k not in ("CLAUDECODE", "CLAUDE_CODE_CHILD_SESSION")},
            "GIT_CONFIG_GLOBAL": str(gitconfig),
            "GIT_CONFIG_NOSYSTEM": "1",
            "HOME": str(home),
            "USERPROFILE": str(home),
            "PYTHONPATH": str(ROOT),
            "PYTHONIOENCODING": "utf-8",
            "PYTHONDONTWRITEBYTECODE": "1",
        }

    def rapid(self, *args, stdin=None):
        return subprocess.run(
            [sys.executable, str(ROOT / "rapid.py"), *args],
            cwd=str(self.root),
            env=self.env,
            input=stdin,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=120,
        )

    def ok(self, *args, stdin=None):
        result = self.rapid(*args, stdin=stdin)
        self.assertEqual(result.returncode, 0, f"rapid {args}\n{result.stdout}\n{result.stderr}")
        return result

    def onboard(self, agents="claude", test_command="none", docs=("brief", "business", "data-model", "architecture", "deployment")):
        for step in (("stack", "python-fastapi"), ("topology", "backend-only"), ("archetype", "mvp"), ("ai", "no"),
                     ("agents", agents), ("test-command", test_command), ("services", "none")):
            self.ok("setup", "set", *step)
        for doc in docs:
            self.ok("setup", "doc", doc, "--skip")
        self.ok("setup", "finish")

    def doctor_codes(self):
        report = json.loads(self.rapid("doctor", "--json").stdout)
        return [d["code"] for d in report["diagnostics"]]


class DoctorOverlapTests(Sandbox):
    """H-40: RAPID1321 compares the agents chosen in the project, not every harness Rapid OS knows."""

    def test_a_project_with_only_codex_gets_no_warning(self):
        self.onboard(agents="codex")
        self.assertNotIn("RAPID1321", self.doctor_codes())

    def test_a_real_overlap_among_the_chosen_agents_still_warns(self):
        self.onboard(agents="cursor,codex")
        self.assertIn("RAPID1321", self.doctor_codes())

    def test_codex_and_antigravity_write_one_folder_so_nothing_overlaps(self):
        self.onboard(agents="codex,antigravity")
        self.assertNotIn("RAPID1321", self.doctor_codes())

    def test_without_a_configured_project_there_is_no_warning(self):
        self.assertNotIn("RAPID1321", self.doctor_codes())


if __name__ == "__main__":
    unittest.main()
