from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from rapid_os.adapters.evidence_registry import EvidenceRegistry
from rapid_os.adapters.run_registry import RunRegistry
from rapid_os.adapters.spec_registry import SpecRegistry
from rapid_os.domain.evals import (
    BehavioralEvaluator,
    EvaluationVerdict,
)
from rapid_os.domain.evidence import EvidenceKind
from rapid_os.domain.execution import (
    GateDisposition,
    GateKind,
    RunStatus,
    TaskStatus,
)
from rapid_os.orchestration.actions import ActionKind, NextAction
from rapid_os.orchestration.conductor import (
    gate_satisfied,
    next_action,
    next_action_without_run,
)
from rapid_os.orchestration.playbooks import Playbook, PlaybookError, load_playbook


def _get_dir_tree(root: Path) -> dict[str, int]:
    """Capture relative file paths and sizes in a directory for purity checking."""
    tree = {}
    if not root.exists():
        return tree
    for p in root.rglob("*"):
        if p.is_file():
            tree[str(p.relative_to(root))] = p.stat().st_size
    return tree


class OrchestrationConductorTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.rapid_dir = self.root / ".rapid-os"
        self.spec_registry = SpecRegistry(self.root, self.rapid_dir)
        self.run_registry = RunRegistry(self.root, self.rapid_dir)
        self.evidence_registry = EvidenceRegistry(self.root, self.rapid_dir)
        self.evaluator = BehavioralEvaluator()
        self.playbook = load_playbook("feature")

        # Create baseline spec
        self.spec = self.spec_registry.create(
            title="Calculator Feature",
            mode="feature",
            scope=["math operations"],
            implementation_tasks=["Implement add", "Implement subtract"],
            acceptance_criteria=["add works", "subtract works"],
        )
        self.spec = self.spec_registry.set_status(self.spec.id, "ready")

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_next_action_without_run(self):
        action = next_action_without_run("feature", self.playbook)
        self.assertEqual(action.kind, ActionKind.AUTHOR_SPEC)
        self.assertIsNone(action.run_id)
        self.assertEqual(action.mode, "feature")
        self.assertIsNone(action.command)
        self.assertIsNone(action.after)
        self.assertEqual(action.awaiting_human, ())
        self.assertEqual(action.missing, ())
        self.assertEqual(action.tasks_done, 0)
        self.assertEqual(action.tasks_total, 0)
        self.assertIsNone(action.outcome)

        d = action.to_dict()
        self.assertEqual(d["schema_version"], 1)
        self.assertEqual(d["action"]["kind"], "author_spec")
        self.assertEqual(d["progress"]["tasks_total"], 0)

    def test_rule_a_run_status_terminal_done(self):
        # 1. CANCELLED
        record = self.run_registry.create(spec_id=self.spec.id, spec_revision=1)
        contract = self.run_registry.get_contract(record.id)
        self.run_registry.transition_status(record.id, target_status=RunStatus.CANCELLED, reason="User cancelled")
        state = self.run_registry.get_state(record.id)

        action = next_action(contract, state, (), self.playbook, evaluator=self.evaluator)
        self.assertEqual(action.kind, ActionKind.DONE)
        self.assertEqual(action.outcome, "cancelled")
        self.assertIsNone(action.command)
        self.assertEqual(action.to_dict()["action"]["kind"], "done")
        self.assertEqual(action.to_dict()["outcome"], "cancelled")

        # 2. FAILED
        record2 = self.run_registry.create(spec_id=self.spec.id, spec_revision=1)
        contract2 = self.run_registry.get_contract(record2.id)
        # To reach ACTIVE, baseline gate must be acknowledged
        self.run_registry.transition_gate(record2.id, "gate.baseline", GateDisposition.ACKNOWLEDGED, reason="Baseline acknowledged")
        self.run_registry.transition_status(record2.id, target_status=RunStatus.ACTIVE, reason="Starting")
        self.run_registry.transition_status(record2.id, target_status=RunStatus.FAILED, reason="Fatal build error")
        state2 = self.run_registry.get_state(record2.id)

        action2 = next_action(contract2, state2, (), self.playbook, evaluator=self.evaluator)
        self.assertEqual(action2.kind, ActionKind.DONE)
        self.assertEqual(action2.outcome, "failed")

    def test_rule_b_run_status_blocked(self):
        record = self.run_registry.create(spec_id=self.spec.id, spec_revision=1)
        contract = self.run_registry.get_contract(record.id)
        self.run_registry.transition_gate(record.id, "gate.baseline", GateDisposition.ACKNOWLEDGED, reason="Baseline acknowledged")
        self.run_registry.transition_status(record.id, target_status=RunStatus.ACTIVE, reason="Starting")
        self.run_registry.transition_status(record.id, target_status=RunStatus.BLOCKED, reason="Blocked on external API key")
        state = self.run_registry.get_state(record.id)

        action = next_action(contract, state, (), self.playbook, evaluator=self.evaluator)
        self.assertEqual(action.kind, ActionKind.BLOCKED)
        self.assertIsNone(action.command)
        self.assertIn("Blocked on external API key", action.instructions)

    def test_rule_c_prepared_with_pending_baseline(self):
        record = self.run_registry.create(spec_id=self.spec.id, spec_revision=1)
        contract = self.run_registry.get_contract(record.id)
        state = self.run_registry.get_state(record.id)

        # Baseline gate is pending and unverified -> run_baseline
        action = next_action(
            contract, state, (), self.playbook,
            evaluator=self.evaluator,
            test_command=["python", "-m", "pytest"]
        )
        self.assertEqual(action.kind, ActionKind.RUN_BASELINE)
        self.assertIn("gate.baseline", action.gate_ids)
        self.assertEqual(action.command, ["rapid", "check", "--gate", "gate.baseline", "--", "python", "-m", "pytest"])
        self.assertIsNone(action.after)

        # When baseline evidence is registered and gate assertion is PASS -> activate
        (self.root / "base.log").write_text("All passed\n", encoding="utf-8")
        self.evidence_registry.add(
            record.id,
            {
                "kind": "command_result",
                "producer": "harness:cursor",
                "summary": "Baseline check passed",
                "gate_ids": ["gate.baseline"],
                "payload": {"label": "pytest", "exit_code": 0},
                "artifacts": ["base.log"],
            },
        )
        evidence = self.evidence_registry.list(record.id)
        # Disposition acknowledged
        self.run_registry.transition_gate(record.id, "gate.baseline", GateDisposition.ACKNOWLEDGED, reason="Baseline green")
        state = self.run_registry.get_state(record.id)

        action_act = next_action(
            contract, state, evidence, self.playbook,
            evaluator=self.evaluator,
            test_command=["python", "-m", "pytest"]
        )
        self.assertEqual(action_act.kind, ActionKind.ACTIVATE)
        self.assertEqual(action_act.command, ["rapid", "start", "--resume"])

    def test_rule_d_active_with_tasks(self):
        record = self.run_registry.create(spec_id=self.spec.id, spec_revision=1)
        contract = self.run_registry.get_contract(record.id)
        self.run_registry.transition_gate(record.id, "gate.baseline", GateDisposition.ACKNOWLEDGED, reason="Baseline OK")
        self.run_registry.transition_status(record.id, target_status=RunStatus.ACTIVE, reason="Started")
        state = self.run_registry.get_state(record.id)

        # First task T001 is pending -> implement_task with start command
        action = next_action(contract, state, (), self.playbook, evaluator=self.evaluator)
        self.assertEqual(action.kind, ActionKind.IMPLEMENT_TASK)
        self.assertEqual(action.task_id, "T001")
        self.assertEqual(action.command, ["rapid", "task", "start", "T001"])
        self.assertEqual(action.after, ["rapid", "task", "done", "T001"])

        # When T001 is already in_progress -> command is None
        self.run_registry.transition_task(record.id, "T001", TaskStatus.IN_PROGRESS, reason="Working")
        state = self.run_registry.get_state(record.id)
        action_in_prog = next_action(contract, state, (), self.playbook, evaluator=self.evaluator)
        self.assertEqual(action_in_prog.kind, ActionKind.IMPLEMENT_TASK)
        self.assertEqual(action_in_prog.task_id, "T001")
        self.assertIsNone(action_in_prog.command)
        self.assertEqual(action_in_prog.after, ["rapid", "task", "done", "T001"])

        # When a task is BLOCKED -> blocked
        self.run_registry.transition_task(record.id, "T001", TaskStatus.BLOCKED, reason="Missing dependency")
        state = self.run_registry.get_state(record.id)
        action_blocked = next_action(contract, state, (), self.playbook, evaluator=self.evaluator)
        self.assertEqual(action_blocked.kind, ActionKind.BLOCKED)
        self.assertEqual(action_blocked.task_id, "T001")

    def test_rule_e_and_f_and_g_lifecycle(self):
        record = self.run_registry.create(spec_id=self.spec.id, spec_revision=1)
        contract = self.run_registry.get_contract(record.id)
        # Record baseline evidence first
        (self.root / "base.log").write_text("Baseline OK\n", encoding="utf-8")
        self.evidence_registry.add(
            record.id,
            {
                "kind": "command_result",
                "producer": "harness:cursor",
                "summary": "Baseline passed",
                "gate_ids": ["gate.baseline"],
                "payload": {"label": "pytest", "exit_code": 0},
                "artifacts": ["base.log"],
            },
        )
        self.run_registry.transition_gate(record.id, "gate.baseline", GateDisposition.ACKNOWLEDGED, reason="Baseline OK")
        self.run_registry.transition_status(record.id, target_status=RunStatus.ACTIVE, reason="Started")
        # Mark tasks done
        self.run_registry.transition_task(record.id, "T001", TaskStatus.IN_PROGRESS, reason="Start")
        self.run_registry.transition_task(record.id, "T001", TaskStatus.DONE, reason="Done")
        self.run_registry.transition_task(record.id, "T002", TaskStatus.IN_PROGRESS, reason="Start")
        self.run_registry.transition_task(record.id, "T002", TaskStatus.DONE, reason="Done")
        state = self.run_registry.get_state(record.id)

        evidence_base = self.evidence_registry.list(record.id)
        # Rule e.2: tasks terminal but without task execution evidence -> verify task T001
        action_verify_task = next_action(
            contract, state, evidence_base, self.playbook,
            evaluator=self.evaluator,
            test_command=["python", "-m", "pytest"]
        )
        self.assertEqual(action_verify_task.kind, ActionKind.VERIFY)
        self.assertEqual(action_verify_task.task_id, "T001")
        self.assertEqual(action_verify_task.command, ["rapid", "check", "--task", "T001", "--", "python", "-m", "pytest"])

        # Record test evidence linked to tasks
        (self.root / "test.log").write_text("Tests OK\n", encoding="utf-8")
        self.evidence_registry.add(
            record.id,
            {
                "kind": "test_result",
                "producer": "harness:cursor",
                "summary": "Implementation tests passed",
                "task_ids": ["T001", "T002"],
                "gate_ids": ["gate.tests"],
                "payload": {
                    "suite": "pytest",
                    "exit_code": 0,
                    "passed": 2,
                    "failed": 0,
                    "skipped": 0,
                },
                "artifacts": ["test.log"],
            },
        )
        self.evidence_registry.add(
            record.id,
            {
                "kind": "workspace",
                "producer": "harness:cursor",
                "summary": "Current workspace observation",
                "capability_ids": ["workspace.current"],
                "payload": {"mode": "current"},
            },
        )
        self.run_registry.transition_gate(record.id, "gate.tests", GateDisposition.ACKNOWLEDGED, reason="OK")
        evidence = self.evidence_registry.list(record.id)
        state = self.run_registry.get_state(record.id)

        # Rule f: Machine gates passed, but human gate (gate.final-verification) is pending -> await_human_approval
        action_human = next_action(contract, state, evidence, self.playbook, evaluator=self.evaluator)
        self.assertEqual(action_human.kind, ActionKind.AWAIT_HUMAN_APPROVAL)
        self.assertIn("gate.final-verification", action_human.awaiting_human)

        # Acknowledge human gate with review evidence
        self.evidence_registry.add(
            record.id,
            {
                "kind": "review",
                "producer": "harness:cursor",
                "summary": "Final human review passed",
                "gate_ids": ["gate.final-verification"],
                "payload": {
                    "review_type": "final",
                    "outcome": "approved",
                    "reviewer": "human_lead",
                },
            },
        )
        self.run_registry.transition_gate(record.id, "gate.final-verification", GateDisposition.ACKNOWLEDGED, reason="Approved")
        evidence = self.evidence_registry.list(record.id)
        state = self.run_registry.get_state(record.id)

        # Rule g: All resolved -> finish
        action_finish = next_action(contract, state, evidence, self.playbook, evaluator=self.evaluator)
        self.assertEqual(action_finish.kind, ActionKind.FINISH)
        self.assertEqual(action_finish.command, ["rapid", "finish"])

    def test_determinism_and_purity(self):
        record = self.run_registry.create(spec_id=self.spec.id, spec_revision=1)
        contract = self.run_registry.get_contract(record.id)
        state = self.run_registry.get_state(record.id)
        evidence = self.evidence_registry.list(record.id)

        # Purity check: compare tree before and after
        tree_before = _get_dir_tree(self.rapid_dir)

        action_1 = next_action(contract, state, evidence, self.playbook, evaluator=self.evaluator)
        dict_1 = action_1.to_dict()
        bytes_1 = json.dumps(dict_1, sort_keys=True).encode("utf-8")

        tree_middle = _get_dir_tree(self.rapid_dir)
        self.assertEqual(tree_before, tree_middle, "next_action must NOT write anything to disk")

        action_2 = next_action(contract, state, evidence, self.playbook, evaluator=self.evaluator)
        dict_2 = action_2.to_dict()
        bytes_2 = json.dumps(dict_2, sort_keys=True).encode("utf-8")

        tree_after = _get_dir_tree(self.rapid_dir)
        self.assertEqual(tree_before, tree_after, "next_action must NOT write anything to disk")

        # Determinism check: identical byte-for-byte
        self.assertEqual(bytes_1, bytes_2)
        self.assertEqual(dict_1, dict_2)

    def test_playbook_loading_and_errors(self):
        # Valid feature playbook
        pb = load_playbook("feature")
        self.assertEqual(pb.schema_version, 1)
        self.assertEqual(pb.mode, "feature")
        self.assertIn("author_spec", pb.instructions)
        self.assertIn("implement_task", pb.instructions)

        # Non-existent mode raises RAPID1303 PlaybookError
        with self.assertRaises(PlaybookError) as ctx:
            load_playbook("non_existent_mode_xyz")
        self.assertIn("RAPID1303", str(ctx.exception))
        self.assertEqual(ctx.exception.code, "RAPID1303")

    def test_gate_satisfied_pure_function(self):
        record = self.run_registry.create(spec_id=self.spec.id, spec_revision=1)
        contract = self.run_registry.get_contract(record.id)
        state = self.run_registry.get_state(record.id)

        # Initially with no evidence, gate.baseline is not satisfied
        self.assertFalse(gate_satisfied(contract, state, (), "gate.baseline", evaluator=self.evaluator))

        # Add qualifying baseline evidence
        (self.root / "base_sat.log").write_text("OK\n", encoding="utf-8")
        self.evidence_registry.add(
            record.id,
            {
                "kind": "command_result",
                "producer": "harness:cursor",
                "summary": "Baseline check passed",
                "gate_ids": ["gate.baseline"],
                "payload": {"label": "pytest", "exit_code": 0},
                "artifacts": ["base_sat.log"],
            },
        )
        evidence = self.evidence_registry.list(record.id)
        # Gate state remains PENDING on disk
        self.assertEqual(state.gates[0].disposition, GateDisposition.PENDING)
        # gate_satisfied returns True hypothetically without modifying disk
        self.assertTrue(gate_satisfied(contract, state, evidence, "gate.baseline", evaluator=self.evaluator))

    def test_full_lifecycle_without_manual_machine_gate_transitions(self):
        # Baseline and machine gates remain PENDING in RunState; conductor recognizes they are satisfied
        record = self.run_registry.create(spec_id=self.spec.id, spec_revision=1)
        contract = self.run_registry.get_contract(record.id)
        state = self.run_registry.get_state(record.id)

        # 1. PREPARED with pending baseline and no evidence -> run_baseline
        action = next_action(contract, state, (), self.playbook, evaluator=self.evaluator, test_command=["pytest"])
        self.assertEqual(action.kind, ActionKind.RUN_BASELINE)

        # 2. Add baseline evidence. Gate remains PENDING in state! -> activate
        (self.root / "base_flow.log").write_text("Baseline OK\n", encoding="utf-8")
        self.evidence_registry.add(
            record.id,
            {
                "kind": "command_result",
                "producer": "harness:cursor",
                "summary": "Baseline OK",
                "gate_ids": ["gate.baseline"],
                "payload": {"label": "pytest", "exit_code": 0},
                "artifacts": ["base_flow.log"],
            },
        )
        evidence = self.evidence_registry.list(record.id)
        action_act = next_action(contract, state, evidence, self.playbook, evaluator=self.evaluator, test_command=["pytest"])
        self.assertEqual(action_act.kind, ActionKind.ACTIVATE)
        self.assertEqual(action_act.command, ["rapid", "start", "--resume"])

        # 3. Transition run to ACTIVE (via gate acknowledgment for precondition) and complete tasks
        self.run_registry.transition_gate(record.id, "gate.baseline", GateDisposition.ACKNOWLEDGED, reason="Base OK")
        self.run_registry.transition_status(record.id, target_status=RunStatus.ACTIVE, reason="Start")
        self.run_registry.transition_task(record.id, "T001", TaskStatus.IN_PROGRESS, reason="Start")
        self.run_registry.transition_task(record.id, "T001", TaskStatus.DONE, reason="Done")
        self.run_registry.transition_task(record.id, "T002", TaskStatus.IN_PROGRESS, reason="Start")
        self.run_registry.transition_task(record.id, "T002", TaskStatus.DONE, reason="Done")
        state_active = self.run_registry.get_state(record.id)
        # 4. Tasks done without task evidence -> verify task T001
        action_verify = next_action(contract, state_active, evidence, self.playbook, evaluator=self.evaluator, test_command=["pytest"])
        self.assertEqual(action_verify.kind, ActionKind.VERIFY)
        self.assertEqual(action_verify.task_id, "T001")
        self.assertEqual(action_verify.command, ["rapid", "check", "--task", "T001", "--", "pytest"])

        # 5. Add qualifying test evidence for T001 and T002. gate.tests remains PENDING in RunState!
        (self.root / "test_flow.log").write_text("Tests OK\n", encoding="utf-8")
        self.evidence_registry.add(
            record.id,
            {
                "kind": "test_result",
                "producer": "harness:cursor",
                "summary": "Tests OK",
                "task_ids": ["T001", "T002"],
                "gate_ids": ["gate.tests"],
                "payload": {"suite": "pytest", "exit_code": 0, "passed": 2, "failed": 0, "skipped": 0},
                "artifacts": ["test_flow.log"],
            },
        )
        self.evidence_registry.add(
            record.id,
            {
                "kind": "workspace",
                "producer": "harness:cursor",
                "summary": "Workspace observation",
                "capability_ids": ["workspace.current"],
                "payload": {"mode": "current"},
            },
        )
        evidence2 = self.evidence_registry.list(record.id)

        # gate.tests is now gate_satisfied! Next action is await_human_approval (for gate.final-verification)
        action_human = next_action(contract, state_active, evidence2, self.playbook, evaluator=self.evaluator, test_command=["pytest"])
        self.assertEqual(action_human.kind, ActionKind.AWAIT_HUMAN_APPROVAL)
        self.assertIn("gate.final-verification", action_human.awaiting_human)

        # 6. Human reviews and acknowledges gate.final-verification
        self.evidence_registry.add(
            record.id,
            {
                "kind": "review",
                "producer": "harness:cursor",
                "summary": "Review approved",
                "gate_ids": ["gate.final-verification"],
                "payload": {"review_type": "final", "outcome": "approved", "reviewer": "qa_lead"},
            },
        )
        self.run_registry.transition_gate(record.id, "gate.final-verification", GateDisposition.ACKNOWLEDGED, reason="Approved")
        state_reviewed = self.run_registry.get_state(record.id)
        evidence3 = self.evidence_registry.list(record.id)

        # All resolved -> finish (rapid finish will acknowledge gate.tests)
        action_finish = next_action(contract, state_reviewed, evidence3, self.playbook, evaluator=self.evaluator, test_command=["pytest"])
        self.assertEqual(action_finish.kind, ActionKind.FINISH)
        self.assertEqual(action_finish.command, ["rapid", "finish"])

    def test_unverified_task_without_evidence_triggers_verify_task(self):
        record = self.run_registry.create(spec_id=self.spec.id, spec_revision=1)
        contract = self.run_registry.get_contract(record.id)
        self.run_registry.transition_gate(record.id, "gate.baseline", GateDisposition.ACKNOWLEDGED, reason="Base OK")
        self.run_registry.transition_status(record.id, target_status=RunStatus.ACTIVE, reason="Start")
        # Mark tasks done without linking any execution evidence to T001
        self.run_registry.transition_task(record.id, "T001", TaskStatus.IN_PROGRESS, reason="Start")
        self.run_registry.transition_task(record.id, "T001", TaskStatus.DONE, reason="Done")
        self.run_registry.transition_task(record.id, "T002", TaskStatus.IN_PROGRESS, reason="Start")
        self.run_registry.transition_task(record.id, "T002", TaskStatus.DONE, reason="Done")
        state = self.run_registry.get_state(record.id)

        action = next_action(
            contract, state, (), self.playbook,
            evaluator=self.evaluator,
            test_command=["python", "-m", "pytest"]
        )
        self.assertEqual(action.kind, ActionKind.VERIFY)
        self.assertEqual(action.task_id, "T001")
        self.assertEqual(action.command, ["rapid", "check", "--task", "T001", "--", "python", "-m", "pytest"])

    def test_no_test_command_returns_command_none_and_rapid1301_instruction(self):
        record = self.run_registry.create(spec_id=self.spec.id, spec_revision=1)
        contract = self.run_registry.get_contract(record.id)
        state = self.run_registry.get_state(record.id)

        # Baseline check without test_command
        action_base = next_action(
            contract, state, (), self.playbook,
            evaluator=self.evaluator,
            test_command=None
        )
        self.assertEqual(action_base.kind, ActionKind.RUN_BASELINE)
        self.assertIsNone(action_base.command)
        self.assertIn("RAPID1301", action_base.instructions)
        self.assertIn("rapid setup set test-command", action_base.instructions)

        # Task verification without test_command
        self.run_registry.transition_gate(record.id, "gate.baseline", GateDisposition.ACKNOWLEDGED, reason="Base OK")
        self.run_registry.transition_status(record.id, target_status=RunStatus.ACTIVE, reason="Start")
        self.run_registry.transition_task(record.id, "T001", TaskStatus.IN_PROGRESS, reason="Start")
        self.run_registry.transition_task(record.id, "T001", TaskStatus.DONE, reason="Done")
        self.run_registry.transition_task(record.id, "T002", TaskStatus.IN_PROGRESS, reason="Start")
        self.run_registry.transition_task(record.id, "T002", TaskStatus.DONE, reason="Done")
        state_done = self.run_registry.get_state(record.id)

        action_verify = next_action(
            contract, state_done, (), self.playbook,
            evaluator=self.evaluator,
            test_command=None
        )
        self.assertEqual(action_verify.kind, ActionKind.VERIFY)
        self.assertIsNone(action_verify.command)
        self.assertIn("RAPID1301", action_verify.instructions)
        self.assertIn("rapid setup set test-command", action_verify.instructions)

    def test_unverified_tests_execute_capability_proposes_rapid_check_test_command(self):
        record = self.run_registry.create(spec_id=self.spec.id, spec_revision=1)
        contract = self.run_registry.get_contract(record.id)
        self.run_registry.transition_gate(record.id, "gate.baseline", GateDisposition.ACKNOWLEDGED, reason="Base OK")
        self.run_registry.transition_status(record.id, target_status=RunStatus.ACTIVE, reason="Start")
        self.run_registry.transition_task(record.id, "T001", TaskStatus.IN_PROGRESS, reason="Start")
        self.run_registry.transition_task(record.id, "T001", TaskStatus.DONE, reason="Done")
        self.run_registry.transition_task(record.id, "T002", TaskStatus.IN_PROGRESS, reason="Start")
        self.run_registry.transition_task(record.id, "T002", TaskStatus.DONE, reason="Done")

        # Provide evidence for tasks and workspace and gates, but NOT tests.execute capability
        (self.root / "flow.log").write_text("OK\n", encoding="utf-8")
        self.evidence_registry.add(
            record.id,
            {
                "kind": "command_result",
                "producer": "rapid:check",
                "summary": "Task evidence",
                "task_ids": ["T001", "T002"],
                "gate_ids": ["gate.tests"],
                "payload": {"label": "build", "exit_code": 0},
                "artifacts": ["flow.log"],
            },
        )
        self.evidence_registry.add(
            record.id,
            {
                "kind": "workspace",
                "producer": "harness:cursor",
                "summary": "Workspace observation",
                "capability_ids": ["workspace.current"],
                "payload": {"mode": "current"},
            },
        )
        self.run_registry.transition_gate(record.id, "gate.tests", GateDisposition.ACKNOWLEDGED, reason="Tests acknowledged")
        evidence = self.evidence_registry.list(record.id)
        state = self.run_registry.get_state(record.id)

        action = next_action(
            contract, state, evidence, self.playbook,
            evaluator=self.evaluator,
            test_command=["pytest", "-v"],
        )
        self.assertEqual(action.kind, ActionKind.VERIFY)
        self.assertEqual(action.command, ["rapid", "check", "--", "pytest", "-v"])


if __name__ == "__main__":
    unittest.main()

