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
        """All authoring JSON snippets in evidence-engine.md validate against domain payload rules.
        
        Strictness: No silent try/except json.JSONDecodeError pass-through. Every ```json
        codeblock in evidence-engine.md MUST be valid JSON, avoiding unparseable or illustrative
        pseudocode marked as json.
        """
        doc_text = (DOCS / "cookbooks" / "evidence-engine.md").read_text(encoding="utf-8")
        json_blocks = re.findall(r"```json\s*\n(.*?)\n```", doc_text, re.DOTALL)
        
        self.assertEqual(len(json_blocks), 9, f"Expected exactly 9 valid JSON blocks in evidence cookbook, got {len(json_blocks)}")
        
        kinds_tested = set()
        for idx, block in enumerate(json_blocks, start=1):
            # Strict parse: will raise JSONDecodeError if invalid JSON is presented
            data = json.loads(block)
            self.assertIsInstance(data, dict, f"Block {idx} must be a JSON object")
            self.assertIn("kind", data, f"Block {idx} missing 'kind'")
            self.assertIn("payload", data, f"Block {idx} missing 'payload'")
            
            kind_str = data["kind"]
            payload = data["payload"]
            kinds_tested.add(kind_str)
            with self.subTest(kind=kind_str):
                validated = validate_evidence_payload(kind_str, payload)
                self.assertIsInstance(validated, dict)
                self.assertEqual(validated.keys(), PAYLOAD_REQUIRED_KEYS[EvidenceKind.coerce(kind_str)])

        self.assertEqual(len(kinds_tested), 9, f"All 9 EvidenceKinds must be covered, got: {kinds_tested}")

    def test_harness_profiles_cookbook_json_validates_strictly(self):
        """The HarnessProfile JSON example in harness-profiles.md validates via HarnessProfile.
        
        Strictness: Every ```json block in harness-profiles.md must parse as valid JSON.
        """
        doc_text = (DOCS / "cookbooks" / "harness-profiles.md").read_text(encoding="utf-8")
        json_blocks = re.findall(r"```json\s*\n(.*?)\n```", doc_text, re.DOTALL)
        
        self.assertGreaterEqual(len(json_blocks), 1, "Expected at least 1 JSON block in harness cookbook")
        
        for idx, block in enumerate(json_blocks, start=1):
            data = json.loads(block)
            self.assertIsInstance(data, dict, f"Block {idx} must be a JSON object")
            self.assertEqual(data.get("schema_version"), 1)
            self.assertIn("id", data)
            self.assertIn("capabilities", data)
            self.assertIsInstance(data["capabilities"], list)
            
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

    def test_workspace_isolation_fails_with_current_mode(self):
        """Semantic verification: mode: current evidence must NOT satisfy gate.workspace-isolation.
        
        rule.gate.workspace_isolation.v1 explicitly requires ACKNOWLEDGED disposition
        plus WORKSPACE evidence with mode == 'isolated'. mode == 'current' produces FAIL.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            rapid_cli = [sys.executable, str(ROOT / "rapid.py")]
            env = os.environ.copy()
            env["PYTHONUTF8"] = "1"
            env["PYTHONIOENCODING"] = "utf-8"

            (tmp_path / "app.py").write_text("def hello(): return 'world'\n", encoding="utf-8")
            init_input = "1\n1\n\nn\n\nn\n"
            subprocess.run(
                rapid_cli + ["init", "--stack", "docs-modern", "--archetype", "mvp", "--no-scan"],
                cwd=tmpdir,
                input=init_input,
                capture_output=True,
                text=True,
                encoding="utf-8",
                env=env,
                check=True,
            )
            subprocess.run(
                rapid_cli + ["scan", "--write"],
                cwd=tmpdir,
                capture_output=True,
                text=True,
                encoding="utf-8",
                env=env,
                check=True,
            )
            # Create high risk spec which requires gate.workspace-isolation
            res = subprocess.run(
                rapid_cli + [
                    "spec", "create",
                    "--title", "High Risk Spec",
                    "--mode", "feature",
                    "--objective", "Verify workspace isolation",
                    "--problem", "Security isolation requirement",
                    "--scope", "src/",
                    "--acceptance", "Passed",
                    "--task", "Task 1",
                    "--tag", "architecture",
                    "--status", "ready",
                ],
                cwd=tmpdir,
                capture_output=True,
                text=True,
                encoding="utf-8",
                env=env,
            )
            self.assertEqual(res.returncode, 0, f"spec create failed: {res.stderr}")

            res = subprocess.run(
                rapid_cli + [
                    "run", "create",
                    "--spec", "high-risk-spec",
                    "--harness", "codex",
                    "--classification", "architectural",
                    "--risk", "high",
                ],
                cwd=tmpdir,
                capture_output=True,
                text=True,
                encoding="utf-8",
                env=env,
            )
            self.assertEqual(res.returncode, 0, f"run create failed: {res.stderr}")
            run_id = "high-risk-spec-r1-run-001"

            # Ingest evidence with mode: current linked to gate.workspace-isolation
            bad_ws_ev = {
                "kind": "workspace",
                "producer": "workspace-manager",
                "summary": "Workspace checked in current mode",
                "gate_ids": ["gate.workspace-isolation"],
                "capability_ids": ["workspace.current"],
                "payload": {"mode": "current"},
            }
            ev_file = tmp_path / "bad_ws.json"
            ev_file.write_text(json.dumps(bad_ws_ev), encoding="utf-8")
            subprocess.run(
                rapid_cli + ["evidence", "add", "--run", run_id, "--input", str(ev_file)],
                cwd=tmpdir,
                capture_output=True,
                text=True,
                encoding="utf-8",
                env=env,
                check=True,
            )

            # Acknowledge PRE_EXECUTION gates before transitioning to active
            subprocess.run(
                rapid_cli + ["run", "gate", run_id, "gate.workspace-isolation", "acknowledged", "--reason", "Acknowledged with current mode evidence"],
                cwd=tmpdir,
                capture_output=True,
                text=True,
                encoding="utf-8",
                env=env,
                check=True,
            )
            subprocess.run(
                rapid_cli + ["run", "gate", run_id, "gate.baseline", "acknowledged", "--reason", "Baseline verified for test"],
                cwd=tmpdir,
                capture_output=True,
                text=True,
                encoding="utf-8",
                env=env,
                check=True,
            )

            # Transition to active
            subprocess.run(
                rapid_cli + ["run", "status", run_id, "active", "--reason", "Testing"],
                cwd=tmpdir,
                capture_output=True,
                text=True,
                encoding="utf-8",
                env=env,
                check=True,
            )

            # Evaluate run while active (evaluating gates)
            eval_res = subprocess.run(
                rapid_cli + ["eval", "run", "--run", run_id, "--json"],
                cwd=tmpdir,
                capture_output=True,
                text=True,
                encoding="utf-8",
                env=env,
            )
            self.assertEqual(eval_res.returncode, 0, f"eval run failed: {eval_res.stderr}")
            eval_data = json.loads(eval_res.stdout)
            
            # Find the assertion for gate.workspace-isolation
            ws_assertion = next(
                (a for a in eval_data["assertions"] if a["id"] == "gate.gate.workspace-isolation.evidence"),
                None,
            )
            self.assertIsNotNone(ws_assertion, "Missing assertion for gate.workspace-isolation")
            self.assertEqual(
                ws_assertion["status"],
                "fail",
                f"mode: current MUST produce fail for gate.workspace-isolation, got: {ws_assertion['status']}",
            )
            self.assertEqual(eval_data["verdict"], "fail")

    def test_end_to_end_evidence_ingestion_all_nine_kinds(self):
        """Functional E2E test verifying real CLI ingests all 9 EvidenceKind inputs cleanly.
        
        Direct Connection: The fixtures ingested are extracted directly from the 9 ```json
        codeblocks in docs/cookbooks/evidence-engine.md, guaranteeing zero divergence between
        documentation and executable verification.
        """
        # Extract the 9 authoring documents directly from docs
        doc_text = (DOCS / "cookbooks" / "evidence-engine.md").read_text(encoding="utf-8")
        docs_json_blocks = re.findall(r"```json\s*\n(.*?)\n```", doc_text, re.DOTALL)
        self.assertEqual(len(docs_json_blocks), 9, "Expected exactly 9 json blocks in evidence-engine.md")
        
        extracted_evidence_docs = [json.loads(b) for b in docs_json_blocks]

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

            # 5. Create Run with high risk to include all gates referenced by docs (gate.tests, gate.review, gate.workspace-isolation)
            res = subprocess.run(
                rapid_cli + [
                    "run", "create",
                    "--spec", "audit-feature",
                    "--harness", "codex",
                    "--classification", "bounded",
                    "--risk", "high",
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

            # 6. For artifact kinds, ensure referenced files exist in tmpdir
            for ev_doc in extracted_evidence_docs:
                for art_path in ev_doc.get("artifacts", []):
                    full_art_path = tmp_path / art_path
                    full_art_path.parent.mkdir(parents=True, exist_ok=True)
                    full_art_path.write_text("Dummy artifact content", encoding="utf-8")

            # 7. Ingest all 9 extracted documents via real CLI
            for idx, ev_doc in enumerate(extracted_evidence_docs, start=1):
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
                    f"rapid evidence add failed for documented kind '{ev_doc['kind']}': {res.stderr}",
                )

            # 8. Verify evidence records E001..E009 exist on disk
            records_dir = tmp_path / ".rapid-os" / "evidence" / run_id / "records"
            for i in range(1, 10):
                ev_id = f"E{i:03d}"
                self.assertTrue((records_dir / f"{ev_id}.json").is_file(), f"Missing record {ev_id}.json")

            # 9. Verify with real CLI
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
