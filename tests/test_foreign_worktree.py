"""H-71: `rapid start` and `rapid next` refuse a linked worktree that is not the worktree of a run.

In the rc.3 end-to-end run on Windows, Codex created its own worktree (codex_tui/create_worktree) before
`rapid start hardening`. Rapid OS ran inside it: the run state stayed in Codex's worktree, the run's worktree
was created as its sibling, `rapid approve` in the person's checkout did not see the run and
`finish --merge` integrated there instead of in main.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from rapid_os.orchestration.workspace import (
    FOREIGN_WORKTREE_CODE,
    foreign_worktree_message,
    worktree_path_for,
)

ROOT = Path(__file__).resolve().parents[1]

SPEC = {
    "title": "Validate inputs",
    "business_objective": "Reject hostile input",
    "problem_statement": "add accepts anything",
    "acceptance_criteria": ["H001: invalid input is rejected (CWE-20)"],
    "findings": [{
        "id": "H001", "title": "Reject hostile input", "cwe": "CWE-20",
        "cvss_v4_vector": "CVSS:4.0/AV:N/AC:L/AT:N/PR:N/UI:P/VC:L/VI:L/VA:N/SC:N/SI:N/SA:N",
        "severity": "medium", "standard_ref": "CVSS v4.0",
    }],
    "tasks": ["T001: Add validation"],
}


def _norm(path: Path | str) -> str:
    return os.path.normcase(str(Path(path).resolve()))


class ForeignWorktreeTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        # The project lives one level below the temp dir so that sibling worktrees stay inside it.
        self.base = Path(self.temp_dir.name).resolve()
        self.project = self.base / "project"
        self.project.mkdir()
        self._git("init", "-q")
        self._git("config", "user.name", "Rapid Dev")
        self._git("config", "user.email", "dev@example.com")
        (self.project / "m.py").write_text("def add(a, b):\n    return a + b\n", encoding="utf-8")
        tests = self.project / "tests"
        tests.mkdir()
        (tests / "__init__.py").write_text("", encoding="utf-8")
        (tests / "test_m.py").write_text(
            "import unittest\nimport m\n\n\nclass T(unittest.TestCase):\n"
            "    def test_add(self):\n        self.assertEqual(m.add(1, 2), 3)\n",
            encoding="utf-8",
        )
        self._git("add", ".")
        self._git("commit", "-qm", "baseline")
        test_cmd = f'"{sys.executable}" -m unittest discover -s tests -t .'
        res = self._rapid("init", "--yes", "--no-scan", "--archetype", "corporate", "--test-command", test_cmd)
        self.assertEqual(res.returncode, 0, res.stderr)
        # As in the e2e project: .rapid-os/ is committed, so a harness worktree carries a copy of it.
        self._git("add", "-A")
        self._git("commit", "-qm", "rapid init")
        self.foreign = self.base / "codex-wt"
        self._git("worktree", "add", "-q", "-b", "codex/task", str(self.foreign))

    def tearDown(self):
        subprocess.run(["git", "worktree", "prune"], cwd=str(self.project), capture_output=True, check=False)
        self.temp_dir.cleanup()

    def _git(self, *args, cwd=None):
        return subprocess.run(
            ["git", *args], cwd=str(cwd or self.project), check=True, capture_output=True, text=True
        )

    def _rapid(self, *args, cwd=None, input_str=None):
        env = {k: v for k, v in os.environ.items() if k not in ("CLAUDECODE", "CLAUDE_CODE_CHILD_SESSION")}
        env["PYTHONPATH"] = str(ROOT)
        return subprocess.run(
            [sys.executable, "-m", "rapid_os.cli.main", *args],
            cwd=str(cwd or self.project),
            input=input_str,
            capture_output=True,
            text=True,
            encoding="utf-8",
            env=env,
        )

    def _assert_refused(self, res):
        self.assertEqual(res.returncode, 1, res.stdout + res.stderr)
        self.assertIn(FOREIGN_WORKTREE_CODE, res.stderr)
        # The message names the main checkout (first line of `git worktree list`) to run from.
        self.assertIn(_norm(self.project), os.path.normcase(res.stderr))

    def test_start_in_a_foreign_worktree_is_refused_naming_the_main_checkout(self):
        res = self._rapid("start", "hardening", "--spec-file", "-", "--json", cwd=self.foreign, input_str=json.dumps(SPEC))
        self._assert_refused(res)
        # Nothing was written: no session in either checkout, no sibling worktree of a run.
        self.assertFalse((self.foreign / ".rapid-os" / "session.json").exists())
        self.assertFalse((self.project / ".rapid-os" / "session.json").exists())
        listed = self._git("worktree", "list", "--porcelain").stdout
        self.assertNotIn("rapid/", listed)

        resumed = self._rapid("start", "--resume", "--worktree", "--json", cwd=self.foreign)
        self._assert_refused(resumed)

    def test_next_in_a_foreign_worktree_is_refused_also_from_a_subfolder(self):
        self._assert_refused(self._rapid("next", "--json", cwd=self.foreign))
        self._assert_refused(self._rapid("next", cwd=self.foreign / "tests"))

    def test_main_checkout_and_run_worktree_work_as_today(self):
        started = self._rapid("start", "hardening", "--spec-file", "-", "--json", input_str=json.dumps(SPEC))
        self.assertEqual(started.returncode, 0, started.stderr)
        action = json.loads(started.stdout)["action"]
        self.assertEqual(action["command"], ["rapid", "start", "--resume", "--worktree"])

        resumed = self._rapid("start", "--resume", "--worktree", "--json")
        self.assertEqual(resumed.returncode, 0, resumed.stderr)
        session = json.loads((self.project / ".rapid-os" / "session.json").read_text(encoding="utf-8"))
        workspace = Path(session["workspace_path"])
        self.assertEqual(_norm(workspace), _norm(worktree_path_for(self.project, session["active_run_id"])))

        from_main = self._rapid("next", "--json")
        self.assertEqual(from_main.returncode, 0, from_main.stderr)
        self.assertEqual(json.loads(from_main.stdout)["run_id"], session["active_run_id"])

        # From the run's own worktree the commands are not refused (they behave as before this guard).
        from_run = self._rapid("next", "--json", cwd=workspace)
        self.assertEqual(from_run.returncode, 0, from_run.stderr)
        self.assertNotIn(FOREIGN_WORKTREE_CODE, from_run.stderr)
        self.assertIsNone(foreign_worktree_message(workspace))

        # A harness worktree is still refused while the run is active.
        self._assert_refused(self._rapid("next", "--json", cwd=self.foreign))

    def test_a_run_worktree_is_recognized_by_its_path_and_branch_without_a_session(self):
        # e.g. after `rapid abort`, which keeps the run's worktree.
        run_worktree = worktree_path_for(self.project, "old-run-001")
        self._git("worktree", "add", "-q", "-b", "rapid/old-run-001", str(run_worktree))
        self.assertIsNone(foreign_worktree_message(run_worktree))

        # The same branch somewhere else is not a run worktree.
        elsewhere = self.base / "elsewhere"
        self._git("worktree", "add", "-q", "-b", "rapid/other-run-001", str(elsewhere))
        self.assertIn(FOREIGN_WORKTREE_CODE, foreign_worktree_message(elsewhere) or "")

    def test_the_temporary_worktree_of_a_reproduction_check_is_not_foreign(self):
        repro = self.base / "rapid-repro-abc123" / "baseline"
        self._git("worktree", "add", "-q", "--detach", str(repro), "HEAD")
        self.assertIsNone(foreign_worktree_message(repro))

    def test_no_message_in_the_main_checkout_or_outside_git(self):
        self.assertIsNone(foreign_worktree_message(self.project))
        self.assertIsNone(foreign_worktree_message(self.project / "tests"))
        outside = self.base / "plain"
        outside.mkdir()
        self.assertIsNone(foreign_worktree_message(outside))


if __name__ == "__main__":
    unittest.main()
