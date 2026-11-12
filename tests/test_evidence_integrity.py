"""Evidence integrity (ruleset 3): a verdict reaches PASS only with real tests and a real human approval.

Each test reproduces a finding of the 3.2 audit on the feature lab starter:
R1 a command without a test summary satisfied gate.tests; R2 plumbing satisfied a human gate; R3 `evidence add`
could impersonate Rapid OS; R4 test evidence without a tree failed open; P1-3 the approval did not keep the tree
it approved; and a test command other than the baseline's was only a warning.
"""

from __future__ import annotations

import json
import sys

from rapid_os.adapters.eval_registry import EvalRegistry
from rapid_os.adapters.run_registry import RunRegistry
from rapid_os.domain.evidence import EvidenceKind
from tests.test_intent_loop import LabScenarioBase

SPEC = {
    "title": "Booking availability",
    "business_objective": "Reject double bookings",
    "problem_statement": "Bookings can overlap",
    "acceptance_criteria": ["overlapping bookings are rejected"],
    "tasks": ["T001: Implement availability control"],
}

BROKEN_TEST = """import unittest


class BrokenTests(unittest.TestCase):
    def test_always_red(self):
        self.assertEqual(1, 2)
"""


class EvidenceIntegrityTests(LabScenarioBase):
    LAB = "feature"

    # -- helpers -------------------------------------------------------------
    def _implement(self, action):
        self._copy_solution("booking.py", "tests/test_booking.py")

    def _to_task_done(self):
        """Start the run and implement T001; stop before any gate check."""
        run_id = self._start("feature", SPEC)["run_id"]
        self.assertEqual(self._rapid("task", "start", "T001").returncode, 0)
        self._implement(None)
        done = self._rapid("task", "done", "T001")
        self.assertEqual(done.returncode, 0, done.stderr)
        return run_id

    def _to_approval(self):
        run_id = self._start("feature", SPEC)["run_id"]
        action, _ = self._drive(self._implement)
        self.assertEqual(action["kind"], "await_human_approval", action)
        return run_id

    def _gate_state(self, run_id, gate_id):
        state = RunRegistry(self.project, self.project / ".rapid-os").get_state(run_id)
        return next(g for g in state.gates if g.id == gate_id).disposition.value

    def _evidence_add(self, run_id, name, payload):
        path = self.base / name  # outside the project: the input is not part of the verified tree
        path.write_text(json.dumps(payload), encoding="utf-8")
        return self._rapid("evidence", "add", "--run", run_id, "--input", str(path))

    def _reports(self, run_id):
        return EvalRegistry(self.project, self.project / ".rapid-os").list_reports(run_id)

    # -- R1 --------------------------------------------------------------------
    def test_r1_a_command_without_test_summary_does_not_satisfy_gate_tests(self):
        run_id = self._to_task_done()
        fake = self._rapid("check", "--gate", "gate.tests", "--kind", "test", "--", sys.executable, "-c",
                           "print('hello')")
        # H-68: a command other than test_command is recorded as a normal check, not for gate.tests.
        self.assertEqual(fake.returncode, 1, fake.stderr)
        self.assertIn("RAPID1440", fake.stderr)
        recorded = [e for e in self._registry().list(run_id) if "gate.tests" in e.gate_ids]
        self.assertEqual(recorded, [])

        action = self._next()
        self.assertEqual(action["kind"], "verify")
        self.assertIn("gate.tests", action["gate_ids"])
        self.assertEqual(action["command"], ["rapid", "check", "--gate", "gate.tests"])
        self.assertNotEqual(action["kind"], "await_human_approval")

        # Even acknowledged by plumbing and with the suite red, finish gives no PASS.
        (self.project / "tests" / "test_broken.py").write_text(BROKEN_TEST, encoding="utf-8")
        forced = self._rapid("run", "gate", run_id, "gate.tests", "acknowledged")
        self.assertEqual(forced.returncode, 0, forced.stderr)
        self.assertEqual(self._approve("gate.final-verification").returncode, 1)
        finish = self._rapid("finish", "--json")
        self.assertNotIn('"verdict": "pass"', finish.stdout)
        self.assertFalse(any(r.verdict.value == "pass" for r in self._reports(run_id)))

    def test_r1_a_test_check_that_ran_no_test_is_unverified(self):
        run_id = self._to_task_done()
        # The project's own test command, run by Rapid OS, that ran no test.
        config_file = self.project / ".rapid-os" / "config.json"
        config = json.loads(config_file.read_text(encoding="utf-8"))
        config["test_command"] = [sys.executable, "-c", "print('no tests ran, 0 passed in 0.01s')"]
        config_file.write_text(json.dumps(config), encoding="utf-8")
        empty = self._rapid("check", "--gate", "gate.tests")
        self.assertEqual(empty.returncode, 0, empty.stderr)
        last = [e for e in self._registry().list(run_id) if "gate.tests" in e.gate_ids][-1]
        self.assertTrue(last.payload["counted"])
        self.assertEqual(last.payload["passed"] + last.payload["failed"], 0)
        action = self._next()
        self.assertEqual(action["kind"], "verify")
        self.assertIn("no ejecutó ningún test", action["instructions"])

    # -- R2 / R3 -----------------------------------------------------------------
    def test_r2_plumbing_cannot_satisfy_a_human_gate(self):
        run_id = self._to_approval()
        review = self._evidence_add(run_id, "review.json", {
            "kind": "review", "producer": "user", "summary": "Approved by hand",
            "gate_ids": ["gate.final-verification"],
            "payload": {"review_type": "final", "outcome": "approved", "reviewer": "someone"},
        })
        self.assertEqual(review.returncode, 1)
        self.assertIn("RAPID1430", review.stderr)
        gate = self._rapid("run", "gate", run_id, "gate.final-verification", "acknowledged")
        self.assertEqual(gate.returncode, 1)
        self.assertIn("RAPID1431", gate.stderr)
        self.assertIn("rapid approve gate.final-verification", gate.stderr)
        self.assertEqual(self._gate_state(run_id, "gate.final-verification"), "pending")
        self.assertEqual(self._next()["kind"], "await_human_approval")

    def test_r2_a_review_from_another_producer_does_not_satisfy_the_gate_in_ruleset_3(self):
        run_id = self._to_approval()
        smuggled = self._evidence_add(run_id, "review.json", {
            "kind": "review", "producer": "ci:pipeline", "summary": "Approved by CI",
            "gate_ids": ["gate.final-verification"],
            "payload": {"review_type": "final", "outcome": "approved", "reviewer": "ci", "via": "rapid:approve"},
        })
        self.assertEqual(smuggled.returncode, 1)
        self.assertIn("RAPID1430", smuggled.stderr)
        added = self._evidence_add(run_id, "review.json", {
            "kind": "review", "producer": "ci:pipeline", "summary": "Approved by CI",
            "gate_ids": ["gate.final-verification"],
            "payload": {"review_type": "final", "outcome": "approved", "reviewer": "ci"},
        })
        self.assertEqual(added.returncode, 0, added.stderr)
        report = EvalRegistry(self.project, self.project / ".rapid-os").evaluate_run(run_id)
        self.assertEqual(report.ruleset_version, 3)
        gate = next(a for a in report.assertions if a.id == "gate.gate.final-verification.evidence")
        self.assertEqual(gate.status.value, "unverified")

    def test_r3_evidence_add_cannot_impersonate_rapid_os(self):
        run_id = self._to_task_done()
        for producer in ("rapid:check", "rapid:start", "rapid:finish", "rapid:attach", "rapid:approve"):
            with self.subTest(producer=producer):
                res = self._evidence_add(run_id, "fake.json", {
                    "kind": "test_result", "producer": producer, "summary": "Tests passed",
                    "gate_ids": ["gate.tests"],
                    "payload": {"suite": "unittest", "exit_code": 0, "passed": 9, "failed": 0, "skipped": 0,
                                "counted": True},
                })
                self.assertEqual(res.returncode, 1)
                self.assertIn("RAPID1430", res.stderr)
        self.assertFalse(any(e.producer.startswith("rapid:") and "gate.tests" in e.gate_ids
                             for e in self._registry().list(run_id)))

    # -- R4 ----------------------------------------------------------------------
    def test_r4_last_test_evidence_without_tree_asks_for_a_new_check(self):
        run_id = self._to_approval()
        added = self._evidence_add(run_id, "ci_tests.json", {
            "kind": "test_result", "producer": "ci:pipeline", "summary": "CI tests",
            "gate_ids": ["gate.tests"],
            "payload": {"suite": "unittest", "exit_code": 0, "passed": 4, "failed": 0, "skipped": 0},
        })
        self.assertEqual(added.returncode, 0, added.stderr)
        action = self._next()
        self.assertEqual(action["kind"], "verify")
        self.assertIn("RAPID1434", action["instructions"])
        approve = self._approve("gate.final-verification")
        self.assertEqual(approve.returncode, 1)
        self.assertIn("RAPID1434", approve.stderr)
        finish = self._rapid("finish")
        self.assertNotEqual(finish.returncode, 0)
        self.assertEqual(self._reports(run_id), ())
        # A new check from Rapid OS records the tree again and the run goes on.
        self.assertEqual(self._run_command(action["command"]).returncode, 0)
        self.assertEqual(self._next()["kind"], "await_human_approval")

    # -- P1-3 --------------------------------------------------------------------
    def test_p1_3_finish_refuses_code_changed_after_the_approval(self):
        run_id = self._to_approval()
        self.assertEqual(self._approve("gate.final-verification").returncode, 0)
        review = [e for e in self._registry().list(run_id) if e.kind == EvidenceKind.REVIEW][-1]
        self.assertEqual(review.payload["via"], "rapid:approve")
        self.assertTrue(review.payload["tree"])

        booking = self.project / "booking.py"
        booking.write_text(booking.read_text(encoding="utf-8") + "\n# edited after the approval\n",
                           encoding="utf-8")
        finish = self._rapid("finish")
        self.assertEqual(finish.returncode, 1)
        self.assertIn("booking.py", finish.stderr)

        # A new check covers the tests, but nobody approved this code yet.
        self.assertEqual(self._run_command(self._next()["command"]).returncode, 0)
        action = self._next()
        self.assertEqual(action["kind"], "await_human_approval")
        self.assertIn("RAPID1433", action["instructions"])
        finish = self._rapid("finish")
        self.assertEqual(finish.returncode, 1)
        self.assertIn("RAPID1433", finish.stderr)
        self.assertIn("booking.py", finish.stderr)

        self.assertEqual(self._approve("gate.final-verification").returncode, 0)
        self.assertEqual(self._finish()["verdict"], "pass")

    # -- test command other than the baseline's ------------------------------------
    def _with_other_test_command(self):
        run_id = self._to_approval()
        # A task check may use another command (it does not satisfy a test gate); it is the latest test run.
        other = self._rapid("check", "--task", "T001", "--", sys.executable, "-m", "unittest", "discover",
                            "-s", "tests", "-t", ".", "-v")
        self.assertEqual(other.returncode, 0, other.stderr)
        self.assertEqual(self._approve("gate.final-verification").returncode, 0)
        return run_id

    def test_another_test_command_blocks_finish(self):
        run_id = self._with_other_test_command()
        finish = self._rapid("finish")
        self.assertEqual(finish.returncode, 1)
        self.assertIn("RAPID1435", finish.stderr)
        self.assertIn("--accept-test-command", finish.stderr)
        self.assertEqual(self._reports(run_id), ())
        from_agent = self._rapid_tty(["finish", "--accept-test-command", "same suite, verbose"],
                                     "s", extra_env={"CLAUDE_CODE_CHILD_SESSION": "1"})
        self.assertEqual(from_agent.returncode, 1)
        self.assertIn("RAPID1310", from_agent.stderr)
        self.assertEqual(self._reports(run_id), ())

    def test_another_test_command_accepted_in_the_terminal_passes_with_the_evidence(self):
        run_id = self._with_other_test_command()
        accepted = self._rapid_tty(["finish", "--accept-test-command", "same suite, verbose"],
                                   "s")
        self.assertEqual(accepted.returncode, 0, accepted.stdout + accepted.stderr)
        self.assertIn("verdict PASS", accepted.stdout)
        acceptance = [e for e in self._registry().list(run_id)
                      if e.kind == EvidenceKind.REVIEW and e.payload.get("accepts") == "test_command_mismatch"]
        self.assertEqual(len(acceptance), 1)
        self.assertEqual(acceptance[0].payload["reason"], "same suite, verbose")
        self.assertEqual(acceptance[0].payload["via"], "rapid:finish")

    # -- reproduction of reports of earlier rulesets -----------------------------
    def test_a_report_saved_with_ruleset_2_still_replays_unaltered(self):
        run_id = self._to_approval()
        self.assertEqual(self._approve("gate.final-verification").returncode, 0)
        self._finish()
        saved = self._rapid("eval", "run", "--run", run_id, "--ruleset", "2", "--write", "--json")
        self.assertEqual(saved.returncode, 0, saved.stderr)
        self.assertEqual(json.loads(saved.stdout)["ruleset_version"], 2)
        shown = self._rapid("eval", "show", "--run", run_id, "--revision", "2")
        self.assertEqual(shown.returncode, 0, shown.stderr)
        self.assertIn("v2", shown.stdout)
        validated = self._rapid("validate")
        self.assertEqual(validated.returncode, 0, validated.stdout + validated.stderr)
        entries = EvalRegistry(self.project, self.project / ".rapid-os").list_report_entries(run_id)
        self.assertEqual([report.ruleset_version for _rev, _path, report, _stale in entries], [3, 2])
        self.assertEqual([stale for *_rest, stale in entries], [False, False])
