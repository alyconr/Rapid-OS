import ast
import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from rapid_os.adapters.capability_lock import write_capability_lock
from rapid_os.adapters.eval_registry import EvalRegistry
from rapid_os.adapters.evidence_registry import EvidenceRegistry
from rapid_os.adapters.harness_registry import HarnessRegistry
from rapid_os.adapters.run_registry import RunRegistry
from rapid_os.adapters.spec_registry import SpecRegistry
from rapid_os.cli import main as cli_main
from rapid_os.cli.main import create_parser
from rapid_os.domain.evals import (
    BEHAVIORAL_RULESET_VERSION,
    DEFAULT_BEHAVIORAL_RULESET_DIGEST,
    EVALUATION_REPORT_SCHEMA_VERSION,
    BehavioralEvaluator,
    EvalAssertionStatus,
    EvaluationBindingMismatchError,
    EvaluationOverwriteError,
    EvaluationReport,
    EvaluationReportDigestMismatchError,
    EvaluationReportNotFoundError,
    EvaluationVerdict,
    InvalidEvaluationReportError,
)
from rapid_os.domain.evidence import (
    RUN_EVIDENCE_SCHEMA_VERSION,
    EvidenceArtifact,
    EvidenceArtifactIntegrityError,
    EvidenceBindingMismatchError,
    EvidenceKind,
    EvidenceNotFoundError,
    EvidenceOverwriteError,
    EvidenceSequenceGapError,
    InvalidEvidenceIdError,
    InvalidEvidencePayloadError,
    InvalidEvidenceReferenceError,
    InvalidRunEvidenceError,
    RunEvidence,
    UnsafeEvidencePathError,
    compute_evidence_set_digest,
    format_evidence_id,
    validate_evidence_id,
    validate_evidence_payload,
)
from rapid_os.domain.validation import (
    ERROR,
    INFO,
    WARNING,
    validate_eval_registry,
    validate_evidence_registry,
)


def _setup_ready_project(
    root: Path,
    *,
    spec_id: str = "checkout-idempotency",
    tasks: tuple[str, ...] = ("Implement idempotency key handler",),
    harness: str = "codex",
    classification: str = "bounded",
    risk: str = "high",
) -> tuple[Path, SpecRegistry, RunRegistry, str]:
    rapid_dir = root / ".rapid-os"
    standards = rapid_dir / "standards"
    standards.mkdir(parents=True, exist_ok=True)
    (standards / "tech-stack.md").write_text(
        "# Tech Stack\nPython 3.12\n",
        encoding="utf-8",
    )
    (standards / "topology.md").write_text(
        "# Topology\nSeparated fullstack\n",
        encoding="utf-8",
    )
    (standards / "security.md").write_text(
        "# Security\nValidate all inputs.\n",
        encoding="utf-8",
    )
    (standards / "coding-rules.md").write_text(
        "# Coding Rules\nStrict typing.\n",
        encoding="utf-8",
    )
    (rapid_dir / "config.json").write_text(
        json.dumps({"version": "3.0", "tools": ["cursor", "codex"]}, indent=2),
        encoding="utf-8",
    )

    spec_reg = SpecRegistry(root, rapid_dir)
    spec_reg.create(
        spec_id=spec_id,
        title="Checkout Idempotency",
        mode="research" if classification == "spike" else "feature",
        business_objective="Prevent duplicate charges on retries",
        scope=("API endpoint",),
        acceptance_criteria=("Retries return identical receipt",),
        testing_strategy=("Unit tests for retry key",),
        implementation_tasks=tasks,
    )
    spec_reg.set_status(spec_id, "ready")
    run_reg = RunRegistry(root, rapid_dir)
    record = run_reg.create(
        spec_id=spec_id,
        harness=harness,
        classification=classification,
        risk=risk,
    )
    return rapid_dir, spec_reg, run_reg, record.id


def _run_cli(project_root: Path, argv: list[str]) -> tuple[int, str, str]:
    stdout_buf = io.StringIO()
    stderr_buf = io.StringIO()
    rapid_dir = project_root / ".rapid-os"
    config_file = rapid_dir / "config.json"
    exit_code = 0
    with patch.object(cli_main, "CURRENT_DIR", project_root), patch.object(
        cli_main, "PROJECT_RAPID_DIR", rapid_dir
    ), patch.object(cli_main, "CONFIG_FILE", config_file), contextlib.redirect_stdout(
        stdout_buf
    ), contextlib.redirect_stderr(
        stderr_buf
    ):
        try:
            cli_main.main(argv)
        except SystemExit as exc:
            exit_code = int(exc.code) if exc.code is not None else 0
    return exit_code, stdout_buf.getvalue(), stderr_buf.getvalue()


def _snapshot_tree_bytes(base: Path) -> dict[str, bytes]:
    if not base.exists():
        return {}
    return {
        p.relative_to(base).as_posix(): p.read_bytes()
        for p in sorted(base.rglob("*"))
        if p.is_file()
    }


class EvidenceDomainAndPayloadTests(unittest.TestCase):
    def test_evidence_id_validation_and_formatting(self):
        self.assertEqual(format_evidence_id(1), "E001")
        self.assertEqual(format_evidence_id(42), "E042")
        self.assertEqual(format_evidence_id(1000), "E1000")
        self.assertEqual(validate_evidence_id("E001"), "E001")
        self.assertEqual(validate_evidence_id("E1000"), "E1000")

        for invalid in ("", "E000", "E1", "E01", "e001", "E001 ", "../E001", 123):
            with self.assertRaises(InvalidEvidenceIdError) as ctx:
                validate_evidence_id(invalid)
            self.assertEqual(ctx.exception.code, "RAPID1201")

    def test_evidence_kind_payload_schemas_and_secret_rejection(self):
        self.assertEqual(
            validate_evidence_payload(
                "command_result",
                {"label": "lint", "exit_code": 0},
            ),
            {"label": "lint", "exit_code": 0},
        )
        self.assertEqual(
            validate_evidence_payload(
                "test_result",
                {
                    "suite": "unittest",
                    "exit_code": 0,
                    "passed": 259,
                    "failed": 0,
                    "skipped": 1,
                },
            ),
            {
                "suite": "unittest",
                "exit_code": 0,
                "passed": 259,
                "failed": 0,
                "skipped": 1,
            },
        )
        self.assertEqual(
            validate_evidence_payload(
                "file_change",
                {"paths": ["src/b.py", "src/a.py", "src/a.py"]},
            ),
            {"paths": ["src/a.py", "src/b.py"]},
        )
        self.assertEqual(
            validate_evidence_payload("git_result", {"operation": "inspect"}),
            {"operation": "inspect"},
        )
        self.assertEqual(
            validate_evidence_payload("workspace", {"mode": "isolated"}),
            {"mode": "isolated"},
        )
        self.assertEqual(
            validate_evidence_payload(
                "review",
                {
                    "review_type": "peer",
                    "outcome": "approved",
                    "reviewer": "alice-dev",
                },
            ),
            {
                "review_type": "peer",
                "outcome": "approved",
                "reviewer": "alice-dev",
            },
        )
        self.assertEqual(
            validate_evidence_payload(
                "tool_invocation",
                {"tool_id": "mcp.postgres", "outcome": "success"},
            ),
            {"tool_id": "mcp.postgres", "outcome": "success"},
        )
        self.assertEqual(
            validate_evidence_payload(
                "delegation",
                {"target": "subagent.research", "outcome": "success"},
            ),
            {"target": "subagent.research", "outcome": "success"},
        )
        self.assertEqual(
            validate_evidence_payload("artifact", {"label": "coverage-report"}),
            {"label": "coverage-report"},
        )

        # Reject fake manual success kind
        with self.assertRaises(InvalidEvidencePayloadError) as ctx:
            validate_evidence_payload("manual_success", {})
        self.assertEqual(ctx.exception.code, "RAPID1206")

        # Reject secret/env/arbitrary fields in payload
        for forbidden_key in ("password", "secret", "token", "environment", "env"):
            with self.assertRaises(InvalidEvidencePayloadError) as ctx:
                validate_evidence_payload(
                    "command_result",
                    {"label": "build", "exit_code": 0, forbidden_key: "leaked"},
                )
            self.assertEqual(ctx.exception.code, "RAPID1206")

        # Reject unsafe paths in FILE_CHANGE
        for bad_path in ("../secret.txt", "/etc/passwd", "C:\\Windows\\win.ini", "a\\b.py"):
            with self.assertRaises(InvalidEvidencePayloadError) as ctx:
                validate_evidence_payload("file_change", {"paths": [bad_path]})
            self.assertEqual(ctx.exception.code, "RAPID1206")

        # Reject negative counts in TEST_RESULT
        with self.assertRaises(InvalidEvidencePayloadError) as ctx:
            validate_evidence_payload(
                "test_result",
                {
                    "suite": "unittest",
                    "exit_code": 0,
                    "passed": -1,
                    "failed": 0,
                    "skipped": 0,
                },
            )
        self.assertEqual(ctx.exception.code, "RAPID1206")

    def test_artifact_evidence_requires_at_least_one_artifact(self):
        with self.assertRaises(InvalidEvidencePayloadError) as ctx:
            RunEvidence(
                schema_version=RUN_EVIDENCE_SCHEMA_VERSION,
                id="E001",
                run_id="run-001",
                contract_digest="a" * 64,
                state_revision=1,
                state_digest="b" * 64,
                kind=EvidenceKind.ARTIFACT,
                producer="user",
                summary="Build report without artifact",
                task_ids=(),
                gate_ids=(),
                capability_ids=(),
                payload={"label": "report"},
                artifacts=(),
            )
        self.assertEqual(ctx.exception.code, "RAPID1206")


class EvidenceRegistryIntegrityTests(unittest.TestCase):
    def test_artifact_tampering_produces_rapid1205_and_external_mutation_is_isolated(self):
        # Section 25, 27, 91
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            rapid_dir, _, _, run_id = _setup_ready_project(root)
            ev_reg = EvidenceRegistry(root, rapid_dir)

            ext_log = root / "test-output.txt"
            ext_log.write_text("Ran 259 tests in 1.2s\nOK\n", encoding="utf-8")

            added = ev_reg.add(
                run_id,
                {
                    "kind": "test_result",
                    "producer": "harness:codex",
                    "summary": "Unit test execution",
                    "task_ids": ["T001"],
                    "gate_ids": ["gate.tests"],
                    "capability_ids": ["tests.execute"],
                    "payload": {
                        "suite": "unittest",
                        "exit_code": 0,
                        "passed": 259,
                        "failed": 0,
                        "skipped": 0,
                    },
                    "artifacts": ["test-output.txt"],
                },
            )
            self.assertEqual(added.id, "E001")
            self.assertEqual(len(added.artifacts), 1)

            # Mutating external source file after ingest must not affect registry integrity
            ext_log.write_text("mutated external file", encoding="utf-8")
            self.assertEqual(len(ev_reg.verify(run_id)), 1)

            # Tampering with 1 byte of the copied artifact inside .rapid-os/evidence/ -> RAPID1205
            ingested_artifact = root / added.artifacts[0].path
            raw_bytes = bytearray(ingested_artifact.read_bytes())
            raw_bytes[0] ^= 0xFF
            ingested_artifact.write_bytes(bytes(raw_bytes))

            with self.assertRaises(EvidenceArtifactIntegrityError) as ctx:
                ev_reg.verify(run_id)
            self.assertEqual(ctx.exception.code, "RAPID1205")

            report = validate_evidence_registry(rapid_dir, root)
            self.assertTrue(report.has_errors)
            self.assertIn("RAPID1205", [d.code for d in report.diagnostics])

    def test_record_tampering_produces_rapid1202(self):
        # Section 92
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            rapid_dir, _, _, run_id = _setup_ready_project(root)
            ev_reg = EvidenceRegistry(root, rapid_dir)

            ev_reg.add(
                run_id,
                {
                    "kind": "file_change",
                    "producer": "harness:codex",
                    "summary": "Modified handler",
                    "task_ids": ["T001"],
                    "payload": {"paths": ["rapid_os/handler.py"]},
                },
            )
            rec_file = rapid_dir / "evidence" / run_id / "records" / "E001.json"
            data = json.loads(rec_file.read_text(encoding="utf-8"))
            data["summary"] = "Tampered summary without updating digest"
            rec_file.write_text(json.dumps(data, indent=2), encoding="utf-8")

            with self.assertRaises(InvalidRunEvidenceError) as ctx:
                ev_reg.verify(run_id)
            self.assertEqual(ctx.exception.code, "RAPID1202")

            val_report = validate_evidence_registry(rapid_dir, root)
            self.assertIn("RAPID1202", [d.code for d in val_report.diagnostics])

    def test_state_binding_and_historical_state_verification_produces_rapid1203(self):
        # Section 13 & 93
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            rapid_dir, _, run_reg, run_id = _setup_ready_project(root)
            run_reg.transition_gate(run_id, "gate.workspace-isolation", "acknowledged", reason="isolated")
            run_reg.transition_gate(run_id, "gate.baseline", "acknowledged", reason="baseline")
            run_reg.transition_status(run_id, "active", reason="start")

            ev_reg = EvidenceRegistry(root, rapid_dir)
            # Binding to historical state s2 while current state is s3 is valid
            e1 = ev_reg.add(
                run_id,
                {
                    "kind": "workspace",
                    "producer": "harness:codex",
                    "summary": "Isolated worktree verified at s2",
                    "state_revision": 2,
                    "gate_ids": ["gate.workspace-isolation"],
                    "payload": {"mode": "isolated"},
                },
            )
            self.assertEqual(e1.state_revision, 2)

            # Corrupting state_digest in E001.json (even with recomputed content_digest) -> RAPID1203
            rec_file = rapid_dir / "evidence" / run_id / "records" / "E001.json"
            s1 = run_reg.get_state(run_id, revision=1)
            forged = RunEvidence(
                schema_version=RUN_EVIDENCE_SCHEMA_VERSION,
                id="E001",
                run_id=run_id,
                contract_digest=e1.contract_digest,
                state_revision=2,
                state_digest=s1.content_digest,  # s1 digest instead of s2 digest!
                kind=e1.kind,
                producer=e1.producer,
                summary=e1.summary,
                task_ids=e1.task_ids,
                gate_ids=e1.gate_ids,
                capability_ids=e1.capability_ids,
                payload=e1.payload,
                artifacts=e1.artifacts,
            )
            rec_file.write_text(forged.to_json(indent=2), encoding="utf-8")

            with self.assertRaises(EvidenceBindingMismatchError) as ctx:
                ev_reg.verify(run_id)
            self.assertEqual(ctx.exception.code, "RAPID1203")

    def test_contract_and_harness_producer_binding_produces_rapid1203(self):
        # Section 31 & 94
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            rapid_dir, _, run_reg, run_a = _setup_ready_project(
                root,
                spec_id="spec-a",
                harness="codex",
            )
            run_b_rec = run_reg.create(
                spec_id="spec-a",
                run_id="spec-a-r1-run-002",
                harness="claude",
            )
            run_b = run_b_rec.id

            ev_reg = EvidenceRegistry(root, rapid_dir)
            ev_reg.add(
                run_a,
                {
                    "kind": "file_change",
                    "producer": "harness:codex",
                    "summary": "Changed file in run A",
                    "task_ids": ["T001"],
                    "payload": {"paths": ["app.py"]},
                },
            )

            # Producer mismatch: harness:claude on a codex run -> RAPID1203
            with self.assertRaises(EvidenceBindingMismatchError) as ctx_prod:
                ev_reg.add(
                    run_a,
                    {
                        "kind": "file_change",
                        "producer": "harness:claude",
                        "summary": "Wrong harness producer",
                        "task_ids": ["T001"],
                        "payload": {"paths": ["app.py"]},
                    },
                )
            self.assertEqual(ctx_prod.exception.code, "RAPID1203")

            # Copying E001.json from Run A to Run B -> RAPID1203
            run_b_records = rapid_dir / "evidence" / run_b / "records"
            run_b_records.mkdir(parents=True)
            (run_b_records / "E001.json").write_bytes(
                (rapid_dir / "evidence" / run_a / "records" / "E001.json").read_bytes()
            )
            with self.assertRaises(EvidenceBindingMismatchError) as ctx_copy:
                ev_reg.verify(run_b)
            self.assertEqual(ctx_copy.exception.code, "RAPID1203")

    def test_invalid_task_gate_and_capability_references_produce_rapid1207(self):
        # Section 32 & 33
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            rapid_dir, _, _, run_id = _setup_ready_project(root)
            ev_reg = EvidenceRegistry(root, rapid_dir)

            for bad_field in (
                {"task_ids": ["T999"]},
                {"gate_ids": ["gate.nonexistent"]},
                {"capability_ids": ["unknown.capability"]},
            ):
                payload = {
                    "kind": "file_change",
                    "producer": "harness:codex",
                    "summary": "Bad reference",
                    "payload": {"paths": ["app.py"]},
                    **bad_field,
                }
                with self.assertRaises(InvalidEvidenceReferenceError) as ctx:
                    ev_reg.add(run_id, payload)
                self.assertEqual(ctx.exception.code, "RAPID1207")

    def test_history_gap_produces_rapid1208(self):
        # Section 40 & 95
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            rapid_dir, _, _, run_id = _setup_ready_project(root)
            ev_reg = EvidenceRegistry(root, rapid_dir)

            for idx in range(3):
                ev_reg.add(
                    run_id,
                    {
                        "kind": "file_change",
                        "producer": "harness:codex",
                        "summary": f"Change {idx}",
                        "task_ids": ["T001"],
                        "payload": {"paths": [f"file_{idx}.py"]},
                    },
                )

            # Remove E002.json to create E001, E003 gap
            (rapid_dir / "evidence" / run_id / "records" / "E002.json").unlink()

            with self.assertRaises(EvidenceSequenceGapError) as ctx:
                ev_reg.verify(run_id)
            self.assertEqual(ctx.exception.code, "RAPID1208")

            report = validate_evidence_registry(rapid_dir, root)
            self.assertIn("RAPID1208", [d.code for d in report.diagnostics])

    def test_orphan_artifact_directory_produces_rapid1209_warning_and_next_id_skips_orphan(self):
        # Section 39 & 96
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            rapid_dir, _, _, run_id = _setup_ready_project(root)
            ev_reg = EvidenceRegistry(root, rapid_dir)

            ev_reg.add(
                run_id,
                {
                    "kind": "file_change",
                    "producer": "harness:codex",
                    "summary": "Change 1",
                    "task_ids": ["T001"],
                    "payload": {"paths": ["file_1.py"]},
                },
            )
            ev_reg.add(
                run_id,
                {
                    "kind": "file_change",
                    "producer": "harness:codex",
                    "summary": "Change 2",
                    "task_ids": ["T001"],
                    "payload": {"paths": ["file_2.py"]},
                },
            )

            # Simulate crash after creating artifacts/E003/ before writing records/E003.json
            orphan_dir = rapid_dir / "evidence" / run_id / "artifacts" / "E003"
            orphan_dir.mkdir(parents=True)
            orphan_file = orphan_dir / "partial.log"
            orphan_file.write_text("partial crash output", encoding="utf-8")

            val_report = validate_evidence_registry(rapid_dir, root)
            self.assertFalse(val_report.has_errors)
            self.assertTrue(val_report.has_warnings)
            self.assertIn("RAPID1209", [d.code for d in val_report.diagnostics])
            self.assertTrue(orphan_file.exists())

            # Next evidence addition must avoid colliding with E003 and allocate E004
            next_ev = ev_reg.add(
                run_id,
                {
                    "kind": "file_change",
                    "producer": "harness:codex",
                    "summary": "Change after crash orphan",
                    "task_ids": ["T001"],
                    "payload": {"paths": ["file_4.py"]},
                },
            )
            self.assertEqual(next_ev.id, "E004")
            self.assertEqual(
                orphan_file.read_text(encoding="utf-8"),
                "partial crash output",
            )

    def test_append_only_record_and_artifact_overwrite_protection_produces_rapid1211(self):
        # Section 37 & 97
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            rapid_dir, _, _, run_id = _setup_ready_project(root)
            ev_reg = EvidenceRegistry(root, rapid_dir)

            art_src = root / "out.txt"
            art_src.write_text("original artifact bytes", encoding="utf-8")

            e1 = ev_reg.add(
                run_id,
                {
                    "kind": "artifact",
                    "producer": "user",
                    "summary": "Supporting build report",
                    "task_ids": ["T001"],
                    "payload": {"label": "build-report"},
                    "artifacts": ["out.txt"],
                },
            )
            rec_path = rapid_dir / "evidence" / run_id / "records" / "E001.json"
            art_path = root / e1.artifacts[0].path
            orig_rec_bytes = rec_path.read_bytes()
            orig_art_bytes = art_path.read_bytes()

            with self.assertRaises(EvidenceOverwriteError) as ctx_rec:
                ev_reg._write_record_file(run_id, e1)
            self.assertEqual(ctx_rec.exception.code, "RAPID1211")
            self.assertEqual(rec_path.read_bytes(), orig_rec_bytes)

            with self.assertRaises(EvidenceOverwriteError) as ctx_art:
                ev_reg._write_artifact_file(run_id, "E001", "out.txt", b"tampered")
            self.assertEqual(ctx_art.exception.code, "RAPID1211")
            self.assertEqual(art_path.read_bytes(), orig_art_bytes)


class BehavioralEvaluatorAndRegistryTests(unittest.TestCase):
    def test_acknowledged_without_evidence_and_pending_with_evidence_remain_unverified(self):
        # Section 52, 54, 89, 98
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            rapid_dir, _, run_reg, run_id = _setup_ready_project(root)
            ev_reg = EvidenceRegistry(root, rapid_dir)
            eval_reg = EvalRegistry(root, rapid_dir)

            # 1. Pending gate with valid test evidence -> UNVERIFIED, and gate stays pending
            log_file = root / "tests.log"
            log_file.write_text("OK", encoding="utf-8")
            ev_reg.add(
                run_id,
                {
                    "kind": "test_result",
                    "producer": "harness:codex",
                    "summary": "Passing tests before gate ack",
                    "gate_ids": ["gate.tests"],
                    "capability_ids": ["tests.execute"],
                    "payload": {
                        "suite": "unittest",
                        "exit_code": 0,
                        "passed": 10,
                        "failed": 0,
                        "skipped": 0,
                    },
                    "artifacts": ["tests.log"],
                },
            )
            rep_pending = eval_reg.evaluate_run(run_id)
            gate_assertion = next(
                a for a in rep_pending.assertions if a.id == "gate.gate.tests.evidence"
            )
            self.assertEqual(gate_assertion.status, EvalAssertionStatus.UNVERIFIED)
            self.assertEqual(rep_pending.verdict, EvaluationVerdict.UNVERIFIED)

            # Verify gate was NOT auto-acknowledged in Phase 4
            current_state = run_reg.get_state(run_id)
            gate_state = next(g for g in current_state.gates if g.id == "gate.tests")
            self.assertEqual(gate_state.disposition.value, "pending")

        # 2. Acknowledged gate without any evidence -> UNVERIFIED (Section 98)
        with tempfile.TemporaryDirectory() as tmp2:
            root2 = Path(tmp2)
            rapid_dir2, _, run_reg2, run_id2 = _setup_ready_project(root2)
            run_reg2.transition_gate(run_id2, "gate.workspace-isolation", "acknowledged", reason="ack")
            run_reg2.transition_gate(run_id2, "gate.baseline", "acknowledged", reason="ack")
            run_reg2.transition_status(run_id2, "active", reason="start")
            run_reg2.transition_task(run_id2, "T001", "in_progress", reason="work")
            run_reg2.transition_task(run_id2, "T001", "done", reason="done")
            run_reg2.transition_gate(run_id2, "gate.tests", "acknowledged", reason="claimed pass")
            run_reg2.transition_gate(run_id2, "gate.review", "acknowledged", reason="claimed review")
            run_reg2.transition_gate(run_id2, "gate.final-verification", "acknowledged", reason="claimed final")
            run_reg2.transition_status(run_id2, "finished", reason="complete")

            eval_reg2 = EvalRegistry(root2, rapid_dir2)
            rep_ack_no_ev = eval_reg2.evaluate_run(run_id2)
            gate_tests_a = next(
                a for a in rep_ack_no_ev.assertions if a.id == "gate.gate.tests.evidence"
            )
            self.assertEqual(gate_tests_a.status, EvalAssertionStatus.UNVERIFIED)
            self.assertEqual(rep_ack_no_ev.verdict, EvaluationVerdict.UNVERIFIED)

    def test_gate_tests_pass_failure_and_conservative_multiple_evidence(self):
        # Section 55, 59, 99, 100
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            rapid_dir, _, run_reg, run_id = _setup_ready_project(root)
            run_reg.transition_gate(run_id, "gate.workspace-isolation", "acknowledged", reason="iso")
            run_reg.transition_gate(run_id, "gate.baseline", "acknowledged", reason="base")
            run_reg.transition_status(run_id, "active", reason="start")
            run_reg.transition_task(run_id, "T001", "in_progress", reason="work")
            run_reg.transition_task(run_id, "T001", "done", reason="done")
            run_reg.transition_gate(run_id, "gate.tests", "acknowledged", reason="ran tests")
            run_reg.transition_gate(run_id, "gate.review", "acknowledged", reason="reviewed")
            run_reg.transition_gate(run_id, "gate.final-verification", "acknowledged", reason="final")
            run_reg.transition_status(run_id, "finished", reason="done")

            ev_reg = EvidenceRegistry(root, rapid_dir)
            eval_reg = EvalRegistry(root, rapid_dir)

            log_file = root / "test-pass.txt"
            log_file.write_text("Ran 25 tests\nOK\n", encoding="utf-8")

            # Add passing artifact-backed test evidence -> gate.tests PASS (Section 99)
            ev_reg.add(
                run_id,
                {
                    "kind": "test_result",
                    "producer": "harness:codex",
                    "summary": "Passing unit tests",
                    "task_ids": ["T001"],
                    "gate_ids": ["gate.tests"],
                    "capability_ids": ["tests.execute"],
                    "payload": {
                        "suite": "unittest",
                        "exit_code": 0,
                        "passed": 25,
                        "failed": 0,
                        "skipped": 0,
                    },
                    "artifacts": ["test-pass.txt"],
                },
            )
            rep_pass = eval_reg.evaluate_run(run_id)
            gate_tests = next(
                a for a in rep_pass.assertions if a.id == "gate.gate.tests.evidence"
            )
            self.assertEqual(gate_tests.status, EvalAssertionStatus.PASS)

            # Add failing test evidence for the same gate -> FAIL dominates PASS (Section 59 & 100)
            fail_log = root / "test-fail.txt"
            fail_log.write_text("FAILED (failures=2)\n", encoding="utf-8")
            ev_reg.add(
                run_id,
                {
                    "kind": "test_result",
                    "producer": "harness:codex",
                    "summary": "Regression failure",
                    "gate_ids": ["gate.tests"],
                    "capability_ids": ["tests.execute"],
                    "payload": {
                        "suite": "unittest",
                        "exit_code": 1,
                        "passed": 23,
                        "failed": 2,
                        "skipped": 0,
                    },
                    "artifacts": ["test-fail.txt"],
                },
            )
            rep_fail = eval_reg.evaluate_run(run_id)
            gate_tests_after = next(
                a for a in rep_fail.assertions if a.id == "gate.gate.tests.evidence"
            )
            self.assertEqual(gate_tests_after.status, EvalAssertionStatus.FAIL)
            self.assertEqual(gate_tests_after.evidence_ids, ("E001", "E002"))
            self.assertEqual(rep_fail.verdict, EvaluationVerdict.FAIL)

    def test_tasks_done_with_and_without_evidence_and_skipped_task(self):
        # Section 50, 102, 103, 104
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            rapid_dir, _, run_reg, run_id = _setup_ready_project(
                root,
                tasks=("Task One", "Task Two"),
                classification="spike",
                risk="low",
            )
            run_reg.transition_status(run_id, "active", reason="start")
            run_reg.transition_task(run_id, "T001", "in_progress", reason="work")
            run_reg.transition_task(run_id, "T001", "done", reason="completed")
            run_reg.transition_task(run_id, "T002", "skipped", reason="not needed")

            ev_reg = EvidenceRegistry(root, rapid_dir)
            eval_reg = EvalRegistry(root, rapid_dir)

            # T001 done without evidence -> UNVERIFIED; T002 skipped -> NOT_APPLICABLE
            rep1 = eval_reg.evaluate_run(run_id)
            a_t1 = next(a for a in rep1.assertions if a.id == "task.T001.evidence")
            a_t2 = next(a for a in rep1.assertions if a.id == "task.T002.evidence")
            self.assertEqual(a_t1.status, EvalAssertionStatus.UNVERIFIED)
            self.assertEqual(a_t2.status, EvalAssertionStatus.NOT_APPLICABLE)
            self.assertFalse(a_t2.required)

            # Link FILE_CHANGE to T001 -> task.T001.evidence becomes PASS
            ev_reg.add(
                run_id,
                {
                    "kind": "file_change",
                    "producer": "harness:codex",
                    "summary": "Implemented T001",
                    "task_ids": ["T001"],
                    "payload": {"paths": ["rapid_os/feature.py"]},
                },
            )
            rep2 = eval_reg.evaluate_run(run_id)
            a_t1_after = next(
                a for a in rep2.assertions if a.id == "task.T001.evidence"
            )
            self.assertEqual(a_t1_after.status, EvalAssertionStatus.PASS)
            self.assertEqual(a_t1_after.evidence_ids, ("E001",))

    def test_capability_observations_and_non_observable_capabilities(self):
        # Section 60, 61, 62, 63, 105, 106
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            rapid_dir, _, _, run_id = _setup_ready_project(root)
            ev_reg = EvidenceRegistry(root, rapid_dir)
            eval_reg = EvalRegistry(root, rapid_dir)

            rep_initial = eval_reg.evaluate_run(
                run_id,
                extra_capability_requirements=("mcp.invoke",),
            )
            by_id = {a.id: a for a in rep_initial.assertions}

            # Non-observable capabilities must be NOT_APPLICABLE without fake proof
            for non_obs in (
                "capability.context.consume.observed",
                "capability.repository.read.observed",
            ):
                self.assertEqual(
                    by_id[non_obs].status,
                    EvalAssertionStatus.NOT_APPLICABLE,
                )
                self.assertFalse(by_id[non_obs].required)
                self.assertIn(
                    "not objectively observable by Evidence Engine v1",
                    by_id[non_obs].reason,
                )

            # Observable capabilities without evidence are UNVERIFIED
            self.assertEqual(
                by_id["capability.tests.execute.observed"].status,
                EvalAssertionStatus.UNVERIFIED,
            )
            self.assertEqual(
                by_id["capability.mcp.invoke.observed"].status,
                EvalAssertionStatus.UNVERIFIED,
            )

            # Add test_result and tool_invocation evidence -> both become PASS
            ev_reg.add(
                run_id,
                {
                    "kind": "test_result",
                    "producer": "harness:codex",
                    "summary": "Unit tests",
                    "payload": {
                        "suite": "unittest",
                        "exit_code": 0,
                        "passed": 12,
                        "failed": 0,
                        "skipped": 0,
                    },
                },
            )
            ev_reg.add(
                run_id,
                {
                    "kind": "tool_invocation",
                    "producer": "harness:codex",
                    "summary": "MCP query",
                    "capability_ids": ["mcp.invoke"],
                    "payload": {"tool_id": "mcp.context7", "outcome": "success"},
                },
            )

            rep_after = eval_reg.evaluate_run(
                run_id,
                extra_capability_requirements=("mcp.invoke",),
            )
            by_id_after = {a.id: a for a in rep_after.assertions}
            self.assertEqual(
                by_id_after["capability.tests.execute.observed"].status,
                EvalAssertionStatus.PASS,
            )
            self.assertEqual(
                by_id_after["capability.mcp.invoke.observed"].status,
                EvalAssertionStatus.PASS,
            )

    def test_evaluation_determinism_and_stale_report_warnings(self):
        # Section 69, 70, 85, 107, 108, 109
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            rapid_dir, _, run_reg, run_id = _setup_ready_project(root)
            ev_reg = EvidenceRegistry(root, rapid_dir)
            eval_reg = EvalRegistry(root, rapid_dir)

            ev_reg.add(
                run_id,
                {
                    "kind": "file_change",
                    "producer": "harness:codex",
                    "summary": "Initial change",
                    "task_ids": ["T001"],
                    "payload": {"paths": ["a.py"]},
                },
            )

            rep_a = eval_reg.evaluate_run(run_id, write=True)
            rep_b = eval_reg.evaluate_run(run_id, write=True)
            self.assertEqual(rep_a.assertions, rep_b.assertions)
            self.assertEqual(rep_a.verdict, rep_b.verdict)
            self.assertEqual(rep_a.report_digest, rep_b.report_digest)
            self.assertEqual(rep_a.to_json(), rep_b.to_json())

            # Fresh report is not stale
            val_fresh = validate_eval_registry(rapid_dir, root)
            self.assertFalse(val_fresh.has_errors)
            self.assertFalse(val_fresh.has_warnings)
            self.assertIn("RAPID1220", [d.code for d in val_fresh.diagnostics])

            # Adding new evidence E002 makes stored report stale -> RAPID1227 WARNING (Section 108)
            ev_reg.add(
                run_id,
                {
                    "kind": "file_change",
                    "producer": "harness:codex",
                    "summary": "Second change",
                    "task_ids": ["T001"],
                    "payload": {"paths": ["b.py"]},
                },
            )
            val_stale_ev = validate_eval_registry(rapid_dir, root)
            self.assertFalse(val_stale_ev.has_errors)
            self.assertTrue(val_stale_ev.has_warnings)
            self.assertIn("RAPID1227", [d.code for d in val_stale_ev.diagnostics])

            # Write a new report 0003.json -> no longer stale
            eval_reg.evaluate_run(run_id, write=True)
            self.assertFalse(validate_eval_registry(rapid_dir, root).has_warnings)

            # Advancing RunState makes 0003.json stale -> RAPID1227 WARNING (Section 109)
            run_reg.transition_gate(run_id, "gate.workspace-isolation", "acknowledged", reason="iso")
            val_stale_state = validate_eval_registry(rapid_dir, root)
            self.assertFalse(val_stale_state.has_errors)
            self.assertTrue(val_stale_state.has_warnings)
            self.assertIn("RAPID1227", [d.code for d in val_stale_state.diagnostics])

            # Historical reports remain valid and retrievable
            self.assertEqual(len(eval_reg.list_reports(run_id)), 3)
            self.assertEqual(eval_reg.get_report(run_id, revision=1), rep_a)

    def test_read_only_eval_and_write_isolation_preserve_phase4_and_phase5_bytes(self):
        # Section 4, 86, 87, 88, 90, 110, 111
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            rapid_dir, _, _, run_id = _setup_ready_project(root)
            harness_reg = HarnessRegistry(root, rapid_dir)
            harness_reg.initialize_project_profile("codex")
            write_capability_lock(root, rapid_dir, registry=harness_reg)

            ev_reg = EvidenceRegistry(root, rapid_dir)
            art = root / "artifact.txt"
            art.write_text("immutable artifact", encoding="utf-8")
            ev_reg.add(
                run_id,
                {
                    "kind": "test_result",
                    "producer": "harness:codex",
                    "summary": "Tests",
                    "task_ids": ["T001"],
                    "gate_ids": ["gate.tests"],
                    "capability_ids": ["tests.execute"],
                    "payload": {
                        "suite": "unittest",
                        "exit_code": 0,
                        "passed": 10,
                        "failed": 0,
                        "skipped": 0,
                    },
                    "artifacts": ["artifact.txt"],
                },
            )

            before_all = _snapshot_tree_bytes(rapid_dir)

            # Read-only eval run: zero bytes changed in .rapid-os
            code, out, err = _run_cli(
                root,
                ["eval", "run", "--run", run_id, "--json"],
            )
            self.assertEqual(code, 0, err)
            self.assertEqual(json.loads(out)["run_id"], run_id)
            self.assertEqual(_snapshot_tree_bytes(rapid_dir), before_all)

            # Eval run --write: only .rapid-os/evals/<run_id>/reports/0001.json is added
            code_w, out_w, err_w = _run_cli(
                root,
                ["eval", "run", "--run", run_id, "--write", "--json"],
            )
            self.assertEqual(code_w, 0, err_w)
            after_write = _snapshot_tree_bytes(rapid_dir)
            added_Paths = set(after_write.keys()) - set(before_all.keys())
            self.assertEqual(
                added_Paths,
                {f"evals/{run_id}/reports/0001.json"},
            )
            for k, v in before_all.items():
                self.assertEqual(after_write[k], v, f"Modified {k}")


class EndToEndGovernanceLoopAndCliTests(unittest.TestCase):
    def test_e2e_113_full_verified_run_and_strict_exit_codes(self):
        # Section 112 & 113: Spec ready -> Run create -> PRE gates ack -> Run active ->
        # tasks done -> evidence imported -> POST gates ack -> Run finished -> eval PASS
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            rapid_dir, _, run_reg, run_id = _setup_ready_project(root)

            # Acknowledge PRE gates & activate run
            run_reg.transition_gate(
                run_id,
                "gate.workspace-isolation",
                "acknowledged",
                reason="Isolated worktree ready",
            )
            run_reg.transition_gate(
                run_id,
                "gate.baseline",
                "acknowledged",
                reason="Baseline green",
            )
            run_reg.transition_status(run_id, "active", reason="Start execution")

            # Complete task T001
            run_reg.transition_task(run_id, "T001", "in_progress", reason="Working")
            run_reg.transition_task(run_id, "T001", "done", reason="Implemented")

            # Ingest evidence via CLI (`rapid evidence add --json`)
            test_log = root / "unittest-output.txt"
            test_log.write_text("Ran 259 tests in 0.9s\nOK\n", encoding="utf-8")

            inputs = [
                {
                    "kind": "workspace",
                    "producer": "harness:codex",
                    "summary": "Isolated worktree verified",
                    "gate_ids": ["gate.workspace-isolation"],
                    "capability_ids": ["workspace.isolated"],
                    "payload": {"mode": "isolated"},
                },
                {
                    "kind": "file_change",
                    "producer": "harness:codex",
                    "summary": "Updated checkout handler",
                    "task_ids": ["T001"],
                    "capability_ids": ["repository.write"],
                    "payload": {"paths": ["rapid_os/checkout.py"]},
                },
                {
                    "kind": "test_result",
                    "producer": "harness:codex",
                    "summary": "Unit tests passed",
                    "task_ids": ["T001"],
                    "gate_ids": ["gate.baseline", "gate.tests"],
                    "capability_ids": ["tests.execute"],
                    "payload": {
                        "suite": "unittest",
                        "exit_code": 0,
                        "passed": 259,
                        "failed": 0,
                        "skipped": 0,
                    },
                    "artifacts": ["unittest-output.txt"],
                },
                {
                    "kind": "review",
                    "producer": "external:review-system",
                    "summary": "Peer review approved",
                    "gate_ids": ["gate.review"],
                    "payload": {
                        "review_type": "peer",
                        "outcome": "approved",
                        "reviewer": "reviewer-1",
                    },
                },
                {
                    "kind": "review",
                    "producer": "user",
                    "summary": "Final verification approved",
                    "gate_ids": ["gate.final-verification"],
                    "payload": {
                        "review_type": "final",
                        "outcome": "approved",
                        "reviewer": "lead-1",
                    },
                },
            ]
            for idx, item in enumerate(inputs, start=1):
                in_file = root / f"ev_{idx}.json"
                in_file.write_text(json.dumps(item), encoding="utf-8")
                c_add, out_add, err_add = _run_cli(
                    root,
                    [
                        "evidence",
                        "add",
                        "--run",
                        run_id,
                        "--input",
                        str(in_file),
                        "--json",
                    ],
                )
                self.assertEqual(c_add, 0, err_add)
                self.assertEqual(json.loads(out_add)["id"], f"E{idx:03d}")

            # Acknowledge POST gates and finish run
            run_reg.transition_gate(run_id, "gate.tests", "acknowledged", reason="Tests green")
            run_reg.transition_gate(run_id, "gate.review", "acknowledged", reason="Peer approved")
            run_reg.transition_gate(run_id, "gate.final-verification", "acknowledged", reason="Final verified")
            run_reg.transition_status(run_id, "finished", reason="All gates met")

            run_snapshot_before_eval = _snapshot_tree_bytes(
                rapid_dir / "runs" / run_id
            )

            # Verify evidence CLI commands (`list`, `show`, `verify`)
            c_list, out_list, err_list = _run_cli(
                root,
                ["evidence", "list", "--run", run_id, "--json"],
            )
            self.assertEqual(c_list, 0, err_list)
            self.assertEqual(len(json.loads(out_list)["records"]), 5)

            c_show, out_show, err_show = _run_cli(
                root,
                ["evidence", "show", "--run", run_id, "E003", "--json"],
            )
            self.assertEqual(c_show, 0, err_show)
            self.assertEqual(json.loads(out_show)["id"], "E003")

            c_ver, out_ver, err_ver = _run_cli(
                root,
                ["evidence", "verify", "--run", run_id, "--json"],
            )
            self.assertEqual(c_ver, 0, err_ver)
            self.assertTrue(json.loads(out_ver)["ok"])

            # Evaluate with `--require-pass` and `--write`
            c_eval, out_eval, err_eval = _run_cli(
                root,
                [
                    "eval",
                    "run",
                    "--run",
                    run_id,
                    "--write",
                    "--require-pass",
                    "--json",
                ],
            )
            self.assertEqual(c_eval, 0, err_eval)
            eval_payload = json.loads(out_eval)
            self.assertEqual(eval_payload["verdict"], "pass")

            # Run files remain byte-for-byte identical
            self.assertEqual(
                _snapshot_tree_bytes(rapid_dir / "runs" / run_id),
                run_snapshot_before_eval,
            )

            # Check `eval list` and `eval show`
            c_elist, out_elist, _ = _run_cli(
                root,
                ["eval", "list", "--run", run_id, "--json"],
            )
            self.assertEqual(c_elist, 0)
            self.assertEqual(len(json.loads(out_elist)["reports"]), 1)

            c_eshow, out_eshow, _ = _run_cli(
                root,
                ["eval", "show", "--run", run_id, "--revision", "1", "--json"],
            )
            self.assertEqual(c_eshow, 0)
            self.assertEqual(
                json.loads(out_eshow)["report_digest"],
                eval_payload["report_digest"],
            )

    def test_e2e_114_declared_but_unproven_produces_unverified_and_rapid1225(self):
        # Section 112 & 114: Run finished, all gates acknowledged, tasks done, no evidence -> UNVERIFIED
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _, _, run_reg, run_id = _setup_ready_project(root)

            run_reg.transition_gate(run_id, "gate.workspace-isolation", "acknowledged", reason="ack")
            run_reg.transition_gate(run_id, "gate.baseline", "acknowledged", reason="ack")
            run_reg.transition_status(run_id, "active", reason="active")
            run_reg.transition_task(run_id, "T001", "in_progress", reason="work")
            run_reg.transition_task(run_id, "T001", "done", reason="done")
            run_reg.transition_gate(run_id, "gate.tests", "acknowledged", reason="ack")
            run_reg.transition_gate(run_id, "gate.review", "acknowledged", reason="ack")
            run_reg.transition_gate(run_id, "gate.final-verification", "acknowledged", reason="ack")
            run_reg.transition_status(run_id, "finished", reason="finished")

            # Informational eval exits 0 with verdict == unverified
            c_info, out_info, err_info = _run_cli(
                root,
                ["eval", "run", "--run", run_id, "--json"],
            )
            self.assertEqual(c_info, 0, err_info)
            self.assertEqual(json.loads(out_info)["verdict"], "unverified")

            # Strict `--require-pass` exits 1 with RAPID1225
            c_strict, out_strict, err_strict = _run_cli(
                root,
                ["eval", "run", "--run", run_id, "--require-pass", "--json"],
            )
            self.assertEqual(c_strict, 1)
            self.assertEqual(json.loads(out_strict)["verdict"], "unverified")
            self.assertIn("RAPID1225", err_strict)

    def test_e2e_115_failed_test_evidence_overrides_acknowledged_gate_and_produces_rapid1226(self):
        # Section 112 & 115: Run finished, gate.tests acknowledged, TestEvidence failed > 0 -> FAIL
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            rapid_dir, _, run_reg, run_id = _setup_ready_project(root)

            run_reg.transition_gate(run_id, "gate.workspace-isolation", "acknowledged", reason="ack")
            run_reg.transition_gate(run_id, "gate.baseline", "acknowledged", reason="ack")
            run_reg.transition_status(run_id, "active", reason="active")
            run_reg.transition_task(run_id, "T001", "in_progress", reason="work")
            run_reg.transition_task(run_id, "T001", "done", reason="done")
            run_reg.transition_gate(run_id, "gate.tests", "acknowledged", reason="claimed pass")
            run_reg.transition_gate(run_id, "gate.review", "acknowledged", reason="ack")
            run_reg.transition_gate(run_id, "gate.final-verification", "acknowledged", reason="ack")
            run_reg.transition_status(run_id, "finished", reason="finished")

            ev_reg = EvidenceRegistry(root, rapid_dir)
            fail_log = root / "fail.log"
            fail_log.write_text("FAIL: test_checkout\n", encoding="utf-8")
            ev_reg.add(
                run_id,
                {
                    "kind": "test_result",
                    "producer": "harness:codex",
                    "summary": "Unit test run had 1 failure",
                    "task_ids": ["T001"],
                    "gate_ids": ["gate.tests"],
                    "capability_ids": ["tests.execute"],
                    "payload": {
                        "suite": "unittest",
                        "exit_code": 0,
                        "passed": 10,
                        "failed": 1,
                        "skipped": 0,
                    },
                    "artifacts": ["fail.log"],
                },
            )

            c_strict, out_strict, err_strict = _run_cli(
                root,
                ["eval", "run", "--run", run_id, "--require-pass", "--json"],
            )
            self.assertEqual(c_strict, 1)
            report_dict = json.loads(out_strict)
            self.assertEqual(report_dict["verdict"], "fail")
            self.assertIn("RAPID1226", err_strict)

    def test_e2e_116_waived_review_produces_pass_with_waivers_and_exits_zero_on_require_pass(self):
        # Section 76, 101, 112, 116: all evidence passes, gate.review waived -> PASS_WITH_WAIVERS
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            rapid_dir, _, run_reg, run_id = _setup_ready_project(root)

            run_reg.transition_gate(run_id, "gate.workspace-isolation", "acknowledged", reason="iso")
            run_reg.transition_gate(run_id, "gate.baseline", "acknowledged", reason="base")
            run_reg.transition_status(run_id, "active", reason="active")
            run_reg.transition_task(run_id, "T001", "in_progress", reason="work")
            run_reg.transition_task(run_id, "T001", "done", reason="done")
            run_reg.transition_gate(run_id, "gate.tests", "acknowledged", reason="tests green")
            run_reg.transition_gate(run_id, "gate.review", "waived", reason="solo hotfix waiver")
            run_reg.transition_gate(run_id, "gate.final-verification", "acknowledged", reason="final")
            run_reg.transition_status(run_id, "finished", reason="finished")

            ev_reg = EvidenceRegistry(root, rapid_dir)
            test_log = root / "pass.log"
            test_log.write_text("OK\n", encoding="utf-8")

            ev_reg.add(
                run_id,
                {
                    "kind": "workspace",
                    "producer": "harness:codex",
                    "summary": "Isolated workspace",
                    "gate_ids": ["gate.workspace-isolation"],
                    "capability_ids": ["workspace.isolated"],
                    "payload": {"mode": "isolated"},
                },
            )
            ev_reg.add(
                run_id,
                {
                    "kind": "file_change",
                    "producer": "harness:codex",
                    "summary": "Code change",
                    "task_ids": ["T001"],
                    "capability_ids": ["repository.write"],
                    "payload": {"paths": ["rapid_os/hotfix.py"]},
                },
            )
            ev_reg.add(
                run_id,
                {
                    "kind": "test_result",
                    "producer": "harness:codex",
                    "summary": "Tests pass",
                    "task_ids": ["T001"],
                    "gate_ids": ["gate.baseline", "gate.tests"],
                    "capability_ids": ["tests.execute"],
                    "payload": {
                        "suite": "unittest",
                        "exit_code": 0,
                        "passed": 40,
                        "failed": 0,
                        "skipped": 0,
                    },
                    "artifacts": ["pass.log"],
                },
            )
            ev_reg.add(
                run_id,
                {
                    "kind": "review",
                    "producer": "user",
                    "summary": "Final check approved",
                    "gate_ids": ["gate.final-verification"],
                    "payload": {
                        "review_type": "final",
                        "outcome": "approved",
                        "reviewer": "lead-1",
                    },
                },
            )

            c_pass, out_pass, err_pass = _run_cli(
                root,
                ["eval", "run", "--run", run_id, "--require-pass", "--json"],
            )
            self.assertEqual(c_pass, 0, err_pass)
            payload = json.loads(out_pass)
            self.assertEqual(payload["verdict"], "pass_with_waivers")
            review_assertion = next(
                a for a in payload["assertions"] if a["id"] == "gate.gate.review.evidence"
            )
            self.assertEqual(review_assertion["status"], "waived")

    def test_phase6_modules_contain_no_subprocess_or_shell_execution(self):
        # Section 5: Phase 6 is purely offline and never invokes subprocess/os.system/Popen
        repo_root = Path(__file__).resolve().parents[1]
        phase6_files = (
            repo_root / "rapid_os" / "domain" / "evidence.py",
            repo_root / "rapid_os" / "domain" / "evals.py",
            repo_root / "rapid_os" / "adapters" / "evidence_registry.py",
            repo_root / "rapid_os" / "adapters" / "eval_registry.py",
        )
        forbidden_modules = {"subprocess"}
        forbidden_calls = {"system", "popen", "Popen"}

        for file_path in phase6_files:
            tree = ast.parse(file_path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        self.assertNotIn(
                            alias.name.split(".")[0],
                            forbidden_modules,
                            f"Forbidden import in {file_path.name}",
                        )
                elif isinstance(node, ast.ImportFrom) and node.module:
                    self.assertNotIn(
                        node.module.split(".")[0],
                        forbidden_modules,
                        f"Forbidden from-import in {file_path.name}",
                    )
                elif isinstance(node, ast.Attribute):
                    self.assertNotIn(
                        node.attr,
                        forbidden_calls,
                        f"Forbidden call attribute '{node.attr}' in {file_path.name}",
                    )


if __name__ == "__main__":
    unittest.main()
