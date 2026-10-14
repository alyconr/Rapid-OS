"""Acceptance test for Rapid OS intent loop.

Simulates an agent driving the full lifecycle from `rapid start` to `rapid finish`
via `rapid next --json`, interactive human approval, and contract validation assertions.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class IntentLoopAcceptanceTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self.temp_dir.name)

        # 1. Initialize git repository
        self._git("init")
        self._git("config", "user.name", "Rapid Agent")
        self._git("config", "user.email", "agent@rapid.os")

        # 2. Minimal Python fixture and green test suite
        (self.tmp_path / "math_ops.py").write_text(
            "def add(a: int, b: int) -> int:\n    return a + b\n",
            encoding="utf-8",
        )
        tests_dir = self.tmp_path / "tests"
        tests_dir.mkdir(parents=True, exist_ok=True)
        (tests_dir / "__init__.py").write_text("", encoding="utf-8")
        (tests_dir / "test_math_ops.py").write_text(
            "import unittest\n"
            "import math_ops\n\n"
            "class TestMathOps(unittest.TestCase):\n"
            "    def test_add(self):\n"
            "        self.assertEqual(math_ops.add(2, 3), 5)\n\n"
            "if __name__ == '__main__':\n"
            "    unittest.main()\n",
            encoding="utf-8",
        )

        self._git("add", ".")
        self._git("commit", "-m", "Initial baseline commit")

    def tearDown(self):
        self.temp_dir.cleanup()

    def _git(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["git", *args],
            cwd=str(self.tmp_path),
            check=True,
            capture_output=True,
            text=True,
        )

    def _rapid(
        self,
        *args: str,
        input_str: str | None = None,
        extra_env: dict[str, str] | None = None,
    ) -> subprocess.CompletedProcess[str]:
        cmd = [sys.executable, "-m", "rapid_os.cli.main", *args]
        env = {
            k: v
            for k, v in os.environ.items()
            if k not in ("CLAUDECODE", "CLAUDE_CODE_CHILD_SESSION")
        }
        env["PYTHONPATH"] = str(ROOT)
        if extra_env:
            env.update(extra_env)
        return subprocess.run(
            cmd,
            cwd=str(self.tmp_path),
            input=input_str,
            capture_output=True,
            text=True,
            env=env,
        )

    def test_agent_intent_loop_full_lifecycle(self):
        # Step 1: rapid init with --yes and --test-command
        test_cmd_str = f'"{sys.executable}" -m unittest discover -s tests -t .'
        init_res = self._rapid("init", "--yes", "--test-command", test_cmd_str)
        self.assertEqual(init_res.returncode, 0, f"rapid init failed: {init_res.stderr}")

        # Verify .rapid-os created
        rapid_dir = self.tmp_path / ".rapid-os"
        self.assertTrue(rapid_dir.is_dir())

        # Step 2: rapid start feature --spec-file -
        spec_payload = {
            "title": "Extended Math Operations",
            "mode": "feature",
            "business_objective": "Support subtraction and multiplication",
            "problem_statement": "Only addition is currently supported",
            "scope": ["basic arithmetic operations"],
            "acceptance_criteria": ["subtract works", "multiply works"],
            "tasks": [
                "T001: Implement subtraction function",
                "T002: Implement multiplication function",
            ],
        }
        spec_json = json.dumps(spec_payload)

        start_res = self._rapid("start", "feature", "--spec-file", "-", "--json", input_str=spec_json)
        self.assertEqual(start_res.returncode, 0, f"rapid start failed: {start_res.stderr}")
        start_data = json.loads(start_res.stdout)
        self.assertIn("action", start_data)
        run_id = start_data["run_id"]
        self.assertIn("-run-", run_id)

        # Check status
        status_res = self._rapid("status", "--json")
        self.assertEqual(status_res.returncode, 0)
        status_data = json.loads(status_res.stdout)
        self.assertEqual(status_data["session"]["active_run_id"], run_id)
        self.assertEqual(status_data["run"]["status"], "active")

        # Step 3: Agent loop
        executed_commands: list[list[str]] = []
        max_iterations = 20
        iteration = 0
        human_gate_to_approve: str | None = None

        while iteration < max_iterations:
            iteration += 1
            next_res = self._rapid("next", "--json")
            self.assertEqual(next_res.returncode, 0, f"rapid next failed: {next_res.stderr}")
            next_data = json.loads(next_res.stdout)
            action = next_data["action"]
            action_kind = action["kind"]

            if action_kind == "await_human_approval":
                awaiting = action.get("awaiting_human") or action.get("gate_ids")
                self.assertTrue(awaiting, "Expected awaiting human gates")
                human_gate_to_approve = awaiting[0]
                break

            cmd = action.get("command")
            if cmd:
                executed_commands.append(list(cmd))
                if cmd[0] == "rapid":
                    sub_res = self._rapid(*cmd[1:])
                else:
                    sub_res = subprocess.run(
                        cmd,
                        cwd=str(self.tmp_path),
                        capture_output=True,
                        text=True,
                    )
                self.assertEqual(sub_res.returncode, 0, f"Command {cmd} failed: {getattr(sub_res, 'stderr', '')}")

            if action_kind == "implement_task":
                task_id = action.get("task_id")
                self.assertIsNotNone(task_id)

                # Edit code fixtures according to task
                if task_id == "T001":
                    with open(self.tmp_path / "math_ops.py", "a", encoding="utf-8") as f:
                        f.write("\ndef subtract(a: int, b: int) -> int:\n    return a - b\n")
                    with open(self.tmp_path / "tests" / "test_math_ops.py", "a", encoding="utf-8") as f:
                        f.write("\n    def test_subtract(self):\n        self.assertEqual(math_ops.subtract(5, 2), 3)\n")
                elif task_id == "T002":
                    with open(self.tmp_path / "math_ops.py", "a", encoding="utf-8") as f:
                        f.write("\ndef multiply(a: int, b: int) -> int:\n    return a * b\n")
                    with open(self.tmp_path / "tests" / "test_math_ops.py", "a", encoding="utf-8") as f:
                        f.write("\n    def test_multiply(self):\n        self.assertEqual(math_ops.multiply(3, 4), 12)\n")

                after_cmd = action.get("after")
                if after_cmd:
                    executed_commands.append(list(after_cmd))
                    if after_cmd[0] == "rapid":
                        after_res = self._rapid(*after_cmd[1:])
                    else:
                        after_res = subprocess.run(
                            after_cmd,
                            cwd=str(self.tmp_path),
                            capture_output=True,
                            text=True,
                        )
                    self.assertEqual(
                        after_res.returncode,
                        0,
                        f"After command {after_cmd} failed: {getattr(after_res, 'stderr', '')}",
                    )

        self.assertLess(iteration, max_iterations, "Loop exceeded maximum iterations")
        self.assertIsNotNone(human_gate_to_approve)
        self.assertEqual(human_gate_to_approve, "gate.final-verification")

        # Step 4: Verify non-TTY approval fails with RAPID1310
        tty_fail_res = self._rapid("approve", human_gate_to_approve)
        self.assertEqual(tty_fail_res.returncode, 1)
        self.assertIn("RAPID1310", tty_fail_res.stderr)

        # Step 5: Simulate interactive TTY approval with prompt confirmation
        approve_py = (
            "import sys, unittest.mock as mock, rapid_os.cli.main as m; "
            f"sys.argv = ['rapid', 'approve', '{human_gate_to_approve}']; "
            "mock.patch('sys.stdin.isatty', return_value=True).start(); "
            "mock.patch('rapid_os.orchestration.lifecycle.read_ancestry', "
            "return_value=__import__('rapid_os.core.ancestry', fromlist=['x']).AncestryResult(())).start(); "
            f"mock.patch('builtins.input', return_value='aprobar {human_gate_to_approve}').start(); "
            "sys.exit(m.main())"
        )
        env = {
            k: v
            for k, v in os.environ.items()
            if k not in ("CLAUDECODE", "CLAUDE_CODE_CHILD_SESSION")
        }
        env["PYTHONPATH"] = str(ROOT)
        approve_res = subprocess.run(
            [sys.executable, "-c", approve_py],
            cwd=str(self.tmp_path),
            capture_output=True,
            text=True,
            env=env,
        )
        self.assertEqual(approve_res.returncode, 0, f"Approve failed: {approve_res.stderr}")

        # Step 6: rapid finish --json
        finish_res = self._rapid("finish", "--json")
        self.assertEqual(finish_res.returncode, 0, f"rapid finish failed: {finish_res.stderr}")
        finish_data = json.loads(finish_res.stdout)
        self.assertEqual(finish_data["verdict"], "pass")

        # Step 7: Final assertions
        # 7.1 No manually created JSON files outside initial spec
        root_json_files = list(self.tmp_path.glob("*.json"))
        self.assertEqual(root_json_files, [], f"Agent wrote JSON files in root: {root_json_files}")

        # 7.2 No executed command contained a typed run_id
        for executed_cmd in executed_commands:
            self.assertNotIn(
                run_id,
                executed_cmd,
                f"Command '{executed_cmd}' contained explicitly typed run_id '{run_id}'!",
            )

    def test_start_errors_diagnostics(self):
        # 1. Project not initialized -> RAPID1309
        uninit_res = self._rapid("start", "feature")
        self.assertEqual(uninit_res.returncode, 1)
        self.assertIn("RAPID1309", uninit_res.stderr)

        # Initialize project
        self._rapid("init", "--yes", "--test-command", "python -m unittest")

        # Create active run
        spec_payload = {
            "title": "Test Spec",
            "mode": "feature",
            "tasks": ["T001: Task 1"],
        }
        start_res = self._rapid("start", "feature", "--spec-file", "-", input_str=json.dumps(spec_payload))
        self.assertEqual(start_res.returncode, 0)

        # 2. Start another run while active run exists -> RAPID1308
        start_again = self._rapid("start", "feature")
        self.assertEqual(start_again.returncode, 1)
        self.assertIn("RAPID1308", start_again.stderr)

    def test_abort_workflow(self):
        self._rapid("init", "--yes", "--test-command", "python -m unittest")
        spec_payload = {
            "title": "Abort Spec",
            "mode": "feature",
            "tasks": ["T001: Task 1"],
        }
        start_res = self._rapid("start", "feature", "--spec-file", "-", input_str=json.dumps(spec_payload))
        self.assertEqual(start_res.returncode, 0)

        # Status shows active run
        st1 = self._rapid("status", "--json")
        self.assertEqual(st1.returncode, 0)
        data1 = json.loads(st1.stdout)
        self.assertIsNotNone(data1["session"]["active_run_id"])
        self.assertEqual(data1["run"]["status"], "active")

        # Abort run
        abort_res = self._rapid("abort", "--reason", "Aborting this test run")
        self.assertEqual(abort_res.returncode, 0)

        # Status shows no active run
        st2 = self._rapid("status", "--json")
        self.assertEqual(st2.returncode, 0)
        data2 = json.loads(st2.stdout)
        self.assertIsNone(data2["session"])


    def test_red_baseline_to_activate_loop(self):
        # 1. Start with RED baseline
        (self.tmp_path / "math_ops.py").write_text(
            "def add(a: int, b: int) -> int:\n    return 0\n",
            encoding="utf-8",
        )
        self._git("add", ".")
        self._git("commit", "-m", "Failing baseline commit")

        test_cmd_str = f'"{sys.executable}" -m unittest discover -s tests -t .'
        init_res = self._rapid("init", "--yes", "--test-command", test_cmd_str)
        self.assertEqual(init_res.returncode, 0)

        spec_payload = {
            "title": "Fix Math Ops",
            "mode": "feature",
            "tasks": ["T001: Implement real add"],
        }
        start_res = self._rapid("start", "feature", "--spec-file", "-", input_str=json.dumps(spec_payload))
        self.assertEqual(start_res.returncode, 0)

        # Baseline was red, so next action must be run_baseline
        next1 = self._rapid("next", "--json")
        self.assertEqual(next1.returncode, 0)
        data1 = json.loads(next1.stdout)
        self.assertEqual(data1["action"]["kind"], "run_baseline")
        self.assertIn("rapid abort", data1["action"]["instructions"])

        # Test fixes the code
        (self.tmp_path / "math_ops.py").write_text(
            "def add(a: int, b: int) -> int:\n    return a + b\n",
            encoding="utf-8",
        )

        # Agent loop executes literally each action.command until implement_task
        iteration = 0
        while iteration < 10:
            iteration += 1
            res = self._rapid("next", "--json")
            self.assertEqual(res.returncode, 0)
            data = json.loads(res.stdout)
            action = data["action"]
            if action["kind"] == "implement_task":
                break
            cmd = action.get("command")
            self.assertIsNotNone(cmd, f"Expected command for action {action['kind']}")
            if cmd[0] == "rapid":
                cmd_res = self._rapid(*cmd[1:])
            else:
                cmd_res = subprocess.run(cmd, cwd=str(self.tmp_path), capture_output=True, text=True)
            self.assertEqual(cmd_res.returncode, 0, f"Command {cmd} failed: {getattr(cmd_res, 'stderr', '')}")

        self.assertLess(iteration, 10)
        self.assertEqual(action["kind"], "implement_task")
        self.assertEqual(action["task_id"], "T001")

    def test_resume_preserves_start_head_across_commits(self):
        from rapid_os.adapters.evidence_registry import EvidenceRegistry
        from rapid_os.orchestration.session import load_session

        test_cmd_str = f'"{sys.executable}" -m unittest discover -s tests -t .'
        init_res = self._rapid("init", "--yes", "--test-command", test_cmd_str)
        self.assertEqual(init_res.returncode, 0)

        spec_payload = {
            "title": "Preserve Start Head Spec",
            "mode": "feature",
            "tasks": ["T001: Implement task"],
        }
        start_res = self._rapid("start", "feature", "--spec-file", "-", input_str=json.dumps(spec_payload))
        self.assertEqual(start_res.returncode, 0)

        sess_before = load_session(self.tmp_path / ".rapid-os")
        self.assertIsNotNone(sess_before)
        initial_head = sess_before.start_head
        self.assertIsNotNone(initial_head)

        # Make a commit between start and resume
        (self.tmp_path / "interim.txt").write_text("interim change\n", encoding="utf-8")
        self._git("add", "interim.txt")
        self._git("commit", "-m", "Commit between start and resume")

        # Call start --resume without mode
        resume_res = self._rapid("start", "--resume", "--json")
        self.assertEqual(resume_res.returncode, 0, f"start --resume failed: {resume_res.stderr}")

        sess_after = load_session(self.tmp_path / ".rapid-os")
        self.assertIsNotNone(sess_after)
        self.assertEqual(sess_after.start_head, initial_head, "start_head was modified on resume!")

        # Complete task
        start_t_res = self._rapid("task", "start", "T001")
        self.assertEqual(start_t_res.returncode, 0)
        done_res = self._rapid("task", "done", "T001", "--no-check")
        self.assertEqual(done_res.returncode, 0)

        # Check gate.tests
        chk_res = self._rapid("check", "--gate", "gate.tests", "--", sys.executable, "-m", "unittest", "discover", "-s", "tests", "-t", ".")
        self.assertEqual(chk_res.returncode, 0)

        # Approve human gate
        approve_py = (
            "import sys, unittest.mock as mock, rapid_os.cli.main as m; "
            "sys.argv = ['rapid', 'approve', 'gate.final-verification']; "
            "mock.patch('sys.stdin.isatty', return_value=True).start(); "
            "mock.patch('rapid_os.orchestration.lifecycle.read_ancestry', "
            "return_value=__import__('rapid_os.core.ancestry', fromlist=['x']).AncestryResult(())).start(); "
            "mock.patch('builtins.input', return_value='aprobar gate.final-verification').start(); "
            "sys.exit(m.main())"
        )
        env = {
            k: v
            for k, v in os.environ.items()
            if k not in ("CLAUDECODE", "CLAUDE_CODE_CHILD_SESSION")
        }
        env["PYTHONPATH"] = str(ROOT)
        env["PYTHONIOENCODING"] = "utf-8"
        subprocess.run([sys.executable, "-c", approve_py], cwd=str(self.tmp_path), check=True, env=env)

        # rapid finish
        finish_res = self._rapid("finish", "--json")
        self.assertEqual(finish_res.returncode, 0, f"rapid finish failed: {finish_res.stderr}")

        ev_reg = EvidenceRegistry(self.tmp_path, self.tmp_path / ".rapid-os")
        evs = ev_reg.list(sess_before.active_run_id)
        file_change_ev = next((e for e in evs if e.kind.value == "file_change"), None)
        self.assertIsNotNone(file_change_ev)
        self.assertIn("interim.txt", file_change_ev.payload["paths"])

    def test_approve_reject_requires_reason(self):
        test_cmd_str = f'"{sys.executable}" -m unittest discover -s tests -t .'
        self._rapid("init", "--yes", "--test-command", test_cmd_str)

        spec_payload = {
            "title": "Approval Test Spec",
            "mode": "feature",
            "tasks": ["T001: Task 1"],
        }
        self._rapid("start", "feature", "--spec-file", "-", input_str=json.dumps(spec_payload))

        # Reject without reason -> exit 1
        reject_fail = self._rapid("approve", "gate.final-verification", "--reject")
        self.assertEqual(reject_fail.returncode, 1)
        self.assertIn("Reason is required", reject_fail.stderr)

    def test_approve_rejects_under_claude_code_session(self):
        test_cmd_str = f'"{sys.executable}" -m unittest discover -s tests -t .'
        self._rapid("init", "--yes", "--test-command", test_cmd_str)

        spec_payload = {
            "title": "Claude Code Approval Guard Spec",
            "mode": "feature",
            "tasks": ["T001: Task 1"],
        }
        self._rapid("start", "feature", "--spec-file", "-", input_str=json.dumps(spec_payload))

        # Rejection from Claude Code agent session (CLAUDE_CODE_CHILD_SESSION=1) -> RAPID1310
        agent_py = (
            "import sys, unittest.mock as mock, rapid_os.cli.main as m; "
            "sys.argv = ['rapid', 'approve', 'gate.final-verification']; "
            "mock.patch('sys.stdin.isatty', return_value=True).start(); "
            "mock.patch('rapid_os.orchestration.lifecycle.read_ancestry', "
            "return_value=__import__('rapid_os.core.ancestry', fromlist=['x']).AncestryResult(())).start(); "
            "mock.patch('builtins.input', return_value='aprobar gate.final-verification').start(); "
            "sys.exit(m.main())"
        )
        env = {
            k: v
            for k, v in os.environ.items()
            if k not in ("CLAUDECODE", "CLAUDE_CODE_CHILD_SESSION")
        }
        env["PYTHONPATH"] = str(ROOT)
        env["PYTHONIOENCODING"] = "utf-8"
        env["CLAUDE_CODE_CHILD_SESSION"] = "1"
        agent_res = subprocess.run([sys.executable, "-c", agent_py], cwd=str(self.tmp_path), capture_output=True, text=True, env=env)
        self.assertEqual(agent_res.returncode, 1)
        self.assertIn("RAPID1310", agent_res.stderr)
        self.assertIn("debe hacerla una persona en su propia terminal", agent_res.stderr.lower())

    def test_all_action_kind_commands_are_syntactically_valid_cli_commands(self):
        self._rapid("init", "--yes", "--test-command", "python -m unittest")
        spec_payload = {
            "title": "Syntax Test Spec",
            "mode": "feature",
            "tasks": ["T001: Task 1"],
        }
        self._rapid("start", "feature", "--spec-file", "-", input_str=json.dumps(spec_payload))

        # Commands generated across ActionKinds
        command_candidates = [
            ["rapid", "start", "--resume"],
            ["rapid", "check", "--gate", "gate.baseline", "--", sys.executable, "-c", "import sys; sys.exit(0)"],
            ["rapid", "task", "start", "T001"],
            ["rapid", "task", "done", "T001", "--no-check"],
            ["rapid", "check", "--gate", "gate.tests", "--", sys.executable, "-c", "import sys; sys.exit(0)"],
            ["rapid", "check", "--task", "T001", "--", sys.executable, "-c", "import sys; sys.exit(0)"],
            ["rapid", "check", "--", sys.executable, "-c", "import sys; sys.exit(0)"],
            ["rapid", "finish"],
        ]

        for cmd in command_candidates:
            res = self._rapid(*cmd[1:])
            self.assertNotEqual(
                res.returncode,
                2,
                f"Command '{cmd}' exited with code 2 (syntax/argparse failure): {res.stderr}",
            )


# ---------------------------------------------------------------------------
# One scenario per engineering mode, driven through the labs in examples/.
# ---------------------------------------------------------------------------

import shutil  # noqa: E402

from rapid_os.adapters.evidence_registry import EvidenceRegistry  # noqa: E402
from rapid_os.domain.evidence import EvidenceKind  # noqa: E402

EXAMPLES = ROOT / "examples"


class LabScenarioBase(unittest.TestCase):
    """Copies a lab starter into a temp git repo, runs `rapid init`, and drives the loop."""

    LAB = ""
    ARCHETYPE: str | None = None

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        # The project lives one level below the temp dir so that sibling worktrees
        # (../<repo>-<run-id>) stay inside the temp dir.
        self.base = Path(self.temp_dir.name)
        self.project = self.base / "project"
        shutil.copytree(EXAMPLES / f"{self.LAB}-lab" / "starter", self.project)
        self._git("init", "-q")
        self._git("config", "user.name", "Lab Dev")
        self._git("config", "user.email", "lab@example.com")
        self.prepare_starter()
        self._git("add", ".")
        self._git("commit", "-qm", "baseline")
        test_cmd = f'"{sys.executable}" -m unittest discover -s tests -t .'
        init_args = ["init", "--yes", "--no-scan", "--test-command", test_cmd]
        if self.ARCHETYPE:
            init_args += ["--archetype", self.ARCHETYPE]
        res = self._rapid(*init_args)
        self.assertEqual(res.returncode, 0, res.stderr)

    def tearDown(self):
        # Remove registered worktrees before the temp dir disappears.
        subprocess.run(
            ["git", "worktree", "prune"], cwd=str(self.project), capture_output=True, check=False
        )
        self.temp_dir.cleanup()

    # -- hooks -------------------------------------------------------------
    def prepare_starter(self):
        """Adjust the starter before the baseline commit (default: nothing)."""

    # -- helpers -----------------------------------------------------------
    def _env(self, extra=None):
        env = {k: v for k, v in os.environ.items() if k not in ("CLAUDECODE", "CLAUDE_CODE_CHILD_SESSION")}
        env["PYTHONPATH"] = str(ROOT)
        env.update(extra or {})
        return env

    def _git(self, *args, cwd=None):
        return subprocess.run(
            ["git", *args], cwd=str(cwd or self.project), check=True, capture_output=True, text=True
        )

    def _rapid(self, *args, input_str=None, extra_env=None):
        return subprocess.run(
            [sys.executable, "-m", "rapid_os.cli.main", *args],
            cwd=str(self.project),
            input=input_str,
            capture_output=True,
            text=True,
            encoding="utf-8",
            env=self._env(extra_env),
        )

    def _rapid_tty(self, args, *answers, extra_env=None):
        """Run `rapid <args>` with a faked interactive terminal answering `answers` in order."""
        code = (
            "import sys, unittest.mock as mock, rapid_os.cli.main as m; "
            f"sys.argv = ['rapid'] + {list(args)!r}; "
            "mock.patch('sys.stdin.isatty', return_value=True).start(); "
            "mock.patch('rapid_os.orchestration.lifecycle.read_ancestry', "
            "return_value=__import__('rapid_os.core.ancestry', fromlist=['x']).AncestryResult(())).start(); "
            f"mock.patch('builtins.input', side_effect=[EOFError if a == '__EOF__' else a for a in {list(answers)!r}]).start(); "
            "sys.exit(m.main())"
        )
        return subprocess.run(
            [sys.executable, "-c", code],
            cwd=str(self.project),
            capture_output=True,
            text=True,
            encoding="utf-8",
            env=self._env(extra_env),
        )

    def _approve(self, gate, *extra):
        return self._rapid_tty(["approve", gate, *extra], f"aprobar {gate}")

    def _start(self, mode, spec, *flags):
        res = self._rapid("start", mode, "--spec-file", "-", "--json", *flags, input_str=json.dumps(spec))
        self.assertEqual(res.returncode, 0, f"rapid start failed: {res.stderr}")
        return json.loads(res.stdout)

    def _next(self):
        res = self._rapid("next", "--json")
        self.assertEqual(res.returncode, 0, res.stderr)
        return json.loads(res.stdout)["action"]

    def _run_command(self, cmd):
        assert cmd[0] == "rapid", cmd
        return self._rapid(*cmd[1:])

    def _drive(self, on_task, *, max_iterations=30):
        """Agent loop: follow `next` until done / await_human_approval / blocked."""
        trace = []
        for _ in range(max_iterations):
            action = self._next()
            trace.append(action)
            kind = action["kind"]
            if kind in ("await_human_approval", "done", "blocked"):
                return action, trace
            if kind == "implement_task":
                if action.get("command"):
                    res = self._run_command(action["command"])
                    self.assertEqual(res.returncode, 0, f"{action['command']} failed: {res.stderr}")
                    action = self._next()
                    trace.append(action)
                on_task(action)
                if action.get("after"):
                    res = self._run_command(action["after"])
                    self.assertEqual(res.returncode, 0, f"{action['after']} failed: {res.stderr}{res.stdout}")
                continue
            if action.get("command"):
                res = self._run_command(action["command"])
                self.assertEqual(res.returncode, 0, f"{action['command']} failed: {res.stderr}{res.stdout}")
                continue
            self.fail(f"Loop stuck on {kind}: {action}")
        self.fail("Loop exceeded maximum iterations")

    def _registry(self):
        return EvidenceRegistry(self.project, self.project / ".rapid-os")

    def _file_change_paths(self, run_id):
        paths = []
        for ev in self._registry().list(run_id):
            if ev.kind == EvidenceKind.FILE_CHANGE:
                paths.extend(ev.payload["paths"])
        return paths

    def _copy_solution(self, *relative, dest_root=None):
        dest_root = Path(dest_root or self.project)
        for rel in relative:
            target = dest_root / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(EXAMPLES / f"{self.LAB}-lab" / "solution" / rel, target)

    def _finish(self):
        res = self._rapid("finish", "--json")
        self.assertEqual(res.returncode, 0, f"rapid finish failed: {res.stderr}{res.stdout}")
        return json.loads(res.stdout)


class FeatureLabScenarioTests(LabScenarioBase):
    LAB = "feature"

    def test_feature_lab_and_start_untracked_attribution(self):
        # Untracked before `rapid start` (like the .cursorrules written by `rapid init`).
        (self.project / "notes.txt").write_text("scratch notes\n", encoding="utf-8")
        self.assertTrue((self.project / ".cursorrules").exists())

        data = self._start(
            "feature",
            {
                "title": "Booking availability",
                "business_objective": "Reject double bookings",
                "problem_statement": "Bookings can overlap",
                "acceptance_criteria": ["overlapping bookings are rejected"],
                "tasks": ["T001: Implement availability control"],
            },
        )
        run_id = data["run_id"]
        session = json.loads((self.project / ".rapid-os" / "session.json").read_text(encoding="utf-8"))
        self.assertIn("notes.txt", session["start_untracked"])
        self.assertIn(".cursorrules", session["start_untracked"])

        def implement(action):
            self._copy_solution("booking.py", "tests/test_booking.py")
            (self.project / "created_during_run.py").write_text("X = 1\n", encoding="utf-8")

        action, _ = self._drive(implement)
        self.assertEqual(action["kind"], "await_human_approval")
        self.assertEqual(self._approve("gate.final-verification").returncode, 0)
        report = self._finish()
        self.assertEqual(report["verdict"], "pass")

        changed = self._file_change_paths(run_id)
        self.assertIn("booking.py", changed)
        self.assertIn("created_during_run.py", changed)
        self.assertNotIn("notes.txt", changed)
        self.assertNotIn(".cursorrules", changed)


class BugfixLabScenarioTests(LabScenarioBase):
    LAB = "bugfix"

    def prepare_starter(self):
        # The shipped starter is already red (test_regression_expected_discount). A bugfix run
        # needs a green baseline taken BEFORE the reproduction test exists, so drop that test;
        # T001 writes it back.
        test_file = self.project / "tests" / "test_pricer.py"
        text = test_file.read_text(encoding="utf-8")
        start = text.index("    def test_regression_expected_discount")
        end = text.index("if __name__")
        test_file.write_text(text[:start] + "\n" + text[end:], encoding="utf-8")

    def test_bugfix_lab_reproduces_before_fixing(self):
        data = self._start(
            "bugfix",
            {
                "title": "Discount is applied as a multiplier",
                "business_objective": "Charge the right discounted total",
                "problem_statement": "A 10% discount on 100 yields -900",
                "acceptance_criteria": ["10% of 100 is 90"],
                "tasks": [
                    "T001: Reproducir con un test en rojo",
                    "T002: Corregir la causa raíz",
                    "T003: Verificar la regresión",
                ],
            },
        )
        run_id = data["run_id"]

        # The baseline was taken before any reproduction test: 2 tests, all green.
        baseline = [
            e for e in self._registry().list(run_id)
            if e.kind == EvidenceKind.TEST_RESULT and "gate.baseline" in e.gate_ids
        ]
        self.assertEqual(len(baseline), 1)
        self.assertEqual(baseline[0].payload["passed"], 2)
        self.assertEqual(baseline[0].payload["failed"], 0)

        # T001 (pending): `next` hands over the task start.
        action = self._next()
        self.assertEqual((action["kind"], action["task_id"]), ("implement_task", "T001"))
        self.assertEqual(action["command"], ["rapid", "task", "start", "T001"])
        self.assertEqual(self._run_command(action["command"]).returncode, 0)

        # T001 (in progress, no reproduction yet): `next` proposes the expected-failure check.
        action = self._next()
        cmd = action["command"]
        self.assertEqual(cmd[:7], ["rapid", "check", "--expect", "fail", "--task", "T001", "--"])
        self.assertEqual(action["after"][:4], ["rapid", "task", "done", "T001"])

        # Before the red test exists the expected failure is NOT reproduced: no evidence.
        premature = self._run_command(cmd)
        self.assertNotEqual(premature.returncode, 0)
        self.assertEqual([e for e in self._registry().list(run_id) if e.payload.get("expectation") == "fail"], [])

        test_file = self.project / "tests" / "test_pricer.py"
        text = test_file.read_text(encoding="utf-8")
        repro = (
            "    def test_regression_expected_discount(self):\n"
            "        items = [{\"price\": 100.0, \"qty\": 1}]\n"
            "        self.assertEqual(OrderPricer.calculate_total(items, 10.0), 90.0)\n\n"
        )
        test_file.write_text(text.replace("if __name__", repro + "if __name__", 1), encoding="utf-8")
        recorded = self._run_command(cmd)
        self.assertEqual(recorded.returncode, 0, recorded.stderr + recorded.stdout)

        # Reproduced: closing T001 must not rerun the (red by design) suite.
        action = self._next()
        self.assertEqual(action["after"], ["rapid", "task", "done", "T001", "--no-check"])
        closed = self._run_command(action["after"])
        self.assertEqual(closed.returncode, 0, closed.stderr + closed.stdout)

        expected_failures = [
            e for e in self._registry().list(run_id)
            if e.payload.get("expectation") == "fail" and "T001" in e.task_ids
        ]
        self.assertEqual(len(expected_failures), 1)
        self.assertGreater(expected_failures[0].payload["failed"], 0)

        # T002 fixes the bug; T003 verifies.
        def implement(action):
            if action["task_id"] == "T002":
                self._copy_solution("pricer.py")
                # The characterization test documents the defect (-900) and goes away with it.
                test_path = self.project / "tests" / "test_pricer.py"
                source = test_path.read_text(encoding="utf-8")
                begin = source.index("    def test_defect_characterization")
                finish = source.index("    def test_regression_expected_discount")
                test_path.write_text(source[:begin] + source[finish:], encoding="utf-8")

        action, _ = self._drive(implement)
        self.assertEqual(action["kind"], "await_human_approval", action)
        self.assertEqual(self._approve("gate.final-verification").returncode, 0)
        self.assertEqual(self._finish()["verdict"], "pass")


class RefactorLabScenarioTests(LabScenarioBase):
    LAB = "refactor"

    SPEC = {
        "title": "Decouple commission",
        "business_objective": "Separate calculation from formatting",
        "problem_statement": "Calculation is coupled to console formatting",
        "acceptance_criteria": ["same public behavior"],
    }

    def test_refactor_lab_happy_path(self):
        data = self._start(
            "refactor",
            {**self.SPEC, "tasks": ["T001: Refactor the calculator", "T002: Verify against the baseline"]},
        )
        run_id = data["run_id"]
        baseline = next(
            e for e in self._registry().list(run_id)
            if e.kind == EvidenceKind.TEST_RESULT and "gate.baseline" in e.gate_ids
        )

        def implement(action):
            if action["task_id"] == "T001":
                self._copy_solution("commission.py", "tests/test_commission.py")

        action, _ = self._drive(implement)
        self.assertEqual(action["kind"], "await_human_approval", action)
        latest = [e for e in self._registry().list(run_id) if e.kind == EvidenceKind.TEST_RESULT][-1]
        self.assertGreaterEqual(latest.payload["passed"], baseline.payload["passed"])
        self.assertEqual(self._approve("gate.final-verification").returncode, 0)
        self.assertEqual(self._finish()["verdict"], "pass")

    def test_refactor_blocks_when_passed_tests_drop_below_baseline(self):
        data = self._start("refactor", {**self.SPEC, "tasks": ["T001: Refactor the calculator"]})
        run_id = data["run_id"]
        baseline = next(
            e for e in self._registry().list(run_id)
            if e.kind == EvidenceKind.TEST_RESULT and "gate.baseline" in e.gate_ids
        )
        baseline_passed = baseline.payload["passed"]
        self.assertGreaterEqual(baseline_passed, 2)

        self.assertEqual(self._rapid("task", "start", "T001").returncode, 0)
        # "Refactor" by deleting a test: the suite stays green but passes fewer tests.
        test_file = self.project / "tests" / "test_commission.py"
        text = test_file.read_text(encoding="utf-8")
        first = text.index("    def test_")
        second = text.index("    def test_", first + 1)
        end = text.index("if __name__") if "if __name__" in text else len(text)
        test_file.write_text(text[:second] + "\n" + text[end:], encoding="utf-8")
        self.assertEqual(self._rapid("task", "done", "T001").returncode, 0)

        action = self._next()
        self.assertEqual(action["kind"], "blocked")
        self.assertIn(f"baseline had {baseline_passed} passed", action["instructions"])
        self.assertIn(f"{baseline_passed - 1} passed", action["instructions"])
        self.assertIn("1 fewer", action["instructions"])


class HardeningLabScenarioTests(LabScenarioBase):
    LAB = "hardening"
    ARCHETYPE = "corporate"  # hardening requires the security standard

    SPEC = {
        "title": "Validate profile inputs",
        "business_objective": "Reject hostile input",
        "problem_statement": "register_user accepts anything",
        "acceptance_criteria": ["invalid usernames are rejected"],
        "tasks": ["T001: Add defensive validation", "T002: Verify in the isolated workspace"],
    }

    def _session(self):
        return json.loads((self.project / ".rapid-os" / "session.json").read_text(encoding="utf-8"))

    def _start_and_complete_tasks(self):
        """Start with a worktree and drive every task to done (gates can then be modified)."""
        data = self._start("hardening", self.SPEC, "--worktree")
        workspace = Path(self._session()["workspace_path"])

        def implement(action):
            if action["task_id"] == "T001":
                self._copy_solution("profile_mgr.py", "tests/test_profile_mgr.py", dest_root=workspace)

        action, _ = self._drive(implement)
        self.assertEqual(action["kind"], "await_human_approval", action)
        return data

    def test_start_without_worktree_proposes_it(self):
        data = self._start("hardening", self.SPEC)
        action = data["action"]
        self.assertEqual(action["kind"], "blocked")
        self.assertEqual(action["command"], ["rapid", "start", "--resume", "--worktree"])
        self.assertNotIn("workspace_path", self._session())

        resumed = self._rapid("start", "--resume", "--worktree", "--json")
        self.assertEqual(resumed.returncode, 0, resumed.stderr)
        workspace = Path(self._session()["workspace_path"])
        self.assertTrue(workspace.is_dir())
        self.assertEqual(json.loads(resumed.stdout)["action"]["workspace_path"], str(workspace))

    def test_hardening_lab_runs_inside_an_isolated_worktree(self):
        data = self._start("hardening", self.SPEC, "--worktree")
        run_id = data["run_id"]
        session = self._session()
        workspace = Path(session["workspace_path"])
        self.assertEqual(workspace.name, f"project-{run_id}")
        self.assertEqual(workspace.parent.resolve(), self.base.resolve())
        branch = self._git("rev-parse", "--abbrev-ref", "HEAD", cwd=workspace).stdout.strip()
        self.assertEqual(branch, f"rapid/{run_id}")
        # The ledger stays in the main repository.
        self.assertTrue((self.project / ".rapid-os" / "runs" / run_id).is_dir())
        self.assertEqual(data["action"].get("workspace_path"), str(workspace))
        isolated = [
            e for e in self._registry().list(run_id)
            if e.kind == EvidenceKind.WORKSPACE and e.payload["mode"] == "isolated"
        ]
        self.assertEqual(len(isolated), 1)

        def implement(action):
            self.assertEqual(action["workspace_path"], str(workspace))
            if action["task_id"] == "T001":
                # Edit in the worktree only; the main checkout must stay untouched.
                self._copy_solution("profile_mgr.py", "tests/test_profile_mgr.py", dest_root=workspace)

        action, _ = self._drive(implement)
        self.assertEqual(action["kind"], "await_human_approval", action)
        self.assertEqual(action["gate_ids"], ["gate.final-verification", "gate.review"])

        main_text = (self.project / "profile_mgr.py").read_text(encoding="utf-8")
        solution_text = (EXAMPLES / "hardening-lab" / "solution" / "profile_mgr.py").read_text(encoding="utf-8")
        self.assertNotEqual(main_text, solution_text)
        self.assertEqual(
            (workspace / "profile_mgr.py").read_text(encoding="utf-8"), solution_text
        )

        # Listing pending human gates needs no TTY.
        listing = self._rapid("approve")
        self.assertEqual(listing.returncode, 0, listing.stderr)
        self.assertIn("gate.review", listing.stdout)
        self.assertIn("gate.final-verification", listing.stdout)

        # Without a TTY every mutating variant fails with RAPID1310.
        for extra in ((), ("--reject", "--reason", "no"), ("--waive", "--reason", "n/a")):
            res = self._rapid("approve", "gate.review", *extra, input_str="")
            self.assertEqual(res.returncode, 1)
            self.assertIn("RAPID1310", res.stderr, extra)

        self.assertEqual(self._approve("gate.review").returncode, 0)
        self.assertEqual(self._approve("gate.final-verification").returncode, 0)
        report = self._finish()
        self.assertEqual(report["verdict"], "pass")
        self.assertIn("profile_mgr.py", self._file_change_paths(run_id))

    def test_waive_only_waivable_gates_with_a_reason(self):
        self._start_and_complete_tasks()

        # final-verification is not waivable.
        res = self._rapid_tty(
            ["approve", "gate.final-verification", "--waive", "--reason", "skip"],
            "dispensar gate.final-verification",
        )
        self.assertEqual(res.returncode, 1)
        self.assertIn("not waivable", res.stderr)

        # Missing reason is the same error as validate_gate_transition's.
        res = self._rapid_tty(["approve", "gate.review", "--waive"], "dispensar gate.review")
        self.assertEqual(res.returncode, 1)
        self.assertIn("non-empty '--reason' is required when waiving", res.stderr)

        res = self._rapid_tty(
            ["approve", "gate.review", "--waive", "--reason", "covered by the security audit"],
            "dispensar gate.review",
        )
        self.assertEqual(res.returncode, 0, res.stderr)
        status = json.loads(self._rapid("status", "--json").stdout)
        review = next(g for g in status["run"]["gates"] if g["id"] == "gate.review")
        self.assertEqual(review["disposition"], "waived")

    def test_closed_terminal_is_reported_as_rapid1310_not_a_traceback(self):
        # Windows reports isatty() == True for stdin redirected to NUL; the prompt then hits EOF.
        self._start_and_complete_tasks()
        res = self._rapid_tty(["approve", "gate.review"], "__EOF__")
        self.assertEqual(res.returncode, 1)
        self.assertIn("RAPID1310", res.stderr)
        self.assertNotIn("Traceback", res.stderr)

    def test_reject_leaves_the_gate_failed_and_next_proposes_abort(self):
        self._start("hardening", self.SPEC, "--worktree")
        res = self._rapid_tty(
            ["approve", "gate.review", "--reject", "--reason", "validation is incomplete"],
            "rechazar gate.review",
        )
        self.assertEqual(res.returncode, 0, res.stderr)

        run_id = self._session()["active_run_id"]
        reviews = [e for e in self._registry().list(run_id) if e.kind == EvidenceKind.REVIEW]
        self.assertEqual([e.payload["outcome"] for e in reviews], ["changes_requested"])
        self.assertEqual(reviews[0].payload["reviewer"], "Lab Dev")

        action = self._next()
        self.assertEqual(action["kind"], "blocked")
        self.assertEqual(action["command"], ["rapid", "abort"])
        self.assertEqual(action["gate_ids"], ["gate.review"])

        # The gate cannot be approved or waived afterwards.
        again = self._approve("gate.review")
        self.assertEqual(again.returncode, 1)
        self.assertIn("RAPID1332", again.stderr)

        self.assertEqual(self._rapid("abort", "--reason", "changes requested").returncode, 0)
        self.assertFalse((self.project / ".rapid-os" / "session.json").exists())

    def test_reviewer_defaults_to_git_user_then_asks_on_the_terminal(self):
        self._start_and_complete_tasks()
        run_id = self._session()["active_run_id"]

        # Explicit --reviewer wins.
        self.assertEqual(
            self._approve("gate.review", "--reviewer", "Grace Hopper").returncode, 0
        )
        # No git identity at all (ignore global/system config): the terminal is asked.
        self._git("config", "--unset", "user.name")
        isolated_git = {
            "GIT_CONFIG_GLOBAL": os.devnull,
            "GIT_CONFIG_SYSTEM": os.devnull,
            "GIT_CONFIG_NOSYSTEM": "1",
        }
        res = self._rapid_tty(
            ["approve", "gate.final-verification"],
            "Ada Lovelace",
            "aprobar gate.final-verification",
            extra_env=isolated_git,
        )
        self.assertEqual(res.returncode, 0, res.stderr)
        reviewers = {
            e.gate_ids[0]: e.payload["reviewer"]
            for e in self._registry().list(run_id)
            if e.kind == EvidenceKind.REVIEW
        }
        self.assertEqual(reviewers["gate.review"], "Grace Hopper")
        self.assertEqual(reviewers["gate.final-verification"], "Ada Lovelace")


class ResearchLabScenarioTests(LabScenarioBase):
    LAB = "research"

    def test_research_lab_needs_no_tests_and_attaches_evidence(self):
        data = self._start(
            "research",
            {
                "title": "JSON vs SQLite",
                "business_objective": "Pick a storage backend",
                "problem_statement": "Unknown trade-offs",
                "acceptance_criteria": ["a recommendation backed by evidence"],
                "tasks": ["T001: Compare the backends", "T002: Document the recommendation"],
            },
        )
        run_id = data["run_id"]
        # Spike: LOW risk, no baseline and no test gate.
        status = json.loads(self._rapid("status", "--json").stdout)
        self.assertEqual([g["id"] for g in status["run"]["gates"]], ["gate.final-verification"])

        commands = []

        def implement(action):
            task = action["task_id"]
            note = self.project / "notes" / f"{task}.md"
            note.parent.mkdir(exist_ok=True)
            note.write_text(f"# Findings for {task}\nJSON is simpler; SQLite scales.\n", encoding="utf-8")
            res = self._rapid("attach", f"notes/{task}.md", "--label", f"findings {task}")
            self.assertEqual(res.returncode, 0, res.stderr)
            commands.append(res.stdout)

        action, trace = self._drive(implement)
        self.assertEqual(action["kind"], "await_human_approval", action)
        self.assertFalse(any((a.get("command") or [""])[:2] == ["rapid", "check"] for a in trace))

        evidence = self._registry().list(run_id)
        attached = [e for e in evidence if e.kind == EvidenceKind.ARTIFACT]
        self.assertEqual(len(attached), 2)
        self.assertTrue(all(e.producer == "rapid:attach" for e in attached))
        self.assertEqual({tuple(e.task_ids) for e in attached}, {("T001",), ("T002",)})
        self.assertFalse(any(e.kind == EvidenceKind.TEST_RESULT for e in evidence))

        self.assertEqual(self._approve("gate.final-verification").returncode, 0)
        self.assertEqual(self._finish()["verdict"], "pass")

    def test_attach_rejects_bad_input_with_a_code(self):
        self._start(
            "research",
            {
                "title": "JSON vs SQLite",
                "business_objective": "Pick",
                "problem_statement": "Unknown",
                "acceptance_criteria": ["x"],
                "tasks": ["T001: Compare"],
            },
        )
        for args in (("missing.md", "--label", "x"), ("experiment.py", "--label", " ")):
            res = self._rapid("attach", *args)
            self.assertEqual(res.returncode, 1, args)
            self.assertIn("RAPID1336", res.stderr)
            self.assertNotIn("Traceback", res.stderr)
        outside = self.base / "outside.md"
        outside.write_text("x", encoding="utf-8")
        res = self._rapid("attach", str(outside), "--label", "x")
        self.assertEqual(res.returncode, 1)
        self.assertIn("RAPID1336", res.stderr)


if __name__ == "__main__":
    unittest.main()
