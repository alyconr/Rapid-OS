"""F5: Rapid OS works inside the Codex sandbox on Windows (git run by another user)
and hands the person the one command only they can run."""

from __future__ import annotations

import ast
import json
import os
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path
from unittest import mock

from rapid_os.orchestration.git import (
    PERSON_ACTION_ID,
    person_action_lines,
    person_actions,
    person_git_trust,
    run_git,
)
from tests.test_no_git import BRIEF, SMOKE_TEST, SPEC, TEST_COMMAND, GitIsolated, _remove

ROOT = Path(__file__).resolve().parents[1]
DUBIOUS_STDERR = "fatal: detected dubious ownership in repository at '{path}'\n"

# A `subprocess.run` for a repository owned by another user: git refuses every command that
# does not carry `-c safe.directory=...`, exactly like the sandbox does.
SHIM = textwrap.dedent(
    """
    import os, subprocess, sys
    from pathlib import Path
    import unittest.mock as mock

    _real = subprocess.run

    def _run(argv, *args, **kwargs):
        if isinstance(argv, list) and argv and argv[0] == "git":
            cwd = Path(kwargs.get("cwd") or ".")
            trusted = any(str(item).startswith("safe.directory=") for item in argv)
            if not trusted and (cwd / ".git").exists():
                return subprocess.CompletedProcess(
                    argv, 128, "", "fatal: detected dubious ownership in repository at '%s'\\n" % cwd.as_posix()
                )
        return _real(argv, *args, **kwargs)

    subprocess.run = _run
    gate = os.environ.get("SHIM_APPROVE_GATE")
    if gate:
        mock.patch("sys.stdin.isatty", return_value=True).start()
        mock.patch("rapid_os.orchestration.lifecycle.stdin_is_windows_nul", return_value=False).start()
        mock.patch(
            "rapid_os.orchestration.lifecycle.read_ancestry",
            return_value=__import__("rapid_os.core.ancestry", fromlist=["x"]).AncestryResult(()),
        ).start()
        mock.patch("builtins.input", return_value="aprobar " + gate).start()
    sys.argv = ["rapid", *sys.argv[1:]]
    import rapid_os.cli.main as m
    sys.exit(m.main())
    """
)


class RunGitTests(unittest.TestCase):
    def test_it_adds_the_two_settings_and_trusts_only_the_root(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with mock.patch("subprocess.run") as run:
                run_git(root, "status", "--short")
        (argv,), kwargs = run.call_args
        self.assertEqual(
            argv,
            [
                "git",
                "-c",
                f"safe.directory={root.absolute().as_posix()}",
                "-c",
                "core.fsmonitor=false",
                "status",
                "--short",
            ],
        )
        self.assertEqual(kwargs["cwd"], str(root.absolute()))
        self.assertFalse(kwargs["shell"])
        joined = " ".join(argv)
        self.assertNotIn("safe.directory=*", joined)
        self.assertNotIn("--system", joined)

    def test_the_root_uses_forward_slashes(self):
        with tempfile.TemporaryDirectory() as tmp, mock.patch("subprocess.run") as run:
            run_git(tmp, "status")
        self.assertNotIn("\\", run.call_args[0][0][2])


class InventoryTests(unittest.TestCase):
    def test_no_git_subprocess_outside_the_one_door(self):
        door = ROOT / "rapid_os" / "orchestration" / "git.py"
        offenders = []
        for path in sorted((ROOT / "rapid_os").rglob("*.py")):
            if path == door:
                continue
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            for node in ast.walk(tree):
                if (
                    isinstance(node, (ast.List, ast.Tuple))
                    and node.elts
                    and isinstance(node.elts[0], ast.Constant)
                    and node.elts[0].value == "git"
                ):
                    offenders.append(f"{path.relative_to(ROOT).as_posix()}:{node.lineno}")
        self.assertEqual(offenders, [], "git commands must go through rapid_os/orchestration/git.py")


class OtherOwnerSandboxTests(GitIsolated):
    """The repository belongs to another Windows user: only commands with `-c safe.directory` work."""

    def setUp(self):
        super().setUp()
        self.shim = Path(self._tmp.name) / "owner_shim.py"
        self.shim.write_text(SHIM, encoding="utf-8")

    def as_other_owner(self, *argv, stdin=None, gate=None):
        env = {**self.env}
        if gate:
            env["SHIM_APPROVE_GATE"] = gate
        return subprocess.run(
            [sys.executable, str(self.shim), *argv],
            cwd=self.root, input=stdin, capture_output=True, text=True, encoding="utf-8", env=env,
        )

    def setup_everything(self, test_command="none", brief=False, cwd=None):  # runs every step as the other owner
        for key, value in (
            ("stack", "generic"), ("topology", "fullstack-baas"), ("archetype", "mvp"),
            ("agents", "codex"), ("test-command", test_command),
        ):
            result = self.as_other_owner("setup", "set", key, value)
            self.assertEqual(result.returncode, 0, result.stderr)
        if brief:
            written = self.as_other_owner("setup", "doc", "brief", "--source", "drafted", "--file", "-", stdin=BRIEF)
            self.assertEqual(written.returncode, 0, written.stderr)
        for doc in ("brief", "business", "data-model", "architecture"):
            if brief and doc == "brief":
                continue
            self.assertEqual(self.as_other_owner("setup", "doc", doc, "--skip").returncode, 0)
        if brief:  # the drafted brief stays a draft: the person only went through it
            self.assertEqual(self.as_other_owner("setup", "review", "--done").returncode, 0)
        return self.as_other_owner("setup", "finish", "--json")

    def command(self):
        return f"git config --global --add safe.directory {self.root.absolute().as_posix()}"

    def test_setup_finish_creates_the_repository_and_hands_over_the_command(self):
        finished = self.setup_everything()
        self.assertEqual(finished.returncode, 0, finished.stderr)
        self.assertTrue((self.root / ".git").exists())
        self.assertEqual(self.git("symbolic-ref", "HEAD").stdout.strip(), "refs/heads/main")
        self.assertNotEqual(self.git("rev-parse", "--verify", "HEAD").returncode, 0)  # no commits
        payload = json.loads(finished.stdout)
        self.assertEqual(payload["kind"], "done")
        (action,) = payload["person_actions"]
        self.assertEqual(action["id"], PERSON_ACTION_ID)
        self.assertEqual(action["command"], self.command())
        self.assertIn("otro usuario de Windows", action["why"])
        self.assertNotIn("--system", action["command"])
        self.assertNotIn("*", action["command"])

    def test_text_and_next_and_doctor_carry_the_action_too(self):
        self.setup_everything()
        for argv in (("setup", "next"), ("setup", "finish")):
            result = self.as_other_owner(*argv)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn(
                f"Para usar git tú mismo en esta carpeta, ejecuta en tu terminal: {self.command()}",
                result.stdout,
            )
        as_json = self.as_other_owner("setup", "next", "--json")
        self.assertEqual(json.loads(as_json.stdout)["person_actions"][0]["command"], self.command())
        doctor = self.as_other_owner("doctor", "--json")
        self.assertEqual(json.loads(doctor.stdout)["person_actions"][0]["command"], self.command())
        self.assertIn("Para usar git tú mismo", self.as_other_owner("doctor").stdout)

    def test_start_runs_and_finish_sees_the_files(self):
        finished = self.setup_everything(test_command=TEST_COMMAND, brief=True)
        self.assertEqual(finished.returncode, 0, finished.stderr)
        started = self.as_other_owner("start", "feature", "--spec-file", "-", "--json", stdin=json.dumps(SPEC))
        self.assertEqual(started.returncode, 0, started.stderr)
        self.assertNotIn("RAPID1416", started.stderr + started.stdout)

        gate = None
        for _ in range(25):
            action = json.loads(self.as_other_owner("next", "--json").stdout)["action"]
            if action["kind"] == "await_human_approval":
                gate = action["gate_ids"][0]
                break
            if action["kind"] == "implement_task":
                (self.root / "app").mkdir(exist_ok=True)
                (self.root / "app" / "x.py").write_text("x = 1\n", encoding="utf-8")
                (self.root / "tests").mkdir(exist_ok=True)
                (self.root / "tests" / "__init__.py").write_text("", encoding="utf-8")
                (self.root / "tests" / "test_smoke.py").write_text(SMOKE_TEST, encoding="utf-8")
            for key in ("command", "after"):
                if action.get(key):
                    result = self.as_other_owner(*action[key][1:])
                    self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        self.assertIsNotNone(gate, "the run never reached a human gate")
        self.assertEqual(self.as_other_owner("approve", gate, gate=gate).returncode, 0)

        done = self.as_other_owner("finish", "--json")
        self.assertEqual(done.returncode, 0, done.stderr)
        # The story is ticked here too; the agent files it rebuilds must not reach stdout.
        self.assertTrue(done.stdout.lstrip().startswith("{"), done.stdout[:200])
        self.assertEqual(json.loads(done.stdout)["verdict"], "pass")
        from rapid_os.adapters.evidence_registry import EvidenceRegistry

        run_id = json.loads((self.root / ".rapid-os" / "session.json").read_text("utf-8"))["active_run_id"]
        paths = [
            p
            for record in EvidenceRegistry(self.root, self.root / ".rapid-os").list(run_id)
            if record.kind.value == "file_change"
            for p in record.payload["paths"]
        ]
        self.assertIn("app/x.py", paths)

    def test_person_git_trust_unit(self):
        self.git("init", "-q")

        def fake(argv, *args, **kwargs):
            if "safe.directory=" in " ".join(argv):
                return subprocess.CompletedProcess(argv, 0, "true\n", "")
            return subprocess.CompletedProcess(argv, 128, "", DUBIOUS_STDERR.format(path=self.root.as_posix()))

        with mock.patch("subprocess.run", side_effect=fake):
            trust = person_git_trust(self.root)
            actions = person_actions(self.root)
        self.assertTrue(trust.needs_exception)
        self.assertEqual(trust.command, self.command())
        self.assertEqual([a["id"] for a in actions], [PERSON_ACTION_ID])
        self.assertEqual(
            person_action_lines(actions)[0],
            f"Para usar git tú mismo en esta carpeta, ejecuta en tu terminal: {self.command()}",
        )

    def test_if_run_git_fails_too_there_is_no_person_action(self):
        def fake(argv, *args, **kwargs):
            return subprocess.CompletedProcess(argv, 128, "", DUBIOUS_STDERR.format(path=self.root.as_posix()))

        with mock.patch("subprocess.run", side_effect=fake):
            self.assertFalse(person_git_trust(self.root).needs_exception)


class OrdinaryRepositoryTests(GitIsolated):
    def test_a_repository_the_person_owns_has_no_person_actions(self):
        for key, value in (
            ("stack", "generic"), ("topology", "fullstack-baas"), ("archetype", "mvp"),
            ("agents", "codex"), ("test-command", "none"),
        ):
            self.assertEqual(self.rapid("setup", "set", key, value).returncode, 0)
        for doc in ("brief", "business", "data-model", "architecture"):
            self.assertEqual(self.rapid("setup", "doc", doc, "--skip").returncode, 0)
        finished = self.rapid("setup", "finish", "--json")
        self.assertEqual(finished.returncode, 0, finished.stderr)
        self.assertNotIn("person_actions", json.loads(finished.stdout))
        text = self.rapid("setup", "next")
        self.assertNotIn("Para usar git tú mismo", text.stdout)
        self.assertNotIn("person_actions", json.loads(self.rapid("doctor", "--json").stdout))

    def test_outside_a_repository_and_without_git_there_is_nothing_to_hand_over(self):
        self.assertFalse(person_git_trust(self.root).needs_exception)  # not a repository
        empty = Path(self._tmp.name) / "empty-path"
        empty.mkdir()
        with mock.patch.dict(os.environ, {"PATH": str(empty)}):
            self.assertFalse(person_git_trust(self.root).needs_exception)  # git missing


class PartialInitTests(GitIsolated):
    def test_init_worked_but_the_next_step_failed_says_what_was_created(self):
        from rapid_os.orchestration.setup_apply import ensure_git_repository

        real = subprocess.run

        def flaky(argv, *args, **kwargs):
            if "symbolic-ref" in argv:
                return subprocess.CompletedProcess(argv, 1, "", "fatal: cannot lock ref 'HEAD'\n")
            return real(argv, *args, **kwargs)

        with mock.patch("subprocess.run", side_effect=flaky):
            result = ensure_git_repository(self.root)
        self.assertTrue((self.root / ".git").exists())
        self.assertIsNone(result.note)
        self.assertIn("Se creó el repositorio git (git init)", result.warning)
        self.assertIn("no se pudo fijar la rama main", result.warning)
        self.assertNotIn("No se pudo crear", result.warning)

    def test_init_itself_failing_still_says_it_could_not_create(self):
        from rapid_os.orchestration.setup_apply import ensure_git_repository

        real = subprocess.run

        def broken(argv, *args, **kwargs):
            if "init" in argv:
                return subprocess.CompletedProcess(argv, 1, "", "fatal: cannot mkdir .git\n")
            return real(argv, *args, **kwargs)

        with mock.patch("subprocess.run", side_effect=broken):
            result = ensure_git_repository(self.root)
        self.assertIn("No se pudo crear el repositorio git", result.warning)


@unittest.skipUnless(hasattr(os, "geteuid") and os.geteuid() == 0, "needs root to give the repository to another uid")
class RealForeignOwnerTests(GitIsolated):
    """On POSIX as root: the folder really belongs to another uid and git really refuses it."""

    OTHER_UID = 54321

    def chown_tree(self):
        for dirpath, dirnames, filenames in os.walk(self.root):
            for name in [dirpath, *[os.path.join(dirpath, n) for n in dirnames + filenames]]:
                os.chown(name, self.OTHER_UID, self.OTHER_UID)

    def test_setup_start_and_finish_work_without_asking_anything(self):
        os.chown(self.root, self.OTHER_UID, self.OTHER_UID)
        finished = self.setup_everything(test_command=TEST_COMMAND, brief=True)
        self.assertEqual(finished.returncode, 0, finished.stderr)
        self.chown_tree()
        self.assertIn("person_actions", finished.stdout + self.rapid("setup", "next", "--json").stdout)
        started = self.rapid("start", "feature", "--spec-file", "-", "--json", stdin=json.dumps(SPEC))
        self.assertEqual(started.returncode, 0, started.stderr)
        self.assertNotIn("RAPID1416", started.stderr + started.stdout)


if __name__ == "__main__":
    unittest.main()
