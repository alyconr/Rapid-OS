"""H-38: projects written before hardening findings (#104) still read.

`tests/fixtures/pre_findings_project/.rapid-os` was written by Rapid OS at main 5f1a0d89: its specs have no
`findings` key and a content digest computed without it, and it has a finished hardening run with its
evaluation report. With c5562ce every one of those specs failed `rapid validate` (RAPID804) and the hardening
report ended `rapid validate` with a traceback.
"""

from __future__ import annotations

import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

from rapid_os.adapters.spec_registry import SpecRegistry
from rapid_os.domain.specs import SpecRevision

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests" / "fixtures" / "pre_findings_project" / ".rapid-os"
MODES = ("feature", "bugfix", "refactor", "hardening", "research")
RUN_ID = "legacy-hardening-r1-run-001"


class LegacySpecTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        shutil.copytree(FIXTURE, self.root / ".rapid-os")

    def tearDown(self):
        self.temp_dir.cleanup()

    def rapid(self, *args):
        return subprocess.run(
            [sys.executable, str(ROOT / "rapid.py"), *args],
            cwd=str(self.root),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            env={"PYTHONPATH": str(ROOT), **{k: v for k, v in __import__("os").environ.items() if k != "PYTHONPATH"}},
        )

    def revision_file(self, mode):
        return self.root / ".rapid-os" / "specs" / f"legacy-{mode}" / "revisions" / "0001" / "revision.json"

    def test_the_fixture_is_from_before_findings(self):
        for mode in MODES:
            payload = json.loads(self.revision_file(mode).read_text(encoding="utf-8"))
            with self.subTest(mode=mode):
                self.assertNotIn("findings", payload)
        contract = json.loads((self.root / ".rapid-os" / "runs" / RUN_ID / "contract.json").read_text("utf-8"))
        self.assertNotIn("ruleset_version", contract)

    def test_validate_spec_show_and_eval_show_work(self):
        validated = self.rapid("validate", "--json")
        self.assertNotIn("Traceback", validated.stderr)
        self.assertEqual(validated.returncode, 0, validated.stdout + validated.stderr)
        report = json.loads(validated.stdout)
        self.assertEqual(report["summary"]["error"], 0, report["diagnostics"])
        codes = {d["code"] for d in report["diagnostics"]}
        self.assertNotIn("RAPID804", codes)
        self.assertNotIn("RAPID1003", codes)
        for mode in MODES:
            shown = self.rapid("spec", "show", f"legacy-{mode}")
            with self.subTest(mode=mode):
                self.assertEqual(shown.returncode, 0, shown.stderr)
                self.assertIn(f"Legacy {mode} spec", shown.stdout)
        evaluation = self.rapid("eval", "show", "--run", RUN_ID)
        self.assertEqual(evaluation.returncode, 0, evaluation.stderr)
        self.assertIn("v2", evaluation.stdout)

    def test_one_rule_for_the_digest(self):
        payload = json.loads(self.revision_file("hardening").read_text(encoding="utf-8"))
        revision = SpecRevision.from_dict(payload)
        self.assertTrue(revision.stored_without_findings)
        self.assertNotEqual(payload["content_digest"], revision.content_digest)
        self.assertEqual(payload["content_digest"], revision.legacy_content_digest)
        self.assertTrue(revision.matches_content_digest(payload["content_digest"]))
        self.assertTrue(revision.matches_content_digest(revision.content_digest))
        # The legacy digest is only accepted for a payload without `findings`.
        self.assertFalse(revision.matches_content_digest(payload["content_digest"], without_findings=False))
        with self.assertRaises(Exception) as ctx:
            SpecRevision.from_dict({**payload, "findings": []})
        self.assertEqual(getattr(ctx.exception, "code", None), "RAPID804")
        # The registry reads it with the same rule.
        self.assertEqual(SpecRegistry(self.root, self.root / ".rapid-os").get_revision("legacy-hardening").title,
                         "Legacy hardening spec")

    def test_an_altered_legacy_spec_is_a_diagnostic_not_a_traceback(self):
        path = self.revision_file("hardening")
        payload = json.loads(path.read_text(encoding="utf-8"))
        payload["business_objective"] = "changed by hand"
        path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        validated = self.rapid("validate", "--json")
        self.assertNotIn("Traceback", validated.stderr)
        self.assertEqual(validated.returncode, 1)
        report = json.loads(validated.stdout)
        errors = [d for d in report["diagnostics"] if d["level"] == "error"]
        self.assertTrue(errors)
        self.assertTrue(all(d["code"].startswith("RAPID") for d in errors))
        self.assertIn("RAPID804", {d["code"] for d in errors})
        shown = self.rapid("eval", "show", "--run", RUN_ID)
        self.assertNotIn("Traceback", shown.stderr)
        self.assertNotEqual(shown.returncode, 0)
        self.assertIn("RAPID1223", shown.stderr)  # the replay cannot run, and says the spec is why
        self.assertIn("Spec 'legacy-hardening' r1 of run", shown.stderr)


if __name__ == "__main__":
    unittest.main()
