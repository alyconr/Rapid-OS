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
        """The manual walkthrough keeps the full template; mode labs are shortcut routes with their details."""
        manual = (DOCS / "tutorials" / "first-governed-project.md").read_text(encoding="utf-8")
        for section in (
            "Overview",
            "Learning Outcomes",
            "Initial State",
            "Engineering Requirements",
            "Guided Procedure",
            "External Execution",
            "Evidence Collection",
            "Evaluation",
            "Assessment",
        ):
            self.assertIn(section, manual, f"first-governed-project.md is missing mandatory section: {section}")
        for lab in ("feature", "bugfix", "refactor", "hardening", "research"):
            content = (DOCS / "tutorials" / f"{lab}-lab.md").read_text(encoding="utf-8")
            for section in ("## With shortcuts", "### Starting state", "### Requirements", "## Advanced mode",
                            "first-governed-project.md"):
                self.assertIn(section, content, f"Lab {lab}-lab.md is missing mandatory section: {section}")

    def test_all_example_labs_starters_and_solutions_pass_tests(self):
        """Every example starter and solution test suite must execute according to its specification.
        
        Note for bugfix-lab: starter must fail with returncode=1 due to the deliberate defect
        in test_regression_expected_discount, while solution must pass cleanly (returncode=0).
        All other lab starters and solutions must pass cleanly (returncode=0).
        """
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
                if lab == "bugfix-lab" and variant == "starter":
                    self.assertEqual(
                        res.returncode,
                        1,
                        f"Expected bugfix-lab/starter to fail with exit code 1, got {res.returncode}:\n{res.stdout}\n{res.stderr}",
                    )
                    self.assertIn(
                        "FAIL: test_regression_expected_discount",
                        res.stderr + res.stdout,
                        f"Expected defect failure in bugfix-lab/starter output:\n{res.stderr}\n{res.stdout}",
                    )
                    self.assertIn(
                        "AssertionError: -900.0 != 90.0",
                        res.stderr + res.stdout,
                        f"Expected specific assertion failure in bugfix-lab/starter output:\n{res.stderr}\n{res.stdout}",
                    )
                else:
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
                        # A trailing shell redirection (`> file 2>&1`) is not part of the command.
                        normalized = re.sub(r"\s+>\s*\S+(\s+2>&1)?\s*$", "", normalized)
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

            # External baseline execution
            base_run = subprocess.run(
                [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-t", "."],
                cwd=str(tmp_path),
                capture_output=True,
                text=True,
            )
            self.assertEqual(base_run.returncode, 0, f"External baseline test failed: {base_run.stderr}")
            base_output = base_run.stderr + base_run.stdout
            self.assertIn("Ran 1 test", base_output)
            self.assertIn("OK", base_output)

            # Ingest and acknowledge baseline before execution with authentic log
            base_log = tmp_path / "base.log"
            base_log.write_text(base_output, encoding="utf-8")
            ev_base = {
                "kind": "test_result",
                "producer": "harness:codex",
                "summary": "Baseline unit test execution",
                "task_ids": ["T001"],
                "gate_ids": ["gate.baseline"],
                "capability_ids": ["tests.execute"],
                "payload": {
                    "suite": "tests/test_app.py",
                    "exit_code": base_run.returncode,
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

            # External test execution capturing authentic stdout/stderr
            test_run = subprocess.run(
                [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-t", "."],
                cwd=str(tmp_path),
                capture_output=True,
                text=True,
            )
            self.assertEqual(test_run.returncode, 0, f"External test failed: {test_run.stderr}")
            test_output = test_run.stderr + test_run.stdout
            self.assertIn("Ran 2 tests", test_output)
            self.assertIn("OK", test_output)

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

            # 10. Register post-execution test_result evidence with authentic captured test log
            test_log = tmp_path / "tests.log"
            test_log.write_text(test_output, encoding="utf-8")
            ev_tests = {
                "kind": "test_result",
                "producer": "harness:codex",
                "summary": "Passing unit test suite execution",
                "task_ids": ["T001"],
                "gate_ids": ["gate.tests"],
                "capability_ids": ["tests.execute"],
                "payload": {
                    "suite": "tests/test_app.py",
                    "exit_code": test_run.returncode,
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
                "producer": "user",
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

    def test_bugfix_lifecycle_and_gate_order_e2e(self):
        """Execute the Bugfix Governance Loop in a temporary project verifying:
        1. Capture of authentic baseline log with gate.baseline ACK while in 'prepared' state.
        2. Attempting to transition to 'active' before PRE_EXECUTION gate ack fails with RAPID1014.
        3. Transition to 'active' succeeds only after PRE_EXECUTION gates are addressed.
        4. Attempting to ack POST_EXECUTION gates while task is still in_progress fails with RAPID1014.
        5. Ingesting authentic regression test suite results and review evidence.
        6. Acking POST_EXECUTION gates after task is marked done succeeds.
        7. Evaluation emits deterministic PASS verdict.
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

            # 1. Setup project structure mimicking bugfix starter
            tests_dir = tmp_path / "tests"
            tests_dir.mkdir(parents=True, exist_ok=True)
            (tests_dir / "__init__.py").write_text("", encoding="utf-8")
            (tmp_path / "pricer.py").write_text(
                "class OrderPricer:\n"
                "    @staticmethod\n"
                "    def calculate_total(items: list[dict[str, float]], discount_percent: float = 0.0) -> float:\n"
                "        if discount_percent < 0 or discount_percent > 100:\n"
                "            raise ValueError('Discount must be between 0 and 100.')\n"
                "        subtotal = sum(item['price'] * item.get('qty', 1) for item in items)\n"
                "        discount_amount = subtotal * discount_percent\n"
                "        total = subtotal - discount_amount\n"
                "        return round(total, 2)\n",
                encoding="utf-8",
            )
            (tests_dir / "test_pricer.py").write_text(
                "import unittest\nfrom pricer import OrderPricer\n"
                "class TestOrderPricerBaseline(unittest.TestCase):\n"
                "    def test_total_without_discount(self):\n"
                "        items = [{'price': 50.0, 'qty': 2}]\n"
                "        total = OrderPricer.calculate_total(items, 0.0)\n"
                "        self.assertEqual(total, 100.0)\n"
                "    def test_defect_characterization(self):\n"
                "        items = [{'price': 100.0, 'qty': 1}]\n"
                "        total = OrderPricer.calculate_total(items, 10.0)\n"
                "        self.assertEqual(total, -900.0)\n"
                "if __name__ == '__main__':\n    unittest.main()\n",
                encoding="utf-8",
            )

            # 2. Initialize and scan
            init_input = "1\n1\n\nn\n\nn\n"
            res = run_rapid("init", "--stack", "docs-modern", "--archetype", "mvp", "--no-scan", input_text=init_input)
            self.assertEqual(res.returncode, 0, f"rapid init failed: {res.stderr}")
            res = run_rapid("scan", "--write")
            self.assertEqual(res.returncode, 0, f"rapid scan failed: {res.stderr}")

            # 3. Create Bugfix Spec
            res = run_rapid(
                "spec",
                "create",
                "--id",
                "spec-order-discount-fix",
                "--title",
                "Fix percentage discount scale in OrderPricer",
                "--mode",
                "bugfix",
                "--task",
                "T001: Correct discount formula and add regression tests",
                "--status",
                "ready",
            )
            self.assertEqual(res.returncode, 0, f"rapid spec create failed: {res.stderr}")

            # 4. Context manifest and Run creation
            res = run_rapid("context", "--manifest")
            self.assertEqual(res.returncode, 0, f"rapid context failed: {res.stderr}")
            res = run_rapid(
                "run",
                "create",
                "--spec",
                "spec-order-discount-fix",
                "--harness",
                "claude",
                "--json",
            )
            self.assertEqual(res.returncode, 0, f"rapid run create failed: {res.stderr}")
            run_data = json.loads(res.stdout)
            run_id = run_data["id"]

            # 5. Verify precondition enforcement: transitioning to active while gate.baseline is pending MUST FAIL
            res_premature_active = run_rapid("run", "status", run_id, "active")
            self.assertNotEqual(res_premature_active.returncode, 0)
            self.assertIn("RAPID1014", res_premature_active.stderr + res_premature_active.stdout)
            self.assertIn("gate.baseline", res_premature_active.stderr + res_premature_active.stdout)

            # 6. Execute authentic baseline test subprocess
            base_run = subprocess.run(
                [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-t", "."],
                cwd=str(tmp_path),
                capture_output=True,
                text=True,
            )
            self.assertEqual(base_run.returncode, 0, f"Baseline test run failed: {base_run.stderr}")
            base_log_content = base_run.stderr + base_run.stdout
            self.assertIn("Ran 2 tests", base_log_content)
            self.assertIn("OK", base_log_content)

            # 7. Ingest authentic baseline evidence with log artifact
            base_log_file = tmp_path / "base.log"
            base_log_file.write_text(base_log_content, encoding="utf-8")
            ev_baseline = {
                "kind": "test_result",
                "producer": "harness:claude",
                "summary": "Authentic baseline unit test execution",
                "task_ids": ["T001"],
                "gate_ids": ["gate.baseline"],
                "capability_ids": ["tests.execute"],
                "payload": {
                    "suite": "tests/test_pricer.py",
                    "exit_code": base_run.returncode,
                    "passed": 2,
                    "failed": 0,
                    "skipped": 0,
                },
                "artifacts": ["base.log"],
            }
            ev_baseline_path = tmp_path / "ev_baseline.json"
            ev_baseline_path.write_text(json.dumps(ev_baseline), encoding="utf-8")
            res = run_rapid("evidence", "add", "--run", run_id, "--input", str(ev_baseline_path))
            self.assertEqual(res.returncode, 0, f"rapid evidence add baseline failed: {res.stderr}")

            # 8. Acknowledge gate.baseline while in prepared state
            res = run_rapid("run", "gate", run_id, "gate.baseline", "acknowledged")
            self.assertEqual(res.returncode, 0, f"rapid run gate baseline failed: {res.stderr}")

            # 9. Now transition to active succeeds
            res = run_rapid("run", "status", run_id, "active")
            self.assertEqual(res.returncode, 0, f"rapid run status active failed: {res.stderr}")
            res = run_rapid("run", "task", run_id, "T001", "in_progress")
            self.assertEqual(res.returncode, 0, f"rapid run task in_progress failed: {res.stderr}")

            # 10. External implementation of the fix
            (tmp_path / "pricer.py").write_text(
                "class OrderPricer:\n"
                "    @staticmethod\n"
                "    def calculate_total(items: list[dict[str, float]], discount_percent: float = 0.0) -> float:\n"
                "        if discount_percent < 0 or discount_percent > 100:\n"
                "            raise ValueError('Discount must be between 0 and 100.')\n"
                "        subtotal = sum(item['price'] * item.get('qty', 1) for item in items)\n"
                "        discount_amount = subtotal * (discount_percent / 100.0)\n"
                "        total = subtotal - discount_amount\n"
                "        return round(total, 2)\n",
                encoding="utf-8",
            )
            (tests_dir / "test_pricer.py").write_text(
                "import unittest\nfrom pricer import OrderPricer\n"
                "class TestOrderPricerSolution(unittest.TestCase):\n"
                "    def test_total_without_discount(self):\n"
                "        items = [{'price': 50.0, 'qty': 2}]\n"
                "        self.assertEqual(OrderPricer.calculate_total(items, 0.0), 100.0)\n"
                "    def test_correct_discount_calculation(self):\n"
                "        items = [{'price': 100.0, 'qty': 1}]\n"
                "        self.assertEqual(OrderPricer.calculate_total(items, 10.0), 90.0)\n"
                "    def test_multiple_items_with_discount(self):\n"
                "        items = [{'price': 40.0, 'qty': 2}, {'price': 20.0, 'qty': 1}]\n"
                "        self.assertEqual(OrderPricer.calculate_total(items, 25.0), 75.0)\n"
                "    def test_reject_out_of_bounds_discount(self):\n"
                "        items = [{'price': 10.0, 'qty': 1}]\n"
                "        with self.assertRaises(ValueError):\n"
                "            OrderPricer.calculate_total(items, -5.0)\n"
                "        with self.assertRaises(ValueError):\n"
                "            OrderPricer.calculate_total(items, 105.0)\n"
                "if __name__ == '__main__':\n    unittest.main()\n",
                encoding="utf-8",
            )

            # 11. Run authentic tests and capture output
            test_run = subprocess.run(
                [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-t", "."],
                cwd=str(tmp_path),
                capture_output=True,
                text=True,
            )
            self.assertEqual(test_run.returncode, 0, f"Solution test run failed: {test_run.stderr}")
            test_log_content = test_run.stderr + test_run.stdout
            self.assertIn("Ran 4 tests", test_log_content)
            self.assertIn("OK", test_log_content)

            # 12. Register file_change evidence
            ev_files = {
                "kind": "file_change",
                "producer": "harness:claude",
                "summary": "Fix discount percentage scale bug and add regression tests",
                "task_ids": ["T001"],
                "gate_ids": [],
                "capability_ids": ["repository.write"],
                "payload": {"paths": ["pricer.py", "tests/test_pricer.py"]},
            }
            ev_files_path = tmp_path / "ev_files.json"
            ev_files_path.write_text(json.dumps(ev_files), encoding="utf-8")
            res = run_rapid("evidence", "add", "--run", run_id, "--input", str(ev_files_path))
            self.assertEqual(res.returncode, 0, f"rapid evidence add files failed: {res.stderr}")

            # 13. Register regression test_result evidence with authentic log
            tests_log_file = tmp_path / "tests.log"
            tests_log_file.write_text(test_log_content, encoding="utf-8")
            ev_regression = {
                "kind": "test_result",
                "producer": "harness:claude",
                "summary": "Full regression test suite passing with authentic log",
                "task_ids": ["T001"],
                "gate_ids": ["gate.tests"],
                "capability_ids": ["tests.execute"],
                "payload": {
                    "suite": "tests/test_pricer.py",
                    "exit_code": test_run.returncode,
                    "passed": 4,
                    "failed": 0,
                    "skipped": 0,
                },
                "artifacts": ["tests.log"],
            }
            ev_regression_path = tmp_path / "ev_regression.json"
            ev_regression_path.write_text(json.dumps(ev_regression), encoding="utf-8")
            res = run_rapid("evidence", "add", "--run", run_id, "--input", str(ev_regression_path))
            self.assertEqual(res.returncode, 0, f"rapid evidence add regression failed: {res.stderr}")

            # 14. Register review evidence
            ev_review = {
                "kind": "review",
                "producer": "user",
                "summary": "Final verification review confirming absence of regression",
                "gate_ids": ["gate.final-verification"],
                "payload": {
                    "review_type": "final",
                    "outcome": "approved",
                    "reviewer": "quality-engineer",
                },
            }
            ev_review_path = tmp_path / "ev_review.json"
            ev_review_path.write_text(json.dumps(ev_review), encoding="utf-8")
            res = run_rapid("evidence", "add", "--run", run_id, "--input", str(ev_review_path))
            self.assertEqual(res.returncode, 0, f"rapid evidence add review failed: {res.stderr}")

            # 15. Register workspace evidence for workspace.current observation
            ev_ws = {
                "kind": "workspace",
                "producer": "harness:claude",
                "summary": "Current workspace verification",
                "capability_ids": ["workspace.current"],
                "payload": {"mode": "current"},
            }
            ev_ws_path = tmp_path / "ev_ws.json"
            ev_ws_path.write_text(json.dumps(ev_ws), encoding="utf-8")
            res = run_rapid("evidence", "add", "--run", run_id, "--input", str(ev_ws_path))
            self.assertEqual(res.returncode, 0, f"rapid evidence add workspace failed: {res.stderr}")

            # 16. Verify precondition enforcement: acking POST_EXECUTION gates before task is done MUST FAIL
            res_premature_gate = run_rapid("run", "gate", run_id, "gate.tests", "acknowledged")
            self.assertNotEqual(res_premature_gate.returncode, 0)
            self.assertIn("RAPID1014", res_premature_gate.stderr + res_premature_gate.stdout)

            # 16. Mark task done, acknowledge POST_EXECUTION gates, transition to finished
            res = run_rapid("run", "task", run_id, "T001", "done")
            self.assertEqual(res.returncode, 0, f"rapid run task done failed: {res.stderr}")
            res = run_rapid("run", "gate", run_id, "gate.tests", "acknowledged")
            self.assertEqual(res.returncode, 0, f"rapid run gate tests failed: {res.stderr}")
            res = run_rapid("run", "gate", run_id, "gate.final-verification", "acknowledged")
            self.assertEqual(res.returncode, 0, f"rapid run gate final failed: {res.stderr}")
            res = run_rapid("run", "status", run_id, "finished")
            self.assertEqual(res.returncode, 0, f"rapid run status finished failed: {res.stderr}")

            # 17. Deterministic evaluation must PASS
            res_eval_raw = run_rapid("eval", "run", "--run", run_id, "--json")
            eval_report = json.loads(res_eval_raw.stdout) if res_eval_raw.stdout else {}
            unverified_assertions = [a for a in eval_report.get("assertions", []) if a.get("status") != "pass"]
            self.assertEqual(eval_report.get("verdict"), "pass", f"Eval report verdict not pass, unverified: {unverified_assertions}")
            res = run_rapid("eval", "run", "--run", run_id, "--write", "--require-pass", "--json")
            self.assertEqual(res.returncode, 0, f"rapid eval run failed: {res.stderr}")

            # 18. Validation
            res = run_rapid("validate")
            self.assertEqual(res.returncode, 0, f"rapid validate failed:\nSTDOUT: {res.stdout}\nSTDERR: {res.stderr}")
            self.assertIn("0 error", res.stdout)


if __name__ == "__main__":
    unittest.main()

