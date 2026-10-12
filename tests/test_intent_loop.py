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
    ) -> subprocess.CompletedProcess[str]:
        cmd = [sys.executable, "-m", "rapid_os.cli.main", *args]
        env = os.environ.copy()
        env["PYTHONPATH"] = str(ROOT)
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
            f"mock.patch('builtins.input', return_value='aprobar {human_gate_to_approve}').start(); "
            "sys.exit(m.main())"
        )
        env = os.environ.copy()
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


if __name__ == "__main__":
    unittest.main()
