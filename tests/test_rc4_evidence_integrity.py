"""rc.4 evidence integrity (e2e of rc.3 on Windows with Codex).

H-68 and H-61: `rapid check --gate gate.tests -- python -c "print('==== 31 passed ... ====')"` satisfied gate.tests
and `rapid finish` gave PASS; a script in %TEMP% was accepted too. Now `rapid check --gate gate.tests` without a
command runs the configured test_command itself, and another command needs a person's acceptance.

H-66: with a combined test command (backend and frontend) only the last summary was counted (Angular's 2 tests,
not the backend's 31). Rapid OS runs each component of the command it combined and adds the counts; for any other
command the parser adds one summary per runner it recognizes.
"""

from __future__ import annotations

import hashlib
import json
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

from rapid_os.adapters.eval_registry import EvalRegistry
from rapid_os.domain.evidence import EvidenceKind
from rapid_os.domain.execution import GateKind
from rapid_os.orchestration.check import argv_digest, combined_components, parse_test_summaries, parse_test_summary
from rapid_os.orchestration.setup_conductor import combine_test_commands
from rapid_os.orchestration.conductor import test_command_mismatch
from tests.test_intent_loop import LabScenarioBase

ROOT = Path(__file__).resolve().parents[1]
SHORTCUTS = ROOT / "templates" / "shortcuts"
FAKE_SUMMARY = "print('==== 31 passed, 7 skipped in 1.00s ====')"
SPEC = {
    "title": "Booking availability",
    "business_objective": "Reject double bookings",
    "problem_statement": "Bookings can overlap",
    "acceptance_criteria": ["overlapping bookings are rejected"],
    "tasks": ["T001: Implement availability control"],
}


class GateTestsRunsTheConfiguredCommandTests(LabScenarioBase):
    LAB = "feature"

    def _to_task_done(self):
        run_id = self._start("feature", SPEC)["run_id"]
        self.assertEqual(self._rapid("task", "start", "T001").returncode, 0)
        self._copy_solution("booking.py", "tests/test_booking.py")
        done = self._rapid("task", "done", "T001")
        self.assertEqual(done.returncode, 0, done.stderr)
        return run_id

    def _test_command(self):
        config = json.loads((self.project / ".rapid-os" / "config.json").read_text(encoding="utf-8"))
        return config["test_command"]

    def _gate_tests_evidence(self, run_id):
        return [e for e in self._registry().list(run_id) if "gate.tests" in e.gate_ids]

    def _fake_script(self):
        # Outside the project, as the agent's script in %TEMP% (H-61).
        script = self.base / "fake_tests.py"
        script.write_text(FAKE_SUMMARY + "\n", encoding="utf-8")
        return script

    def _no_pass(self, run_id):
        finish = self._rapid("finish", "--json")
        self.assertNotEqual(finish.returncode, 0, finish.stdout)
        self.assertNotIn('"verdict": "pass"', finish.stdout)
        reports = EvalRegistry(self.project, self.project / ".rapid-os").list_reports(run_id)
        self.assertFalse(any(r.verdict.value == "pass" for r in reports))

    def test_next_gives_the_check_without_argv(self):
        self._to_task_done()
        action = self._next()
        self.assertEqual(action["kind"], "verify")
        self.assertEqual(action["command"], ["rapid", "check", "--gate", "gate.tests"])

    def test_gate_tests_without_a_command_runs_test_command(self):
        run_id = self._to_task_done()
        checked = self._rapid("check", "--gate", "gate.tests")
        self.assertEqual(checked.returncode, 0, checked.stderr)
        self.assertIn("Tests:", checked.stdout)
        evidence = self._gate_tests_evidence(run_id)
        self.assertEqual(len(evidence), 1)
        payload = evidence[0].payload
        self.assertEqual(evidence[0].kind, EvidenceKind.TEST_RESULT)
        self.assertTrue(payload["test_command"])
        self.assertTrue(payload["counted"])
        self.assertGreater(payload["passed"], 0)
        self.assertEqual(payload["argv_digest"], argv_digest(self._test_command()))
        self.assertNotIn("gate.tests", self._next().get("gate_ids", []))

    def test_python_c_print_does_not_satisfy_gate_tests_and_finish_gives_no_pass(self):
        run_id = self._to_task_done()
        fake = self._rapid("check", "--gate", "gate.tests", "--", sys.executable, "-c", FAKE_SUMMARY)
        self.assertEqual(fake.returncode, 1, fake.stdout + fake.stderr)
        self.assertIn("RAPID1440", fake.stderr)
        self.assertIn("`rapid check --gate gate.tests`", fake.stderr)
        self.assertNotIn("Check passed", fake.stdout)
        self.assertEqual(self._gate_tests_evidence(run_id), [])
        recorded = self._registry().list(run_id)[-1]
        self.assertEqual(recorded.producer, "rapid:check")
        self.assertNotIn("gate.tests", recorded.gate_ids)
        action = self._next()
        self.assertEqual(action["kind"], "verify")
        self.assertEqual(action["command"], ["rapid", "check", "--gate", "gate.tests"])
        self._no_pass(run_id)

    def test_a_temporary_script_does_not_satisfy_gate_tests(self):
        run_id = self._to_task_done()
        fake = self._rapid("check", "--json", "--gate", "gate.tests", "--", sys.executable, str(self._fake_script()))
        self.assertEqual(fake.returncode, 1, fake.stdout + fake.stderr)
        result = json.loads(fake.stdout)
        self.assertEqual(result["refused_gates"], ["gate.tests"])
        self.assertEqual(result["code"], "RAPID1440")
        self.assertEqual(self._gate_tests_evidence(run_id), [])
        self._no_pass(run_id)

    def test_the_default_binding_is_refused_too_but_the_check_is_recorded(self):
        run_id = self._to_task_done()  # every task done: a check without --gate binds gate.tests
        fake = self._rapid("check", "--", sys.executable, "-c", FAKE_SUMMARY)
        self.assertEqual(fake.returncode, 0, fake.stderr)
        self.assertIn("RAPID1440", fake.stderr)
        self.assertEqual(self._gate_tests_evidence(run_id), [])

    def test_accepted_by_the_person_satisfies_the_gate_and_keeps_argv_and_digests(self):
        run_id = self._to_task_done()
        script = self._fake_script()
        accepted = self._rapid_tty(
            ["check", "--gate", "gate.tests", "--accept-test-command", "CI corre este script", "--",
             sys.executable, str(script)],
            "s",
        )
        self.assertEqual(accepted.returncode, 0, accepted.stdout + accepted.stderr)
        evidence = self._gate_tests_evidence(run_id)
        self.assertEqual(len(evidence), 1)
        payload = evidence[0].payload
        self.assertEqual(payload["accepted"], {"reviewer": "Lab Dev", "reason": "CI corre este script",
                                               "via": "rapid:check"})
        self.assertEqual(payload["argv"][-1], "<externo>/fake_tests.py")
        self.assertIn(
            {"path": "<externo>/fake_tests.py", "sha256": hashlib.sha256(script.read_bytes()).hexdigest()},
            payload["argv_files"],
        )
        self.assertFalse(payload["test_command"])
        self.assertEqual(payload["passed"], 31)
        self.assertNotIn("gate.tests", self._next().get("gate_ids", []))

    def test_a_script_inside_the_project_is_recorded_by_its_relative_path(self):
        run_id = self._to_task_done()
        script = self.project / "scripts" / "run_tests.py"
        script.parent.mkdir()
        script.write_text(FAKE_SUMMARY + "\n", encoding="utf-8")
        accepted = self._rapid_tty(
            ["check", "--gate", "gate.tests", "--accept-test-command", "motivo", "--", sys.executable,
             "scripts/run_tests.py"],
            "s",
        )
        self.assertEqual(accepted.returncode, 0, accepted.stdout + accepted.stderr)
        payload = self._gate_tests_evidence(run_id)[0].payload
        self.assertIn("scripts/run_tests.py", payload["argv"])
        self.assertIn("scripts/run_tests.py", [f["path"] for f in payload["argv_files"]])

    def test_only_the_person_accepts_another_command(self):
        run_id = self._to_task_done()
        script = self._fake_script()
        argv = ["check", "--gate", "gate.tests", "--accept-test-command", "motivo", "--", sys.executable, str(script)]
        from_agent = self._rapid_tty(argv, "s", extra_env={"CLAUDE_CODE_CHILD_SESSION": "1"})
        self.assertEqual(from_agent.returncode, 1)
        self.assertIn("RAPID1310", from_agent.stderr)
        declined = self._rapid_tty(argv, "N")
        self.assertEqual(declined.returncode, 1)
        self.assertIn("no se aceptó", declined.stderr)
        without_tty = self._rapid(*argv)
        self.assertEqual(without_tty.returncode, 1)
        self.assertIn("RAPID1310", without_tty.stderr)
        self.assertEqual(self._gate_tests_evidence(run_id), [])
        # Nothing ran: no check log either.
        checks = self.project / ".rapid-os" / "scratch" / "checks" / run_id
        self.assertEqual(sorted(p.name for p in checks.glob("*.log")), ["1.log", "2.log"])  # baseline, task done

    def test_without_test_command_a_check_without_argv_says_how_to_configure_it(self):
        self._to_task_done()
        config_file = self.project / ".rapid-os" / "config.json"
        config = json.loads(config_file.read_text(encoding="utf-8"))
        config.pop("test_command")
        config_file.write_text(json.dumps(config), encoding="utf-8")
        result = self._rapid("check", "--gate", "gate.tests")
        self.assertEqual(result.returncode, 1)
        self.assertIn("RAPID1301", result.stderr)


class Phase10RefactorTests(LabScenarioBase):
    """Fase 10 of talleres-rc2: a refactor whose baseline ran the configured command and whose last test check
    printed a summary with `python -c`. RAPID1435 did not fire: the baseline kept no `command` (too long, or a
    Windows path with backslashes), so there was nothing to compare."""

    LAB = "refactor"
    SPEC = {
        "title": "Decouple commission",
        "business_objective": "Separate calculation from formatting",
        "problem_statement": "Calculation is coupled to console formatting",
        "acceptance_criteria": ["same public behavior"],
        "tasks": ["T001: Refactor the calculator"],
    }

    def test_a_printed_summary_after_the_baseline_blocks_finish_with_rapid1435(self):
        run_id = self._start("refactor", self.SPEC)["run_id"]

        def implement(action):
            self._copy_solution("commission.py", "tests/test_commission.py")

        action, _ = self._drive(implement)
        self.assertEqual(action["kind"], "await_human_approval", action)
        self.assertEqual(self._approve("gate.final-verification").returncode, 0)
        fake = self._rapid("check", "--task", "T001", "--", sys.executable, "-c", FAKE_SUMMARY)
        self.assertEqual(fake.returncode, 0, fake.stderr)
        finish = self._rapid("finish")
        self.assertEqual(finish.returncode, 1, finish.stdout)
        self.assertIn("RAPID1435", finish.stderr)
        self.assertEqual(EvalRegistry(self.project, self.project / ".rapid-os").list_reports(run_id), ())


class MismatchOfOldEvidenceTests(unittest.TestCase):
    """Evidence written before `argv_digest`: the flag `test_command` still tells the two commands apart."""

    def contract(self):
        return SimpleNamespace(gates=(SimpleNamespace(id="gate.baseline", kind=GateKind.BASELINE_CHECK),))

    def evidence(self, gate_ids, **payload):
        base = {"suite": "x", "exit_code": 0, "passed": 2, "failed": 0, "skipped": 0}
        return SimpleNamespace(kind=EvidenceKind.TEST_RESULT, gate_ids=tuple(gate_ids), payload={**base, **payload})

    def test_the_phase_10_payloads_are_a_mismatch(self):
        baseline = self.evidence(["gate.baseline"], counted=True, test_command=True)  # no `command`: too long
        latest = self.evidence(["gate.tests"], counted=True, test_command=False, passed=31,
                               command="python -c print('==== 31 passed, 7 skipped in 1.00s ====')")
        mismatch = test_command_mismatch(self.contract(), [baseline, latest])
        self.assertEqual(mismatch[0], "el test_command del proyecto")
        self.assertIn("31 passed", mismatch[1])

    def test_digests_decide_when_both_have_them(self):
        same = argv_digest(["python", "-m", "pytest"])
        baseline = self.evidence(["gate.baseline"], test_command=True, argv_digest=same)
        latest = self.evidence(["gate.tests"], test_command=True, argv_digest=same)
        self.assertIsNone(test_command_mismatch(self.contract(), [baseline, latest]))
        other = self.evidence(["gate.tests"], test_command=True, argv_digest=argv_digest(["pytest", "-q"]))
        self.assertIsNotNone(test_command_mismatch(self.contract(), [baseline, other]))

    def test_evidence_without_flags_or_commands_says_nothing(self):
        self.assertIsNone(test_command_mismatch(self.contract(), [self.evidence(["gate.baseline"]),
                                                                  self.evidence(["gate.tests"])]))


PYTEST_OUTPUT = "tests/test_reservas.py ....\n==== 31 passed, 7 skipped in 1.00s ====\n"
VITEST_OUTPUT = (
    " ✓ src/app.spec.ts (2 tests) 4ms\n"
    " Test Files  1 passed (1)\n"
    "      Tests  2 passed (2)\n"
    "   Duration  1.88s\n"
)
BACKEND = [sys.executable, "-c", "print('==== 31 passed, 7 skipped in 1.00s ====')"]
FRONTEND = [sys.executable, "-c", "print(' Test Files  1 passed (1)'); print('      Tests  2 passed (2)')"]
FRONTEND_RED = [sys.executable, "-c",
                "import sys; print('      Tests  1 failed | 1 passed (2)'); sys.exit(1)"]


class SeveralRunnersInOneOutputTests(unittest.TestCase):
    def test_a_pytest_and_a_vitest_summary_are_added_with_their_breakdown(self):
        output = PYTEST_OUTPUT + VITEST_OUTPUT
        self.assertEqual(parse_test_summary(output), {"passed": 33, "failed": 0, "skipped": 7})
        self.assertEqual(
            parse_test_summaries(output),
            [{"runner": "pytest", "passed": 31, "failed": 0, "skipped": 7},
             {"runner": "vitest", "passed": 2, "failed": 0, "skipped": 0}],
        )

    def test_one_runner_counts_as_before(self):
        for output, expected in (
            (PYTEST_OUTPUT, {"passed": 31, "failed": 0, "skipped": 7}),
            (VITEST_OUTPUT, {"passed": 2, "failed": 0, "skipped": 0}),
            ("Tests:       1 failed, 11 passed, 12 total", {"passed": 11, "failed": 1, "skipped": 0}),
            ("Ran 12 tests in 0.1s\n\nFAILED (failures=2, errors=1)", {"passed": 9, "failed": 3, "skipped": 0}),
        ):
            with self.subTest(output=output):
                self.assertEqual(parse_test_summary(output), expected)
                self.assertEqual(len(parse_test_summaries(output)), 1)

    def test_jest_unittest_and_karma_are_recognized_together(self):
        output = (
            "Tests:       1 failed, 11 passed, 12 total\n"
            "Ran 4 tests in 0.1s\n\nOK (skipped=1)\n"
            "Chrome Headless: Executed 5 of 6 (1 FAILED) (skipped 1) (0.1 secs / 0.05 secs)\n"
        )
        runners = [s["runner"] for s in parse_test_summaries(output)]
        self.assertEqual(runners, ["jest", "karma", "unittest"])
        self.assertEqual(parse_test_summary(output), {"passed": 11 + 4 + 3, "failed": 1 + 1, "skipped": 1 + 1})

    def test_the_combined_command_is_recognized_and_nothing_else(self):
        combined = combine_test_commands([["uv", "run", "--directory", "backend", "pytest"], ["pnpm", "test"]])
        self.assertEqual(combined_components(combined), [["uv", "run", "--directory", "backend", "pytest"],
                                                         ["pnpm", "test"]])
        self.assertIsNone(combined_components(["python", "-c", "print('31 passed in 1s')"]))
        self.assertIsNone(combined_components(["uv", "run", "pytest"]))
        self.assertIsNone(combined_components(combine_test_commands([["pytest"]])))  # one command: no wrapper


class CombinedTestCommandTests(LabScenarioBase):
    LAB = "feature"

    def _with_combined_test_command(self, *components):
        run_id = self._start("feature", SPEC)["run_id"]
        self.assertEqual(self._rapid("task", "start", "T001").returncode, 0)
        self._copy_solution("booking.py", "tests/test_booking.py")
        self.assertEqual(self._rapid("task", "done", "T001").returncode, 0)
        config_file = self.project / ".rapid-os" / "config.json"
        config = json.loads(config_file.read_text(encoding="utf-8"))
        config["test_command"] = combine_test_commands(list(components))
        config_file.write_text(json.dumps(config), encoding="utf-8")
        return run_id

    def test_each_component_is_run_and_counted(self):
        run_id = self._with_combined_test_command(BACKEND, FRONTEND)
        checked = self._rapid("check", "--gate", "gate.tests")
        self.assertEqual(checked.returncode, 0, checked.stderr)
        self.assertIn("Tests: 33 passed, 0 failed, 7 skipped", checked.stdout)
        evidence = [e for e in self._registry().list(run_id) if "gate.tests" in e.gate_ids][-1]
        self.assertEqual((evidence.payload["passed"], evidence.payload["skipped"]), (33, 7))
        self.assertTrue(evidence.payload["test_command"])
        parts = evidence.payload["components"]
        self.assertEqual([(p["passed"], p["skipped"], p["exit_code"], p["counted"]) for p in parts],
                         [(31, 7, 0, True), (2, 0, 0, True)])
        self.assertTrue(parts[0]["command"].endswith("print('==== 31 passed, 7 skipped in 1.00s ====')"))
        log = (self.project / evidence.artifacts[0].path).read_text(encoding="utf-8")
        self.assertEqual(log.count("===== rapid check: "), 2)

    def test_a_failing_component_fails_the_check_and_still_runs_the_others(self):
        run_id = self._with_combined_test_command(FRONTEND_RED, BACKEND)
        checked = self._rapid("check", "--json", "--gate", "gate.tests")
        self.assertEqual(checked.returncode, 1)
        result = json.loads(checked.stdout)
        self.assertEqual([p["exit_code"] for p in result["components"]], [1, 0])
        self.assertEqual((result["passed"], result["failed"]), (32, 1))
        self.assertEqual([e for e in self._registry().list(run_id) if "gate.tests" in e.gate_ids], [])


class ShortcutsUseTheCheckWithoutArgvTests(unittest.TestCase):
    def test_work_shortcuts_run_the_tests_with_rapid_check_without_a_command(self):
        for name in ("rapid-feature", "rapid-bugfix", "rapid-refactor", "rapid-hardening", "rapid-next"):
            text = (SHORTCUTS / f"{name}.md").read_text("utf-8")
            with self.subTest(shortcut=name):
                self.assertIn("Corre los tests siempre con `rapid check` sin comando", text)
                self.assertIn("no lo copies ni lo cites en la terminal", text)
                self.assertNotIn("Corre los tests siempre con `rapid check -- <comando>`", text)


if __name__ == "__main__":
    unittest.main()
