"""Fixes of the 3.2.0rc1 e2e: the installation is not a project, accents in slugs, old evidence still reads."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from rapid_os.domain.evidence import EvidenceArtifact, EvidenceKind, validate_evidence_payload
from rapid_os.domain.specs import SPEC_ID_RE, derive_spec_id

ROOT = Path(__file__).resolve().parents[1]
SHA = "a" * 64


class SlugTests(unittest.TestCase):
    def test_accents_and_enye_are_transliterated(self):
        self.assertEqual(derive_spec_id("Teléfono de contacto"), "telefono-de-contacto")
        self.assertEqual(derive_spec_id("Año Ñandú"), "ano-nandu")
        self.assertEqual(derive_spec_id("Gestión y Reservación"), "gestion-y-reservacion")

    def test_plain_titles_and_symbols_keep_the_same_slug(self):
        self.assertEqual(derive_spec_id("Add user login"), "add-user-login")
        self.assertEqual(derive_spec_id("  API v2 -- (draft)!  "), "api-v2-draft")

    def test_an_id_made_by_the_old_algorithm_is_still_valid(self):
        self.assertRegex("tel-fono", SPEC_ID_RE)


class EvidenceCompatibilityTests(unittest.TestCase):
    PATH = ".rapid-os/evidence/20260101-000000-abcdef/artifacts/E001/1.log"

    def test_an_artifact_without_source_reads_and_writes_back_unchanged(self):
        old = {"path": self.PATH, "sha256": SHA, "size_bytes": 3}
        artifact = EvidenceArtifact.from_dict(old)
        self.assertIsNone(artifact.source)
        self.assertEqual(artifact.to_dict(), old)

    def test_the_source_is_kept_when_present(self):
        new = {"path": self.PATH, "sha256": SHA, "size_bytes": 3, "source": ".rapid-os/scratch/checks/r/1.log"}
        self.assertEqual(EvidenceArtifact.from_dict(new).to_dict(), new)

    def test_a_host_path_is_not_a_valid_source(self):
        with self.assertRaises(Exception):
            EvidenceArtifact.from_dict({"path": self.PATH, "sha256": SHA, "size_bytes": 3, "source": "C:/x/1.log"})

    def test_a_review_may_carry_its_reason_and_old_reviews_do_not_need_it(self):
        base = {"review_type": "manual", "outcome": "changes_requested", "reviewer": "Ada"}
        self.assertNotIn("reason", validate_evidence_payload(EvidenceKind.REVIEW, base))
        self.assertEqual(
            validate_evidence_payload(EvidenceKind.REVIEW, {**base, "reason": " falta validar "})["reason"],
            "falta validar",
        )
        with self.assertRaises(Exception):
            validate_evidence_payload(EvidenceKind.REVIEW, {**base, "reason": "  "})


class InstallationIsNotAProjectTests(unittest.TestCase):
    """From the home folder `.rapid-os` is the installation (RAPID_HOME): nothing may be written there."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.home = Path(self._tmp.name)
        self.install = self.home / ".rapid-os"
        self.install.mkdir()
        (self.install / "marker.txt").write_text("installed checkout", encoding="utf-8")
        self.env = {
            **{k: v for k, v in os.environ.items() if k not in ("CLAUDECODE", "CLAUDE_CODE_CHILD_SESSION")},
            "HOME": str(self.home),
            "USERPROFILE": str(self.home),
            "PYTHONPATH": str(ROOT),
            "PYTHONIOENCODING": "utf-8",
            "PYTHONDONTWRITEBYTECODE": "1",
        }

    def rapid(self, *argv, cwd=None):
        return subprocess.run(
            [sys.executable, "-m", "rapid_os.cli.main", *argv],
            cwd=cwd or self.home, capture_output=True, text=True, encoding="utf-8", env=self.env,
        )

    def snapshot(self):
        return sorted(p.relative_to(self.install).as_posix() for p in self.install.rglob("*"))

    def test_doctor_says_it_is_not_a_project_and_has_no_false_errors(self):
        result = self.rapid("doctor")
        self.assertIn("No estás en un proyecto", result.stdout)
        self.assertNotIn("ERROR", result.stdout)
        self.assertEqual(self.snapshot(), ["marker.txt"])

    def test_state_writing_commands_refuse_with_rapid1417_and_write_nothing(self):
        for argv in (
            ("setup", "set", "test-command", "pytest"),
            ("setup", "doc", "brief", "--skip"),
            ("setup", "finish"),
            ("init", "--yes"),
            ("start", "feature"),
            ("finish",),
            ("abort",),
            ("check", "--", sys.executable, "-c", "pass"),
        ):
            with self.subTest(argv=argv):
                result = self.rapid(*argv)
                self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
                self.assertIn("RAPID1417", result.stderr)
                self.assertIn("No estás en un proyecto", result.stderr)
                self.assertNotIn("Traceback", result.stderr)
                self.assertEqual(self.snapshot(), ["marker.txt"])

    def test_reading_commands_still_work_from_the_home_folder(self):
        for argv in (("--version",), ("guide",)):
            with self.subTest(argv=argv):
                self.assertNotIn("RAPID1417", self.rapid(*argv).stderr)

    def test_a_real_project_is_not_affected(self):
        project = self.home / "mi-proyecto"
        project.mkdir()
        result = self.rapid("doctor", cwd=project)
        self.assertNotIn("No estás en un proyecto", result.stdout)
        refused = self.rapid("setup", "set", "test-command", "pytest", cwd=project)
        self.assertNotIn("RAPID1417", refused.stderr)


if __name__ == "__main__":
    unittest.main()
