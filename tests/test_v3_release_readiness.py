from __future__ import annotations

import contextlib
import hashlib
import io
import json
from pathlib import Path
import re
import tempfile
import unittest
from unittest.mock import patch

import rapid
import rapid_os
from rapid_os.cli import main as cli_main
from rapid_os.cli.main import create_parser
from rapid_os.core.paths import resolve_paths
from rapid_os.domain.validation import validate_project


REPO_ROOT = Path(__file__).resolve().parent.parent


def _run_cli(args: list[str], cwd: Path | None = None) -> tuple[int, str, str]:
    stdout = io.StringIO()
    stderr = io.StringIO()
    project_root = cwd if cwd is not None else REPO_ROOT
    rapid_dir = project_root / ".rapid-os"
    config_file = rapid_dir / "config.json"
    exit_code = 0
    with (
        patch.object(cli_main, "CURRENT_DIR", project_root),
        patch.object(cli_main, "PROJECT_RAPID_DIR", rapid_dir),
        patch.object(cli_main, "CONFIG_FILE", config_file),
        contextlib.redirect_stdout(stdout),
        contextlib.redirect_stderr(stderr),
    ):
        try:
            res = cli_main.main(args)
            if isinstance(res, int):
                exit_code = res
        except SystemExit as exc:
            exit_code = int(exc.code) if exc.code is not None else 0
    return exit_code, stdout.getvalue(), stderr.getvalue()


def _bootstrap_minimal_project(root: Path) -> None:
    """Create a realistic Python project fixture with minimal .rapid-os standards."""
    (root / "src").mkdir(parents=True, exist_ok=True)
    (root / "tests").mkdir(parents=True, exist_ok=True)
    (root / "pyproject.toml").write_text(
        '[project]\nname = "demo-service"\nversion = "0.1.0"\ndependencies = ["fastapi"]\n',
        encoding="utf-8",
    )
    (root / "src" / "booking.py").write_text(
        "def create_booking(key: str) -> dict:\n    return {'key': key, 'status': 'confirmed'}\n",
        encoding="utf-8",
    )
    (root / "tests" / "test_booking.py").write_text(
        "import unittest\nclass BookingTests(unittest.TestCase):\n    def test_ok(self):\n        self.assertTrue(True)\n",
        encoding="utf-8",
    )

    standards_dir = root / ".rapid-os" / "standards"
    standards_dir.mkdir(parents=True, exist_ok=True)
    (standards_dir / "tech-stack.md").write_text("# Tech Stack\nPython 3.10+ and FastAPI.\n", encoding="utf-8")
    (standards_dir / "topology.md").write_text("# Topology\nModular backend service.\n", encoding="utf-8")
    (standards_dir / "security.md").write_text("# Security\nEnforce strict input validation and idempotency.\n", encoding="utf-8")
    (standards_dir / "business.md").write_text("# Business Rules\nBookings must be idempotent.\n", encoding="utf-8")
    (standards_dir / "coding-rules.md").write_text("# Coding Rules\nKeep domain logic deterministic.\n", encoding="utf-8")
    (standards_dir / "design.md").write_text("# Design\nAPI-first service.\n", encoding="utf-8")
    (root / ".rapid-os" / "config.json").write_text(
        json.dumps(
            {
                "version": "3.0.0",
                "stack": "python-ai",
                "topology": "fullstack-separated",
                "tools": ["codex"],
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )


class V3ReleaseReadinessTests(unittest.TestCase):
    def test_version_contract_and_cli_flag(self) -> None:
        self.assertEqual(rapid_os.__version__, "3.0.0")
        self.assertEqual(rapid.__version__, "3.0.0")

        code, out, err = _run_cli(["--version"])
        self.assertEqual(code, 0)
        self.assertEqual(out.strip(), "Rapid OS 3.0.0")
        self.assertEqual(err, "")

    def test_end_to_end_positive_governance_loop_cli(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _bootstrap_minimal_project(root)

            # 1. rapid scan --write --json
            code, scan_out, err = _run_cli(["scan", "--write", "--json"], cwd=root)
            self.assertEqual(code, 0, err)
            scan_doc = json.loads(scan_out)
            self.assertEqual(scan_doc["schema_version"], 1)
            self.assertTrue((root / ".rapid-os" / "project.json").is_file())

            # 2. rapid spec create + status ready
            code, spec_create_out, err = _run_cli(
                [
                    "spec",
                    "create",
                    "--id",
                    "booking-idempotency",
                    "--title",
                    "Booking Idempotency",
                    "--mode",
                    "feature",
                    "--objective",
                    "Prevent duplicate bookings on retry",
                    "--problem",
                    "Client retries can duplicate booking charges",
                    "--scope",
                    "src/booking.py",
                    "--acceptance",
                    "Duplicate idempotency key returns identical booking confirmation",
                    "--task",
                    "Implement idempotency check and unit test",
                    "--json",
                ],
                cwd=root,
            )
            self.assertEqual(code, 0, err)
            spec_doc = json.loads(spec_create_out)
            self.assertEqual(spec_doc["id"], "booking-idempotency")
            self.assertEqual(spec_doc["status"], "draft")

            code, spec_ready_out, err = _run_cli(
                ["spec", "status", "booking-idempotency", "ready", "--json"],
                cwd=root,
            )
            self.assertEqual(code, 0, err)
            self.assertEqual(json.loads(spec_ready_out)["status"], "ready")

            # 3. rapid context compile --spec booking-idempotency --json
            code, ctx_out, err = _run_cli(
                [
                    "context",
                    "compile",
                    "--mode",
                    "feature",
                    "--spec",
                    "booking-idempotency",
                    "--harness",
                    "codex",
                    "--objective",
                    "Prevent duplicate bookings on retry",
                    "--json",
                ],
                cwd=root,
            )
            self.assertEqual(code, 0, err)
            ctx_doc = json.loads(ctx_out)
            self.assertEqual(ctx_doc["schema_version"], 1)
            selected_ids = {entry["source_id"] for entry in ctx_doc["manifest"]["selected"]}
            self.assertIn("spec.booking-idempotency.requirements", selected_ids)

            # 4. rapid policy init + rapid run create
            code, policy_out, err = _run_cli(["policy", "init", "--json"], cwd=root)
            self.assertEqual(code, 0, err)
            self.assertEqual(json.loads(policy_out)["schema_version"], 1)

            code, run_create_out, err = _run_cli(
                [
                    "run",
                    "create",
                    "--spec",
                    "booking-idempotency",
                    "--harness",
                    "codex",
                    "--risk",
                    "medium",
                    "--json",
                ],
                cwd=root,
            )
            self.assertEqual(code, 0, err)
            run_bundle = json.loads(run_create_out)
            run_id = run_bundle["id"]
            self.assertEqual(run_id, "booking-idempotency-r1-run-001")

            # Verify cross-module digest bindings on ExecutionContract
            contract = run_bundle["contract"]
            self.assertEqual(contract["spec_content_digest"], spec_doc["revision"]["content_digest"])
            self.assertEqual(contract["context_digest"], ctx_doc["manifest"]["content_digest"])

            # 5. rapid harness init + customize supported capabilities + lock + resolve --locked --require-compatible
            code, _, err = _run_cli(["harness", "init", "codex", "--json"], cwd=root)
            self.assertEqual(code, 0, err)
            harness_path = root / ".rapid-os" / "harnesses" / "codex.json"
            harness_data = json.loads(harness_path.read_text(encoding="utf-8"))
            for cap in harness_data["capabilities"]:
                if cap["capability_id"] in {"repository.write", "tests.execute"}:
                    cap["status"] = "supported"
                    cap["reason"] = "Configured as supported for project CI governance."
            harness_data.pop("content_digest", None)
            harness_path.write_text(json.dumps(harness_data, indent=2) + "\n", encoding="utf-8")

            code, lock_out, err = _run_cli(["harness", "lock", "--json"], cwd=root)
            self.assertEqual(code, 0, err)
            self.assertEqual(json.loads(lock_out)["schema_version"], 1)

            code, resolve_out, err = _run_cli(
                [
                    "harness",
                    "resolve",
                    "--run",
                    run_id,
                    "--locked",
                    "--require-compatible",
                    "--json",
                ],
                cwd=root,
            )
            self.assertEqual(code, 0, err)
            self.assertEqual(json.loads(resolve_out)["status"], "compatible")

            # 6. Pre-execution gate -> active -> task T001 in_progress -> done
            code, _, err = _run_cli(
                ["run", "gate", run_id, "gate.baseline", "acknowledged", "--reason", "Baseline green", "--json"],
                cwd=root,
            )
            self.assertEqual(code, 0, err)

            code, _, err = _run_cli(
                ["run", "status", run_id, "active", "--reason", "Starting governed execution", "--json"],
                cwd=root,
            )
            self.assertEqual(code, 0, err)

            code, _, err = _run_cli(
                ["run", "task", run_id, "T001", "in_progress", "--reason", "Implementing idempotency", "--json"],
                cwd=root,
            )
            self.assertEqual(code, 0, err)

            code, _, err = _run_cli(
                ["run", "task", run_id, "T001", "done", "--reason", "Implementation complete", "--json"],
                cwd=root,
            )
            self.assertEqual(code, 0, err)

            # 7. Attach verifiable evidence before/during post-execution gates
            baseline_log = root / "baseline.log"
            baseline_log.write_text("Ran 1 test in 0.001s\nOK\n", encoding="utf-8")
            test_log = root / "test-output.log"
            test_log.write_text("Ran 2 tests in 0.002s\nOK\n", encoding="utf-8")

            ev_inputs = [
                {
                    "kind": "workspace",
                    "producer": "harness:codex",
                    "summary": "Executed in current project workspace",
                    "capability_ids": ["workspace.current"],
                    "payload": {"mode": "current"},
                },
                {
                    "kind": "command_result",
                    "producer": "harness:codex",
                    "summary": "Baseline test check passed",
                    "gate_ids": ["gate.baseline"],
                    "payload": {"label": "baseline-unittest", "exit_code": 0},
                    "artifacts": ["baseline.log"],
                },
                {
                    "kind": "file_change",
                    "producer": "harness:codex",
                    "summary": "Updated booking service with idempotency store",
                    "task_ids": ["T001"],
                    "capability_ids": ["repository.write"],
                    "payload": {"paths": ["src/booking.py", "tests/test_booking.py"]},
                },
                {
                    "kind": "test_result",
                    "producer": "harness:codex",
                    "summary": "Unit test suite passed",
                    "task_ids": ["T001"],
                    "gate_ids": ["gate.tests"],
                    "capability_ids": ["tests.execute"],
                    "payload": {"suite": "unittest", "exit_code": 0, "passed": 2, "failed": 0, "skipped": 0},
                    "artifacts": ["test-output.log"],
                },
                {
                    "kind": "review",
                    "producer": "human:reviewer",
                    "summary": "Final verification approved",
                    "gate_ids": ["gate.final-verification"],
                    "payload": {"review_type": "final", "outcome": "approved", "reviewer": "release-lead"},
                },
            ]

            for idx, ev_payload in enumerate(ev_inputs, start=1):
                ev_file = root / f"ev-{idx}.json"
                ev_file.write_text(json.dumps(ev_payload, indent=2) + "\n", encoding="utf-8")
                code, ev_out, err = _run_cli(
                    ["evidence", "add", "--run", run_id, "--input", str(ev_file), "--json"],
                    cwd=root,
                )
                self.assertEqual(code, 0, err)
                self.assertEqual(json.loads(ev_out)["id"], f"E{idx:03d}")

            # 8. Acknowledge post-execution gates and finish the run
            for gate_id in ("gate.tests", "gate.final-verification"):
                code, _, err = _run_cli(
                    ["run", "gate", run_id, gate_id, "acknowledged", "--reason", f"{gate_id} verified", "--json"],
                    cwd=root,
                )
                self.assertEqual(code, 0, err)

            code, _, err = _run_cli(
                ["run", "status", run_id, "finished", "--reason", "All tasks and gates complete", "--json"],
                cwd=root,
            )
            self.assertEqual(code, 0, err)

            # 9. Verify evidence and evaluate with --write --require-pass
            code, verify_out, err = _run_cli(["evidence", "verify", "--run", run_id, "--json"], cwd=root)
            self.assertEqual(code, 0, err)
            verify_doc = json.loads(verify_out)
            self.assertTrue(verify_doc["ok"])
            self.assertEqual(verify_doc["record_count"], 5)

            code, eval_out, err = _run_cli(
                ["eval", "run", "--run", run_id, "--write", "--require-pass", "--json"],
                cwd=root,
            )
            self.assertEqual(code, 0, err)
            eval_doc = json.loads(eval_out)
            self.assertEqual(eval_doc["verdict"], "pass")
            self.assertEqual(eval_doc["evidence_set_digest"], verify_doc["evidence_set_digest"])

            # 10. Validate the entire project (0 errors; informational warnings without --strict exit 0, with --strict exit 1)
            code, val_out, err = _run_cli(["validate", "--json"], cwd=root)
            self.assertEqual(code, 0, f"validate failed: {val_out} {err}")
            val_doc = json.loads(val_out)
            self.assertTrue(val_doc["ok"])
            self.assertEqual(val_doc["summary"]["error"], 0)
            diag_codes = {d["code"] for d in val_doc["diagnostics"]}
            for expected_info in ("RAPID600", "RAPID800", "RAPID1000", "RAPID1100", "RAPID1200", "RAPID1220"):
                self.assertIn(expected_info, diag_codes)

            if val_doc["summary"]["warning"] > 0:
                code_strict, _, _ = _run_cli(["validate", "--strict", "--json"], cwd=root)
                self.assertEqual(code_strict, 1)

    def test_end_to_end_negative_unverified_run_blocks_require_pass_with_rapid1225(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _bootstrap_minimal_project(root)

            _run_cli(
                [
                    "spec",
                    "create",
                    "--id",
                    "unverified-feature",
                    "--title",
                    "Unverified Feature",
                    "--mode",
                    "feature",
                    "--objective",
                    "Test unverified gate detection",
                    "--problem",
                    "Declarations without evidence must not pass",
                    "--scope",
                    "src/booking.py",
                    "--acceptance",
                    "Tests pass",
                    "--task",
                    "Write code",
                    "--status",
                    "ready",
                    "--json",
                ],
                cwd=root,
            )

            _, run_out, _ = _run_cli(
                ["run", "create", "--spec", "unverified-feature", "--harness", "codex", "--risk", "medium", "--json"],
                cwd=root,
            )
            run_id = json.loads(run_out)["id"]

            # Acknowledge pre-gate, activate, mark task done, acknowledge post-gates, finish run — WITHOUT adding evidence
            _run_cli(["run", "gate", run_id, "gate.baseline", "acknowledged", "--reason", "claimed"], cwd=root)
            _run_cli(["run", "status", run_id, "active", "--reason", "active"], cwd=root)
            _run_cli(["run", "task", run_id, "T001", "in_progress", "--reason", "wip"], cwd=root)
            _run_cli(["run", "task", run_id, "T001", "done", "--reason", "claimed done"], cwd=root)
            for gate_id in ("gate.tests", "gate.final-verification"):
                _run_cli(["run", "gate", run_id, gate_id, "acknowledged", "--reason", "claimed"], cwd=root)
            _run_cli(["run", "status", run_id, "finished", "--reason", "finished without evidence"], cwd=root)

            # Informational eval exits 0 with verdict == unverified
            code_info, info_out, _ = _run_cli(["eval", "run", "--run", run_id, "--json"], cwd=root)
            self.assertEqual(code_info, 0)
            self.assertEqual(json.loads(info_out)["verdict"], "unverified")

            # Gate mode (--require-pass) exits non-zero (1) and emits RAPID1225 on stderr
            code_gate, gate_out, gate_err = _run_cli(
                ["eval", "run", "--run", run_id, "--require-pass", "--json"],
                cwd=root,
            )
            self.assertEqual(code_gate, 1)
            self.assertEqual(json.loads(gate_out)["verdict"], "unverified")
            self.assertIn("RAPID1225", gate_err)

    def test_end_to_end_cross_layer_tampering_defense_in_depth(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _bootstrap_minimal_project(root)

            _run_cli(
                [
                    "spec",
                    "create",
                    "--id",
                    "tamper-check",
                    "--title",
                    "Tamper Check",
                    "--mode",
                    "feature",
                    "--objective",
                    "Verify tamper detection across layers",
                    "--problem",
                    "Artifact tampering must be detected",
                    "--scope",
                    "src/booking.py",
                    "--acceptance",
                    "All layers verified",
                    "--task",
                    "Task 1",
                    "--status",
                    "ready",
                    "--json",
                ],
                cwd=root,
            )
            _, run_out, _ = _run_cli(
                ["run", "create", "--spec", "tamper-check", "--harness", "codex", "--json"],
                cwd=root,
            )
            run_id = json.loads(run_out)["id"]

            artifact_src = root / "proof.txt"
            artifact_src.write_text("original artifact content\n", encoding="utf-8")
            ev_input = root / "ev.json"
            ev_input.write_text(
                json.dumps(
                    {
                        "kind": "command_result",
                        "producer": "harness:codex",
                        "summary": "Baseline check",
                        "gate_ids": ["gate.baseline"],
                        "payload": {"label": "check", "exit_code": 0},
                        "artifacts": ["proof.txt"],
                    }
                ),
                encoding="utf-8",
            )
            code_ev, _, err_ev = _run_cli(
                ["evidence", "add", "--run", run_id, "--input", str(ev_input), "--json"],
                cwd=root,
            )
            self.assertEqual(code_ev, 0, err_ev)
            code_eval, _, err_eval = _run_cli(
                ["eval", "run", "--run", run_id, "--write", "--json"],
                cwd=root,
            )
            self.assertEqual(code_eval, 0, err_eval)

            # Layer 1: Tamper with copied EvidenceArtifact bytes -> RAPID1205
            copied_artifact = root / ".rapid-os" / "evidence" / run_id / "artifacts" / "E001" / "proof.txt"
            original_artifact_bytes = copied_artifact.read_bytes()
            copied_artifact.write_text("tampered artifact content!\n", encoding="utf-8")
            code1, out1, _ = _run_cli(["validate", "--json"], cwd=root)
            self.assertEqual(code1, 1)
            self.assertIn("RAPID1205", {d["code"] for d in json.loads(out1)["diagnostics"]})
            copied_artifact.write_bytes(original_artifact_bytes)

            # Layer 2: Tamper with RunEvidence record summary -> RAPID1202
            record_path = root / ".rapid-os" / "evidence" / run_id / "records" / "E001.json"
            original_record_text = record_path.read_text(encoding="utf-8")
            tampered_record = json.loads(original_record_text)
            tampered_record["summary"] = "Tampered summary"
            record_path.write_text(json.dumps(tampered_record, indent=2) + "\n", encoding="utf-8")
            code2, out2, _ = _run_cli(["validate", "--json"], cwd=root)
            self.assertEqual(code2, 1)
            self.assertIn("RAPID1202", {d["code"] for d in json.loads(out2)["diagnostics"]})
            record_path.write_text(original_record_text, encoding="utf-8")

            # Layer 3: Tamper with EvaluationReport assertions + verdict AND recompute report_digest -> caught by semantic replay RAPID1223
            report_path = root / ".rapid-os" / "evals" / run_id / "reports" / "0001.json"
            original_report_text = report_path.read_text(encoding="utf-8")
            valid_report = rapid_os.domain.evals.EvaluationReport.from_json(original_report_text)
            forged_assertions = tuple(
                rapid_os.domain.evals.EvalAssertion(
                    id=a.id,
                    category=a.category,
                    subject_id=a.subject_id,
                    required=a.required,
                    status=rapid_os.domain.evals.EvalAssertionStatus.PASS if a.required else a.status,
                    reason="Forged pass",
                    evidence_ids=a.evidence_ids,
                )
                for a in valid_report.assertions
            )
            forged_report = rapid_os.domain.evals.EvaluationReport(
                schema_version=valid_report.schema_version,
                run_id=valid_report.run_id,
                contract_digest=valid_report.contract_digest,
                state_revision=valid_report.state_revision,
                state_digest=valid_report.state_digest,
                evidence_set_digest=valid_report.evidence_set_digest,
                ruleset_version=valid_report.ruleset_version,
                ruleset_digest=valid_report.ruleset_digest,
                assertions=forged_assertions,
                verdict=rapid_os.domain.evals.EvaluationVerdict.PASS,
                extra_capability_ids=valid_report.extra_capability_ids,
            )
            report_path.write_text(forged_report.to_json(indent=2) + "\n", encoding="utf-8")
            code3, out3, _ = _run_cli(["validate", "--json"], cwd=root)
            self.assertEqual(code3, 1)
            self.assertIn("RAPID1223", {d["code"] for d in json.loads(out3)["diagnostics"]})
            report_path.write_text(original_report_text, encoding="utf-8")

            # Layer 4: Tamper with RunState status -> RAPID1012
            state_path = root / ".rapid-os" / "runs" / run_id / "states" / "0001.json"
            original_state_text = state_path.read_text(encoding="utf-8")
            tampered_state = json.loads(original_state_text)
            tampered_state["status"] = "finished"
            state_path.write_text(json.dumps(tampered_state, indent=2) + "\n", encoding="utf-8")
            code4, out4, _ = _run_cli(["validate", "--json"], cwd=root)
            self.assertEqual(code4, 1)
            self.assertIn("RAPID1012", {d["code"] for d in json.loads(out4)["diagnostics"]})
            state_path.write_text(original_state_text, encoding="utf-8")

    def test_cli_docs_and_product_truth_contract(self) -> None:
        parser = create_parser()
        subparsers_action = next(
            action for action in parser._actions if hasattr(action, "choices") and isinstance(action.choices, dict)
        )
        registered_commands = set(subparsers_action.choices.keys())
        expected_commands = {
            "init",
            "scan",
            "context",
            "spec",
            "policy",
            "run",
            "harness",
            "evidence",
            "eval",
            "validate",
            "doctor",
            "inspect-context",
            "guide",
            "skill",
            "mcp",
            "vision",
            "scope",
            "deploy",
            "refine",
            "prompt",
        }
        self.assertEqual(registered_commands, expected_commands)

        # Verify docs/cli.md documents every public command and has no ghost --root or rapid update
        cli_doc = (REPO_ROOT / "docs" / "cli.md").read_text(encoding="utf-8")
        for cmd in expected_commands:
            self.assertIn(f"rapid {cmd}", cli_doc, f"docs/cli.md is missing 'rapid {cmd}'")
        self.assertNotIn("--root", cli_doc)
        self.assertNotIn("rapid update", cli_doc)

        # Verify required v3.0.0 documentation files exist
        required_docs = [
            REPO_ROOT / "README.md",
            REPO_ROOT / "CHANGELOG.md",
            REPO_ROOT / "pyproject.toml",
            REPO_ROOT / "MANIFEST.in",
            REPO_ROOT / "docs" / "getting-started.md",
            REPO_ROOT / "docs" / "governance-loop.md",
            REPO_ROOT / "docs" / "cli.md",
            REPO_ROOT / "docs" / "architecture" / "rapid-os-v3.md",
            REPO_ROOT / "docs" / "architecture" / "rapid-os-v2.md",
            REPO_ROOT / "docs" / "release-v3.0.0.md",
            REPO_ROOT / "docs" / "release-checklist.md",
        ]
        for doc_path in required_docs:
            self.assertTrue(doc_path.is_file(), f"Missing required documentation/packaging file: {doc_path}")

        # Verify obsolete terms do not appear in docs or domain code
        forbidden_pattern = re.compile(
            r"\b(shared_allowed|isolated_recommended|recorded_at|evaluated_at|SUPPORTED_HARNESSES)\b"
        )
        for doc_path in required_docs:
            text = doc_path.read_text(encoding="utf-8")
            match = forbidden_pattern.search(text)
            self.assertIsNone(match, f"Forbidden obsolete term '{match.group(0) if match else ''}' found in {doc_path}")

    def test_guide_and_packaged_templates_resolution(self) -> None:
        code, guide_out, err = _run_cli(["guide"])
        self.assertEqual(code, 0, err)
        for step in ("1. scan", "2. spec", "3. context", "4. policy/run", "5. harness", "6. evidence", "7. eval", "8. validate"):
            self.assertIn(step, guide_out)

        # Verify resolve_paths locates templates even when script_dir is omitted and rapid_home has no templates
        with tempfile.TemporaryDirectory() as tmp:
            empty_home = Path(tmp) / "empty-home"
            empty_project = Path(tmp) / "empty-project"
            empty_home.mkdir()
            empty_project.mkdir()
            paths = resolve_paths(current_dir=empty_project, rapid_home=empty_home)
            self.assertTrue((paths.templates_dir / "stacks").is_dir())
            self.assertTrue((paths.templates_dir / "topologies").is_dir())


if __name__ == "__main__":
    unittest.main()
