"""A brand-new repository: scaffold task instead of a baseline, and only `feature` can start."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from rapid_os.domain.execution import CANONICAL_EXECUTION_CONTRACT_KEYS, ExecutionContract
from rapid_os.domain.scanner import is_empty_repository
from rapid_os.orchestration.lifecycle import (
    SCAFFOLD_TASK_TEXT,
    has_scaffold_task,
    scaffold_notes,
    with_scaffold_task,
)

ROOT = Path(__file__).resolve().parents[1]
SPEC = {
    "title": "Primera funcionalidad", "mode": "feature", "business_objective": "o",
    "problem_statement": "p", "scope": ["s"], "acceptance_criteria": ["c"],
    "tasks": ["T001: Hacer A", "T002: Hacer B"],
}
TEST_COMMAND = f'"{sys.executable}" -m unittest discover -s tests -t .'
SMOKE_TEST = "import unittest\n\nclass Smoke(unittest.TestCase):\n    def test_smoke(self):\n        self.assertTrue(True)\n"


def rapid(cwd, *argv, stdin=None):
    env = {
        **{k: v for k, v in os.environ.items() if k not in ("CLAUDECODE", "CLAUDE_CODE_CHILD_SESSION")},
        "PYTHONPATH": str(ROOT),
        "PYTHONIOENCODING": "utf-8",
    }
    return subprocess.run(
        [sys.executable, "-m", "rapid_os.cli.main", *argv],
        cwd=cwd, input=stdin, capture_output=True, text=True, encoding="utf-8", env=env,
    )


def git_repo(root: Path):
    for argv in (("init", "-q"), ("config", "user.name", "Rapid"), ("config", "user.email", "r@example.com")):
        subprocess.run(["git", *argv], cwd=root, check=True, capture_output=True)


def commit_all(root: Path):
    subprocess.run(["git", "add", "-A"], cwd=root, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-q", "-m", "base", "--allow-empty"], cwd=root, check=True, capture_output=True)


def contract_of(root: Path) -> dict:
    path = next((root / ".rapid-os" / "runs").glob("*/contract.json"))
    return json.loads(path.read_text(encoding="utf-8"))


class IsEmptyRepositoryTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)

    def write(self, relative: str, text: str = "x\n"):
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    def test_nothing_or_only_configuration_and_docs_is_empty(self):
        self.assertTrue(is_empty_repository(self.root))
        for relative in ("README.md", "pyproject.toml", ".gitignore", "docs/ARCHITECTURE.md",
                         ".rapid-os/config.json", ".claude/skills/x/SKILL.md", "package.json"):
            self.write(relative, "{}\n" if relative.endswith(".json") else "x\n")
        self.assertTrue(is_empty_repository(self.root))

    def test_source_outside_docs_and_hidden_folders_is_not_empty(self):
        for relative in ("app.py", "src/main.ts", "cmd/server.go", "lib/a.rs"):
            with self.subTest(relative=relative):
                fresh = tempfile.TemporaryDirectory()
                self.addCleanup(fresh.cleanup)
                path = Path(fresh.name) / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("x\n", encoding="utf-8")
                self.assertFalse(is_empty_repository(Path(fresh.name)))

    def test_source_inside_docs_hidden_or_ignored_folders_does_not_count(self):
        for relative in ("docs/example.py", ".rapid-os/scratch/x.py", ".github/scripts/ci.py", "node_modules/p/index.js"):
            self.write(relative)
        self.assertTrue(is_empty_repository(self.root))

    def test_tests_or_a_test_runner_config_make_it_non_empty(self):
        self.write("tests/placeholder.txt")
        self.assertFalse(is_empty_repository(self.root))
        other = tempfile.TemporaryDirectory()
        self.addCleanup(other.cleanup)
        (Path(other.name) / "pytest.ini").write_text("[pytest]\n", encoding="utf-8")
        self.assertFalse(is_empty_repository(Path(other.name)))


class ScaffoldTaskTests(unittest.TestCase):
    def test_the_scaffold_goes_first_and_written_numbers_follow_the_contract_ids(self):
        tasks = with_scaffold_task(["T001: Hacer A", "T002 - Hacer B", "Sin número"])
        self.assertEqual(
            tasks,
            [f"T001: {SCAFFOLD_TASK_TEXT}", "T002: Hacer A", "T003: Hacer B", "Sin número"],
        )
        self.assertTrue(has_scaffold_task(tasks))

    def test_it_is_idempotent(self):
        once = with_scaffold_task(["T001: Hacer A"])
        self.assertEqual(with_scaffold_task(once), once)

    def test_the_note_maps_every_renumbered_task(self):
        written = ["T001: Registro", "T002: Login", "Sin número"]
        (note,) = scaffold_notes(written, with_scaffold_task(written))
        self.assertIn("T001", note)
        self.assertIn(SCAFFOLD_TASK_TEXT, note)
        self.assertIn("T001→T002, T002→T003", note)

    def test_the_note_without_written_numbers_only_announces_the_scaffold(self):
        written = ["Registro", "Login"]
        (note,) = scaffold_notes(written, with_scaffold_task(written))
        self.assertIn(SCAFFOLD_TASK_TEXT, note)
        self.assertNotIn("renumeraron", note)

    def test_an_empty_task_list_becomes_just_the_scaffold(self):
        self.assertEqual(with_scaffold_task([]), [f"T001: {SCAFFOLD_TASK_TEXT}"])


class StartInADifferentRepositoryTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)
        git_repo(self.root)

    def init(self):
        result = rapid(self.root, "init", "--yes", "--skip-docs", "--test-command", TEST_COMMAND)
        self.assertEqual(result.returncode, 0, result.stderr)

    def start(self, spec=SPEC, mode="feature"):
        return rapid(self.root, "start", mode, "--spec-file", "-", "--json", stdin=json.dumps({**spec, "mode": mode}))

    def test_empty_repository_gets_the_scaffold_task_and_no_baseline(self):
        commit_all(self.root)
        self.init()
        started = self.start()
        self.assertEqual(started.returncode, 0, started.stderr)
        self.assertEqual(json.loads(started.stdout)["action"]["kind"], "implement_task")

        contract = contract_of(self.root)
        self.assertEqual(contract["baseline_waived"], "empty_repository")
        self.assertNotIn("gate.baseline", [g["id"] for g in contract["gates"]])
        self.assertNotIn("gate.baseline", [g["id"] for g in contract["decision"]["gates"]])
        self.assertEqual(
            [t["description"] for t in contract["tasks"]],
            [f"T001: {SCAFFOLD_TASK_TEXT}", "T002: Hacer A", "T003: Hacer B"],
        )
        self.assertEqual([t["id"] for t in contract["tasks"]], ["T001", "T002", "T003"])
        # The contract still verifies (digest and consistency).
        ExecutionContract.from_dict(contract)

        # `rapid start` says what changed in the task list the agent wrote.
        notes = json.loads(started.stdout)["notes"]
        self.assertEqual(len(notes), 1)
        self.assertIn("T001→T002, T002→T003", notes[0])
        self.assertIn(SCAFFOLD_TASK_TEXT, notes[0])

        status = rapid(self.root, "status")
        self.assertIn("Sin baseline: proyecto nuevo", status.stdout)
        as_json = json.loads(rapid(self.root, "status", "--json").stdout)
        self.assertEqual(as_json["run"]["baseline_waived"], "empty_repository")
        self.assertEqual(as_json["run"]["status"], "active")

    def test_repository_with_code_but_no_tests_keeps_the_baseline(self):
        (self.root / "app.py").write_text("print('hi')\n", encoding="utf-8")
        commit_all(self.root)
        self.init()
        started = self.start()
        self.assertEqual(started.returncode, 0, started.stderr)

        contract = contract_of(self.root)
        self.assertNotIn("baseline_waived", contract)
        self.assertIn("gate.baseline", [g["id"] for g in contract["gates"]])
        self.assertEqual([t["description"] for t in contract["tasks"]], ["T001: Hacer A", "T002: Hacer B"])
        self.assertNotIn("Sin baseline", rapid(self.root, "status").stdout)
        self.assertNotIn("notes", json.loads(started.stdout))

    def test_repository_with_tests_has_the_contract_it_always_had(self):
        (self.root / "tests").mkdir()
        (self.root / "tests" / "__init__.py").write_text("", encoding="utf-8")
        (self.root / "tests" / "test_smoke.py").write_text(SMOKE_TEST, encoding="utf-8")
        commit_all(self.root)
        self.init()
        self.assertEqual(self.start().returncode, 0)

        contract = contract_of(self.root)
        self.assertEqual(set(contract), CANONICAL_EXECUTION_CONTRACT_KEYS)
        self.assertIn("gate.baseline", [g["id"] for g in contract["gates"]])
        self.assertEqual([t["description"] for t in contract["tasks"]], ["T001: Hacer A", "T002: Hacer B"])

    def test_modes_that_need_code_are_refused_with_rapid1413(self):
        commit_all(self.root)
        self.init()
        for mode, verb in (("bugfix", "arreglar"), ("refactor", "refactorizar"), ("hardening", "endurecer")):
            with self.subTest(mode=mode):
                result = self.start(mode=mode)
                self.assertEqual(result.returncode, 1)
                self.assertIn(f"RAPID1413 No hay código que {verb}; usa /rapid-feature", result.stderr)
                self.assertNotIn("Traceback", result.stderr)
                self.assertFalse((self.root / ".rapid-os" / "runs").exists())
        # Without a spec it is refused too, and research is not.
        self.assertEqual(rapid(self.root, "start", "bugfix").returncode, 1)
        self.assertEqual(rapid(self.root, "start", "research", "--json").returncode, 0)

    def test_the_scaffold_run_can_be_finished_without_a_baseline(self):
        commit_all(self.root)
        self.init()
        self.assertEqual(self.start(spec={**SPEC, "tasks": ["T001: Hacer A"]}).returncode, 0)
        gate = None
        for _ in range(25):
            output = json.loads(rapid(self.root, "next", "--json").stdout)
            action = output["action"]
            if action["kind"] == "await_human_approval":
                gate = action["gate_ids"][0]
                break
            if action["kind"] == "implement_task" and action["task_id"] == "T001":
                (self.root / "tests").mkdir(exist_ok=True)
                (self.root / "tests" / "__init__.py").write_text("", encoding="utf-8")
                (self.root / "tests" / "test_smoke.py").write_text(SMOKE_TEST, encoding="utf-8")
            for key in ("command", "after"):
                if action.get(key):
                    result = rapid(self.root, *action[key][1:])
                    self.assertEqual(result.returncode, 0, f"{action[key]}: {result.stderr}{result.stdout}")
        self.assertIsNotNone(gate)
        approve = (
            "import sys, unittest.mock as mock, rapid_os.cli.main as m; "
            f"sys.argv = ['rapid', 'approve', '{gate}']; "
            "mock.patch('sys.stdin.isatty', return_value=True).start(); "
            "mock.patch('rapid_os.orchestration.lifecycle.read_ancestry', "
            "return_value=__import__('rapid_os.core.ancestry', fromlist=['x']).AncestryResult(())).start(); "
            f"mock.patch('builtins.input', return_value='aprobar {gate}').start(); sys.exit(m.main())"
        )
        env = {k: v for k, v in os.environ.items() if k not in ("CLAUDECODE", "CLAUDE_CODE_CHILD_SESSION")}
        env["PYTHONPATH"] = str(ROOT)
        result = subprocess.run([sys.executable, "-c", approve], cwd=self.root, capture_output=True, text=True, env=env)
        self.assertEqual(result.returncode, 0, result.stderr)

        finished = rapid(self.root, "finish")
        self.assertEqual(finished.returncode, 0, finished.stderr)
        self.assertIn("verdict PASS", finished.stdout)
        self.assertIn("Sin baseline: proyecto nuevo", finished.stdout)
        as_json = rapid(self.root, "finish", "--json")
        self.assertEqual(json.loads(as_json.stdout)["verdict"], "pass")
        self.assertIn("Sin baseline: proyecto nuevo", as_json.stderr)


if __name__ == "__main__":
    unittest.main()
