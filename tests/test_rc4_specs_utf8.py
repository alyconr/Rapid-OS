"""rc.4 fixes from the rc.3 e2e on Windows with Codex: H-55 (a spec whose accents became '?' is refused),
H-54 (task progress in `rapid status`), H-56 (handing a story over for approval) and H-57 (`rapid check`
reads the command's output as UTF-8)."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from rapid_os.domain.project_docs import find_lost_characters
from rapid_os.domain.specs import find_spec_lost_characters

ROOT = Path(__file__).resolve().parents[1]
SHORTCUTS = ROOT / "templates" / "shortcuts"
WORK_SHORTCUTS = ("rapid-feature", "rapid-bugfix", "rapid-refactor", "rapid-hardening", "rapid-research")
TEST_COMMAND = f'"{sys.executable}" -m unittest discover -s tests -t .'
SMOKE_TEST = "import unittest\n\nclass Smoke(unittest.TestCase):\n    def test_smoke(self):\n        self.assertTrue(True)\n"


def rapid(cwd, *argv, stdin=None, env_extra=None):
    env = {
        **{k: v for k, v in os.environ.items() if k not in ("CLAUDECODE", "CLAUDE_CODE_CHILD_SESSION")},
        "PYTHONPATH": str(ROOT),
        "PYTHONIOENCODING": "utf-8",
        "PYTHONDONTWRITEBYTECODE": "1",
        **(env_extra or {}),
    }
    return subprocess.run(
        [sys.executable, "-m", "rapid_os.cli.main", *argv],
        cwd=cwd, input=stdin, capture_output=True, text=True, encoding="utf-8", env=env,
    )


def git(cwd, *argv):
    subprocess.run(["git", *argv], cwd=cwd, check=True, capture_output=True)


def spec(**overrides):
    payload = {
        "title": "Reserva pública", "mode": "feature", "business_objective": "Reservar un taller",
        "problem_statement": "No se puede reservar", "scope": ["reservas"],
        "acceptance_criteria": ["La reserva queda guardada"], "tasks": ["T001: Añadir el módulo de reservas"],
    }
    payload.update(overrides)
    return payload


class Project(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name) / "project"
        self.root.mkdir()
        git(self.root, "init", "-q")
        git(self.root, "config", "user.email", "t@example.com")
        git(self.root, "config", "user.name", "T")
        init = rapid(self.root, "init", "--yes", "--skip-docs", "--test-command", TEST_COMMAND)
        self.assertEqual(init.returncode, 0, init.stderr)
        (self.root / "app.py").write_text("x = 1\n", encoding="utf-8")
        (self.root / "tests").mkdir()
        (self.root / "tests" / "__init__.py").write_text("", encoding="utf-8")
        (self.root / "tests" / "test_smoke.py").write_text(SMOKE_TEST, encoding="utf-8")
        git(self.root, "add", "-A")
        git(self.root, "commit", "-q", "-m", "base")

    def specs_dir(self):
        return self.root / ".rapid-os" / "specs"

    def stored_specs(self):
        directory = self.specs_dir()
        return sorted(p.name for p in directory.iterdir() if p.is_dir()) if directory.is_dir() else []

    def runs(self):
        directory = self.root / ".rapid-os" / "runs"
        return sorted(p.name for p in directory.iterdir() if p.is_dir()) if directory.is_dir() else []


class LostCharacterDetectionTests(unittest.TestCase):
    def test_the_word_that_lost_characters_is_named(self):
        self.assertEqual(find_lost_characters("Tarea de creaci?n at?mica"), "creaci?n")
        self.assertIsNone(find_lost_characters("¿Qué pasa? Usa `a?b` en el patrón"))

    def test_every_text_field_of_a_spec_is_checked(self):
        self.assertEqual(
            find_spec_lost_characters(spec(tasks=["T001: ok", "T002: creaci?n at?mica"])),
            ("tasks[1]", "creaci?n"),
        )
        self.assertEqual(find_spec_lost_characters(spec(title="Reserva p?blica"))[0], "title")
        self.assertEqual(
            find_spec_lost_characters(spec(findings=[{"title": "Inyecci?n", "severity": "high"}]))[0],
            "findings[0].title",
        )
        self.assertIsNone(find_spec_lost_characters(spec(business_objective="¿Qué pasa? Usa `a?b`")))


class StartRefusesLostCharactersTests(Project):
    def test_start_with_a_task_that_lost_accents_is_refused_and_writes_nothing(self):
        bad = spec(tasks=["T001: creaci?n at?mica del m?dulo"])
        result = rapid(self.root, "start", "feature", "--spec-file", "-", stdin=json.dumps(bad, ensure_ascii=False))
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("RAPID1415", result.stderr)
        self.assertIn("creaci?n", result.stderr)
        self.assertIn("Set-Content -Encoding utf8", result.stderr)
        self.assertIn("--spec-file", result.stderr)
        self.assertNotIn("Traceback", result.stderr)
        self.assertEqual(self.stored_specs(), [])
        self.assertEqual(self.runs(), [])
        self.assertFalse((self.root / ".rapid-os" / "session.json").exists())

    def test_question_marks_that_belong_to_the_text_are_accepted(self):
        good = spec(
            problem_statement="¿Qué pasa si la reserva ya existe?",
            tasks=["T001: Validar el patrón `a?b` del módulo"],
        )
        result = rapid(self.root, "start", "feature", "--spec-file", "-", "--json", stdin=json.dumps(good, ensure_ascii=False))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(len(self.runs()), 1)

    def test_a_utf8_file_with_bom_keeps_the_title_and_the_slug(self):
        # What `Set-Content -Encoding utf8` writes in Windows PowerShell 5.1: UTF-8 with a BOM.
        path = Path(self._tmp.name) / "rapid-spec.json"
        path.write_bytes(b"\xef\xbb\xbf" + json.dumps(spec(), ensure_ascii=False).encode("utf-8"))
        result = rapid(self.root, "start", "feature", "--spec-file", str(path), "--json")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.stored_specs(), ["reserva-publica"])
        revision = json.loads((self.specs_dir() / "reserva-publica" / "revisions" / "0001" / "revision.json").read_text("utf-8"))
        self.assertEqual(revision["title"], "Reserva pública")
        self.assertEqual(revision["implementation_tasks"], ["T001: Añadir el módulo de reservas"])


class SpecCommandsRefuseLostCharactersTests(Project):
    def test_spec_create_is_refused_without_writing(self):
        result = rapid(
            self.root, "spec", "create", "--title", "Reserva", "--objective", "Reservar",
            "--task", "T001: creaci?n at?mica",
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("RAPID1415", result.stderr)
        self.assertEqual(self.stored_specs(), [])

    def test_spec_revise_is_refused_and_the_current_revision_stays(self):
        created = rapid(self.root, "spec", "create", "--title", "Reserva", "--objective", "Reservar", "--task", "T001: Crear")
        self.assertEqual(created.returncode, 0, created.stderr)
        result = rapid(self.root, "spec", "revise", "reserva", "--task", "T001: creaci?n at?mica")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("RAPID1415", result.stderr)
        record = json.loads((self.specs_dir() / "reserva" / "spec.json").read_text("utf-8"))
        self.assertEqual(record["current_revision"], 1)
        self.assertEqual(
            sorted(p.name for p in (self.specs_dir() / "reserva" / "revisions").iterdir()), ["0001"]
        )

    def test_spec_create_with_intact_text_is_accepted(self):
        result = rapid(
            self.root, "spec", "create", "--title", "Reserva pública", "--objective", "¿Qué pasa?",
            "--task", "T001: Añadir `a?b`",
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.stored_specs(), ["reserva-publica"])


class WorkShortcutsSendSpecsByFileOnPowerShellTests(unittest.TestCase):
    def test_every_work_shortcut_has_the_powershell_rule(self):
        for name in WORK_SHORTCUTS:
            text = (SHORTCUTS / f"{name}.md").read_text("utf-8")
            with self.subTest(shortcut=name):
                self.assertIn("En Windows PowerShell no pases la spec por tubería", text)
                self.assertIn("Set-Content -Encoding utf8 $env:TEMP\\rapid-spec.json", text)
                self.assertIn("RAPID1415", text)
                self.assertIn("stdin (heredoc) sigue bien", text)


if __name__ == "__main__":
    unittest.main()
