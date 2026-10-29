"""H-28 and H-27: a refactor cannot lose its tests unnoticed, and code cannot change between the last check and
the approval without a new check."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from rapid_os.orchestration import tree_fingerprint
from rapid_os.orchestration.check import parse_test_summary

ROOT = Path(__file__).resolve().parents[1]
TEST_TEMPLATE = (
    "import unittest\n\n\nclass T(unittest.TestCase):\n    def test_1(self):\n        self.assertTrue(True)\n\n"
    "    def test_2(self):\n        self.assertTrue(True)\n"
)
UNITTEST = [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-t", "."]
REFACTOR_SPEC = {
    "title": "Limpiar", "business_objective": "Separar", "problem_statement": "Acoplado",
    "acceptance_criteria": ["mismo comportamiento"], "tasks": ["T001: Limpiar", "T002: Verificar"],
}
FEATURE_SPEC = {
    "title": "Agendar citas", "mode": "feature", "business_objective": "Agendar", "problem_statement": "No hay agenda",
    "scope": ["citas"], "acceptance_criteria": ["se agenda"], "tasks": ["T001: Crear algo"],
}


class ParseTestSummaryTests(unittest.TestCase):
    def test_every_runner(self):
        cases = {
            "pytest -q": ("41 passed in 0.3s", (41, 0, 0)),
            "pytest": ("=== 3 failed, 5 passed, 1 skipped in 2s ===", (5, 3, 1)),
            "pytest warnings": ("41 passed, 2 warnings in 0.4s", (41, 0, 0)),
            "unittest": ("Ran 12 tests in 0.1s\n\nOK", (12, 0, 0)),
            "unittest failed": ("Ran 12 tests in 0.1s\n\nFAILED (failures=2, errors=1)", (9, 3, 0)),
            "unittest skipped": ("Ran 12 tests in 0.1s\n\nOK (skipped=2)", (10, 0, 2)),
            "vitest": (" Test Files  2 passed (2)\n      Tests  12 passed (12)", (12, 0, 0)),
            "jest": ("Tests:       1 failed, 11 passed, 12 total", (11, 1, 0)),
            "cargo": ("test result: ok. 10 passed; 0 failed; 1 ignored;\ntest result: ok. 2 passed; 0 failed; 0 ignored;", (12, 0, 1)),
            "go test -v": ("--- PASS: TestA (0.00s)\n--- FAIL: TestB (0.00s)\n    --- SKIP: TestC (0.00s)\n", (1, 1, 1)),
        }
        for name, (output, (passed, failed, skipped)) in cases.items():
            with self.subTest(runner=name):
                self.assertEqual(parse_test_summary(output), {"passed": passed, "failed": failed, "skipped": skipped})

    def test_no_summary_is_none_not_zero(self):
        for output in ("", "hello", "ok  \tpkg\t0.1s\n", "Build succeeded"):
            with self.subTest(output=output):
                self.assertIsNone(parse_test_summary(output))


class Fingerprint(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)
        for argv in (("init", "-q"), ("config", "user.name", "T"), ("config", "user.email", "t@example.com")):
            subprocess.run(["git", *argv], cwd=self.root, check=True, capture_output=True)
        (self.root / "app.py").write_text("x = 1\n", encoding="utf-8")
        (self.root / "test_app.py").write_text("t = 1\n", encoding="utf-8")
        subprocess.run(["git", "add", "-A"], cwd=self.root, check=True, capture_output=True)
        subprocess.run(["git", "commit", "-q", "-m", "base"], cwd=self.root, check=True, capture_output=True)

    def test_a_clean_tree_is_empty_and_ignores_rapid_os_and_tool_artifacts(self):
        (self.root / ".rapid-os").mkdir()
        (self.root / ".rapid-os" / "session.json").write_text("{}", encoding="utf-8")
        (self.root / "__pycache__").mkdir()
        (self.root / "__pycache__" / "app.cpython-312.pyc").write_bytes(b"\0")
        self.assertEqual(tree_fingerprint.working_tree_snapshot(self.root), {})

    def test_edits_deletions_and_new_files_change_the_digest_and_are_named(self):
        clean = tree_fingerprint.working_tree_snapshot(self.root)
        (self.root / "app.py").write_text("x = 2\n", encoding="utf-8")
        (self.root / "test_app.py").unlink()
        (self.root / "nuevo.py").write_text("n = 1\n", encoding="utf-8")
        now = tree_fingerprint.working_tree_snapshot(self.root)
        self.assertNotEqual(tree_fingerprint.digest(clean), tree_fingerprint.digest(now))
        self.assertEqual(tree_fingerprint.changed_files(clean, now), ["app.py", "nuevo.py", "test_app.py"])
        self.assertEqual(now["test_app.py"], tree_fingerprint.MISSING)

    def test_the_same_tree_has_the_same_digest(self):
        (self.root / "app.py").write_text("x = 2\n", encoding="utf-8")
        first = tree_fingerprint.working_tree_snapshot(self.root)
        second = tree_fingerprint.working_tree_snapshot(self.root)
        self.assertEqual(tree_fingerprint.digest(first), tree_fingerprint.digest(second))

    def test_outside_git_there_is_no_fingerprint(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertIsNone(tree_fingerprint.working_tree_snapshot(tmp))

    def test_the_map_is_stored_by_digest_and_read_back(self):
        snapshot = {"a.py": "1" * 64}
        with tempfile.TemporaryDirectory() as tmp:
            digest = tree_fingerprint.save_snapshot(tmp, "run-1", snapshot)
            self.assertEqual(tree_fingerprint.load_snapshot(tmp, "run-1", digest), snapshot)
            self.assertIsNone(tree_fingerprint.load_snapshot(tmp, "run-1", "0" * 64))


class Project(unittest.TestCase):
    """A python-fastapi backend-only project with 3 test files (6 tests) whose configured test command is not
    the one the agent uses (as `pytest` and `uv run --directory backend pytest -q` in the e2e)."""

    CONFIGURED = "pytest-no-instalado"

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        base = Path(self._tmp.name)
        self.root = base / "project"
        (self.root / "tests").mkdir(parents=True)
        gitconfig = base / "gitconfig"
        gitconfig.write_text("[user]\n\tname = T\n\temail = t@example.com\n[init]\n\tdefaultBranch = main\n", encoding="utf-8")
        self.env = {
            **{k: v for k, v in os.environ.items() if k not in ("CLAUDECODE", "CLAUDE_CODE_CHILD_SESSION")},
            "GIT_CONFIG_GLOBAL": str(gitconfig), "GIT_CONFIG_NOSYSTEM": "1",
            "PYTHONPATH": str(ROOT), "PYTHONIOENCODING": "utf-8", "PYTHONDONTWRITEBYTECODE": "1",
        }
        subprocess.run(["git", "init", "-q"], cwd=self.root, env=self.env, check=True, capture_output=True)
        (self.root / "tests" / "__init__.py").write_text("", encoding="utf-8")
        for name in "abc":
            (self.root / "tests" / f"test_{name}.py").write_text(TEST_TEMPLATE, encoding="utf-8")
        for step in (("stack", "python-fastapi"), ("topology", "backend-only"), ("archetype", "mvp"), ("ai", "no"),
                     ("agents", "claude"), ("test-command", self.CONFIGURED), ("services", "none")):
            self.ok("setup", "set", *step)
        for doc in ("brief", "business", "data-model", "architecture", "deployment"):
            self.ok("setup", "doc", doc, "--skip")
        self.ok("setup", "finish")
        subprocess.run(["git", "add", "-A"], cwd=self.root, env=self.env, check=True, capture_output=True)
        subprocess.run(["git", "commit", "-q", "-m", "base"], cwd=self.root, env=self.env, check=True, capture_output=True)

    def rapid(self, *argv, stdin=None):
        return subprocess.run(
            [sys.executable, "-m", "rapid_os.cli.main", *argv], cwd=self.root, capture_output=True, text=True,
            encoding="utf-8", env=self.env, input=stdin,
        )

    def ok(self, *argv, stdin=None):
        result = self.rapid(*argv, stdin=stdin)
        self.assertEqual(result.returncode, 0, f"{argv}: {result.stdout}{result.stderr}")
        return result

    def start(self, mode, spec):
        self.ok("start", mode, "--spec-file", "-", "--json", stdin=json.dumps(spec))

    def next(self):
        return json.loads(self.ok("next", "--json").stdout)

    def evidence(self):
        records = sorted((self.root / ".rapid-os" / "evidence").glob("*/records/E*.json"))
        return [json.loads(path.read_text("utf-8")) for path in records]


class H28RefactorProtectionTests(Project):
    def baseline_with_another_argv(self):
        self.start("refactor", REFACTOR_SPEC)
        self.ok("check", "--gate", "gate.baseline", "--", *UNITTEST, "-v")
        self.ok("start", "--resume")
        self.ok("task", "start", "T001")

    def test_a_baseline_with_another_argv_is_still_a_counted_test_result(self):
        self.baseline_with_another_argv()
        baseline = next(e for e in self.evidence() if "gate.baseline" in e["gate_ids"])
        self.assertEqual(baseline["kind"], "test_result")
        self.assertEqual(baseline["payload"]["passed"], 6)
        self.assertTrue(baseline["payload"]["command"].endswith("-t . -v"))

    def test_the_exact_reproduction_ends_in_blocked_refactor_lost_test_coverage(self):
        self.baseline_with_another_argv()
        (self.root / "tests" / "test_c.py").unlink()  # 6 passed -> 4
        checked = self.ok("check", "--task", "T001", "--", *UNITTEST, "-q")
        self.assertIn("Tests: 4 passed, 0 failed, 0 skipped", checked.stdout)
        action = self.next()["action"]
        self.assertEqual(action["kind"], "blocked")
        self.assertIn("Refactor lost test coverage: baseline had 6 passed, the latest test run has 4 passed", action["instructions"])

    def test_rapid_check_always_prints_the_count_of_a_test_run(self):
        self.start("refactor", REFACTOR_SPEC)
        out = self.ok("check", "--gate", "gate.baseline", "--", *UNITTEST).stdout
        self.assertIn("Tests: 6 passed, 0 failed, 0 skipped", out)

    def test_a_check_without_a_readable_summary_says_so_and_blocks_the_refactor(self):
        self.start("refactor", REFACTOR_SPEC)
        result = self.ok("check", "--gate", "gate.baseline", "--", sys.executable, "-c", "print('ok')")
        self.assertIn("No se pudo leer un conteo de tests", result.stderr)
        self.assertEqual(next(e for e in self.evidence() if "gate.baseline" in e["gate_ids"])["kind"], "command_result")
        self.ok("start", "--resume")
        action = self.next()["action"]
        self.assertEqual(action["kind"], "blocked")
        self.assertIn("no baseline with a test count", action["instructions"])
        self.assertEqual(action["command"][:5], ["rapid", "check", "--gate", "gate.baseline", "--"])

    def test_repeating_the_baseline_with_a_countable_command_unblocks(self):
        self.start("refactor", REFACTOR_SPEC)
        self.ok("check", "--gate", "gate.baseline", "--", sys.executable, "-c", "print('ok')")
        self.ok("start", "--resume")
        self.assertEqual(self.next()["action"]["kind"], "blocked")
        self.ok("check", "--gate", "gate.baseline", "--", *UNITTEST)
        self.assertNotEqual(self.next()["action"]["kind"], "blocked")

    def test_an_explicit_command_kind_is_respected(self):
        self.start("refactor", REFACTOR_SPEC)
        self.ok("check", "--gate", "gate.baseline", "--kind", "command", "--", *UNITTEST)
        self.assertEqual(next(e for e in self.evidence() if "gate.baseline" in e["gate_ids"])["kind"], "command_result")

    def test_different_commands_for_the_baseline_and_the_latest_check_are_warned_in_next(self):
        self.baseline_with_another_argv()
        self.ok("check", "--task", "T001", "--", *UNITTEST, "-q")  # same 6 tests: not a regression
        data = self.next()
        self.assertNotEqual(data["action"]["kind"], "blocked")
        warning = " ".join(data.get("notes", []))
        self.assertIn("La baseline se grabó con", warning)
        self.assertIn("-v", warning)
        self.assertIn("-q", warning)

    def test_the_same_command_has_no_warning(self):
        self.start("refactor", REFACTOR_SPEC)
        self.ok("check", "--gate", "gate.baseline", "--", *UNITTEST)
        self.ok("start", "--resume")
        self.ok("task", "start", "T001")
        self.ok("check", "--task", "T001", "--", *UNITTEST)
        self.assertEqual(self.next().get("notes", []), [])

    def test_a_feature_run_is_not_subject_to_the_refactor_guard(self):
        self.start("feature", FEATURE_SPEC)
        self.ok("check", "--gate", "gate.baseline", "--", sys.executable, "-c", "print('ok')")
        self.ok("start", "--resume")
        self.assertNotEqual(self.next()["action"]["kind"], "blocked")

    def test_finish_warns_about_mixed_commands(self):
        from rapid_os.orchestration.lifecycle import verification_warning

        self.baseline_with_another_argv()
        self.ok("check", "--task", "T001", "--", *UNITTEST, "-q")
        warning = verification_warning(self.root, self.root / ".rapid-os")
        self.assertIn("La baseline se grabó con", warning)


class H27ChangedAfterTheLastCheckTests(Project):
    CONFIGURED = f'"{sys.executable}" -m unittest discover -s tests -t .'

    def run_to_approval(self):
        """Drive a feature run like an agent until a person has to approve; returns the gate id."""
        self.start("feature", FEATURE_SPEC)
        for _ in range(30):
            action = self.next()["action"]
            if action["kind"] == "await_human_approval":
                return action["gate_ids"][0]
            if action["kind"] == "implement_task":
                (self.root / "app.py").write_text("x = 1\n", encoding="utf-8")
            for key in ("command", "after"):
                if action.get(key):
                    self.ok(*action[key][1:])
        self.fail("the run never reached a human gate")

    def approve(self, gate):
        code = (
            "import sys, unittest.mock as mock, rapid_os.cli.main as m; "
            f"sys.argv = ['rapid', 'approve', '{gate}']; "
            "mock.patch('sys.stdin.isatty', return_value=True).start(); "
            "mock.patch('rapid_os.orchestration.lifecycle.stdin_is_windows_nul', return_value=False).start(); "
            "mock.patch('rapid_os.orchestration.lifecycle.read_ancestry', "
            "return_value=__import__('rapid_os.core.ancestry', fromlist=['x']).AncestryResult(())).start(); "
            f"mock.patch('builtins.input', return_value='aprobar {gate}').start(); sys.exit(m.main())"
        )
        return subprocess.run([sys.executable, "-c", code], cwd=self.root, capture_output=True, text=True, env=self.env)

    def test_every_check_records_the_tree_it_saw(self):
        self.start("feature", FEATURE_SPEC)
        self.ok("check", "--gate", "gate.baseline", "--", *UNITTEST)
        evidence = self.evidence()
        self.assertTrue(all(len(e["payload"]["tree"]) == 64 for e in evidence if e["kind"] in ("test_result", "command_result")))
        digest = next(e["payload"]["tree"] for e in evidence if "gate.baseline" in e["gate_ids"])
        tree = self.root / ".rapid-os" / "scratch" / "trees"
        self.assertTrue(list(tree.glob(f"*/{digest}.json")))

    def test_code_changed_after_the_last_check_blocks_next_approve_and_finish(self):
        gate = self.run_to_approval()
        # Untouched since the last check: the person can approve.
        self.assertEqual(self.next()["action"]["kind"], "await_human_approval")
        # A test is deleted and nothing checks it.
        (self.root / "tests" / "test_c.py").unlink()
        (self.root / "app.py").write_text("x = 99\n", encoding="utf-8")
        action = self.next()["action"]
        self.assertEqual(action["kind"], "verify")
        self.assertIn("RAPID1423", action["instructions"])
        self.assertIn("tests/test_c.py", action["instructions"])
        self.assertIn("app.py", action["instructions"])
        self.assertEqual(action["command"][:5], ["rapid", "check", "--gate", "gate.tests", "--"])
        refused = self.approve(gate)
        self.assertEqual(refused.returncode, 1, refused.stdout)
        self.assertIn("RAPID1423", refused.stderr)
        self.assertIn("tests/test_c.py", refused.stderr)
        finished = self.rapid("finish", "--json")  # a human gate is still pending: no verdict either way
        self.assertNotIn('"verdict"', finished.stdout)
        # A new check on the changed code lifts all three.
        self.ok(*action["command"][1:])
        self.assertEqual(self.next()["action"]["kind"], "await_human_approval")
        approved = self.approve(gate)
        self.assertEqual(approved.returncode, 0, approved.stderr)
        done = self.rapid("finish", "--json")
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertEqual(json.loads(done.stdout)["verdict"], "pass")

    def test_a_change_after_approving_blocks_finish(self):
        gate = self.run_to_approval()
        self.assertEqual(self.approve(gate).returncode, 0)
        (self.root / "app.py").write_text("x = 'despues'\n", encoding="utf-8")
        finished = self.rapid("finish", "--json")
        self.assertEqual(finished.returncode, 1)
        self.assertIn("app.py", finished.stderr)

    def test_a_rejection_does_not_need_a_new_check(self):
        gate = self.run_to_approval()
        (self.root / "app.py").write_text("x = 5\n", encoding="utf-8")
        code = (
            "import sys, unittest.mock as mock, rapid_os.cli.main as m; "
            f"sys.argv = ['rapid', 'approve', '{gate}', '--reject', '--reason', 'no']; "
            "mock.patch('sys.stdin.isatty', return_value=True).start(); "
            "mock.patch('rapid_os.orchestration.lifecycle.stdin_is_windows_nul', return_value=False).start(); "
            "mock.patch('rapid_os.orchestration.lifecycle.read_ancestry', "
            "return_value=__import__('rapid_os.core.ancestry', fromlist=['x']).AncestryResult(())).start(); "
            f"mock.patch('builtins.input', return_value='rechazar {gate}').start(); sys.exit(m.main())"
        )
        result = subprocess.run([sys.executable, "-c", code], cwd=self.root, capture_output=True, text=True, env=self.env)
        self.assertEqual(result.returncode, 0, result.stderr)


class OldEvidenceTests(unittest.TestCase):
    def test_evidence_without_a_tree_or_command_is_not_judged(self):
        from rapid_os.domain.evidence import EvidenceKind, validate_evidence_payload

        old = {"suite": "pytest", "exit_code": 0, "passed": 3, "failed": 0, "skipped": 0}
        self.assertEqual(validate_evidence_payload(EvidenceKind.TEST_RESULT, old), old)
        new = {**old, "command": "uv run pytest -q", "tree": "a" * 64}
        self.assertEqual(validate_evidence_payload(EvidenceKind.TEST_RESULT, new), new)
        with self.assertRaises(Exception):
            validate_evidence_payload(EvidenceKind.TEST_RESULT, {**old, "tree": "short"})


if __name__ == "__main__":
    unittest.main()
