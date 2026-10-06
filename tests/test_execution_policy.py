from contextlib import redirect_stderr, redirect_stdout
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from rapid_os.adapters.execution_policy import (
    load_execution_policy,
    write_default_execution_policy,
)
from rapid_os.adapters.run_registry import RunRegistry
from rapid_os.adapters.spec_registry import SpecRegistry
from rapid_os.cli import main as cli_main
from rapid_os.domain.context import (
    ContextCompiler,
    ContextPriority,
    ContextRequest,
    ContextSource,
    ContextSourceKind,
)
from rapid_os.domain.execution import (
    DEFAULT_EXECUTION_POLICY,
    EXECUTION_CONTRACT_SCHEMA_VERSION,
    EXECUTION_POLICY_SCHEMA_VERSION,
    RUN_SCHEMA_VERSION,
    RUN_STATE_SCHEMA_VERSION,
    ContextSnapshotMismatchError,
    DuplicateRunIdentityError,
    ExecutionClass,
    ExecutionContract,
    ExecutionPolicy,
    ExecutionPolicyEvaluator,
    ExecutionPreconditionError,
    GateDisposition,
    GateKind,
    GatePhase,
    GateState,
    InvalidExecutionContractError,
    InvalidExecutionPolicyError,
    InvalidGateTransitionError,
    InvalidRunRecordError,
    InvalidRunStateError,
    InvalidRunTransitionError,
    InvalidSpecBindingError,
    InvalidTaskTransitionError,
    PolicyViolationError,
    RiskLevel,
    RunNotFoundError,
    RunRecord,
    RunState,
    RunStateHistoryGapError,
    RunStatus,
    TaskContract,
    TaskState,
    TaskStatus,
    UnsafeRunPathError,
    WorkspaceRequirement,
    build_execution_contract,
    derive_run_id,
    derive_task_contracts,
    validate_run_id,
    verify_initial_run_state,
    verify_run_state_transition,
)
from rapid_os.domain.project import ProjectModel
from rapid_os.domain.specs import SpecMode, SpecRevision, SpecStatus
from rapid_os.domain.validation import (
    ERROR,
    INFO,
    WARNING,
    validate_execution_policy,
    validate_project,
    validate_run_registry,
)


def _make_spec_revision(
    *,
    spec_id: str = "checkout-flow",
    revision: int = 1,
    title: str = "Checkout Flow",
    mode: SpecMode = SpecMode.FEATURE,
    business_objective: str = "Improve checkout conversion",
    problem_statement: str = "Users drop off during payment",
    scope: tuple[str, ...] = ("Checkout UI", "Order service"),
    technical_constraints: tuple[str, ...] = ("Deterministic idempotency",),
    affected_paths: tuple[str, ...] = ("src/checkout/service.py",),
    data_impact: str = "",
    acceptance_criteria: tuple[str, ...] = ("Orders are idempotent",),
    testing_strategy: tuple[str, ...] = ("Unit tests",),
    implementation_tasks: tuple[str, ...] = (
        "Add idempotency key model",
        "Validate duplicate requests",
    ),
    tags: tuple[str, ...] = (),
) -> SpecRevision:
    return SpecRevision(
        schema_version=1,
        spec_id=spec_id,
        revision=revision,
        title=title,
        mode=mode,
        business_objective=business_objective,
        problem_statement=problem_statement,
        scope=scope,
        out_of_scope=("Legacy billing",),
        actors_users=("Customer",),
        main_flow=("Submit order", "Confirm payment"),
        edge_cases=("Network retry",),
        business_rules=("Never charge twice",),
        technical_constraints=technical_constraints,
        affected_paths=affected_paths,
        data_impact=data_impact,
        acceptance_criteria=acceptance_criteria,
        testing_strategy=testing_strategy,
        implementation_tasks=implementation_tasks,
        tags=tags,
    )


def _seed_project(root: Path) -> Path:
    rapid_dir = root / ".rapid-os"
    standards_dir = rapid_dir / "standards"
    standards_dir.mkdir(parents=True, exist_ok=True)
    (standards_dir / "business.md").write_text(
        "# Business Rules\n- Orders must be idempotent.\n",
        encoding="utf-8",
    )
    (standards_dir / "tech-stack.md").write_text(
        "# Tech Stack\n- Python 3.12\n- FastAPI\n",
        encoding="utf-8",
    )
    (standards_dir / "topology.md").write_text(
        "# Topology\n- Modular monolith\n",
        encoding="utf-8",
    )
    (standards_dir / "security.md").write_text(
        "# Security\n- Enforce strict input validation.\n",
        encoding="utf-8",
    )
    (standards_dir / "coding-rules.md").write_text(
        "# Coding Rules\n- Explicit domain contracts.\n",
        encoding="utf-8",
    )
    (rapid_dir / "config.json").write_text(
        json.dumps({"tools": ["cursor"]}, indent=2) + "\n",
        encoding="utf-8",
    )
    return rapid_dir


class ExecutionPolicyEvaluatorTests(unittest.TestCase):
    """Sections 77-81: Pure domain tests for classification, risk, gates, overrides, and contract determinism."""

    def setUp(self):
        self.evaluator = ExecutionPolicyEvaluator()
        self.policy = DEFAULT_EXECUTION_POLICY

    def test_classification_rules_by_mode_tags_paths_and_data_impact(self):
        # 1. research -> spike
        research_spec = _make_spec_revision(
            mode=SpecMode.RESEARCH,
            affected_paths=("docs/notes.md",),
        )
        res_decision = self.evaluator.evaluate(research_spec, self.policy)
        self.assertEqual(res_decision.classification, ExecutionClass.SPIKE)

        # 2. simple feature / bugfix / refactor -> bounded
        feature_spec = _make_spec_revision(mode=SpecMode.FEATURE)
        feat_decision = self.evaluator.evaluate(feature_spec, self.policy)
        self.assertEqual(feat_decision.classification, ExecutionClass.BOUNDED)

        bugfix_spec = _make_spec_revision(mode=SpecMode.BUGFIX)
        self.assertEqual(
            self.evaluator.evaluate(bugfix_spec, self.policy).classification,
            ExecutionClass.BOUNDED,
        )

        refactor_spec = _make_spec_revision(mode=SpecMode.REFACTOR)
        self.assertEqual(
            self.evaluator.evaluate(refactor_spec, self.policy).classification,
            ExecutionClass.BOUNDED,
        )

        # 3. hardening -> architectural
        hardening_spec = _make_spec_revision(mode=SpecMode.HARDENING)
        hard_decision = self.evaluator.evaluate(hardening_spec, self.policy)
        self.assertEqual(
            hard_decision.classification,
            ExecutionClass.ARCHITECTURAL,
        )
        self.assertTrue(
            any("mode.hardening" in r for r in hard_decision.reasons)
        )

        # 4. migration tag -> architectural
        migration_spec = _make_spec_revision(
            mode=SpecMode.FEATURE,
            tags=("migration",),
        )
        mig_decision = self.evaluator.evaluate(migration_spec, self.policy)
        self.assertEqual(
            mig_decision.classification,
            ExecutionClass.ARCHITECTURAL,
        )

        # 5. architectural path or data_impact -> architectural
        path_spec = _make_spec_revision(
            mode=SpecMode.FEATURE,
            affected_paths=("db/migrations/0001_init.sql",),
        )
        self.assertEqual(
            self.evaluator.evaluate(path_spec, self.policy).classification,
            ExecutionClass.ARCHITECTURAL,
        )

        data_spec = _make_spec_revision(
            mode=SpecMode.FEATURE,
            data_impact="Adds orders_idempotency table",
        )
        self.assertEqual(
            self.evaluator.evaluate(data_spec, self.policy).classification,
            ExecutionClass.ARCHITECTURAL,
        )

    def test_risk_levels_and_elevating_signals(self):
        # spike -> low
        spike_spec = _make_spec_revision(
            mode=SpecMode.RESEARCH,
            affected_paths=("docs/spike.md",),
        )
        spike_dec = self.evaluator.evaluate(spike_spec, self.policy)
        self.assertEqual(spike_dec.risk, RiskLevel.LOW)
        self.assertEqual(
            spike_dec.workspace,
            WorkspaceRequirement.CURRENT_ALLOWED,
        )

        # bounded -> medium
        bounded_spec = _make_spec_revision(mode=SpecMode.FEATURE)
        bounded_dec = self.evaluator.evaluate(bounded_spec, self.policy)
        self.assertEqual(bounded_dec.risk, RiskLevel.MEDIUM)
        self.assertEqual(
            bounded_dec.workspace,
            WorkspaceRequirement.CURRENT_ALLOWED,
        )

        # architectural -> high
        arch_spec = _make_spec_revision(
            mode=SpecMode.HARDENING,
            tags=("security",),
        )
        arch_dec = self.evaluator.evaluate(arch_spec, self.policy)
        self.assertEqual(arch_dec.risk, RiskLevel.HIGH)
        self.assertEqual(
            arch_dec.workspace,
            WorkspaceRequirement.ISOLATED_REQUIRED,
        )
        signal_ids = {s.id for s in arch_dec.risk_signals}
        self.assertIn("mode.hardening", signal_ids)
        self.assertIn("scope.security", signal_ids)
        self.assertIn("classification.architectural", signal_ids)

        # critical tag -> critical
        crit_spec = _make_spec_revision(
            mode=SpecMode.FEATURE,
            tags=("destructive-migration",),
        )
        crit_dec = self.evaluator.evaluate(crit_spec, self.policy)
        self.assertEqual(crit_dec.risk, RiskLevel.CRITICAL)
        self.assertEqual(
            crit_dec.workspace,
            WorkspaceRequirement.ISOLATED_REQUIRED,
        )

    def test_no_risk_or_classification_downgrade_allowed(self):
        high_spec = _make_spec_revision(
            mode=SpecMode.HARDENING,
            tags=("migration",),
        )
        # Calculated HIGH, requested LOW -> RAPID1006
        with self.assertRaises(PolicyViolationError) as ctx:
            self.evaluator.evaluate(
                high_spec,
                self.policy,
                requested_risk="low",
            )
        self.assertEqual(ctx.exception.code, "RAPID1006")

        # Calculated ARCHITECTURAL, requested BOUNDED -> RAPID1006
        with self.assertRaises(PolicyViolationError) as ctx2:
            self.evaluator.evaluate(
                high_spec,
                self.policy,
                requested_classification="bounded",
            )
        self.assertEqual(ctx2.exception.code, "RAPID1006")

        # Upward escalation is allowed and recorded
        bounded_spec = _make_spec_revision(mode=SpecMode.FEATURE)
        escalated = self.evaluator.evaluate(
            bounded_spec,
            self.policy,
            requested_classification="architectural",
            requested_risk="critical",
        )
        self.assertEqual(
            escalated.classification,
            ExecutionClass.ARCHITECTURAL,
        )
        self.assertEqual(escalated.risk, RiskLevel.CRITICAL)
        self.assertTrue(
            any(s.id == "override.risk" for s in escalated.risk_signals)
        )

    def test_gates_per_risk_level_order_and_deduplication(self):
        # LOW -> final-verification only
        low_spec = _make_spec_revision(mode=SpecMode.RESEARCH)
        low_dec = self.evaluator.evaluate(low_spec, self.policy)
        self.assertEqual(
            tuple(g.id for g in low_dec.gates),
            ("gate.final-verification",),
        )

        # MEDIUM -> baseline, tests, final-verification
        med_spec = _make_spec_revision(mode=SpecMode.FEATURE)
        med_dec = self.evaluator.evaluate(med_spec, self.policy)
        self.assertEqual(
            tuple(g.id for g in med_dec.gates),
            (
                "gate.baseline",
                "gate.tests",
                "gate.final-verification",
            ),
        )

        # HIGH -> workspace-isolation, baseline, tests, review, final-verification
        high_spec = _make_spec_revision(mode=SpecMode.HARDENING)
        high_dec = self.evaluator.evaluate(high_spec, self.policy)
        self.assertEqual(
            tuple(g.id for g in high_dec.gates),
            (
                "gate.workspace-isolation",
                "gate.baseline",
                "gate.tests",
                "gate.review",
                "gate.final-verification",
            ),
        )
        gates_by_id = {g.id: g for g in high_dec.gates}
        self.assertTrue(gates_by_id["gate.review"].waivable)
        self.assertFalse(gates_by_id["gate.baseline"].waivable)
        self.assertFalse(gates_by_id["gate.workspace-isolation"].waivable)
        self.assertFalse(gates_by_id["gate.final-verification"].waivable)

        # HIGH + security + migration signals -> includes security-review and migration-review without duplicates
        sec_mig_spec = _make_spec_revision(
            mode=SpecMode.FEATURE,
            tags=("security", "migration"),
            affected_paths=("src/auth/login.py", "db/migrations/001.sql"),
        )
        sec_mig_dec = self.evaluator.evaluate(sec_mig_spec, self.policy)
        self.assertEqual(
            tuple(g.id for g in sec_mig_dec.gates),
            (
                "gate.workspace-isolation",
                "gate.baseline",
                "gate.tests",
                "gate.review",
                "gate.security-review",
                "gate.migration-review",
                "gate.final-verification",
            ),
        )

        # CRITICAL -> includes manual-approval and makes all gates non-waivable
        crit_spec = _make_spec_revision(
            mode=SpecMode.FEATURE,
            tags=("critical",),
        )
        crit_dec = self.evaluator.evaluate(crit_spec, self.policy)
        self.assertIn(
            "gate.manual-approval",
            tuple(g.id for g in crit_dec.gates),
        )
        self.assertTrue(all(not g.waivable for g in crit_dec.gates))

    def test_execution_contract_determinism_and_strict_schemas(self):
        spec = _make_spec_revision(tags=("security",))
        model = ProjectModel(root=Path("."), facts=())
        sources = (
            ContextSource(
                id="standard.tech-stack",
                kind=ContextSourceKind.TECH_STACK,
                priority=ContextPriority.HIGH,
                content="# Tech Stack\nPython\n",
                required=True,
                provenance=".rapid-os/standards/tech-stack.md",
            ),
        )
        compiled = ContextCompiler().compile(
            request=ContextRequest(mode="feature", harness="cursor"),
            sources=sources,
            project_model=model,
        )
        decision1 = self.evaluator.evaluate(spec, self.policy)
        decision2 = self.evaluator.evaluate(spec, self.policy)
        self.assertEqual(decision1.to_dict(), decision2.to_dict())

        contract1 = build_execution_contract(
            run_id="checkout-flow-r0001-run-001",
            spec=spec,
            compiled_context=compiled,
            project_model=model,
            policy=self.policy,
            policy_source="default",
            decision=decision1,
            harness="cursor",
        )
        contract2 = build_execution_contract(
            run_id="checkout-flow-r0001-run-001",
            spec=spec,
            compiled_context=compiled,
            project_model=model,
            policy=self.policy,
            policy_source="default",
            decision=decision2,
            harness="cursor",
        )
        self.assertEqual(contract1.to_json(), contract2.to_json())
        self.assertEqual(contract1.contract_digest, contract2.contract_digest)

        # Different run ordinal with identical inputs still produces identical contract_digest (Section 74)
        contract_ordinal_2 = build_execution_contract(
            run_id="checkout-flow-r0001-run-002",
            spec=spec,
            compiled_context=compiled,
            project_model=model,
            policy=self.policy,
            policy_source="default",
            decision=decision1,
            harness="cursor",
        )
        self.assertEqual(
            contract1.contract_digest,
            contract_ordinal_2.contract_digest,
        )

        # Strict schema validation rejects unknown fields across all persisted models
        for cls_type, base_dict, expected_code in (
            (ExecutionPolicy, self.policy.to_dict(), "RAPID1005"),
            (ExecutionContract, contract1.to_dict(), "RAPID1002"),
            (
                RunRecord,
                {
                    "schema_version": RUN_SCHEMA_VERSION,
                    "id": "checkout-flow-r0001-run-001",
                    "spec_id": "checkout-flow",
                    "spec_revision": 1,
                    "contract_digest": contract1.contract_digest,
                    "current_state_revision": 1,
                },
                "RAPID1001",
            ),
        ):
            bad = dict(base_dict)
            bad["unexpected_extra_field"] = "forbidden"
            with self.assertRaises( Exception) as err_ctx:
                cls_type.from_dict(bad)
            self.assertEqual(getattr(err_ctx.exception, "code", None), expected_code)


class RunRegistryAndLifecycleTests(unittest.TestCase):
    """Sections 82-94: Filesystem tests for RunRegistry, pinning, snapshots, transitions, gates, waivers, and security."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.rapid_dir = _seed_project(self.root)
        self.spec_registry = SpecRegistry(self.root, self.rapid_dir)
        self.run_registry = RunRegistry(self.root, self.rapid_dir)

    def tearDown(self):
        self._tmp.cleanup()

    def _create_ready_spec(
        self,
        spec_id: str = "booking-idempotency",
        *,
        mode: str = "feature",
        tags: tuple[str, ...] = (),
        tasks: tuple[str, ...] = ("Implement key table", "Add handler check"),
    ):
        rec = self.spec_registry.create(
            spec_id=spec_id,
            title=f"Title for {spec_id}",
            mode=mode,
            business_objective="Ensure idempotent bookings",
            problem_statement="Duplicate bookings on retry",
            scope=("Booking API",),
            technical_constraints=("Zero double charges",),
            affected_paths=("src/booking/api.py",),
            acceptance_criteria=("Idempotent response",),
            testing_strategy=("Unit tests",),
            implementation_tasks=tasks,
            tags=tags,
        )
        return self.spec_registry.set_status(rec.id, SpecStatus.READY)

    def test_spec_must_be_ready_and_pins_exact_revision_and_digest(self):
        # Draft spec rejected -> RAPID1003
        self.spec_registry.create(
            spec_id="draft-spec",
            title="Draft Spec",
            mode="feature",
        )
        with self.assertRaises(InvalidSpecBindingError) as ctx:
            self.run_registry.create(spec_id="draft-spec")
        self.assertEqual(ctx.exception.code, "RAPID1003")

        # Ready spec r1 succeeds
        self._create_ready_spec("booking-idempotency")
        r1 = self.spec_registry.get_revision("booking-idempotency", 1)
        run_rec = self.run_registry.create(
            spec_id="booking-idempotency",
            harness="codex",
        )
        self.assertEqual(run_rec.id, "booking-idempotency-r1-run-001")
        self.assertEqual(run_rec.spec_id, "booking-idempotency")
        self.assertEqual(run_rec.spec_revision, 1)

        # Revise spec to r2
        self.spec_registry.revise(
            "booking-idempotency",
            title="Revised Title r2",
            implementation_tasks=("New task 1", "New task 2", "New task 3"),
        )
        r2 = self.spec_registry.get_revision("booking-idempotency", 2)
        self.assertNotEqual(r1.content_digest, r2.content_digest)

        # Existing run remains pinned to r1 and r1.content_digest
        loaded_rec = self.run_registry.get(run_rec.id)
        loaded_contract = self.run_registry.get_contract(run_rec.id)
        self.assertEqual(loaded_rec.spec_revision, 1)
        self.assertEqual(loaded_contract.spec_revision, 1)
        self.assertEqual(
            loaded_contract.spec_content_digest,
            r1.content_digest,
        )
        self.assertEqual(len(loaded_contract.tasks), 2)

    def test_context_and_policy_snapshots_remain_immutable_after_project_changes(self):
        self._create_ready_spec("snapshot-spec")
        write_default_execution_policy(self.root, self.rapid_dir)
        run_rec = self.run_registry.create(spec_id="snapshot-spec")

        run_dir = self.rapid_dir / "runs" / run_rec.id
        original_context = (run_dir / "context.md").read_text(encoding="utf-8")
        original_contract_json = (run_dir / "contract.json").read_text(
            encoding="utf-8"
        )
        original_contract = self.run_registry.get_contract(run_rec.id)

        # Modify business.md, tech-stack.md, and .rapid-os/policy.json after run creation
        (self.rapid_dir / "standards" / "business.md").write_text(
            "# Business Rules\n- Completely mutated business rules after run creation.\n",
            encoding="utf-8",
        )
        (self.rapid_dir / "standards" / "tech-stack.md").write_text(
            "# Tech Stack\n- Rust + Actix\n",
            encoding="utf-8",
        )
        custom_policy = ExecutionPolicy(
            schema_version=EXECUTION_POLICY_SCHEMA_VERSION,
            minimum_classification=ExecutionClass.ARCHITECTURAL,
            minimum_risk=RiskLevel.HIGH,
            waivable_gate_ids=(),
        )
        (self.rapid_dir / "policy.json").write_text(
            custom_policy.to_json(indent=2) + "\n",
            encoding="utf-8",
        )

        # Run's stored context and contract are completely unchanged and still pass validation
        self.assertEqual(
            (run_dir / "context.md").read_text(encoding="utf-8"),
            original_context,
        )
        self.assertEqual(
            (run_dir / "contract.json").read_text(encoding="utf-8"),
            original_contract_json,
        )
        reloaded_contract = self.run_registry.get_contract(run_rec.id)
        self.assertEqual(
            reloaded_contract.contract_digest,
            original_contract.contract_digest,
        )
        self.assertEqual(
            reloaded_contract.policy_digest,
            original_contract.policy_digest,
        )

    def test_run_status_task_and_gate_transitions_and_preconditions(self):
        # Create a HIGH risk spec (security tag -> gates: workspace-isolation, baseline, tests, review, security-review, final-verification)
        self._create_ready_spec(
            "payment-gateway",
            tags=("security",),
            tasks=("Implement token vault", "Add audit log"),
        )
        run_rec = self.run_registry.create(spec_id="payment-gateway")
        run_id = run_rec.id

        # 1. Cannot activate while PRE_EXECUTION gates are pending -> RAPID1014
        with self.assertRaises(ExecutionPreconditionError) as pre_ctx:
            self.run_registry.transition_status(run_id, "active")
        self.assertEqual(pre_ctx.exception.code, "RAPID1014")

        # 2. Cannot waive non-waivable gate (gate.baseline) -> RAPID1013
        with self.assertRaises(InvalidGateTransitionError) as waive_ctx:
            self.run_registry.transition_gate(
                run_id,
                "gate.baseline",
                "waive",
                reason="Try to skip baseline",
            )
        self.assertEqual(waive_ctx.exception.code, "RAPID1013")

        # 3. Cannot waive waivable gate (gate.review) without reason -> RAPID1013
        with self.assertRaises(InvalidGateTransitionError) as empty_reason_ctx:
            self.run_registry.transition_gate(
                run_id,
                "gate.review",
                "waive",
                reason="   ",
            )
        self.assertEqual(empty_reason_ctx.exception.code, "RAPID1013")

        # 4. Acknowledge PRE_EXECUTION gates (gate.workspace-isolation, gate.baseline)
        self.run_registry.transition_gate(
            run_id,
            "gate.workspace-isolation",
            "acknowledge",
            reason="Isolated worktree ready",
        )
        self.run_registry.transition_gate(
            run_id,
            "gate.baseline",
            "acknowledge",
            reason="Baseline green",
        )

        # 5. Now prepared -> active succeeds!
        state_active = self.run_registry.transition_status(run_id, "active")
        self.assertEqual(state_active.status, RunStatus.ACTIVE)

        # 6. active -> blocked -> active succeeds
        state_blocked = self.run_registry.transition_status(
            run_id,
            "blocked",
            reason="Waiting for vault key format",
        )
        self.assertEqual(state_blocked.status, RunStatus.BLOCKED)
        state_resumed = self.run_registry.transition_status(
            run_id,
            "active",
            reason="Vault key format confirmed",
        )
        self.assertEqual(state_resumed.status, RunStatus.ACTIVE)

        # 7. Cannot finish while tasks are pending -> RAPID1014
        with self.assertRaises(ExecutionPreconditionError) as finish_tasks_ctx:
            self.run_registry.transition_status(run_id, "finished")
        self.assertEqual(finish_tasks_ctx.exception.code, "RAPID1014")

        # 8. Task transitions: T001 pending -> in_progress -> blocked -> in_progress -> done; T002 -> skipped
        # Invalid transition: pending -> done -> RAPID1010
        with self.assertRaises(InvalidTaskTransitionError) as bad_task_ctx:
            self.run_registry.transition_task(run_id, "T001", "done")
        self.assertEqual(bad_task_ctx.exception.code, "RAPID1010")

        self.run_registry.transition_task(run_id, "T001", "in_progress")
        self.run_registry.transition_task(
            run_id,
            "T001",
            "blocked",
            reason="Clarifying encryption header",
        )
        self.run_registry.transition_task(run_id, "T001", "in_progress")
        self.run_registry.transition_task(run_id, "T001", "done")

        # Cannot transition from terminal task state done -> in_progress -> RAPID1010
        with self.assertRaises(InvalidTaskTransitionError) as term_task_ctx:
            self.run_registry.transition_task(run_id, "T001", "in_progress")
        self.assertEqual(term_task_ctx.exception.code, "RAPID1010")

        self.run_registry.transition_task(
            run_id,
            "T002",
            "skipped",
            reason="Deferred to follow-up spec",
        )

        # 9. Tasks are all terminal now, but POST_EXECUTION gates are still pending -> RAPID1014
        with self.assertRaises(ExecutionPreconditionError) as finish_gates_ctx:
            self.run_registry.transition_status(run_id, "finished")
        self.assertEqual(finish_gates_ctx.exception.code, "RAPID1014")

        # 10. Address POST_EXECUTION gates: acknowledge tests, security-review, final-verification; waive review with reason
        self.run_registry.transition_gate(
            run_id,
            "gate.tests",
            "acknowledge",
            reason="Unit tests written",
        )
        self.run_registry.transition_gate(
            run_id,
            "gate.review",
            "waive",
            reason="Paired directly with lead architect",
        )
        self.run_registry.transition_gate(
            run_id,
            "gate.security-review",
            "acknowledge",
            reason="Security checklist reviewed",
        )
        self.run_registry.transition_gate(
            run_id,
            "gate.final-verification",
            "acknowledge",
            reason="Ready for verification phase",
        )

        # 11. Now active -> finished succeeds!
        state_finished = self.run_registry.transition_status(run_id, "finished")
        self.assertEqual(state_finished.status, RunStatus.FINISHED)

        # 12. Cannot transition from terminal status finished -> active -> RAPID1009
        with self.assertRaises(InvalidRunTransitionError) as term_run_ctx:
            self.run_registry.transition_status(run_id, "active")
        self.assertEqual(term_run_ctx.exception.code, "RAPID1009")

    def test_cancelled_terminal_status_rejects_reactivation(self):
        self._create_ready_spec("cancel-spec")
        run_rec = self.run_registry.create(spec_id="cancel-spec")
        self.run_registry.transition_status(
            run_rec.id,
            "cancelled",
            reason="No longer needed",
        )
        with self.assertRaises(InvalidRunTransitionError) as ctx:
            self.run_registry.transition_status(run_rec.id, "active")
        self.assertEqual(ctx.exception.code, "RAPID1009")

    def test_state_immutability_history_gap_corrupt_current_and_future_warning(self):
        self._create_ready_spec("history-spec", mode="research", tasks=("Spike task",))
        run_rec = self.run_registry.create(spec_id="history-spec")
        run_id = run_rec.id
        states_dir = self.rapid_dir / "runs" / run_id / "states"

        s1_bytes = (states_dir / "0001.json").read_bytes()
        self.run_registry.transition_status(run_id, "active")
        s2_bytes = (states_dir / "0002.json").read_bytes()
        self.run_registry.transition_task(run_id, "T001", "in_progress")
        s3_bytes = (states_dir / "0003.json").read_bytes()

        # Byte-for-byte immutability of earlier states
        self.assertEqual((states_dir / "0001.json").read_bytes(), s1_bytes)
        self.assertEqual((states_dir / "0002.json").read_bytes(), s2_bytes)
        self.assertEqual((states_dir / "0003.json").read_bytes(), s3_bytes)

        # Future state warning (0004.json exists while current_state_revision=3)
        s3_obj = self.run_registry.get_state(run_id, 3)
        future_state = RunState(
            schema_version=RUN_STATE_SCHEMA_VERSION,
            run_id=run_id,
            revision=4,
            status=s3_obj.status,
            tasks=s3_obj.tasks,
            gates=s3_obj.gates,
            change_kind="future.test",
            reason="Unreferenced future state",
        )
        (states_dir / "0004.json").write_text(
            future_state.to_json(indent=2) + "\n",
            encoding="utf-8",
        )
        report_future = validate_run_registry(self.rapid_dir, self.root)
        self.assertFalse(report_future.has_errors)
        self.assertTrue(
            any(
                d.level == WARNING and d.code == "RAPID1011"
                for d in report_future.diagnostics
            )
        )
        # get_state(run_id) still returns revision 3, not 4
        self.assertEqual(self.run_registry.get_state(run_id).revision, 3)
        (states_dir / "0004.json").unlink()

        # History gap: remove 0002.json while current_state_revision = 3 -> RAPID1011
        (states_dir / "0002.json").unlink()
        with self.assertRaises(RunStateHistoryGapError) as gap_ctx:
            self.run_registry.get_state(run_id)
        self.assertEqual(gap_ctx.exception.code, "RAPID1011")

        report_gap = validate_run_registry(self.rapid_dir, self.root)
        self.assertTrue(
            any(
                d.level == ERROR and d.code == "RAPID1011"
                for d in report_gap.diagnostics
            )
        )

        # Restore 0002.json, corrupt current state 0003.json -> RAPID1012 (never falls back to 0002.json)
        (states_dir / "0002.json").write_bytes(s2_bytes)
        (states_dir / "0003.json").write_text("{corrupt json", encoding="utf-8")
        with self.assertRaises(InvalidRunStateError) as corrupt_ctx:
            self.run_registry.get_state(run_id)
        self.assertEqual(corrupt_ctx.exception.code, "RAPID1012")

        report_corrupt = validate_run_registry(self.rapid_dir, self.root)
        self.assertTrue(
            any(
                d.level == ERROR and d.code == "RAPID1012"
                for d in report_corrupt.diagnostics
            )
        )

    def test_corrupt_policy_file_fails_explicitly_without_fallback(self):
        policy_path = self.rapid_dir / "policy.json"
        policy_path.write_text("{not valid json", encoding="utf-8")
        with self.assertRaises(InvalidExecutionPolicyError) as ctx:
            load_execution_policy(self.root, self.rapid_dir)
        self.assertEqual(ctx.exception.code, "RAPID1005")

        report = validate_execution_policy(self.rapid_dir, self.root)
        self.assertTrue(
            any(d.level == ERROR and d.code == "RAPID1005" for d in report.diagnostics)
        )

    def test_path_security_and_symlink_rejection(self):
        # 1. Invalid run IDs (traversal, absolute, Windows drive)
        for bad_id in (
            "../escape",
            "..\\escape",
            "/abs/path",
            "C:\\Windows\\System32",
            "Upper_Case",
            "-leading-hyphen",
        ):
            with self.assertRaises(InvalidRunRecordError) as id_ctx:
                validate_run_id(bad_id)
            self.assertEqual(id_ctx.exception.code, "RAPID1001")

        # 2. Symlink checks (if OS allows creating symlinks in temp dir)
        self._create_ready_spec("symlink-spec")
        run_rec = self.run_registry.create(spec_id="symlink-spec")
        run_dir = self.rapid_dir / "runs" / run_rec.id
        outside_target = self.root.parent / f"outside-{self.root.name}.json"

        try:
            outside_target.write_text("{}", encoding="utf-8")
            contract_file = run_dir / "contract.json"
            contract_backup = contract_file.read_bytes()
            contract_file.unlink()
            try:
                contract_file.symlink_to(outside_target)
            except (OSError, NotImplementedError):
                contract_file.write_bytes(contract_backup)
                return

            with self.assertRaises(UnsafeRunPathError) as sym_ctx:
                self.run_registry.get_contract(run_rec.id)
            self.assertEqual(sym_ctx.exception.code, "RAPID1008")

            report = validate_run_registry(self.rapid_dir, self.root)
            self.assertTrue(
                any(
                    d.level == ERROR and d.code == "RAPID1008"
                    for d in report.diagnostics
                )
            )
            contract_file.unlink()
            contract_file.write_bytes(contract_backup)
        finally:
            if outside_target.exists():
                outside_target.unlink()

    def test_initial_state_invariants_reject_forged_s1(self):
        self._create_ready_spec("init-inv-spec", tasks=("Task 1",))
        run_rec = self.run_registry.create(spec_id="init-inv-spec")
        run_id = run_rec.id
        s1_file = self.rapid_dir / "runs" / run_id / "states" / "0001.json"
        s1_orig = self.run_registry.get_state(run_id, 1)

        # 1. Forged s1 with status = active (and recalculated valid digest) -> RAPID1012
        forged_active_s1 = RunState(
            schema_version=RUN_STATE_SCHEMA_VERSION,
            run_id=run_id,
            revision=1,
            status=RunStatus.ACTIVE,
            tasks=s1_orig.tasks,
            gates=s1_orig.gates,
            change_kind="run.prepared",
            reason="Forged active initial state",
        )
        s1_file.write_text(forged_active_s1.to_json(indent=2) + "\n", encoding="utf-8")

        with self.assertRaises(InvalidRunStateError) as ctx:
            self.run_registry.get_state(run_id)
        self.assertEqual(ctx.exception.code, "RAPID1012")

        report = validate_run_registry(self.rapid_dir, self.root)
        self.assertTrue(
            any(d.level == ERROR and d.code == "RAPID1012" for d in report.diagnostics)
        )

        # 2. Forged s1 with non-pending task, non-pending gate, or wrong change_kind -> RAPID1012
        forged_task_s1 = RunState(
            schema_version=RUN_STATE_SCHEMA_VERSION,
            run_id=run_id,
            revision=1,
            status=RunStatus.PREPARED,
            tasks=(
                TaskState(
                    id=s1_orig.tasks[0].id,
                    description=s1_orig.tasks[0].description,
                    status=TaskStatus.DONE,
                    reason="",
                ),
            ),
            gates=s1_orig.gates,
            change_kind="run.prepared",
            reason="Forged task done in s1",
        )
        with self.assertRaises(InvalidRunStateError) as t_ctx:
            verify_initial_run_state(forged_task_s1)
        self.assertEqual(t_ctx.exception.code, "RAPID1012")

        forged_kind_s1 = RunState(
            schema_version=RUN_STATE_SCHEMA_VERSION,
            run_id=run_id,
            revision=1,
            status=RunStatus.PREPARED,
            tasks=s1_orig.tasks,
            gates=s1_orig.gates,
            change_kind="status.prepared",
            reason="Wrong change_kind in s1",
        )
        with self.assertRaises(InvalidRunStateError) as k_ctx:
            verify_initial_run_state(forged_kind_s1)
        self.assertEqual(k_ctx.exception.code, "RAPID1012")

    def test_semantic_run_state_history_rejects_forged_transitions_multi_mutation_and_wrong_change_kind(
        self,
    ):
        self._create_ready_spec(
            "semantic-history-spec",
            mode="research",
            tasks=("Spike 1",),
        )
        run_rec = self.run_registry.create(spec_id="semantic-history-spec")
        run_id = run_rec.id
        run_dir = self.rapid_dir / "runs" / run_id
        states_dir = run_dir / "states"
        s1 = self.run_registry.get_state(run_id, 1)

        # Advance to revision 2 legally (prepared -> active, since research low risk has no PRE gates)
        s2_legal = self.run_registry.transition_status(run_id, "active")
        s2_file = states_dir / "0002.json"

        # Case A: Manually forge 0002.json as prepared -> finished (with recalculated valid digest) -> RAPID1012
        forged_finished = RunState(
            schema_version=RUN_STATE_SCHEMA_VERSION,
            run_id=run_id,
            revision=2,
            status=RunStatus.FINISHED,
            tasks=s1.tasks,
            gates=s1.gates,
            change_kind="status.finished",
            reason="Forged jump prepared -> finished",
        )
        s2_file.write_text(forged_finished.to_json(indent=2) + "\n", encoding="utf-8")

        with self.assertRaises(InvalidRunStateError) as jump_ctx:
            self.run_registry.get_state(run_id)
        self.assertEqual(jump_ctx.exception.code, "RAPID1012")

        report_jump = validate_run_registry(self.rapid_dir, self.root)
        self.assertTrue(
            any(
                d.level == ERROR and d.code == "RAPID1012"
                for d in report_jump.diagnostics
            )
        )

        # Case B: Single snapshot mutates status AND a task simultaneously -> RAPID1012
        forged_multi = RunState(
            schema_version=RUN_STATE_SCHEMA_VERSION,
            run_id=run_id,
            revision=2,
            status=RunStatus.ACTIVE,
            tasks=(
                TaskState(
                    id=s1.tasks[0].id,
                    description=s1.tasks[0].description,
                    status=TaskStatus.IN_PROGRESS,
                    reason="",
                ),
            ),
            gates=s1.gates,
            change_kind="status.active",
            reason="Mutated both status and task",
        )
        s2_file.write_text(forged_multi.to_json(indent=2) + "\n", encoding="utf-8")
        with self.assertRaises(InvalidRunStateError) as multi_ctx:
            self.run_registry.get_state(run_id)
        self.assertEqual(multi_ctx.exception.code, "RAPID1012")

        # Case C: change_kind does not match actual mutation -> RAPID1012
        forged_wrong_kind = RunState(
            schema_version=RUN_STATE_SCHEMA_VERSION,
            run_id=run_id,
            revision=2,
            status=RunStatus.ACTIVE,
            tasks=s1.tasks,
            gates=s1.gates,
            change_kind="task.T001.in_progress",
            reason="Status changed but change_kind says task",
        )
        s2_file.write_text(
            forged_wrong_kind.to_json(indent=2) + "\n",
            encoding="utf-8",
        )
        with self.assertRaises(InvalidRunStateError) as kind_ctx:
            self.run_registry.get_state(run_id)
        self.assertEqual(kind_ctx.exception.code, "RAPID1012")

        # Restore legal s2 and verify clean
        s2_file.write_text(s2_legal.to_json(indent=2) + "\n", encoding="utf-8")
        self.assertEqual(self.run_registry.get_state(run_id).status, RunStatus.ACTIVE)

    def test_existing_future_state_snapshot_is_never_overwritten_on_transition(self):
        self._create_ready_spec(
            "no-overwrite-spec",
            mode="research",
            tasks=("Spike 1",),
        )
        run_rec = self.run_registry.create(spec_id="no-overwrite-spec")
        run_id = run_rec.id
        states_dir = self.rapid_dir / "runs" / run_id / "states"

        # Advance to revision 2 (active)
        s2 = self.run_registry.transition_status(run_id, "active")
        self.assertEqual(s2.revision, 2)

        # Create orphan future snapshot 0003.json while current_state_revision = 2
        orphan_s3 = RunState(
            schema_version=RUN_STATE_SCHEMA_VERSION,
            run_id=run_id,
            revision=3,
            status=RunStatus.BLOCKED,
            tasks=s2.tasks,
            gates=s2.gates,
            change_kind="status.blocked",
            reason="Orphan future snapshot",
        )
        s3_file = states_dir / "0003.json"
        s3_file.write_text(orphan_s3.to_json(indent=2) + "\n", encoding="utf-8")
        orphan_bytes = s3_file.read_bytes()

        # Attempting next transition (which targets 0003.json) must fail with RAPID1012 and preserve 0003.json bytes
        with self.assertRaises(InvalidRunStateError) as overwrite_ctx:
            self.run_registry.transition_task(run_id, "T001", "in_progress")
        self.assertEqual(overwrite_ctx.exception.code, "RAPID1012")
        self.assertEqual(s3_file.read_bytes(), orphan_bytes)
        self.assertEqual(self.run_registry.get(run_id).current_state_revision, 2)

    def test_lifecycle_phase_boundaries_for_tasks_and_pre_post_gates(self):
        self._create_ready_spec(
            "phase-boundary-spec",
            tasks=("Task 1", "Task 2"),
        )
        run_rec = self.run_registry.create(spec_id="phase-boundary-spec")
        run_id = run_rec.id

        # 1. Task transition while prepared -> RAPID1014
        with self.assertRaises(ExecutionPreconditionError) as task_prep_ctx:
            self.run_registry.transition_task(run_id, "T001", "in_progress")
        self.assertEqual(task_prep_ctx.exception.code, "RAPID1014")

        # 2. POST_EXECUTION gate modification while prepared -> RAPID1014
        with self.assertRaises(ExecutionPreconditionError) as post_prep_ctx:
            self.run_registry.transition_gate(
                run_id,
                "gate.tests",
                "acknowledge",
                reason="Too early",
            )
        self.assertEqual(post_prep_ctx.exception.code, "RAPID1014")

        # 3. Acknowledge PRE_EXECUTION gate (gate.baseline) while prepared -> succeeds, then activate
        self.run_registry.transition_gate(
            run_id,
            "gate.baseline",
            "acknowledge",
            reason="Baseline verified",
        )
        self.run_registry.transition_status(run_id, "active")

        # 4. PRE_EXECUTION gate modification after active -> RAPID1014
        with self.assertRaises(ExecutionPreconditionError) as pre_after_active_ctx:
            self.run_registry.transition_gate(
                run_id,
                "gate.baseline",
                "acknowledge",
                reason="Cannot modify PRE gate after active",
            )
        self.assertEqual(pre_after_active_ctx.exception.code, "RAPID1014")

        # 5. Task transition while blocked -> RAPID1014
        self.run_registry.transition_status(
            run_id,
            "blocked",
            reason="Waiting on dependency",
        )
        with self.assertRaises(ExecutionPreconditionError) as task_blocked_ctx:
            self.run_registry.transition_task(run_id, "T001", "in_progress")
        self.assertEqual(task_blocked_ctx.exception.code, "RAPID1014")

        # Resume active
        self.run_registry.transition_status(run_id, "active", reason="Unblocked")

        # 6. POST_EXECUTION gate modification while tasks incomplete -> RAPID1014
        self.run_registry.transition_task(run_id, "T001", "in_progress")
        with self.assertRaises(ExecutionPreconditionError) as post_incomplete_ctx:
            self.run_registry.transition_gate(
                run_id,
                "gate.tests",
                "acknowledge",
                reason="T001 in_progress and T002 pending",
            )
        self.assertEqual(post_incomplete_ctx.exception.code, "RAPID1014")

        # 7. Complete all tasks (T001 done, T002 skipped) while active -> POST_EXECUTION gates now succeed
        self.run_registry.transition_task(run_id, "T001", "done")
        self.run_registry.transition_task(
            run_id,
            "T002",
            "skipped",
            reason="Not needed",
        )
        state_after_gate = self.run_registry.transition_gate(
            run_id,
            "gate.tests",
            "acknowledge",
            reason="All unit tests passing",
        )
        tests_gate = next(
            g for g in state_after_gate.gates if g.id == "gate.tests"
        )
        self.assertEqual(tests_gate.disposition, GateDisposition.ACKNOWLEDGED)

    def test_custom_policy_provenance_forbids_default_and_requires_truthful_source(self):
        self._create_ready_spec("provenance-spec")
        custom_policy = ExecutionPolicy(
            schema_version=EXECUTION_POLICY_SCHEMA_VERSION,
            minimum_classification=ExecutionClass.ARCHITECTURAL,
            minimum_risk=RiskLevel.HIGH,
            waivable_gate_ids=(),
        )

        # 1. Passing custom policy without policy_source -> RAPID1005
        with self.assertRaises(InvalidExecutionPolicyError) as missing_src_ctx:
            self.run_registry.create(
                spec_id="provenance-spec",
                policy=custom_policy,
            )
        self.assertEqual(missing_src_ctx.exception.code, "RAPID1005")

        # 2. Passing custom policy with policy_source="default" -> RAPID1005
        with self.assertRaises(InvalidExecutionPolicyError) as lie_src_ctx:
            self.run_registry.create(
                spec_id="provenance-spec",
                policy=custom_policy,
                policy_source="default",
            )
        self.assertEqual(lie_src_ctx.exception.code, "RAPID1005")

        # 3. Passing custom policy with policy_source="injected" -> succeeds
        rec = self.run_registry.create(
            spec_id="provenance-spec",
            policy=custom_policy,
            policy_source="injected",
        )
        contract = self.run_registry.get_contract(rec.id)
        self.assertEqual(contract.policy_source, "injected")
        self.assertEqual(contract.policy_digest, custom_policy.content_digest())
        self.assertEqual(contract.classification, ExecutionClass.ARCHITECTURAL)
        self.assertEqual(contract.risk, RiskLevel.HIGH)


class ExecutionPolicyCLIE2ETests(unittest.TestCase):
    """Sections 95-96: Full CLI & E2E lifecycle tests and Spec Revision Isolation."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.rapid_dir = _seed_project(self.root)
        self.config_file = self.rapid_dir / "config.json"

    def tearDown(self):
        self._tmp.cleanup()

    def _run_cli(self, argv: list[str]) -> tuple[int, str, str]:
        stdout_buf = io.StringIO()
        stderr_buf = io.StringIO()
        exit_code = 0
        with (
            patch.object(cli_main, "CURRENT_DIR", self.root),
            patch.object(cli_main, "PROJECT_RAPID_DIR", self.rapid_dir),
            patch.object(cli_main, "CONFIG_FILE", self.config_file),
            redirect_stdout(stdout_buf),
            redirect_stderr(stderr_buf),
        ):
            try:
                result = cli_main.main(argv)
                if isinstance(result, int):
                    exit_code = result
            except SystemExit as exc:
                exit_code = int(exc.code) if exc.code is not None else 0
        return exit_code, stdout_buf.getvalue(), stderr_buf.getvalue()

    def test_e2e_full_run_lifecycle_and_artifact_immutability(self):
        # 1. Policy show default -> init -> show project
        code, out, err = self._run_cli(["policy", "show", "--json"])
        self.assertEqual(code, 0, err)
        self.assertEqual(err, "")
        policy_data = json.loads(out)
        self.assertEqual(policy_data["source"], "default")

        code, out, err = self._run_cli(["policy", "init", "--json"])
        self.assertEqual(code, 0, err)
        self.assertEqual(json.loads(out)["source"], ".rapid-os/policy.json")

        # Calling policy init again without force must fail with RAPID1005
        code, out, err = self._run_cli(["policy", "init"])
        self.assertNotEqual(code, 0)
        self.assertIn("RAPID1005", err)

        # 2. Create ready Spec r1
        code, out, err = self._run_cli(
            [
                "spec",
                "create",
                "--id",
                "checkout-payments",
                "--title",
                "Checkout Payments",
                "--mode",
                "feature",
                "--objective",
                "Process card payments safely",
                "--problem",
                "Retries can duplicate charges",
                "--scope",
                "Payment service",
                "--technical-constraint",
                "Idempotency key required",
                "--affected-path",
                "src/payments/charge.py",
                "--acceptance",
                "Single charge per key",
                "--testing",
                "Integration tests",
                "--task",
                "Create payment intent table",
                "--task",
                "Enforce idempotency header",
                "--tag",
                "security",
                "--status",
                "ready",
                "--json",
            ]
        )
        self.assertEqual(code, 0, err)
        spec_payload = json.loads(out)
        spec_rev_path = (
            self.rapid_dir
            / "specs"
            / "checkout-payments"
            / "revisions"
            / "0001"
            / "revision.json"
        )
        original_spec_rev_bytes = spec_rev_path.read_bytes()

        # 3. Create Run via CLI
        code, out, err = self._run_cli(
            [
                "run",
                "create",
                "--spec",
                "checkout-payments",
                "--harness",
                "cursor",
                "--json",
            ]
        )
        self.assertEqual(code, 0, err)
        self.assertEqual(err, "")
        run_created = json.loads(out)
        run_id = run_created["id"]
        self.assertEqual(run_id, "checkout-payments-r1-run-001")
        self.assertEqual(run_created["status"], "prepared")
        self.assertEqual(run_created["classification"], "architectural")
        self.assertEqual(run_created["risk"], "high")
        self.assertEqual(run_created["workspace"], "isolated_required")

        run_dir = self.rapid_dir / "runs" / run_id
        original_contract_bytes = (run_dir / "contract.json").read_bytes()
        s1_bytes = (run_dir / "states" / "0001.json").read_bytes()

        # 4. Inspect Run via `rapid run show` (text and JSON)
        code, show_text, err = self._run_cli(["run", "show", run_id])
        self.assertEqual(code, 0, err)
        self.assertIn("architectural", show_text)
        self.assertIn("high", show_text)
        self.assertIn("isolated_required", show_text)
        self.assertIn("gate.workspace-isolation", show_text)
        self.assertIn("gate.security-review", show_text)

        code, show_json_raw, err = self._run_cli(
            ["run", "show", run_id, "--json"]
        )
        self.assertEqual(code, 0, err)
        show_json = json.loads(show_json_raw)
        self.assertEqual(show_json["spec_id"], "checkout-payments")
        self.assertEqual(show_json["spec_revision"], 1)
        self.assertEqual(
            show_json["spec_content_digest"],
            spec_payload["revision"]["content_digest"],
        )

        # 5. Acknowledge PRE_EXECUTION gates -> activate Run
        for gate_id in ("gate.workspace-isolation", "gate.baseline"):
            code, _, err = self._run_cli(
                [
                    "run",
                    "gate",
                    run_id,
                    gate_id,
                    "acknowledge",
                    "--reason",
                    f"Acknowledged {gate_id}",
                    "--json",
                ]
            )
            self.assertEqual(code, 0, err)

        code, active_out, err = self._run_cli(
            ["run", "status", run_id, "active", "--json"]
        )
        self.assertEqual(code, 0, err)
        self.assertEqual(json.loads(active_out)["status"], "active")

        # 6. Complete tasks T001 (in_progress -> done) and T002 (skipped)
        code, _, err = self._run_cli(
            ["run", "task", run_id, "T001", "in_progress", "--json"]
        )
        self.assertEqual(code, 0, err)
        code, _, err = self._run_cli(
            ["run", "task", run_id, "T001", "done", "--json"]
        )
        self.assertEqual(code, 0, err)
        code, _, err = self._run_cli(
            [
                "run",
                "task",
                run_id,
                "T002",
                "skipped",
                "--reason",
                "Handled in middleware",
                "--json",
            ]
        )
        self.assertEqual(code, 0, err)

        # 7. Acknowledge/waive POST_EXECUTION gates -> finish Run
        for gate_id in (
            "gate.tests",
            "gate.security-review",
            "gate.final-verification",
        ):
            code, _, err = self._run_cli(
                [
                    "run",
                    "gate",
                    run_id,
                    gate_id,
                    "acknowledge",
                    "--reason",
                    f"Completed {gate_id}",
                    "--json",
                ]
            )
            self.assertEqual(code, 0, err)

        code, _, err = self._run_cli(
            [
                "run",
                "gate",
                run_id,
                "gate.review",
                "waive",
                "--reason",
                "Pair programmed",
                "--json",
            ]
        )
        self.assertEqual(code, 0, err)

        code, fin_out, err = self._run_cli(
            ["run", "status", run_id, "finished", "--json"]
        )
        self.assertEqual(code, 0, err)
        fin_data = json.loads(fin_out)
        self.assertEqual(fin_data["status"], "finished")
        self.assertEqual(fin_data["current_state_revision"], 12)

        # 8. Verify SpecRevision, ExecutionContract, and initial state 0001 remain byte-for-byte unchanged
        self.assertEqual(spec_rev_path.read_bytes(), original_spec_rev_bytes)
        self.assertEqual(
            (run_dir / "contract.json").read_bytes(),
            original_contract_bytes,
        )
        self.assertEqual(
            (run_dir / "states" / "0001.json").read_bytes(),
            s1_bytes,
        )

        # 9. Verify `rapid run list --json`, `rapid validate`, and `rapid doctor`
        code, list_out, err = self._run_cli(
            ["run", "list", "--status", "finished", "--json"]
        )
        self.assertEqual(code, 0, err)
        runs_list = json.loads(list_out)["runs"]
        self.assertEqual(len(runs_list), 1)
        self.assertEqual(runs_list[0]["id"], run_id)

        val_report = validate_project(
            self.rapid_dir,
            self.root,
            self.config_file,
            cli_main.TEMPLATES_DIR,
        )
        self.assertFalse(val_report.has_errors)
        codes = [d.code for d in val_report.diagnostics]
        self.assertIn("RAPID1000", codes)

    def test_e2e_spec_revision_isolation_between_runs(self):
        # 1. Create Spec A r1 ready -> Run A
        code, r1_out, err = self._run_cli(
            [
                "spec",
                "create",
                "--id",
                "spec-alpha",
                "--title",
                "Spec Alpha v1",
                "--mode",
                "feature",
                "--objective",
                "Objective v1",
                "--task",
                "Task v1 only",
                "--status",
                "ready",
                "--json",
            ]
        )
        self.assertEqual(code, 0, err)
        r1_digest = json.loads(r1_out)["revision"]["content_digest"]

        code, run_a_out, err = self._run_cli(
            ["run", "create", "--spec", "spec-alpha", "--json"]
        )
        self.assertEqual(code, 0, err)
        run_a = json.loads(run_a_out)
        self.assertEqual(run_a["id"], "spec-alpha-r1-run-001")

        # 2. Revise Spec A -> r2, mark ready -> Run B
        code, r2_out, err = self._run_cli(
            [
                "spec",
                "revise",
                "spec-alpha",
                "--title",
                "Spec Alpha v2",
                "--objective",
                "Objective v2",
                "--task",
                "Task v2 first",
                "--task",
                "Task v2 second",
                "--tag",
                "migration",
                "--json",
            ]
        )
        self.assertEqual(code, 0, err)
        r2_digest = json.loads(r2_out)["revision"]["content_digest"]
        self.assertNotEqual(r1_digest, r2_digest)

        code, _, err = self._run_cli(
            ["spec", "status", "spec-alpha", "ready", "--json"]
        )
        self.assertEqual(code, 0, err)

        code, run_b_out, err = self._run_cli(
            ["run", "create", "--spec", "spec-alpha", "--json"]
        )
        self.assertEqual(code, 0, err)
        run_b = json.loads(run_b_out)
        self.assertEqual(run_b["id"], "spec-alpha-r2-run-001")

        # 3. Verify Run A -> r1 (bounded, medium, 1 task) and Run B -> r2 (architectural, high, 2 tasks) without contamination
        _, show_a_raw, _ = self._run_cli(["run", "show", run_a["id"], "--json"])
        _, show_b_raw, _ = self._run_cli(["run", "show", run_b["id"], "--json"])
        show_a = json.loads(show_a_raw)
        show_b = json.loads(show_b_raw)

        self.assertEqual(show_a["spec_revision"], 1)
        self.assertEqual(show_a["spec_content_digest"], r1_digest)
        self.assertEqual(show_a["classification"], "bounded")
        self.assertEqual(show_a["risk"], "medium")
        self.assertEqual(len(show_a["tasks"]), 1)
        self.assertEqual(show_a["tasks"][0]["description"], "Task v1 only")

        self.assertEqual(show_b["spec_revision"], 2)
        self.assertEqual(show_b["spec_content_digest"], r2_digest)
        self.assertEqual(show_b["classification"], "architectural")
        self.assertEqual(show_b["risk"], "high")
        self.assertEqual(len(show_b["tasks"]), 2)
        self.assertEqual(show_b["tasks"][0]["description"], "Task v2 first")


if __name__ == "__main__":
    unittest.main()
