"""`file_change` evidence counts the project's own changes, not what tools generate."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from rapid_os.adapters.evidence_registry import EvidenceRegistry
from rapid_os.domain.file_changes import is_tool_artifact
from rapid_os.orchestration.session import observed_changes, resolve_git_untracked

ROOT = Path(__file__).resolve().parents[1]
TEST_COMMAND = f'"{sys.executable}" -m unittest discover -s tests -t .'
SMOKE_TEST = "import unittest\n\nclass Smoke(unittest.TestCase):\n    def test_smoke(self):\n        self.assertTrue(True)\n"

ARTIFACTS = (
    "__pycache__/m.cpython-312.pyc",
    "pkg/__pycache__/m.cpython-313.pyc",
    "pkg\\__pycache__\\m.cpython-313.pyc",
    "module.pyc",
    "module.pyo",
    ".coverage",
    ".coverage.host.1234",
    "sub/.coverage",
    ".pytest_cache/v/cache/lastfailed",
    "pkg/.pytest_cache/README.md",
    ".mypy_cache/3.12/x.json",
    ".ruff_cache/0.1/x",
    ".tox/py312/log/x.log",
    ".nox/tests/x",
    "node_modules/left-pad/index.js",
    "web/node_modules/p/x.js",
    ".venv/bin/python",
    "venv/lib/site.py",
    "__pycache__",
)
PROJECT_FILES = (
    "app/listado.py",
    "src/main.ts",
    "README.md",
    "my__pycache__notes.md",
    "pycache/x.py",
    "docs/coverage.md",
    "notes.pyc.md",
    ".coveragerc",
    "coverage",
    "src/venvs/x.py",
    "node_modules_backup/x.js",
    "tests/test_a.py",
    "",
)


def rapid(cwd, *argv, stdin=None, bytecode=True):
    env = {k: v for k, v in os.environ.items() if k not in ("CLAUDECODE", "CLAUDE_CODE_CHILD_SESSION")}
    env.update(PYTHONPATH=str(ROOT), PYTHONIOENCODING="utf-8")
    if bytecode:
        env.pop("PYTHONDONTWRITEBYTECODE", None)  # the tools do write __pycache__
    return subprocess.run(
        [sys.executable, "-m", "rapid_os.cli.main", *argv],
        cwd=cwd, input=stdin, capture_output=True, text=True, encoding="utf-8", env=env,
    )


class IsToolArtifactTests(unittest.TestCase):
    def test_artifacts(self):
        for path in ARTIFACTS:
            with self.subTest(path=path):
                self.assertTrue(is_tool_artifact(path))

    def test_project_files_are_not_artifacts(self):
        for path in PROJECT_FILES:
            with self.subTest(path=path):
                self.assertFalse(is_tool_artifact(path))


def git(root: Path, *argv):
    return subprocess.run(["git", *argv], cwd=root, check=True, capture_output=True, text=True)


class SharedObservationTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)
        git(self.root, "init", "-q")
        git(self.root, "config", "user.name", "t")
        git(self.root, "config", "user.email", "t@example.com")
        (self.root / "app.py").write_text("x = 1\n", encoding="utf-8")
        git(self.root, "add", "-A")
        git(self.root, "commit", "-qm", "base")
        self.head = git(self.root, "rev-parse", "HEAD").stdout.strip()

    def write(self, relative: str, text: str = "x\n"):
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    def test_untracked_listing_skips_artifacts_without_a_gitignore(self):
        self.write("__pycache__/m.pyc")
        self.write(".pytest_cache/README.md")
        self.write("notes.md")
        self.assertEqual(resolve_git_untracked(self.root), ("notes.md",))

    def test_changes_are_diff_plus_new_untracked_minus_artifacts_and_the_ledger(self):
        self.write("app.py", "x = 2\n")  # tracked, modified
        self.write("new.py")  # untracked now
        self.write("old_untracked.py")  # was untracked before the run
        self.write("pkg/__pycache__/x.cpython-312.pyc")
        self.write(".rapid-os/session.json", "{}")
        self.assertEqual(
            sorted(observed_changes(self.root, self.head, ("old_untracked.py",))),
            ["app.py", "new.py"],
        )

    def test_no_changes_at_all_is_an_empty_list(self):
        self.write("__pycache__/m.pyc")
        self.assertEqual(observed_changes(self.root, self.head), [])

    def test_a_directory_that_is_not_a_repository_gives_nothing(self):
        with tempfile.TemporaryDirectory() as other:
            self.assertEqual(observed_changes(other, "HEAD"), [])


class FinishWithoutRealWritesTests(unittest.TestCase):
    """A repository without .gitignore, running unittest the way a project would."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)
        git(self.root, "init", "-q")
        git(self.root, "config", "user.name", "Rapid")
        git(self.root, "config", "user.email", "r@example.com")
        (self.root / "tests").mkdir()
        (self.root / "tests" / "__init__.py").write_text("", encoding="utf-8")
        (self.root / "tests" / "test_ok.py").write_text(SMOKE_TEST, encoding="utf-8")
        git(self.root, "add", "-A")
        git(self.root, "commit", "-qm", "base")
        self.assertFalse((self.root / ".gitignore").exists())
        init = rapid(self.root, "init", "--yes", "--skip-docs", "--test-command", TEST_COMMAND)
        self.assertEqual(init.returncode, 0, init.stderr)
        self.assertFalse((self.root / ".gitignore").exists(), "init must not create a .gitignore")

    def run_the_task(self, change_a_file: bool):
        spec = {
            "title": "Listado", "mode": "feature", "business_objective": "o", "problem_statement": "p",
            "scope": ["s"], "acceptance_criteria": ["c"], "tasks": ["T001: Listar"],
        }
        started = rapid(self.root, "start", "feature", "--spec-file", "-", "--json", stdin=json.dumps(spec))
        self.assertEqual(started.returncode, 0, started.stderr)
        gate = None
        for _ in range(20):
            action = json.loads(rapid(self.root, "next", "--json").stdout)["action"]
            if action["kind"] == "await_human_approval":
                gate = action["gate_ids"][0]
                break
            if action["kind"] == "implement_task" and change_a_file:
                (self.root / "app").mkdir(exist_ok=True)
                (self.root / "app" / "listado.py").write_text("def listar():\n    return []\n", encoding="utf-8")
            for key in ("command", "after"):
                if action.get(key):
                    # `rapid check` runs unittest here WITHOUT PYTHONDONTWRITEBYTECODE: __pycache__ appears.
                    self.assertEqual(rapid(self.root, *action[key][1:]).returncode, 0)
        self.assertIsNotNone(gate)
        approve = (
            "import sys, unittest.mock as mock, rapid_os.cli.main as m; "
            f"sys.argv = ['rapid', 'approve', '{gate}']; "
            "mock.patch('sys.stdin.isatty', return_value=True).start(); "
            "mock.patch('rapid_os.orchestration.lifecycle.stdin_is_windows_nul', return_value=False).start(); "
            "mock.patch('rapid_os.orchestration.lifecycle.read_ancestry', "
            "return_value=__import__('rapid_os.core.ancestry', fromlist=['x']).AncestryResult(())).start(); "
            f"mock.patch('builtins.input', return_value='aprobar {gate}').start(); sys.exit(m.main())"
        )
        env = {k: v for k, v in os.environ.items() if k not in ("CLAUDECODE", "CLAUDE_CODE_CHILD_SESSION", "PYTHONDONTWRITEBYTECODE")}
        env["PYTHONPATH"] = str(ROOT)
        result = subprocess.run([sys.executable, "-c", approve], cwd=self.root, capture_output=True, text=True, env=env)
        self.assertEqual(result.returncode, 0, result.stderr)

    def file_change_records(self):
        run_id = next((self.root / ".rapid-os" / "runs").iterdir()).name
        return [e for e in EvidenceRegistry(self.root, self.root / ".rapid-os").list(run_id) if e.kind.value == "file_change"]

    def test_a_task_that_changes_nothing_records_no_file_change_and_does_not_pass(self):
        self.run_the_task(change_a_file=False)
        self.assertTrue(
            list((self.root / "tests").rglob("*.pyc")), "the check should have left bytecode behind"
        )
        finished = rapid(self.root, "finish", "--json")
        self.assertEqual(self.file_change_records(), [])
        self.assertNotEqual(json.loads(finished.stdout)["verdict"], "pass")
        self.assertEqual(finished.returncode, 1)

    def test_a_real_change_records_only_that_file_and_passes(self):
        self.run_the_task(change_a_file=True)
        finished = rapid(self.root, "finish", "--json")
        self.assertEqual(finished.returncode, 0, finished.stderr)
        self.assertEqual(json.loads(finished.stdout)["verdict"], "pass")
        (record,) = self.file_change_records()
        self.assertEqual(record.payload["paths"], ["app/listado.py"])


class GitignoreTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)

    def lines(self):
        return (self.root / ".gitignore").read_text(encoding="utf-8").splitlines()

    def test_init_adds_the_missing_tool_artifact_lines_to_an_existing_gitignore(self):
        (self.root / ".gitignore").write_text("node_modules/\n*.pyc\n", encoding="utf-8")
        result = rapid(self.root, "init", "--yes", "--skip-docs", "--test-command", "echo")
        self.assertEqual(result.returncode, 0, result.stderr)
        lines = self.lines()
        for entry in ("__pycache__/", "*.pyc", ".pytest_cache/", ".rapid-os/session.json"):
            self.assertIn(entry, lines)
        self.assertEqual(lines.count("*.pyc"), 1, "an entry that was already there is not repeated")
        again = rapid(self.root, "init", "--yes", "--skip-docs", "--test-command", "echo")
        self.assertEqual(again.returncode, 0, again.stderr)
        self.assertEqual(self.lines(), lines)

    def test_setup_finish_adds_them_too_and_no_gitignore_is_never_created(self):
        for argv in (
            ("set", "stack", "python-api"), ("set", "topology", "fullstack-separated"), ("set", "stack", "react-vite"),
            ("set", "archetype", "mvp"),
            ("set", "ai", "no"), ("set", "agents", "claude"), ("set", "test-command", "none"), ("set", "services", "none"),
        ):
            self.assertEqual(rapid(self.root, "setup", *argv).returncode, 0)
        for doc in ("brief", "business", "data-model", "architecture", "deployment"):
            self.assertEqual(rapid(self.root, "setup", "doc", doc, "--skip").returncode, 0)
        self.assertEqual(rapid(self.root, "setup", "finish").returncode, 0)
        self.assertFalse((self.root / ".gitignore").exists())

        (self.root / ".gitignore").write_text("dist/\n", encoding="utf-8")
        rapid(self.root, "setup", "set", "test-command", "none")  # reopens the setup
        self.assertEqual(rapid(self.root, "setup", "finish").returncode, 0)
        for entry in ("__pycache__/", "*.pyc", ".pytest_cache/", ".rapid-os/backups/"):
            self.assertIn(entry, self.lines())


if __name__ == "__main__":
    unittest.main()
