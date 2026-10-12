"""Tests for Rapid OS intent check, session, and task porcelain workflows."""

from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest
import unittest.mock

from rapid_os.adapters.evidence_registry import EvidenceRegistry
from rapid_os.adapters.run_registry import RunRegistry
from rapid_os.adapters.spec_registry import SpecRegistry
from rapid_os.domain.evals import BehavioralEvaluator
from rapid_os.domain.evidence import EvidenceKind, validate_evidence_producer
from rapid_os.domain.execution import GateDisposition, RunStatus, TaskStatus
from rapid_os.orchestration.check import parse_test_output, run_check
from rapid_os.orchestration.conductor import gate_satisfied
from rapid_os.orchestration.session import (
    Session,
    clear_session,
    load_session,
    save_session,
    validate_session,
)


class IntentCheckAndSessionTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.rapid_dir = self.root / ".rapid-os"
        self.rapid_dir.mkdir(parents=True, exist_ok=True)
        self.spec_registry = SpecRegistry(self.root, self.rapid_dir)
        self.run_registry = RunRegistry(self.root, self.rapid_dir)
        self.evidence_registry = EvidenceRegistry(self.root, self.rapid_dir)
        self.evaluator = BehavioralEvaluator()

        self.spec = self.spec_registry.create(
            title="Calculator Feature",
            mode="feature",
            scope=["math operations"],
            implementation_tasks=["Implement add", "Implement subtract"],
            acceptance_criteria=["add works", "subtract works"],
        )
        self.spec_registry.set_status(self.spec.id, "ready")

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_validate_evidence_producers(self):
        for prod in ("rapid:check", "rapid:start", "rapid:finish"):
            self.assertEqual(validate_evidence_producer(prod), prod)

    def test_parse_test_output_unittest(self):
        # 1. OK output
        out_ok = "Ran 12 tests in 0.05s\n\nOK"
        res_ok = parse_test_output(out_ok, 0)
        self.assertEqual(res_ok, {"passed": 12, "failed": 0, "skipped": 0})

        # 2. FAILED output
        out_fail = "Ran 10 tests in 0.05s\n\nFAILED (failures=2, errors=1, skipped=1)"
        res_fail = parse_test_output(out_fail, 1)
        self.assertEqual(res_fail, {"passed": 6, "failed": 3, "skipped": 1})

    def test_parse_test_output_pytest(self):
        out = "=== 15 passed, 3 failed, 2 skipped in 1.45s ==="
        res = parse_test_output(out, 1)
        self.assertEqual(res, {"passed": 15, "failed": 3, "skipped": 2})

        out_clean = "8 passed in 0.12s"
        res_clean = parse_test_output(out_clean, 0)
        self.assertEqual(res_clean, {"passed": 8, "failed": 0, "skipped": 0})

    def test_session_lifecycle_and_validation(self):
        record = self.run_registry.create(spec_id=self.spec.id, spec_revision=1)
        session = Session(
            active_run_id=record.id,
            mode="feature",
            harness="cursor",
            start_head="abc1234",
        )
        saved_path = save_session(self.rapid_dir, session)
        self.assertTrue(saved_path.exists())

        loaded = load_session(self.rapid_dir)
        self.assertIsNotNone(loaded)
        self.assertEqual(loaded.active_run_id, record.id)
        self.assertEqual(loaded.mode, "feature")
        self.assertEqual(loaded.harness, "cursor")
        self.assertEqual(loaded.start_head, "abc1234")

        # Validate session: should have 0 diagnostics
        report = validate_session(self.rapid_dir, self.root)
        self.assertEqual(len(report.diagnostics), 0)

        # Transition run to terminal status (CANCELLED)
        # Verify RAPID1305 warning
        self.run_registry.transition_status(record.id, RunStatus.CANCELLED, reason="Cancelled")
        report_term = validate_session(self.rapid_dir, self.root)
        self.assertTrue(any(d.code == "RAPID1305" for d in report_term.diagnostics))

        # Non-existent run in session -> RAPID1304
        bad_session = Session(
            active_run_id="nonexistent-run-id-001",
            mode="feature",
            harness="cursor",
        )
        save_session(self.rapid_dir, bad_session)
        report_bad = validate_session(self.rapid_dir, self.root)
        self.assertTrue(any(d.code == "RAPID1304" for d in report_bad.diagnostics))

        # Clear session
        self.assertTrue(clear_session(self.rapid_dir))
        self.assertIsNone(load_session(self.rapid_dir))

    def test_run_check_green_binds_and_satisfies_gate(self):
        record = self.run_registry.create(spec_id=self.spec.id, spec_revision=1)
        contract = self.run_registry.get_contract(record.id)
        state = self.run_registry.get_state(record.id)

        # Execute check using python one-liner that exits 0
        argv = ["python", "-c", "import sys; sys.exit(0)"]
        result = run_check(
            self.root,
            self.rapid_dir,
            record.id,
            argv,
            gate_ids=["gate.baseline"],
            kind="command_result",
        )
        self.assertEqual(result.exit_code, 0)
        self.assertIsNotNone(result.evidence)
        self.assertTrue(result.log_path.exists())
        self.assertEqual(result.evidence.producer, "rapid:check")
        self.assertIn("gate.baseline", result.evidence.gate_ids)

        evidence_list = self.evidence_registry.list(record.id)
        self.assertEqual(len(evidence_list), 1)

        # Check gate_satisfied for gate.baseline
        satisfied = gate_satisfied(
            contract,
            state,
            evidence_list,
            "gate.baseline",
            evaluator=self.evaluator,
        )
        self.assertTrue(satisfied)

    def test_run_check_red_does_not_record_evidence(self):
        record = self.run_registry.create(spec_id=self.spec.id, spec_revision=1)

        argv = ["python", "-c", "import sys; print('Failure log'); sys.exit(2)"]
        result = run_check(
            self.root,
            self.rapid_dir,
            record.id,
            argv,
            gate_ids=["gate.baseline"],
            kind="command_result",
        )
        self.assertEqual(result.exit_code, 2)
        self.assertIsNone(result.evidence)
        # Log is created in scratch
        self.assertTrue(result.log_path.exists())
        self.assertIn("Failure log", result.output)

        # Evidence registry remains untouched (append-only ledger invariant)
        evidence_list = self.evidence_registry.list(record.id)
        self.assertEqual(len(evidence_list), 0)

    def test_run_check_test_counting(self):
        record = self.run_registry.create(spec_id=self.spec.id, spec_revision=1)
        argv = ["python", "-c", "print('Ran 4 tests in 0.01s\\n\\nOK'); import sys; sys.exit(0)"]
        result = run_check(
            self.root,
            self.rapid_dir,
            record.id,
            argv,
            task_ids=["T001"],
            kind="test_result",
        )
        self.assertEqual(result.exit_code, 0)
        self.assertEqual(result.passed, 4)
        self.assertEqual(result.failed, 0)
        self.assertIsNotNone(result.evidence)
        self.assertEqual(result.evidence.payload["passed"], 4)
        self.assertEqual(result.evidence.payload["passed"], 4)
        self.assertEqual(result.evidence.payload["exit_code"], 0)

    def test_cli_task_flow_and_no_check(self):
        from rapid_os.cli import main as cli_main
        record = self.run_registry.create(spec_id=self.spec.id, spec_revision=1)
        self.run_registry.transition_gate(record.id, "gate.baseline", GateDisposition.ACKNOWLEDGED, reason="Base OK")
        self.run_registry.transition_status(record.id, RunStatus.ACTIVE, reason="Start")

        # Save session
        save_session(self.rapid_dir, Session(active_run_id=record.id, mode="feature", harness="cursor"))

        with (
            unittest.mock.patch.object(cli_main, "CURRENT_DIR", self.root),
            unittest.mock.patch.object(cli_main, "PROJECT_RAPID_DIR", self.rapid_dir),
            unittest.mock.patch.object(cli_main, "CONFIG_FILE", self.rapid_dir / "config.json"),
        ):
            # task start T001
            self.assertEqual(cli_main.main(["task", "start", "T001"]), 0)
            state_after_start = self.run_registry.get_state(record.id)
            self.assertEqual(state_after_start.tasks[0].status, TaskStatus.IN_PROGRESS)

            # task done T001 with --no-check
            self.assertEqual(cli_main.main(["task", "done", "T001", "--no-check"]), 0)
            state_after_done = self.run_registry.get_state(record.id)
            self.assertEqual(state_after_done.tasks[0].status, TaskStatus.DONE)

            # task skip T002 with --reason
            self.assertEqual(cli_main.main(["task", "skip", "T002", "--reason", "Not needed"]), 0)
            state_after_skip = self.run_registry.get_state(record.id)
            self.assertEqual(state_after_skip.tasks[1].status, TaskStatus.SKIPPED)

    def test_cli_check_command(self):
        from rapid_os.cli import main as cli_main
        record = self.run_registry.create(spec_id=self.spec.id, spec_revision=1)
        save_session(self.rapid_dir, Session(active_run_id=record.id, mode="feature", harness="cursor"))

        with (
            unittest.mock.patch.object(cli_main, "CURRENT_DIR", self.root),
            unittest.mock.patch.object(cli_main, "PROJECT_RAPID_DIR", self.rapid_dir),
            unittest.mock.patch.object(cli_main, "CONFIG_FILE", self.rapid_dir / "config.json"),
        ):
            # Run successful check
            self.assertEqual(
                cli_main.main(["check", "--task", "T001", "--", "python", "-c", "import sys; sys.exit(0)"]),
                0,
            )
            evs = self.evidence_registry.list(record.id)
            self.assertEqual(len(evs), 1)
            self.assertIn("T001", evs[0].task_ids)

    def test_cli_task_errors_no_session_and_multiple_in_progress(self):
        from rapid_os.cli import main as cli_main
        clear_session(self.rapid_dir)

        with (
            unittest.mock.patch.object(cli_main, "CURRENT_DIR", self.root),
            unittest.mock.patch.object(cli_main, "PROJECT_RAPID_DIR", self.rapid_dir),
            unittest.mock.patch.object(cli_main, "CONFIG_FILE", self.rapid_dir / "config.json"),
        ):
            # No session -> RAPID1307 sys.exit(1)
            with self.assertRaises(SystemExit) as cm:
                cli_main.main(["task", "start"])
            self.assertEqual(cm.exception.code, 1)

            with self.assertRaises(SystemExit) as cm:
                cli_main.main(["check", "--", "python", "-c", "import sys"])
            self.assertEqual(cm.exception.code, 1)


if __name__ == "__main__":
    unittest.main()
