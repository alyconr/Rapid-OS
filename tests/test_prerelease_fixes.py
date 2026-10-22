"""Fixes found before tagging v3.1.0: init defaults, hardening security standard, spec reuse, next/blocked."""

from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SPEC = {
    "title": "Harden register",
    "business_objective": "Reject unsafe input",
    "problem_statement": "register_user trusts its input",
    "acceptance_criteria": ["unsafe input is rejected"],
    "tasks": ["T001: Validate input"],
}
STACKS = ("docs-modern", "frontend-creative", "nodejs-ai", "python-ai", "python-api", "web-modern")


class ProjectCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)
        self.git("init", "-q")
        self.git("config", "user.email", "t@example.com")
        self.git("config", "user.name", "t")
        (self.root / "app.py").write_text("print('hi')\n", encoding="utf-8")
        self.git("add", "-A")
        self.git("commit", "-qm", "init")

    def git(self, *args):
        return subprocess.run(["git", *args], cwd=self.root, capture_output=True, text=True, check=True)

    def rapid(self, *args, stdin=None):
        env = {k: v for k, v in os.environ.items() if k not in ("CLAUDECODE", "CLAUDE_CODE_CHILD_SESSION")}
        env.update(PYTHONPATH=str(ROOT), PYTHONUTF8="1", PYTHONIOENCODING="utf-8")
        return subprocess.run(
            [sys.executable, str(ROOT / "rapid.py"), *args],
            cwd=self.root,
            input=stdin,
            stdin=None if stdin is not None else subprocess.DEVNULL,
            capture_output=True,
            text=True,
            encoding="utf-8",
            env=env,
            timeout=120,
        )

    def start(self, mode="hardening", spec=SPEC, *extra):
        return self.rapid("start", mode, "--spec-file", "-", "--json", *extra, stdin=json.dumps(spec))


class InitDefaultsTests(ProjectCase):
    def assert_valid(self):
        res = self.rapid("validate")
        self.assertEqual(res.returncode, 0, res.stdout + res.stderr)
        self.assertNotIn("RAPID402", res.stdout)
        self.assertNotIn("RAPID403", res.stdout)

    def test_yes_without_scanner_suggestion_in_a_python_project_without_pyproject(self):
        self.assertEqual(self.rapid("init", "--yes").returncode, 0)
        self.assert_valid()

    def test_yes_without_scanner_suggestion_in_a_python_project_with_pyproject(self):
        (self.root / "pyproject.toml").write_text('[project]\nname = "demo"\nversion = "0.1.0"\n', encoding="utf-8")
        self.assertEqual(self.rapid("init", "--yes").returncode, 0)
        self.assert_valid()

    def test_doc_site_only_with_docs_modern_and_docs_modern_always_with_doc_site(self):
        for stack in STACKS:
            with self.subTest(stack=stack):
                shutil_dir = self.root / ".rapid-os"
                if shutil_dir.exists():
                    import shutil

                    shutil.rmtree(shutil_dir)
                res = self.rapid("init", "--yes", "--no-scan", "--stack", stack)
                self.assertEqual(res.returncode, 0, res.stdout + res.stderr)
                topology = (self.root / ".rapid-os" / "standards" / "topology.md").read_text(encoding="utf-8").lower()
                is_doc_site = "doc-site" in topology or "documentation site" in topology
                self.assertEqual(is_doc_site, stack == "docs-modern", topology[:200])
                validate = self.rapid("validate")
                self.assertNotIn("RAPID402", validate.stdout)
                self.assertNotIn("RAPID403", validate.stdout)
                self.assertNotIn("RAPID404", validate.stdout)


class HardeningSecurityStandardTests(ProjectCase):
    def test_init_yes_creates_security_standard_and_hardening_start_creates_the_run(self):
        self.assertEqual(self.rapid("init", "--yes", "--test-command", "python -c pass").returncode, 0)
        security = self.root / ".rapid-os" / "standards" / "security.md"
        self.assertTrue(security.is_file())
        self.assertTrue(security.read_text(encoding="utf-8").strip())
        res = self.start()
        self.assertEqual(res.returncode, 0, res.stdout + res.stderr)
        self.assertIn("run_id", json.loads(res.stdout))

    def test_init_does_not_overwrite_an_existing_security_standard(self):
        standards = self.root / ".rapid-os" / "standards"
        standards.mkdir(parents=True)
        (standards / "security.md").write_text("# mine\n", encoding="utf-8")
        self.assertEqual(self.rapid("init", "--yes").returncode, 0)
        self.assertEqual((standards / "security.md").read_text(encoding="utf-8"), "# mine\n")

    def test_corporate_archetype_gets_the_baseline_at_level_l2(self):
        self.assertEqual(self.rapid("init", "--yes", "--archetype", "corporate").returncode, 0)
        text = (self.root / ".rapid-os" / "standards" / "security.md").read_text(encoding="utf-8")
        self.assertIn("ASVS 5.0.0 nivel L2", text)
        self.assertIn("SLSA 1.2 Build L2", text)

    def test_missing_security_standard_names_the_file_and_how_to_create_it(self):
        self.assertEqual(self.rapid("init", "--yes").returncode, 0)
        (self.root / ".rapid-os" / "standards" / "security.md").unlink()
        res = self.start()
        self.assertEqual(res.returncode, 1)
        out = res.stdout + res.stderr
        self.assertIn("RAPID1004", out)
        self.assertIn(".rapid-os/standards/security.md", out)
        self.assertIn("rapid init", out)
        self.assertNotIn("Traceback", out)


class SpecReuseTests(ProjectCase):
    def setUp(self):
        super().setUp()
        self.assertEqual(self.rapid("init", "--yes").returncode, 0)
        self.security = self.root / ".rapid-os" / "standards" / "security.md"
        self.saved = self.security.read_text(encoding="utf-8")
        self.security.unlink()

    def test_repeating_start_after_a_failure_reuses_the_identical_spec(self):
        first = self.start()
        self.assertEqual(first.returncode, 1)
        self.assertTrue((self.root / ".rapid-os" / "specs" / "harden-register").is_dir())
        self.security.write_text(self.saved, encoding="utf-8")
        second = self.start()
        self.assertEqual(second.returncode, 0, second.stdout + second.stderr)
        self.assertNotIn("Traceback", second.stdout + second.stderr)
        listed = self.rapid("spec", "list").stdout
        self.assertEqual(listed.count("harden-register"), 1)

    def test_a_different_content_under_the_same_identity_is_a_clear_error(self):
        self.assertEqual(self.start().returncode, 1)
        self.security.write_text(self.saved, encoding="utf-8")
        changed = dict(SPEC, business_objective="A different objective")
        res = self.start("hardening", changed)
        self.assertEqual(res.returncode, 1)
        out = res.stdout + res.stderr
        self.assertIn("RAPID1322", out)
        self.assertIn("rapid start hardening --spec harden-register", out)
        self.assertNotIn("Traceback", out)


class NextBlockedWithoutWorktreeTests(ProjectCase):
    def test_next_repeats_the_resume_worktree_command_when_the_session_has_no_workspace(self):
        self.assertEqual(self.rapid("init", "--yes", "--test-command", "python -c pass").returncode, 0)
        started = self.start()
        self.assertEqual(started.returncode, 0, started.stdout + started.stderr)
        start_action = json.loads(started.stdout)["action"]
        self.assertEqual(start_action["kind"], "blocked")
        self.assertEqual(start_action["command"], ["rapid", "start", "--resume", "--worktree"])

        nxt = self.rapid("next", "--json")
        self.assertEqual(nxt.returncode, 0, nxt.stdout + nxt.stderr)
        action = json.loads(nxt.stdout)["action"]
        self.assertEqual(action["kind"], "blocked")
        self.assertEqual(action["command"], ["rapid", "start", "--resume", "--worktree"])


class DocumentationTests(unittest.TestCase):
    def test_new_code_and_behaviour_are_documented(self):
        diagnostics = (ROOT / "docs" / "troubleshooting" / "diagnostics.md").read_text(encoding="utf-8")
        self.assertIn("`RAPID1322`", diagnostics)
        changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
        released = changelog[changelog.index("## [3.1.0] - "):changelog.index("## [3.0.0]")]
        fixed = released[released.index("### Fixed"):]
        for needle in ("RAPID402", "security.md", "RAPID1322", "author_spec", "--worktree"):
            self.assertIn(needle, fixed)
        cli = (ROOT / "docs" / "cli.md").read_text(encoding="utf-8")
        self.assertIn("RAPID1322", cli)
        self.assertIn("security.md", cli)


class PlaybookInstructionTests(unittest.TestCase):
    def test_feature_author_spec_points_at_start_not_spec_create(self):
        data = json.loads((ROOT / "templates" / "modes" / "feature.json").read_text(encoding="utf-8"))
        text = data["instructions"]["author_spec"]
        self.assertIn("rapid start <modo> --spec-file -", text)
        self.assertNotIn("rapid spec create", text)


if __name__ == "__main__":
    unittest.main()
