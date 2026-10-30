from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from rapid_os.domain.hardening import validate_hardening_findings


VALID = {
    "id": "H001",
    "title": "Reject unsafe input",
    "cwe": "CWE-20",
    "cvss_v4_vector": "CVSS:4.0/AV:N/AC:L/AT:N/PR:N/UI:P/VC:L/VI:L/VA:N/SC:N/SI:N/SA:N",
    "severity": "medium",
    "standard_ref": "CVSS v4.0",
}


class HardeningFindingValidationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.security = Path(self.temp.name) / "security.md"
        self.security.write_text(
            "- Report CWE and CVSS. [CWE, CVSS v4.0]\n- Encode output. [OWASP A05:2025, CWE-79, ASVS V5.3.3]\n",
            encoding="utf-8",
        )

    def test_valid_finding_passes(self):
        self.assertIsNone(validate_hardening_findings([VALID], self.security))

    def test_requires_at_least_one_finding(self):
        error = validate_hardening_findings([], self.security)
        self.assertIn("RAPID1343", error)
        self.assertIn("al menos un hallazgo", error)

    def test_reports_the_concrete_finding_for_cwe_vector_severity_and_reference_errors(self):
        mutations = (
            ("cwe", "20"),
            ("cvss_v4_vector", "CVSS:3.1/AV:N"),
            ("cvss_v4_vector", "CVSS:4.0/AV:N/AC:L/AT:N/PR:N/UI:P/VC:L/VI:L/VA:N/SC:N/SI:N"),
            ("severity", "critical"),
            ("standard_ref", "OWASP A01"),
        )
        for key, value in mutations:
            with self.subTest(key=key, value=value):
                finding = {**VALID, key: value}
                error = validate_hardening_findings([finding], self.security)
                self.assertIn("RAPID1343", error)
                self.assertIn("H001", error)

    def test_severity_must_match_the_cvss_score(self):
        low = {**VALID, "cvss_v4_vector": "CVSS:4.0/AV:L/AC:H/AT:P/PR:H/UI:P/VC:H/VI:N/VA:N/SC:N/SI:N/SA:N"}
        self.assertIsNone(validate_hardening_findings([{**low, "severity": "Medium"}], self.security))
        error = validate_hardening_findings([{**low, "severity": "high"}], self.security)
        self.assertIn("4.1", error)
        self.assertIn("esperada medium", error)
        critical = {**VALID, "cvss_v4_vector": "CVSS:4.0/AV:N/AC:L/AT:N/PR:N/UI:N/VC:H/VI:H/VA:H/SC:N/SI:N/SA:N"}
        self.assertIsNone(validate_hardening_findings([{**critical, "severity": "critical"}], self.security))
        error = validate_hardening_findings([{**critical, "severity": "high"}], self.security)
        self.assertIn("9.3", error)
        self.assertIn("esperada critical", error)

    def test_a_valid_severity_is_never_rejected_for_its_impact_class(self):
        # 5.3 with only Low impacts is medium; a High-impact vector may still be "medium" if its score says so.
        vector = "CVSS:4.0/AV:P/AC:H/AT:P/PR:H/UI:A/VC:H/VI:N/VA:N/SC:N/SI:N/SA:N"
        from rapid_os.domain.cvss4 import score_vector
        _, expected = score_vector(vector)
        finding = {**VALID, "cvss_v4_vector": vector, "severity": expected}
        self.assertIsNone(validate_hardening_findings([finding], self.security))

    def test_standard_ref_must_be_a_full_citation(self):
        for partial in ("A", "2025", "OWASP", "ASVS", "CWE-7"):
            with self.subTest(partial=partial):
                error = validate_hardening_findings([{**VALID, "standard_ref": partial}], self.security)
                self.assertIn("RAPID1343", error)
                self.assertIn("standard_ref", error)
        for full in ("OWASP A05:2025", "owasp a05:2025", "CWE-79", "ASVS V5.3.3", "  CWE  "):
            with self.subTest(full=full):
                self.assertIsNone(validate_hardening_findings([{**VALID, "standard_ref": full}], self.security))

    def test_standard_ref_error_lists_up_to_five_similar_citations(self):
        self.security.write_text(
            "[" + ", ".join(f"OWASP A0{n}:2025" for n in range(1, 9)) + "]", encoding="utf-8"
        )
        error = validate_hardening_findings([{**VALID, "standard_ref": "2025"}], self.security)
        listed = [part for part in error.split("citas parecidas: ")[1].split(", ")]
        self.assertEqual(len(listed), 5)
        self.assertTrue(all(item.startswith("OWASP A0") for item in listed))


if __name__ == "__main__":
    unittest.main()
