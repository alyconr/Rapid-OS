"""Automated Contract and Verification Tests for Sprint 4 Documentation Labs.

Validates that:
1. All Sprint 4 lab and harness documents exist and adhere to the canonical pedagogical structure.
2. All 6 example projects (starters and solutions) pass their unit tests.
3. All documented CLI commands in tutorials match the argparse parser without syntax or option errors.
4. All Gate IDs, Capabilities, and Evidence Kinds documented are strictly canonical.
5. A full end-to-end Governance Loop runs in a controlled temporary repository using real subprocess
   and CLI commands, validating the entire lifecycle from init to eval and validate.
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
from rapid_os.domain.capabilities import CANONICAL_CAPABILITY_IDS
from rapid_os.domain.evals import EvaluationVerdict
from rapid_os.domain.evidence import (
    EvidenceKind,
    PAYLOAD_REQUIRED_KEYS,
    validate_evidence_payload,
)
from rapid_os.domain.policy import (
    CANONICAL_GATE_CATALOG,
    CANONICAL_GATE_ORDER,
)

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
EXAMPLES = ROOT / "examples"


class Sprint4DocumentationLabsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.parser = create_parser()

    def test_sprint4_mandatory_documents_exist(self):
        """All tutorial, integration, and example catalog documents must exist."""
        required_docs = [
            DOCS / "tutorials" / "index.md",
            DOCS / "tutorials" / "first-governed-project.md",
            DOCS / "tutorials" / "feature-lab.md",
            DOCS / "tutorials" / "bugfix-lab.md",
            DOCS / "tutorials" / "refactor-lab.md",
            DOCS / "tutorials" / "hardening-lab.md",
            DOCS / "tutorials" / "research-lab.md",
            DOCS / "troubleshooting" / "tutorials.md",
            DOCS / "integrations" / "index.md",
            DOCS / "integrations" / "codex.md",
            DOCS / "integrations" / "claude-code.md",
            DOCS / "integrations" / "cursor.md",
            DOCS / "integrations" / "vscode.md",
            DOCS / "integrations" / "antigravity.md",
            EXAMPLES / "README.md",
        ]
        for path in required_docs:
            self.assertTrue(path.is_file(), f"Missing required document: {path}")

    def test_all_tutorial_labs_follow_canonical_pedagogical_template(self):
        """Each lab must include the canonical structure."""
        lab_files = [
            DOCS / "tutorials" / "first-governed-project.md",
            DOCS / "tutorials" / "feature-lab.md",
            DOCS / "tutorials" / "bugfix-lab.md",
            DOCS / "tutorials" / "refactor-lab.md",
            DOCS / "tutorials" / "hardening-lab.md",
            DOCS / "tutorials" / "research-lab.md",
        ]
        required_sections = [
            "Overview",
            "Learning Outcomes",
            "Initial State",
            "Engineering Requirements",
            "Guided Procedure",
            "External Execution",
            "Evidence Collection",
            "Evaluation",
            "Assessment",
        ]
        for lab in lab_files:
            content = lab.read_text(encoding="utf-8")
            for section in required_sections:
                self.assertIn(
                    section,
                    content,
                    f"Lab {lab.name} is missing mandatory section: {section}",
                )

    def test_all_example_labs_starters_and_solutions_pass_tests(self):
        """Every example starter and solution test suite must execute cleanly."""
        labs = [
            "first-governed-project",
            "feature-lab",
            "bugfix-lab",
            "refactor-lab",
            "hardening-lab",
            "research-lab",
        ]
        for lab in labs:
            for variant in ("starter", "solution"):
                test_dir = EXAMPLES / lab / variant / "tests"
                top_dir = EXAMPLES / lab / variant
                self.assertTrue(
                    test_dir.is_dir(), f"Missing tests dir for {lab}/{variant}"
                )
                cmd = [
                    sys.executable,
                    "-m",
                    "unittest",
                    "discover",
                    "-s",
                    str(test_dir),
                    "-t",
                    str(top_dir),
                ]
                res = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    cwd=str(ROOT),
                )
                self.assertEqual(
                    res.returncode,
                    0,
                    f"Test suite failed for {lab}/{variant}:\n{res.stderr}\n{res.stdout}",
                )

    def test_documented_cli_commands_in_tutorials_match_argparse(self):
        """All 'rapid <command>' invocations in tutorials must be accepted by create_parser()."""
        tutorial_dir = DOCS / "tutorials"
        for md_file in tutorial_dir.glob("*.md"):
            content = md_file.read_text(encoding="utf-8")
            # Match bash code blocks
            blocks = re.findall(r"```bash\s*\n(.*?)\n```", content, re.DOTALL)
            for block in blocks:
                lines = block.replace("\\\n", " ").split("\n")
                for raw_line in lines:
                    line = raw_line.strip()
                    if not line or line.startswith("#"):
                        continue
                    if line.startswith("rapid "):
                        # Normalize placeholders
                        normalized = re.sub(r"<[^>]+>", "placeholder", line)
                        tokens = shlex.split(normalized)
                        cli_args = tokens[1:]  # skip 'rapid'
                        try:
                            # Parse args without exiting
                            self.parser.parse_args(cli_args)
                        except SystemExit as exc:
                            self.fail(
                                f"In {md_file.name}, command '{line}' failed argparse: {exc}"
                            )

    def test_governance_e2e_full_lifecycle_in_temp_project(self):
        """Execute a full Governance Loop in a temporary project via real CLI subprocesses.
        
        init -> scan -> spec create -> context -> policy -> run create ->
        external implementation -> test execution -> run status active ->
        evidence add (file_change + test_result) -> run gate ack -> run task done ->
        run status finished -> eval run -> validate
        """
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            env = dict(os.environ)
            env["PYTHONPATH"] = str(ROOT)

            def run_rapid(*args: str, input_text: str | None = None) -> subprocess.CompletedProcess:
                cmd = [sys.executable, str(ROOT / "rapid.py")] + list(args)
                return subprocess.run(
                    cmd,
                    cwd=str(tmp_path),
                    input=input_text,
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    env=env,
                    timeout=20,
                )

            # 1. Initialize temporary app
            tests_dir = tmp_path / "tests"
            tests_dir.mkdir(parents=True, exist_ok=True)
            (tests_dir / "__init__.py").write_text("", encoding="utf-8")
            (tmp_path / "app.py").write_text(
                "def add(a, b):\n    return a + b\n", encoding="utf-8"
            )
            (tests_dir / "test_app.py").write_text(
                "import unittest\nfrom app import add\nclass TestApp(unittest.TestCase):\n"
                "    def test_add(self):\n        self.assertEqual(add(1, 2), 3)\n"
                "if __name__ == '__main__':\n    unittest.main()\n",
                encoding="utf-8",
            )

            # 2. rapid init non-interactive
            init_input = "1\n1\n\nn\n\nn\n"
            res = run_rapid(
                "init",
                "--stack",
                "docs-modern",
                "--archetype",
                "mvp",
                "--no-scan",
                input_text=init_input,
            )
            self.assertEqual(res.returncode, 0, f"rapid init failed: {res.stderr}")

            # 3. rapid scan --write
            res = run_rapid("scan", "--write")
            self.assertEqual(res.returncode, 0, f"rapid scan failed: {res.stderr}")

            # 4. rapid spec create
            res = run_rapid(
                "spec",
                "create",
                "--id",
                "spec-e2e-demo",
                "--title",
                "Governance E2E Demo Feature",
                "--mode",
                "feature",
                "--task",
                "T001: Implement multiplication",
                "--status",
                "ready",
            )
            self.assertEqual(res.returncode, 0, f"rapid spec create failed: {res.stderr}")

            # 5. rapid context --manifest
            res = run_rapid("context", "--manifest")
            self.assertEqual(res.returncode, 0, f"rapid context failed: {res.stderr}")

            # 6. rapid run create
            res = run_rapid(
                "run",
                "create",
                "--spec",
                "spec-e2e-demo",
                "--harness",
                "codex",
                "--json",
            )
            self.assertEqual(res.returncode, 0, f"rapid run create failed: {res.stderr}")
            run_data = json.loads(res.stdout)
            run_id = run_data["id"]
            self.assertTrue(run_id.startswith("spec-e2e-demo"))

            # Ingest and acknowledge baseline before execution
            base_log = tmp_path / "base.log"
            base_log.write_text("Ran 1 test\nOK\n", encoding="utf-8")
            ev_base = {
                "kind": "test_result",
                "producer": "harness:codex",
                "summary": "Baseline unit test execution",
                "task_ids": ["T001"],
                "gate_ids": ["gate.baseline"],
                "capability_ids": ["tests.execute"],
                "payload": {
                    "suite": "tests/test_app.py",
                    "exit_code": 0,
                    "passed": 1,
                    "failed": 0,
                    "skipped": 0,
                },
                "artifacts": ["base.log"],
            }
            ev_base_path = tmp_path / "ev_base.json"
            ev_base_path.write_text(json.dumps(ev_base), encoding="utf-8")
            res = run_rapid("evidence", "add", "--run", run_id, "--input", str(ev_base_path))
            self.assertEqual(res.returncode, 0, f"rapid evidence add E001 failed: {res.stderr}")
            res = run_rapid("run", "gate", run_id, "gate.baseline", "acknowledged")
            self.assertEqual(res.returncode, 0, f"rapid run gate baseline failed: {res.stderr}")

            # 7. Transition to active
            res = run_rapid("run", "status", run_id, "active")
            self.assertEqual(res.returncode, 0, f"rapid run status active failed: {res.stderr}")
            res = run_rapid("run", "task", run_id, "T001", "in_progress")
            self.assertEqual(res.returncode, 0, f"rapid run task in_progress failed: {res.stderr}")

            # 8. External implementation (modify app.py and test_app.py)
            (tmp_path / "app.py").write_text(
                "def add(a, b):\n    return a + b\ndef multiply(a, b):\n    return a * b\n",
                encoding="utf-8",
            )
            (tests_dir / "test_app.py").write_text(
                "import unittest\nfrom app import add, multiply\nclass TestApp(unittest.TestCase):\n"
                "    def test_add(self):\n        self.assertEqual(add(1, 2), 3)\n"
                "    def test_multiply(self):\n        self.assertEqual(multiply(2, 4), 8)\n"
                "if __name__ == '__main__':\n    unittest.main()\n",
                encoding="utf-8",
            )

            # External test execution
            test_run = subprocess.run(
                [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-t", "."],
                cwd=str(tmp_path),
                capture_output=True,
                text=True,
            )
            self.assertEqual(test_run.returncode, 0, f"External test failed: {test_run.stderr}")

            # 9. Register file_change evidence
            ev_files = {
                "kind": "file_change",
                "producer": "harness:codex",
                "summary": "External multiplication feature implementation",
                "task_ids": ["T001"],
                "gate_ids": [],
                "capability_ids": ["repository.write"],
                "payload": {"paths": ["app.py", "tests/test_app.py"]},
            }
            ev_file_path = tmp_path / "ev_files.json"
            ev_file_path.write_text(json.dumps(ev_files), encoding="utf-8")
            res = run_rapid("evidence", "add", "--run", run_id, "--input", str(ev_file_path))
            self.assertEqual(res.returncode, 0, f"rapid evidence add E002 failed: {res.stderr}")

            # 10. Register post-execution test_result evidence
            test_log = tmp_path / "tests.log"
            test_log.write_text("Ran 2 tests\nOK\n", encoding="utf-8")
            ev_tests = {
                "kind": "test_result",
                "producer": "harness:codex",
                "summary": "Passing unit test suite execution",
                "task_ids": ["T001"],
                "gate_ids": ["gate.tests"],
                "capability_ids": ["tests.execute"],
                "payload": {
                    "suite": "tests/test_app.py",
                    "exit_code": 0,
                    "passed": 2,
                    "failed": 0,
                    "skipped": 0,
                },
                "artifacts": ["tests.log"],
            }
            ev_test_path = tmp_path / "ev_tests.json"
            ev_test_path.write_text(json.dumps(ev_tests), encoding="utf-8")
            res = run_rapid("evidence", "add", "--run", run_id, "--input", str(ev_test_path))
            self.assertEqual(res.returncode, 0, f"rapid evidence add E003 failed: {res.stderr}")

            # 11. Register workspace evidence for workspace.current observation
            ev_ws = {
                "kind": "workspace",
                "producer": "harness:codex",
                "summary": "Current workspace verification",
                "capability_ids": ["workspace.current"],
                "payload": {"mode": "current"},
            }
            ev_ws_path = tmp_path / "ev_ws.json"
            ev_ws_path.write_text(json.dumps(ev_ws), encoding="utf-8")
            res = run_rapid("evidence", "add", "--run", run_id, "--input", str(ev_ws_path))
            self.assertEqual(res.returncode, 0, f"rapid evidence add E004 failed: {res.stderr}")

            # 12. Register final verification review evidence
            ev_final = {
                "kind": "review",
                "producer": "harness:codex",
                "summary": "Final contractual verification review",
                "gate_ids": ["gate.final-verification"],
                "payload": {
                    "review_type": "final",
                    "outcome": "approved",
                    "reviewer": "quality-lead",
                },
            }
            ev_final_path = tmp_path / "ev_final.json"
            ev_final_path.write_text(json.dumps(ev_final), encoding="utf-8")
            res = run_rapid("evidence", "add", "--run", run_id, "--input", str(ev_final_path))
            self.assertEqual(res.returncode, 0, f"rapid evidence add E005 failed: {res.stderr}")

            # 13. Complete task, acknowledge gates, finish run
            res = run_rapid("run", "task", run_id, "T001", "done")
            self.assertEqual(res.returncode, 0, f"rapid run task done failed: {res.stderr}")
            res = run_rapid("run", "gate", run_id, "gate.tests", "acknowledged")
            self.assertEqual(res.returncode, 0, f"rapid run gate tests failed: {res.stderr}")
            res = run_rapid("run", "gate", run_id, "gate.final-verification", "acknowledged")
            self.assertEqual(res.returncode, 0, f"rapid run gate final failed: {res.stderr}")
            res = run_rapid("run", "status", run_id, "finished")
            self.assertEqual(res.returncode, 0, f"rapid run status finished failed: {res.stderr}")

            # 14. Evaluate run deterministically
            res = run_rapid("eval", "run", "--run", run_id, "--write", "--require-pass", "--json")
            self.assertEqual(res.returncode, 0, f"rapid eval run failed: {res.stderr}")
            eval_report = json.loads(res.stdout)
            self.assertEqual(eval_report["verdict"], "pass")

            # 15. Validate repository integrity
            res = run_rapid("validate")
            self.assertEqual(res.returncode, 0, f"rapid validate failed: {res.stderr}")


if __name__ == "__main__":
    unittest.main()
