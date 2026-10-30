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
    "standard_ref": "CWE, CVSS v4.0",
}


class HardeningFindingValidationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.security = Path(self.temp.name) / "security.md"
        self.security.write_text("- Report CWE and CVSS. [CWE, CVSS v4.0]\n", encoding="utf-8")

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


if __name__ == "__main__":
    unittest.main()
