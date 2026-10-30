"""Hardening follow-ups: finding example id, whole-word criteria match, RAPID1321 wording."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest

from rapid_os.domain.evals import BehavioralEvaluator, EvalAssertionStatus
from rapid_os.domain.hardening import validate_hardening_findings
from rapid_os.domain.shortcuts import detect_folder_overlaps

ROOT = Path(__file__).resolve().parents[1]


def criteria_status(finding: dict, criteria: tuple[str, ...]):
    contract = SimpleNamespace(tasks=(), run_id="run-1")
    return BehavioralEvaluator()._evaluate_hardening_findings(contract, (finding,), criteria, ())


class HardeningTemplateExampleTests(unittest.TestCase):
    def test_example_finding_does_not_reuse_a_brief_story_id_and_is_valid(self):
        template = json.loads((ROOT / "templates" / "modes" / "hardening.json").read_text(encoding="utf-8"))
        findings = template["spec_template"]["findings"]
        self.assertEqual([f["id"] for f in findings], ["SEC-001"])
        with tempfile.TemporaryDirectory() as tmp:
            security = Path(tmp) / "security.md"
            security.write_text((ROOT / "templates" / "security" / "baseline.md").read_text(encoding="utf-8"), encoding="utf-8")
            self.assertIsNone(validate_hardening_findings(findings, security))


class FindingCriteriaWholeWordTests(unittest.TestCase):
    FINDING = {"id": "SEC-001", "cwe": "CWE-79"}

    def test_cwe_79_does_not_match_cwe_798(self):
        assertion = criteria_status(self.FINDING, ("Se evita la credencial embebida (CWE-798)",))
        self.assertEqual(assertion.status, EvalAssertionStatus.FAIL)

    def test_id_does_not_match_a_longer_id(self):
        assertion = criteria_status(self.FINDING, ("SEC-0010: otro hallazgo", "SEC-001-bis queda fuera",))
        self.assertEqual(assertion.status, EvalAssertionStatus.FAIL)

    def test_whole_id_or_cwe_matches_regardless_of_case_and_punctuation(self):
        for criterion in ("SEC-001: la salida se escapa", "Evita XSS (cwe-79).", "Cubre CWE-79, CWE-798"):
            with self.subTest(criterion=criterion):
                assertion = criteria_status(self.FINDING, (criterion,))
                self.assertNotEqual(assertion.status, EvalAssertionStatus.FAIL)


class ExistingFolderOverlapMessageTests(unittest.TestCase):
    def test_message_says_the_project_already_has_the_shortcuts_in_the_folder(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for folder in (".claude/skills", ".cursor/skills"):
                skill = root / folder / "rapid-feature"
                skill.mkdir(parents=True)
                (skill / "SKILL.md").write_text("x\n", encoding="utf-8")
            [overlap] = detect_folder_overlaps(["cursor"], root)
        self.assertTrue(overlap.existing)
        self.assertIn("this project already has /rapid-* of claude in .claude/skills", overlap.message)
        self.assertNotIn("selecting", overlap.message)
        self.assertNotIn("existing", overlap.to_dict())

    def test_selection_overlap_keeps_the_selecting_wording(self):
        [overlap] = detect_folder_overlaps(["claude", "cursor"])
        self.assertFalse(overlap.existing)
        self.assertIn("selecting cursor, claude", overlap.message)


if __name__ == "__main__":
    unittest.main()
