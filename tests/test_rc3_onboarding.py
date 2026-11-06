"""The onboarding and run findings of the rc.2 end-to-end run on Windows with Codex (H-40 to H-50)."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from rapid_os.adapters.project_docs import load_banks
from rapid_os.domain.project_docs import bank_fingerprint, render_managed_doc

ROOT = Path(__file__).resolve().parents[1]


def draft_body(sections):
    return "\n\n".join(f"## {section.titles[0]}\nContenido." for section in sections) + "\n"


class Sandbox(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.base = Path(tmp.name)
        self.root = self.base / "project"
        self.root.mkdir()
        gitconfig = self.base / "gitconfig"
        gitconfig.write_text("[user]\n\tname = T\n\temail = t@example.com\n[init]\n\tdefaultBranch = main\n", encoding="utf-8")
        home = self.base / "home"
        home.mkdir()
        self.env = {
            **{k: v for k, v in os.environ.items() if k not in ("CLAUDECODE", "CLAUDE_CODE_CHILD_SESSION")},
            "GIT_CONFIG_GLOBAL": str(gitconfig),
            "GIT_CONFIG_NOSYSTEM": "1",
            "HOME": str(home),
            "USERPROFILE": str(home),
            "PYTHONPATH": str(ROOT),
            "PYTHONIOENCODING": "utf-8",
            "PYTHONDONTWRITEBYTECODE": "1",
        }

    def rapid(self, *args, stdin=None):
        return subprocess.run(
            [sys.executable, str(ROOT / "rapid.py"), *args],
            cwd=str(self.root),
            env=self.env,
            input=stdin,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=120,
        )

    def ok(self, *args, stdin=None):
        result = self.rapid(*args, stdin=stdin)
        self.assertEqual(result.returncode, 0, f"rapid {args}\n{result.stdout}\n{result.stderr}")
        return result

    def onboard(self, agents="claude", test_command="none", drafted=()):
        """Decide everything and finish. The documents in `drafted` are written by the agent; the others, skipped."""
        for step in (("stack", "python-fastapi"), ("topology", "backend-only"), ("archetype", "mvp"), ("ai", "no"),
                     ("agents", agents), ("test-command", test_command), ("services", "none")):
            self.ok("setup", "set", *step)
        banks = load_banks(None)
        for doc in ("brief", "business", "data-model", "architecture", "deployment"):
            if doc in drafted:
                self.ok("setup", "doc", doc, "--source", "drafted", "--file", "-", stdin=draft_body(banks[doc].required_sections))
            else:
                self.ok("setup", "doc", doc, "--skip")
        if drafted:
            self.ok("setup", "review", "--done")
        self.ok("setup", "finish")

    def doctor_codes(self):
        report = json.loads(self.rapid("doctor", "--json").stdout)
        return [d["code"] for d in report["diagnostics"]]


class DoctorOverlapTests(Sandbox):
    """H-40: RAPID1321 compares the agents chosen in the project, not every harness Rapid OS knows."""

    def test_a_project_with_only_codex_gets_no_warning(self):
        self.onboard(agents="codex")
        self.assertNotIn("RAPID1321", self.doctor_codes())

    def test_a_real_overlap_among_the_chosen_agents_still_warns(self):
        self.onboard(agents="cursor,codex")
        self.assertIn("RAPID1321", self.doctor_codes())

    def test_codex_and_antigravity_write_one_folder_so_nothing_overlaps(self):
        self.onboard(agents="codex,antigravity")
        self.assertNotIn("RAPID1321", self.doctor_codes())

    def test_without_a_configured_project_there_is_no_warning(self):
        self.assertNotIn("RAPID1321", self.doctor_codes())


class ConfirmedWithAnEarlierBankTests(Sandbox):
    """H-41: a section that became required after the confirmation is not a failure of `validate --strict`."""

    def setUp(self):
        super().setUp()
        self.bank = load_banks(None)["data-model"]
        self.onboard(test_command="python -m unittest", drafted=("data-model",))
        self.ok("setup", "doc", "data-model", "--confirm")
        # Nothing else to warn about: `--strict` depends on the document alone.
        (self.root / ".rapid-os" / "standards" / "business.md").write_text("# Reglas\n", encoding="utf-8")

    def drop_a_required_section(self):
        """The body as an earlier version accepted it: without the last required section."""
        body = draft_body(self.bank.required_sections[:-1])
        (self.root / self.bank.file).write_text(render_managed_doc("data-model", "drafted", "confirmed", body), encoding="utf-8")

    def setup_json(self):
        return json.loads((self.root / ".rapid-os" / "setup.json").read_text(encoding="utf-8"))

    def write_setup_json(self, data):
        (self.root / ".rapid-os" / "setup.json").write_text(json.dumps(data), encoding="utf-8")

    def rapid1403(self):
        report = json.loads(self.rapid("validate", "--json").stdout)
        return [d for d in report["diagnostics"] if d["code"] == "RAPID1403"]

    def test_confirming_records_the_sections(self):
        self.assertEqual(self.setup_json()["docs"]["data-model"]["confirmed_bank"], bank_fingerprint(self.bank))

    def test_no_record_counts_as_earlier(self):
        self.drop_a_required_section()
        data = self.setup_json()
        del data["docs"]["data-model"]["confirmed_bank"]
        self.write_setup_json(data)
        [diagnostic] = self.rapid1403()
        self.assertEqual(diagnostic["level"], "info")
        self.assertIn("rapid setup doc data-model --reopen", diagnostic["hint"])
        strict = self.rapid("validate", "--strict")
        self.assertEqual(strict.returncode, 0, strict.stdout)

    def test_a_different_record_counts_as_earlier(self):
        self.drop_a_required_section()
        data = self.setup_json()
        data["docs"]["data-model"]["confirmed_bank"] = "0" * 64
        self.write_setup_json(data)
        self.assertEqual([d["level"] for d in self.rapid1403()], ["info"])

    def test_confirmed_with_the_current_bank_keeps_the_warning(self):
        self.drop_a_required_section()
        self.assertEqual([d["level"] for d in self.rapid1403()], ["warning"])
        self.assertNotEqual(self.rapid("validate", "--strict").returncode, 0)

    def test_an_unconfirmed_draft_keeps_the_warning(self):
        self.drop_a_required_section()
        path = self.root / self.bank.file
        path.write_text(path.read_text(encoding="utf-8").replace("status: confirmed", "status: draft"), encoding="utf-8")
        data = self.setup_json()
        del data["docs"]["data-model"]["confirmed_bank"]
        self.write_setup_json(data)
        self.assertEqual([d["level"] for d in self.rapid1403()], ["warning"])


if __name__ == "__main__":
    unittest.main()
