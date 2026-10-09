"""Semantic and functional Product Truth contract tests for Sprint 3 remediation (Issue #40).

Guarantees that:
1. All documented CLI commands match real argparse subcommand options.
2. All JSON snippets in cookbooks validate strictly against real domain models.
3. All 9 EvidenceKind types can be ingested via the real CLI in an E2E project.
4. Negative tests assert rejection of invalid flags, unknown fields, and invalid statuses.
"""

from pathlib import Path
import json
import os
import re
import shlex
import subprocess
import sys
import tempfile
import unittest

from rapid_os.cli.main import create_parser
from rapid_os.domain.capabilities import (
    CANONICAL_CAPABILITY_IDS,
    CapabilitySupport,
    CapabilitySupportStatus,
    HarnessProfile,
    InvalidCapabilityIdError,
    InvalidCapabilitySupportError,
)
from rapid_os.domain.evidence import (
    EvidenceKind,
    InvalidEvidencePayloadError,
    PAYLOAD_REQUIRED_KEYS,
    validate_evidence_payload,
)


ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"


class Sprint3RemediationContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.parser = create_parser()

    def test_documented_evidence_cli_snippets_are_valid_in_argparse(self):
        """All 'rapid evidence' command invocations in documentation must be accepted by argparse."""
        evidence_doc = (DOCS / "cookbooks" / "evidence-engine.md").read_text(encoding="utf-8")
        
        # Extract all bash blocks
        bash_blocks = re.findall(r"```bash\s*\n(.*?)\n```", evidence_doc, re.DOTALL)
        for block in bash_blocks:
            # Handle multi-line commands with backslashes
            normalized_block = block.replace("\\\n", " ")
            for raw_line in normalized_block.split("\n"):
                line = raw_line.strip()
                if line.startswith("#") or not line:
                    continue
                if line.startswith("rapid evidence"):
                    # Sanitize placeholder syntax like <run-id> -> run-001 and [--json] -> --json
                    sanitized = re.sub(r"<[^>]+>", "sample-val", line)
                    sanitized = sanitized.replace("[--json]", "--json").replace("[", "").replace("]", "")
                    parts = shlex.split(sanitized)
                    # Remove the initial 'rapid'
                    cli_args = parts[1:]
                    with self.subTest(command=line):
                        try:
                            parsed = self.parser.parse_args(cli_args)
                            self.assertEqual(parsed.command, "evidence")
                        except SystemExit as exc:
                            self.fail(f"CLI parser rejected documented command '{line}' (sanitized: '{sanitized}'): exit code {exc.code}")

    def test_no_forbidden_evidence_add_flags_in_docs(self):
        """Ensure forbidden flags --kind, --producer, --summary are nowhere in 'rapid evidence add' snippets."""
        for md_path in DOCS.rglob("*.md"):
            content = md_path.read_text(encoding="utf-8")
            matches = re.finditer(r"rapid evidence add\s+([^\n`]+)", content)
            for m in matches:
                cmd_line = m.group(0)
                with self.subTest(file=md_path.name, command=cmd_line):
                    self.assertNotIn("--kind", cmd_line, f"Forbidden flag --kind in {md_path.name}: {cmd_line}")
                    self.assertNotIn("--producer", cmd_line, f"Forbidden flag --producer in {md_path.name}: {cmd_line}")
                    self.assertNotIn("--summary", cmd_line, f"Forbidden flag --summary in {md_path.name}: {cmd_line}")

    def test_all_nine_evidence_cookbooks_json_blocks_are_valid(self):
        """All authoring JSON snippets in evidence-engine.md validate against domain payload rules."""
        doc_text = (DOCS / "cookbooks" / "evidence-engine.md").read_text(encoding="utf-8")
        json_blocks = re.findall(r"```json\s*\n(.*?)\n```", doc_text, re.DOTALL)
        
        authoring_blocks_found = 0
        kinds_tested = set()
        for block in json_blocks:
            try:
                data = json.loads(block)
            except json.JSONDecodeError:
                continue
            
            if isinstance(data, dict) and "kind" in data and "payload" in data:
                authoring_blocks_found += 1
                kind_str = data["kind"]
                payload = data["payload"]
                kinds_tested.add(kind_str)
                with self.subTest(kind=kind_str):
                    validated = validate_evidence_payload(kind_str, payload)
                    self.assertIsInstance(validated, dict)
                    self.assertEqual(validated.keys(), PAYLOAD_REQUIRED_KEYS[EvidenceKind.coerce(kind_str)])

        self.assertGreaterEqual(authoring_blocks_found, 9, "Expected at least 9 authoring JSON blocks in evidence cookbook")
        self.assertEqual(len(kinds_tested), 9, f"All 9 EvidenceKinds must be covered, got: {kinds_tested}")

    def test_harness_profiles_cookbook_json_validates_strictly(self):
        """The HarnessProfile JSON example in harness-profiles.md validates via HarnessProfile."""
        doc_text = (DOCS / "cookbooks" / "harness-profiles.md").read_text(encoding="utf-8")
        json_blocks = re.findall(r"```json\s*\n(.*?)\n```", doc_text, re.DOTALL)
        
        profiles_found = 0
        for block in json_blocks:
            try:
                data = json.loads(block)
            except json.JSONDecodeError:
                continue
            
            if isinstance(data, dict) and "schema_version" in data and "capabilities" in data and isinstance(data["capabilities"], list):
                profiles_found += 1
                profile = HarnessProfile(
                    schema_version=data["schema_version"],
                    id=data["id"],
                    capabilities=tuple(
                        CapabilitySupport(
                            capability_id=c["capability_id"],
                            status=CapabilitySupportStatus.coerce(c["status"]),
                            reason=c["reason"],
                        )
                        for c in data["capabilities"]
                    ),
                )
                self.assertEqual(profile.schema_version, 1)
                self.assertEqual(profile.id, data["id"])
                for cap in profile.capabilities:
                    self.assertIn(cap.capability_id, CANONICAL_CAPABILITY_IDS)
                    self.assertIn(cap.status, (CapabilitySupportStatus.SUPPORTED, CapabilitySupportStatus.UNSUPPORTED, CapabilitySupportStatus.UNKNOWN))

        self.assertGreaterEqual(profiles_found, 1, "Expected at least 1 valid HarnessProfile JSON block in harness cookbook")

    def test_no_conditional_status_in_documentation(self):
        """Strictly forbid 'conditional' being documented as a capability support status."""
        for md_path in (DOCS / "cookbooks").glob("*.md"):
            content = md_path.read_text(encoding="utf-8").lower()
            self.assertNotIn('"conditional"', content, f"Forbidden status 'conditional' found in {md_path.name}")

    def test_negative_payload_unknown_fields_rejected(self):
        """Domain validator strictly rejects evidence payload with unexpected fields."""
        with self.assertRaises(InvalidEvidencePayloadError):
            validate_evidence_payload(
                EvidenceKind.COMMAND_RESULT,
                {"label": "test", "exit_code": 0, "extra_unexpected_field": "bad"},
            )

        with self.assertRaises(InvalidEvidencePayloadError):
            validate_evidence_payload(
                EvidenceKind.TEST_RESULT,
                {"suite": "test", "exit_code": 0, "passed": 1, "failed": 0, "skipped": 0, "duration": 1.5},
            )

    def test_negative_capability_support_conditional_rejected(self):
        """CapabilitySupport rejects 'conditional' status."""
        with self.assertRaises(InvalidCapabilitySupportError):
            CapabilitySupport(
                capability_id="shell.execute",
                status="conditional",  # type: ignore[arg-type]
                reason="Only with prompt",
            )

    def test_negative_unknown_capability_id_rejected(self):
        """CapabilitySupport rejects non-canonical IDs like terminal.execute."""
        with self.assertRaises(InvalidCapabilityIdError):
            CapabilitySupport(
                capability_id="terminal.execute",
                status=CapabilitySupportStatus.SUPPORTED,
                reason="terminal execution",
            )

    def test_negative_cli_evidence_add_rejects_forbidden_flags(self):
        """Argparse must exit with error when --kind is supplied to 'rapid evidence add'."""
        with self.assertRaises(SystemExit):
            self.parser.parse_args(["evidence", "add", "--run", "r1", "--kind", "test_result", "--input", "file.json"])

    def test_end_to_end_evidence_ingestion_all_nine_kinds(self):
        """Functional E2E test verifying real CLI ingests all 9 EvidenceKind inputs cleanly."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            rapid_cli = [sys.executable, str(ROOT / "rapid.py")]
            env = os.environ.copy()
            env["PYTHONUTF8"] = "1"
            env["PYTHONIOENCODING"] = "utf-8"

            # 1. Prepopulate a small app file
            (tmp_path / "app.py").write_text("def hello(): return 'world'\n", encoding="utf-8")

            # 2. Init project non-interactive
            init_input = "1\n1\n\nn\n\nn\n"
            res = subprocess.run(
                rapid_cli + ["init", "--stack", "docs-modern", "--archetype", "mvp", "--no-scan"],
                cwd=tmpdir,
                input=init_input,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                env=env,
                timeout=15,
            )
            self.assertEqual(res.returncode, 0, f"init failed: {res.stderr}")

            # 3. Scan --write
            res = subprocess.run(
                rapid_cli + ["scan", "--write"],
                cwd=tmpdir,
                stdin=subprocess.DEVNULL,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                env=env,
                timeout=15,
            )
            self.assertEqual(res.returncode, 0, f"scan failed: {res.stderr}")

            # 4. Create Spec
            res = subprocess.run(
                rapid_cli + [
                    "spec", "create",
                    "--title", "Audit Feature",
                    "--mode", "feature",
                    "--objective", "Verify all evidence kinds",
                    "--problem", "Need empirical evidence for 9 kinds",
                    "--scope", "All domain modules",
                    "--acceptance", "All 9 evidence records ingested",
                    "--task", "Task 1",
                    "--status", "ready",
                ],
                cwd=tmpdir,
                stdin=subprocess.DEVNULL,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                env=env,
                timeout=15,
            )
            self.assertEqual(res.returncode, 0, f"spec create failed: {res.stderr}")

            # 5. Create Run
            res = subprocess.run(
                rapid_cli + [
                    "run", "create",
                    "--spec", "audit-feature",
                    "--harness", "codex",
                    "--classification", "bounded",
                    "--risk", "medium",
                ],
                cwd=tmpdir,
                stdin=subprocess.DEVNULL,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                env=env,
                timeout=15,
            )
            self.assertEqual(res.returncode, 0, f"run create failed: {res.stderr}")
            run_id = "audit-feature-r1-run-001"

            # Prepare artifact dummy file
            sample_artifact = tmp_path / "sample_report.txt"
            sample_artifact.write_text("Integrity report contents", encoding="utf-8")

            # 6. Define authoring documents for all 9 kinds
            evidence_inputs = [
                # 1. command_result
                {
                    "kind": "command_result",
                    "producer": "pytest",
                    "summary": "Executed linting checks",
                    "capability_ids": ["shell.execute"],
                    "payload": {"label": "ruff check", "exit_code": 0},
                },
                # 2. test_result
                {
                    "kind": "test_result",
                    "producer": "pytest",
                    "summary": "Executed test suite",
                    "gate_ids": ["gate.tests"],
                    "capability_ids": ["tests.execute"],
                    "payload": {
                        "suite": "unit-tests",
                        "exit_code": 0,
                        "passed": 10,
                        "failed": 0,
                        "skipped": 0,
                    },
                },
                # 3. file_change
                {
                    "kind": "file_change",
                    "producer": "git-cli",
                    "summary": "Created service module",
                    "capability_ids": ["repository.write"],
                    "payload": {"paths": ["src/service.py"]},
                },
                # 4. git_result
                {
                    "kind": "git_result",
                    "producer": "git-cli",
                    "summary": "Inspected status",
                    "capability_ids": ["git.inspect"],
                    "payload": {"operation": "inspect"},
                },
                # 5. workspace
                {
                    "kind": "workspace",
                    "producer": "system",
                    "summary": "Workspace checked",
                    "capability_ids": ["workspace.current"],
                    "payload": {"mode": "current"},
                },
                # 6. review
                {
                    "kind": "review",
                    "producer": "reviewer",
                    "summary": "Peer review approved",
                    "payload": {
                        "review_type": "peer",
                        "outcome": "approved",
                        "reviewer": "lead-dev",
                    },
                },
                # 7. tool_invocation
                {
                    "kind": "tool_invocation",
                    "producer": "tool-runner",
                    "summary": "Mypy typecheck",
                    "payload": {"tool_id": "mypy", "outcome": "success"},
                },
                # 8. delegation
                {
                    "kind": "delegation",
                    "producer": "orchestrator",
                    "summary": "Delegated subtask",
                    "capability_ids": ["subagents.delegate"],
                    "payload": {"target": "subagent-worker", "outcome": "success"},
                },
                # 9. artifact
                {
                    "kind": "artifact",
                    "producer": "reporter",
                    "summary": "Attached sample report",
                    "artifacts": ["sample_report.txt"],
                    "payload": {"label": "sample-report"},
                },
            ]

            for idx, ev_doc in enumerate(evidence_inputs, start=1):
                input_file = tmp_path / f"ev_input_{idx}.json"
                input_file.write_text(json.dumps(ev_doc, indent=2), encoding="utf-8")

                res = subprocess.run(
                    rapid_cli + [
                        "evidence", "add",
                        "--run", run_id,
                        "--input", str(input_file),
                    ],
                    cwd=tmpdir,
                    stdin=subprocess.DEVNULL,
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    env=env,
                    timeout=15,
                )
                self.assertEqual(
                    res.returncode,
                    0,
                    f"rapid evidence add failed for kind '{ev_doc['kind']}': {res.stderr}",
                )

            # 7. Verify evidence records E001..E009 exist on disk
            records_dir = tmp_path / ".rapid-os" / "evidence" / run_id / "records"
            for i in range(1, 10):
                ev_id = f"E{i:03d}"
                self.assertTrue((records_dir / f"{ev_id}.json").is_file(), f"Missing record {ev_id}.json")

            # 8. Verify with real CLI
            res = subprocess.run(
                rapid_cli + ["evidence", "verify", "--run", run_id],
                cwd=tmpdir,
                stdin=subprocess.DEVNULL,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                env=env,
                timeout=15,
            )
            self.assertEqual(res.returncode, 0, f"rapid evidence verify failed: {res.stderr}")
            self.assertIn("9 record(s)", res.stdout)


if __name__ == "__main__":
    unittest.main()
