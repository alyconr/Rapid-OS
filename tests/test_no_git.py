"""F5: a folder without git reaches PASS without the person knowing `git init` is needed."""

from __future__ import annotations

import json
import os
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from rapid_os.orchestration.lifecycle import unverified_reason
from rapid_os.orchestration.session import git_work_tree_state
from rapid_os.orchestration.setup_apply import ensure_git_repository

ROOT = Path(__file__).resolve().parents[1]
SMOKE_TEST = "import unittest\n\nclass Smoke(unittest.TestCase):\n    def test_smoke(self):\n        self.assertTrue(True)\n"
TEST_COMMAND = f'"{sys.executable}" -m unittest discover -s tests -t .'
BRIEF = "## Problema\nAgendar.\n\n## Usuarios\nOrganizadores.\n\n## Historias\n- [ ] H001: Listar talleres\n"
SPEC = {
    "title": "Listar talleres", "mode": "feature", "business_objective": "Ver los talleres",
    "problem_statement": "No hay listado", "scope": ["listado"], "acceptance_criteria": ["se lista"],
    "tasks": ["T001: Listar"], "tags": ["story:H001"],
}


def _remove(path: Path) -> None:
    def writable(func, target, _exc):
        os.chmod(target, stat.S_IWRITE)
        func(target)

    shutil.rmtree(path, onerror=writable)


class GitIsolated(unittest.TestCase):
    """A temp folder and a git config of its own, so nothing depends on who runs the tests."""

    default_branch: str | None = None

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        base = Path(self._tmp.name)
        self.root = base / "project"
        self.root.mkdir()
        self.git_config = base / "gitconfig"
        self.git_config.write_text(
            f"[init]\n\tdefaultBranch = {self.default_branch}\n" if self.default_branch else "",
            encoding="utf-8",
        )
        self.env = {
            **{k: v for k, v in os.environ.items() if k not in ("CLAUDECODE", "CLAUDE_CODE_CHILD_SESSION")},
            "GIT_CONFIG_GLOBAL": str(self.git_config),
            "GIT_CONFIG_NOSYSTEM": "1",
            "PYTHONPATH": str(ROOT),
            "PYTHONIOENCODING": "utf-8",
            "PYTHONDONTWRITEBYTECODE": "1",
        }
        patcher = mock.patch.dict(os.environ, {k: self.env[k] for k in ("GIT_CONFIG_GLOBAL", "GIT_CONFIG_NOSYSTEM")})
        patcher.start()
        self.addCleanup(patcher.stop)

    def rapid(self, *argv, cwd=None, stdin=None, env=None):
        return subprocess.run(
            [sys.executable, "-m", "rapid_os.cli.main", *argv],
            cwd=cwd or self.root, input=stdin, capture_output=True, text=True, encoding="utf-8",
            env=env or self.env,
        )

    def git(self, *argv, cwd=None):
        return subprocess.run(
            ["git", *argv], cwd=cwd or self.root, capture_output=True, text=True, env=self.env
        )

    def setup_everything(self, test_command="none", brief=False, cwd=None):
        cwd = cwd or self.root
        for key, value in (
            ("stack", "generic"), ("topology", "fullstack-baas"), ("archetype", "mvp"),
            ("agents", "codex"), ("test-command", test_command),
        ):
            result = self.rapid("setup", "set", key, value, cwd=cwd)
            self.assertEqual(result.returncode, 0, result.stderr)
        if brief:
            written = self.rapid("setup", "doc", "brief", "--source", "drafted", "--file", "-", stdin=BRIEF, cwd=cwd)
            self.assertEqual(written.returncode, 0, written.stderr)
        for doc in ("brief", "business", "data-model", "architecture"):
            if brief and doc == "brief":
                continue
            self.assertEqual(self.rapid("setup", "doc", doc, "--skip", cwd=cwd).returncode, 0)
        if brief:  # the drafted brief stays a draft: the person only went through it
            self.assertEqual(self.rapid("setup", "review", "--done", cwd=cwd).returncode, 0)
        return self.rapid("setup", "finish", cwd=cwd)


class SetupFinishCreatesTheRepositoryTests(GitIsolated):
    def test_folder_without_git_gets_a_repository_on_main_without_commits(self):
        finished = self.setup_everything()
        self.assertEqual(finished.returncode, 0, finished.stderr)
        self.assertTrue((self.root / ".git").exists())
        head = self.git("symbolic-ref", "HEAD")
        self.assertEqual(head.stdout.strip(), "refs/heads/main")
        self.assertNotEqual(self.git("rev-parse", "--verify", "HEAD").returncode, 0)  # no commits
        self.assertIn("Repositorio git creado en la rama main", finished.stdout + finished.stderr)
        self.assertIn("Rapid OS observa los cambios con git", finished.stdout + finished.stderr)

    def test_a_second_finish_does_not_announce_it_again(self):
        self.setup_everything()
        again = self.rapid("setup", "finish")
        self.assertEqual(again.returncode, 0, again.stderr)
        self.assertNotIn("Repositorio git creado", again.stdout + again.stderr)


class DefaultBranchTests(GitIsolated):
    default_branch = "master"

    def test_the_branch_is_main_whatever_init_default_branch_says(self):
        # Git for Windows or the sandbox user may carry `master`: Rapid OS still creates `main`.
        finished = self.setup_everything()
        self.assertEqual(finished.returncode, 0, finished.stderr)
        self.assertEqual(self.git("symbolic-ref", "HEAD").stdout.strip(), "refs/heads/main")
        self.assertIn("rama main", finished.stdout + finished.stderr)
        self.assertNotIn("master", finished.stdout + finished.stderr)


class InsideAParentRepositoryTests(GitIsolated):
    def test_it_never_nests_a_repository(self):
        parent = self.root
        self.assertEqual(self.git("init", "-q", cwd=parent).returncode, 0)
        child = parent / "app"
        child.mkdir()
        finished = self.setup_everything(cwd=child)
        self.assertEqual(finished.returncode, 0, finished.stderr)
        self.assertFalse((child / ".git").exists())
        self.assertNotIn("Repositorio git creado", finished.stdout + finished.stderr)
        self.assertEqual(git_work_tree_state(child), "inside")


class EnsureGitRepositoryUnitTests(GitIsolated):
    def test_creates_once_and_reports_the_branch(self):
        first = ensure_git_repository(self.root)
        self.assertEqual(
            first.note, "Repositorio git creado en la rama main (Rapid OS observa los cambios con git)"
        )
        self.assertIsNone(first.warning)
        second = ensure_git_repository(self.root)
        self.assertIsNone(second.note)
        self.assertIsNone(second.warning)

    def test_an_invalid_default_branch_does_not_matter(self):
        self.git_config.write_text("[init]\n\tdefaultBranch = bad..name\n", encoding="utf-8")
        ensure_git_repository(self.root)
        self.assertEqual(self.git("symbolic-ref", "HEAD").stdout.strip(), "refs/heads/main")

    def test_without_git_installed_it_warns_and_does_not_fail(self):
        empty = Path(self._tmp.name) / "empty-path"
        empty.mkdir()
        with mock.patch.dict(os.environ, {"PATH": str(empty)}):
            result = ensure_git_repository(self.root)
            state = git_work_tree_state(self.root)
        self.assertIsNone(result.note)
        self.assertIn("Instala git", result.warning)
        self.assertEqual(state, "missing")
        self.assertFalse((self.root / ".git").exists())

    def test_setup_finish_without_git_exits_zero_with_a_warning(self):
        empty = Path(self._tmp.name) / "empty-path"
        empty.mkdir()
        # Everything the setup needs is written before git is hidden from the final step.
        for key, value in (
            ("stack", "generic"), ("topology", "fullstack-baas"), ("archetype", "mvp"),
            ("agents", "codex"), ("test-command", "none"),
        ):
            self.assertEqual(self.rapid("setup", "set", key, value).returncode, 0)
        for doc in ("brief", "business", "data-model", "architecture"):
            self.assertEqual(self.rapid("setup", "doc", doc, "--skip").returncode, 0)
        env = {**self.env, "PATH": str(empty)}
        finished = self.rapid("setup", "finish", env=env)
        self.assertEqual(finished.returncode, 0, finished.stderr)
        self.assertIn("WARNING", finished.stderr)
        self.assertIn("Instala git", finished.stderr)
        self.assertNotIn("Traceback", finished.stderr)


class StartWithoutGitTests(GitIsolated):
    def finished_project_without_git(self):
        finished = self.setup_everything(brief=True)
        self.assertEqual(finished.returncode, 0, finished.stderr)
        _remove(self.root / ".git")

    def assert_nothing_written(self):
        runs = self.root / ".rapid-os" / "runs"
        self.assertFalse(runs.exists() and any(runs.iterdir()), "a run was created")
        self.assertFalse((self.root / ".rapid-os" / "session.json").exists())

    def test_start_feature_fails_first_with_rapid1416(self):
        self.finished_project_without_git()
        started = self.rapid("start", "feature", "--spec-file", "-", "--json", stdin=json.dumps(SPEC))
        self.assertEqual(started.returncode, 1)
        self.assertIn("RAPID1416", started.stderr + started.stdout)
        self.assertIn("git init", started.stderr + started.stdout)
        self.assertIn("rapid setup finish", started.stderr + started.stdout)
        self.assertNotIn("Traceback", started.stderr)
        self.assert_nothing_written()

    def test_it_comes_before_the_empty_repository_refusal(self):
        self.finished_project_without_git()
        started = self.rapid("start", "bugfix", "--spec-file", "-", stdin=json.dumps({**SPEC, "mode": "bugfix"}))
        self.assertEqual(started.returncode, 1)
        self.assertIn("RAPID1416", started.stderr + started.stdout)
        self.assertNotIn("No hay código", started.stderr + started.stdout)
        self.assert_nothing_written()

    def test_start_without_git_installed_is_the_same_error(self):
        self.finished_project_without_git()
        empty = Path(self._tmp.name) / "empty-path"
        empty.mkdir()
        started = self.rapid(
            "start", "feature", "--spec-file", "-", stdin=json.dumps(SPEC), env={**self.env, "PATH": str(empty)}
        )
        self.assertEqual(started.returncode, 1)
        self.assertIn("RAPID1416", started.stderr + started.stdout)
        self.assert_nothing_written()


class RepairAndResumeTests(StartWithoutGitTests):
    def test_setup_finish_repairs_a_project_whose_git_was_removed(self):
        self.finished_project_without_git()
        repaired = self.rapid("setup", "finish")
        self.assertEqual(repaired.returncode, 0, repaired.stderr)
        self.assertIn("Repositorio git creado en la rama main", repaired.stdout)
        self.assertEqual(self.git("symbolic-ref", "HEAD").stdout.strip(), "refs/heads/main")
        started = self.rapid("start", "feature", "--spec-file", "-", "--json", stdin=json.dumps(SPEC))
        self.assertEqual(started.returncode, 0, started.stderr)  # the message's advice works
        again = self.rapid("setup", "finish")
        self.assertNotIn("Repositorio git creado", again.stdout + again.stderr)

    def test_resume_does_not_repeat_the_git_check(self):
        finished = self.setup_everything(brief=True)
        self.assertEqual(finished.returncode, 0, finished.stderr)
        started = self.rapid("start", "feature", "--spec-file", "-", "--json", stdin=json.dumps(SPEC))
        self.assertEqual(started.returncode, 0, started.stderr)
        _remove(self.root / ".git")
        resumed = self.rapid("start", "--resume", "--json")
        self.assertEqual(resumed.returncode, 0, resumed.stderr)
        self.assertNotIn("RAPID1416", resumed.stderr + resumed.stdout)

    def test_the_creation_note_goes_to_stderr_with_json(self):
        for key, value in (
            ("stack", "generic"), ("topology", "fullstack-baas"), ("archetype", "mvp"),
            ("agents", "codex"), ("test-command", "none"),
        ):
            self.assertEqual(self.rapid("setup", "set", key, value).returncode, 0)
        for doc in ("brief", "business", "data-model", "architecture"):
            self.assertEqual(self.rapid("setup", "doc", doc, "--skip").returncode, 0)
        done = self.rapid("setup", "finish", "--json")
        self.assertEqual(done.returncode, 0, done.stderr)
        json.loads(done.stdout)  # stdout stays JSON alone
        self.assertIn("Repositorio git creado", done.stderr)


def approve(root, gate, env):
    code = (
        "import sys, unittest.mock as mock, rapid_os.cli.main as m; "
        f"sys.argv = ['rapid', 'approve', '{gate}']; "
        "mock.patch('sys.stdin.isatty', return_value=True).start(); "
        "mock.patch('rapid_os.orchestration.lifecycle.stdin_is_windows_nul', return_value=False).start(); "
        "mock.patch('rapid_os.orchestration.lifecycle.read_ancestry', "
        "return_value=__import__('rapid_os.core.ancestry', fromlist=['x']).AncestryResult(())).start(); "
        f"mock.patch('builtins.input', return_value='aprobar {gate}').start(); sys.exit(m.main())"
    )
    return subprocess.run([sys.executable, "-c", code], cwd=root, capture_output=True, text=True, env=env)


class FromAFolderWithoutGitTests(GitIsolated):
    def drive(self, implement):
        for _ in range(25):
            action = json.loads(self.rapid("next", "--json").stdout)["action"]
            if action["kind"] == "await_human_approval":
                return action["gate_ids"][0]
            if action["kind"] == "implement_task":
                implement()
            for key in ("command", "after"):
                if action.get(key):
                    result = self.rapid(*action[key][1:])
                    self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        self.fail("the run never reached a human gate")

    def test_empty_folder_to_pass_and_the_story_is_ticked(self):
        self.assertFalse((self.root / ".git").exists())
        finished = self.setup_everything(test_command=TEST_COMMAND, brief=True)
        self.assertEqual(finished.returncode, 0, finished.stderr)
        started = self.rapid("start", "feature", "--spec-file", "-", "--json", stdin=json.dumps(SPEC))
        self.assertEqual(started.returncode, 0, started.stderr)

        def implement():
            (self.root / "app").mkdir(exist_ok=True)
            (self.root / "app" / "x.py").write_text("x = 1\n", encoding="utf-8")
            (self.root / "tests").mkdir(exist_ok=True)
            (self.root / "tests" / "__init__.py").write_text("", encoding="utf-8")
            (self.root / "tests" / "test_smoke.py").write_text(SMOKE_TEST, encoding="utf-8")

        gate = self.drive(implement)
        self.assertEqual(approve(self.root, gate, self.env).returncode, 0)
        done = self.rapid("finish")
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertIn("verdict PASS", done.stdout)
        self.assertIn("H001 marcada como hecha en docs/PRODUCT_BRIEF.md", done.stdout)
        self.assertIn("- [x] H001: Listar talleres", (self.root / "docs" / "PRODUCT_BRIEF.md").read_text("utf-8"))

    def test_unverified_without_changes_says_why(self):
        finished = self.setup_everything(test_command=f'"{sys.executable}" -c "pass"')
        self.assertEqual(finished.returncode, 0, finished.stderr)
        started = self.rapid("start", "feature", "--spec-file", "-", "--json", stdin=json.dumps({**SPEC, "tags": []}))
        self.assertEqual(started.returncode, 0, started.stderr)
        gate = self.drive(lambda: None)  # the task is "done" and nothing in the project changed
        self.assertEqual(approve(self.root, gate, self.env).returncode, 0)
        as_text = self.rapid("finish")
        self.assertEqual(as_text.returncode, 1)
        self.assertIn("verdict UNVERIFIED", as_text.stdout)
        self.assertIn(
            "No se observaron cambios de archivos: git funciona pero el run no cambió ningún archivo del proyecto",
            as_text.stdout,
        )
        as_json = self.rapid("finish", "--json")
        report = json.loads(as_json.stdout)
        self.assertEqual(report["verdict"], "unverified")
        self.assertIn("no cambió ningún archivo del proyecto", report["unverified_reason"])


class UnverifiedReasonTests(unittest.TestCase):
    def report(self, verdict="unverified", assertions=(("capability.repository.write.observed", "unverified"),)):
        return SimpleNamespace(
            verdict=SimpleNamespace(value=verdict),
            assertions=tuple(
                SimpleNamespace(id=a, status=SimpleNamespace(value=s)) for a, s in assertions
            ),
        )

    def test_not_a_repository(self):
        with tempfile.TemporaryDirectory() as tmp, mock.patch(
            "rapid_os.orchestration.lifecycle.git_work_tree_state", return_value="outside"
        ):
            self.assertEqual(
                unverified_reason(self.report(), tmp),
                "No se observaron cambios de archivos: la carpeta no es un repositorio git",
            )

    def test_git_works_but_nothing_changed(self):
        with mock.patch("rapid_os.orchestration.lifecycle.git_work_tree_state", return_value="inside"):
            self.assertEqual(
                unverified_reason(self.report(), "."),
                "No se observaron cambios de archivos: git funciona pero el run no cambió ningún archivo "
                "del proyecto (fuera de .rapid-os/ y de artefactos de herramientas)",
            )

    def test_only_for_an_unverified_report_that_lacks_the_write_observation(self):
        self.assertIsNone(unverified_reason(self.report(verdict="pass"), "."))
        self.assertIsNone(unverified_reason(self.report(assertions=()), "."))
        self.assertIsNone(
            unverified_reason(self.report(assertions=(("capability.repository.write.observed", "pass"),)), ".")
        )


DUBIOUS = (
    "fatal: detected dubious ownership in repository at 'C:/work/app'\n"
    "To add an exception for this directory, call:\n\n"
    "\tgit config --global --add safe.directory C:/work/app\n"
)


def fake_git(rev_parse_stderr, calls=None):
    """A `subprocess.run` where `git rev-parse` fails with the given stderr and nothing else runs."""

    def run(argv, *args, **kwargs):
        if calls is not None:
            calls.append(list(argv))
        if argv[0] == "git" and "rev-parse" in argv:
            return subprocess.CompletedProcess(argv, 128, stdout="", stderr=rev_parse_stderr)
        raise AssertionError(f"unexpected command: {argv}")

    return run


class UntrustedRepositoryTests(unittest.TestCase):
    """git refuses the folder ("dubious ownership"): not a repository to create, a trust to grant."""

    def state(self, stderr):
        with mock.patch("subprocess.run", side_effect=fake_git(stderr)):
            return git_work_tree_state(".")

    def test_dubious_ownership_and_safe_directory_are_untrusted(self):
        self.assertEqual(self.state(DUBIOUS), "untrusted")
        self.assertEqual(self.state("fatal: unsafe, add it to safe.directory"), "untrusted")

    def test_outside_and_missing_are_unchanged(self):
        self.assertEqual(self.state("fatal: not a git repository (or any of the parent directories): .git"), "outside")
        with mock.patch("subprocess.run", side_effect=FileNotFoundError("git")):
            self.assertEqual(git_work_tree_state("."), "missing")

    def test_ensure_does_not_run_git_init_and_names_the_command_with_gits_path(self):
        calls = []
        with mock.patch("subprocess.run", side_effect=fake_git(DUBIOUS, calls)):
            result = ensure_git_repository(Path("C:/work/app"))
        self.assertTrue(all("rev-parse" in argv for argv in calls), calls)
        self.assertIsNone(result.note)
        self.assertEqual(
            result.warning,
            "git no confía en esta carpeta (dubious ownership). Ejecuta: "
            "git config --global --add safe.directory C:/work/app",
        )

    def test_without_a_path_in_the_message_it_uses_the_projects_with_slashes(self):
        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch("subprocess.run", side_effect=fake_git("fatal: detected dubious ownership")):
                result = ensure_git_repository(Path(tmp))
            self.assertIn(f"safe.directory {Path(tmp).as_posix()}", result.warning)
            self.assertNotIn("\\", result.warning)

    def test_start_says_rapid1416_with_safe_directory_and_creates_nothing(self):
        from rapid_os.orchestration.lifecycle import execute_start

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".rapid-os" / "standards").mkdir(parents=True)
            with mock.patch("subprocess.run", side_effect=fake_git(DUBIOUS)):
                code, message = execute_start(
                    root, root / ".rapid-os", "feature", spec_file="-", stdin_content=json.dumps(SPEC)
                )
            self.assertEqual(code, 1)
            self.assertTrue(message.startswith("RAPID1416 git no confía en esta carpeta (dubious ownership)"), message)
            self.assertIn("git config --global --add safe.directory C:/work/app", message)
            self.assertNotIn("git init", message)
            runs = root / ".rapid-os" / "runs"
            self.assertFalse(runs.exists() and any(runs.iterdir()))
            self.assertFalse((root / ".rapid-os" / "session.json").exists())

    def test_start_outside_keeps_the_text_it_had(self):
        from rapid_os.orchestration.lifecycle import execute_start

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".rapid-os" / "standards").mkdir(parents=True)
            with mock.patch("subprocess.run", side_effect=fake_git("fatal: not a git repository")):
                code, message = execute_start(
                    root, root / ".rapid-os", "feature", spec_file="-", stdin_content=json.dumps(SPEC)
                )
        self.assertEqual(code, 1)
        self.assertIn("RAPID1416 Rapid OS observa los cambios del run con git y esta carpeta no es un repositorio", message)
        self.assertIn("Ejecuta: git init", message)

    def test_unverified_reason_for_an_untrusted_folder(self):
        report = SimpleNamespace(
            verdict=SimpleNamespace(value="unverified"),
            assertions=(
                SimpleNamespace(
                    id="capability.repository.write.observed", status=SimpleNamespace(value="unverified")
                ),
            ),
        )
        with mock.patch("subprocess.run", side_effect=fake_git(DUBIOUS)):
            self.assertEqual(
                unverified_reason(report, "."),
                "No se observaron cambios de archivos: git no confía en esta carpeta (dubious ownership)",
            )


if __name__ == "__main__":
    unittest.main()
