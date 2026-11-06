"""H-51: git must not change the bytes of the evidence, whatever `core.autocrlf` says.

Real git, real clones: `core.autocrlf=true` is what Git for Windows sets by default, and it works the same on Linux.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from rapid_os.orchestration.git import LINE_ENDINGS_RULE
from rapid_os.orchestration.setup_apply import GITATTRIBUTES_BEGIN, GITATTRIBUTES_END, update_gitattributes

ROOT = Path(__file__).resolve().parents[1]
SPEC = {
    "title": "Finales de línea",
    "mode": "research",
    "business_objective": "Comprobar la evidencia en un clon",
    "problem_statement": "Git cambia los bytes",
    "scope": ["evidencia"],
    "acceptance_criteria": ["La evidencia se verifica en un clon"],
    "tasks": ["T001: Comparar opciones"],
}
LF = b"uno\ndos\n"
MIXED = b"uno\r\ndos\n"


class Sandbox(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.base = Path(tmp.name)
        self.root = self.base / "project"
        self.root.mkdir()
        gitconfig = self.base / "gitconfig"
        gitconfig.write_text(
            "[user]\n\tname = T\n\temail = t@example.com\n[init]\n\tdefaultBranch = main\n[core]\n\tautocrlf = true\n",
            encoding="utf-8",
        )
        self.env = {
            **{k: v for k, v in os.environ.items() if k not in ("CLAUDECODE", "CLAUDE_CODE_CHILD_SESSION")},
            "GIT_CONFIG_GLOBAL": str(gitconfig),
            "GIT_CONFIG_NOSYSTEM": "1",
            "PYTHONPATH": str(ROOT),
            "PYTHONIOENCODING": "utf-8",
            "PYTHONDONTWRITEBYTECODE": "1",
        }

    def rapid(self, *args, cwd=None, stdin=None):
        return subprocess.run(
            [sys.executable, str(ROOT / "rapid.py"), *args],
            cwd=str(cwd or self.root),
            env=self.env,
            input=stdin,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=120,
        )

    def ok(self, *args, cwd=None, stdin=None):
        result = self.rapid(*args, cwd=cwd, stdin=stdin)
        self.assertEqual(result.returncode, 0, f"rapid {args}\n{result.stdout}\n{result.stderr}")
        return result

    def git(self, *args, cwd=None):
        result = subprocess.run(
            ["git", *args], cwd=str(cwd or self.root), env=self.env, capture_output=True, timeout=120
        )
        self.assertEqual(result.returncode, 0, f"git {args}\n{result.stderr!r}")
        return result.stdout

    def onboard(self):
        for step in (("stack", "python-fastapi"), ("topology", "backend-only"), ("archetype", "mvp"), ("ai", "no"),
                     ("agents", "claude"), ("test-command", "none"), ("services", "none")):
            self.ok("setup", "set", *step)
        for doc in ("brief", "business", "data-model", "architecture", "deployment"):
            self.ok("setup", "doc", doc, "--skip")
        return self.ok("setup", "finish", "--json")

    def run_with_artifacts(self):
        """A research run whose evidence holds one file with LF and one with mixed line endings."""
        self.ok("start", "research", "--spec-file", "-", "--json", stdin=json.dumps(SPEC, ensure_ascii=False))
        experiments = self.root / "experiments"
        experiments.mkdir()
        (experiments / "lf.md").write_bytes(LF)
        (experiments / "mixed.md").write_bytes(MIXED)
        self.ok("attach", "experiments/lf.md", "--label", "lf")
        self.ok("attach", "experiments/mixed.md", "--label", "mixed")

    def commit_and_clone(self, name="clone"):
        self.git("add", "-A")
        self.git("commit", "-q", "-m", name)
        self.git("clone", "-q", str(self.root), name, cwd=self.base)
        return self.base / name

    def verify(self, cwd=None):
        run_id = next((self.root / ".rapid-os" / "runs").iterdir()).name
        return self.rapid("evidence", "verify", "--run", run_id, cwd=cwd)

    def stored_artifacts(self):
        """Path in the repository of each artifact, keyed by the bytes Rapid OS copied."""
        return sorted(self.root.glob(".rapid-os/evidence/*/artifacts/*/**/*.md"), key=lambda p: p.name)


class CloneTests(Sandbox):
    def test_the_clone_verifies_with_the_rule(self):
        self.onboard()
        self.run_with_artifacts()
        clone = self.commit_and_clone()
        verified = self.verify(cwd=clone)
        self.assertEqual(verified.returncode, 0, verified.stderr)
        validated = self.rapid("validate", cwd=clone)
        self.assertNotIn("RAPID1205", validated.stdout + validated.stderr)
        self.assertNotIn("RAPID1437", validated.stdout + validated.stderr)
        artifacts = self.stored_artifacts()
        self.assertEqual(len(artifacts), 2)
        for artifact in artifacts:
            relative = artifact.relative_to(self.root).as_posix()
            with self.subTest(artifact=relative):
                self.assertEqual((clone / relative).read_bytes(), artifact.read_bytes())
                self.assertEqual(self.git("cat-file", "blob", f"HEAD:{relative}"), artifact.read_bytes())

    def test_without_the_rule_the_clone_fails_and_names_the_cause(self):
        self.onboard()
        (self.root / ".gitattributes").unlink()
        self.run_with_artifacts()
        clone = self.commit_and_clone()
        result = self.verify(cwd=clone)
        self.assertNotEqual(result.returncode, 0, "a converted file must stay rejected")
        self.assertIn("RAPID1205", result.stderr)
        self.assertIn("RAPID1437", result.stderr)
        self.assertIn("core.autocrlf", result.stderr)
        self.assertIn("--renormalize", result.stderr)
        report = json.loads(self.rapid("validate", "--json", cwd=clone).stdout)
        messages = [d["message"] for d in report["diagnostics"] if d["level"] == "error"]
        self.assertTrue(any("RAPID1437" in message for message in messages), messages)

    def test_the_repair_keeps_the_bytes_rapid_wrote(self):
        """In the good copy: add the rule, `git add --renormalize .rapid-os/`, commit. Then a new clone verifies."""
        self.onboard()
        (self.root / ".gitattributes").unlink()
        self.run_with_artifacts()
        broken = self.commit_and_clone("broken")
        self.assertNotEqual(self.verify(cwd=broken).returncode, 0)

        self.assertEqual(self.verify().returncode, 0)  # the good copy
        self.ok("setup", "finish")
        self.git("add", ".gitattributes")
        self.git("add", "--renormalize", ".rapid-os/")
        repaired = self.commit_and_clone("repaired")
        verified = self.verify(cwd=repaired)
        self.assertEqual(verified.returncode, 0, verified.stderr)

    def test_real_tampering_with_the_rule_and_without_autocrlf_has_no_excuse(self):
        self.onboard()
        self.run_with_artifacts()
        self.git("config", "core.autocrlf", "false")
        artifact = self.stored_artifacts()[0]
        artifact.write_bytes(artifact.read_bytes() + b"otra\n")
        result = self.verify()
        self.assertIn("RAPID1205", result.stderr)
        self.assertNotIn("RAPID1437", result.stderr)

    def test_a_binary_artifact_gets_no_line_ending_cause(self):
        self.onboard()
        (self.root / ".gitattributes").unlink()
        self.ok("start", "research", "--spec-file", "-", "--json", stdin=json.dumps(SPEC, ensure_ascii=False))
        (self.root / "image.bin").write_bytes(b"\x00\x01\n\x02")
        self.ok("attach", "image.bin", "--label", "bin")
        artifact = next(self.root.glob(".rapid-os/evidence/*/artifacts/*/**/image.bin"))
        artifact.write_bytes(b"\x00\x01\n\x03\x04")
        result = self.verify()
        self.assertIn("RAPID1205", result.stderr)
        self.assertNotIn("RAPID1437", result.stderr)


class DoctorTests(Sandbox):
    def codes(self):
        report = json.loads(self.rapid("doctor", "--json").stdout)
        return {d["code"]: d for d in report["diagnostics"]}

    def test_doctor_warns_while_the_rule_is_missing_and_stops_after_finish(self):
        self.onboard()
        self.assertNotIn("RAPID1436", self.codes())
        (self.root / ".gitattributes").unlink()
        diagnostic = self.codes()["RAPID1436"]
        self.assertEqual(diagnostic["level"], "warning")
        self.assertIn("rapid setup finish", diagnostic["hint"])
        self.assertIn("--renormalize", diagnostic["hint"])
        self.ok("setup", "finish")
        self.assertNotIn("RAPID1436", self.codes())

    def test_outside_git_there_is_nothing_to_warn_about(self):
        self.onboard()
        shutil.rmtree(self.root / ".git")
        (self.root / ".gitattributes").unlink()
        self.assertNotIn("RAPID1436", self.codes())

    def test_a_broader_rule_of_the_person_counts(self):
        self.onboard()
        (self.root / ".gitattributes").write_text("* -text\n", encoding="utf-8")
        self.assertNotIn("RAPID1436", self.codes())

    def test_a_later_line_that_turns_conversion_back_on_does_not_count(self):
        self.onboard()
        with (self.root / ".gitattributes").open("a", encoding="utf-8") as handle:
            handle.write("* text=auto\n")
        self.assertIn("RAPID1436", self.codes())


class ManagedBlockTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.path = self.root / ".gitattributes"

    def test_creates_the_file_with_the_block(self):
        self.assertTrue(update_gitattributes(self.root))
        self.assertEqual(
            self.path.read_text(encoding="utf-8"),
            f"{GITATTRIBUTES_BEGIN}\n{LINE_ENDINGS_RULE}\n{GITATTRIBUTES_END}\n",
        )

    def test_it_is_idempotent(self):
        update_gitattributes(self.root)
        before = self.path.read_bytes()
        self.assertFalse(update_gitattributes(self.root))
        self.assertEqual(self.path.read_bytes(), before)

    def test_what_is_not_ours_stays_and_the_block_goes_last(self):
        self.path.write_text("*.png binary\n* text=auto", encoding="utf-8")
        self.assertTrue(update_gitattributes(self.root))
        text = self.path.read_text(encoding="utf-8")
        self.assertTrue(text.startswith("*.png binary\n* text=auto\n\n"), text)
        self.assertTrue(text.endswith(f"{GITATTRIBUTES_BEGIN}\n{LINE_ENDINGS_RULE}\n{GITATTRIBUTES_END}\n"), text)

    def test_only_the_block_is_rewritten(self):
        self.path.write_text(
            f"antes -text\n{GITATTRIBUTES_BEGIN}\nviejo -text\n{GITATTRIBUTES_END}\ndespues -text\n", encoding="utf-8"
        )
        self.assertTrue(update_gitattributes(self.root))
        self.assertEqual(
            self.path.read_text(encoding="utf-8"),
            f"antes -text\n{GITATTRIBUTES_BEGIN}\n{LINE_ENDINGS_RULE}\n{GITATTRIBUTES_END}\ndespues -text\n",
        )


class InitTests(Sandbox):
    def test_rapid_init_writes_the_block(self):
        result = self.rapid("init", "--yes", "--stack", "python-fastapi", "--topology", "backend-only",
                            "--archetype", "mvp", "--agents", "claude")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn(LINE_ENDINGS_RULE, (self.root / ".gitattributes").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
