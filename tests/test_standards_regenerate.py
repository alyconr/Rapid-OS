"""H-79: the standards of an existing project are not updated with the version.

After installing rc.4, the agent did not find in talleres-rc2 the supply-chain rules (pnpm, uv) that rc.4 added,
because `.rapid-os/standards/*.md` were written by the rc.2 onboarding and nothing regenerated them. Now the
standards Rapid OS writes from templates (security.md, coding-rules.md) end with a stamp with the digest of their
body; `rapid doctor` reports each one this version would write differently (RAPID1444) and
`rapid setup standards --regenerate` replaces the ones nobody edited (copy in .rapid-os/backups/), writes
`<file>.new` beside an edited or unstamped one, and regenerates AGENTS.md/CLAUDE.md.
"""

from __future__ import annotations

import json
from pathlib import Path
import unittest

from rapid_os.domain.standard_stamp import stamp_standard, standard_state, strip_standard_stamp
from tests.test_ci_component_dirs import TALLERES
from tests.test_no_git import GitIsolated

ROOT = Path(__file__).resolve().parents[1]


class StampTests(unittest.TestCase):
    def test_states(self):
        current = stamp_standard("# Seguridad\n\n- regla uv\n", "security")
        self.assertTrue(current.endswith(" -->\n"))
        self.assertIn("<!-- rapid-os-standard: security sha256=", current)
        self.assertEqual(standard_state(current, current), "current")
        self.assertEqual(standard_state(current.replace("\n", "\r\n"), current), "current")  # core.autocrlf
        older = stamp_standard("# Seguridad\n\n- regla vieja\n", "security")
        self.assertEqual(standard_state(older, current), "outdated")
        self.assertEqual(standard_state(older.replace("vieja", "mía"), current), "edited")
        self.assertEqual(standard_state("# Seguridad\n\n- regla vieja\n", current), "unmarked")

    def test_strip_gives_back_the_body(self):
        body = "# Reglas\n\n- una\n"
        self.assertEqual(strip_standard_stamp(stamp_standard(body, "coding-rules")), body)
        self.assertEqual(strip_standard_stamp(body), body)
        self.assertEqual(strip_standard_stamp(stamp_standard("sin salto", "x")), "sin salto\n")


class DoctorAndRegenerateStandardsTests(GitIsolated):
    def setUp(self):
        super().setUp()
        path = self.root / ".rapid-os" / "setup.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(TALLERES.to_dict(), indent=2), encoding="utf-8")
        result = self.rapid("setup", "finish")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.security = self.root / ".rapid-os" / "standards" / "security.md"
        self.agents_md = self.root / "AGENTS.md"

    def doctor_1444(self):
        report = json.loads(self.rapid("doctor", "--json").stdout)
        return [d for d in report["diagnostics"] if d["code"] == "RAPID1444"]

    def standards(self, *args):
        result = self.rapid("setup", "standards", "--json", *args)
        self.assertEqual(result.returncode, 0, result.stderr)
        return {item["file"]: item for item in json.loads(result.stdout)["standards"]}

    def test_a_new_project_is_current_and_the_agent_context_has_no_stamp(self):
        self.assertIn("<!-- rapid-os-standard: security sha256=", self.security.read_text("utf-8"))
        self.assertEqual({item["status"] for item in self.standards().values()}, {"current"})
        self.assertEqual(self.doctor_1444(), [])
        self.assertNotIn("rapid-os-standard", self.agents_md.read_text("utf-8"))

    def test_a_stamped_standard_nobody_edited_is_replaced_and_agents_md_regenerated(self):
        old = stamp_standard("# Seguridad de una versión anterior\n\n- sin reglas de uv\n", "security")
        self.security.write_text(old, encoding="utf-8")
        self.agents_md.write_text("# AGENTS.md viejo\n", encoding="utf-8")
        [diagnostic] = self.doctor_1444()
        self.assertEqual(diagnostic["level"], "warning")
        self.assertIn("rapid setup standards --regenerate", diagnostic["hint"])
        self.assertEqual(self.standards()[".rapid-os/standards/security.md"]["status"], "outdated")
        regenerated = self.standards("--regenerate")[".rapid-os/standards/security.md"]
        self.assertEqual(regenerated["action"], "replaced")
        self.assertEqual(standard_state(self.security.read_text("utf-8"), self.security.read_text("utf-8")), "current")
        self.assertNotIn("sin reglas de uv", self.security.read_text("utf-8"))
        backups = list((self.root / ".rapid-os" / "backups").glob("security.md.*"))
        self.assertEqual([b.read_text("utf-8") for b in backups], [old])
        self.assertNotEqual(self.agents_md.read_text("utf-8"), "# AGENTS.md viejo\n")
        self.assertIn(strip_standard_stamp(self.security.read_text("utf-8")).strip()[:40], self.agents_md.read_text("utf-8"))
        self.assertEqual(self.doctor_1444(), [])

    def test_an_edited_standard_gets_a_new_file_beside_it(self):
        edited = self.security.read_text("utf-8").replace("# ", "# (mío) ", 1)
        self.security.write_text(edited, encoding="utf-8")
        [diagnostic] = self.doctor_1444()
        self.assertEqual(diagnostic["level"], "info")
        regenerated = self.standards("--regenerate")[".rapid-os/standards/security.md"]
        self.assertEqual((regenerated["status"], regenerated["action"]), ("edited", "new"))
        self.assertEqual(self.security.read_text("utf-8"), edited)
        new = self.security.with_name("security.md.new")
        self.assertEqual(standard_state(new.read_text("utf-8"), new.read_text("utf-8")), "current")
        self.assertIn("<!-- rapid-os-standard: security sha256=", new.read_text("utf-8"))

    def test_an_unstamped_rc2_standard_gets_a_new_file_and_the_text_names_it(self):
        rc2 = strip_standard_stamp(self.security.read_text("utf-8")).replace("uv", "pip")
        self.security.write_text(rc2, encoding="utf-8")
        [diagnostic] = self.doctor_1444()
        self.assertEqual(diagnostic["level"], "warning")
        self.assertIn("no lleva la marca de Rapid OS", diagnostic["message"])
        text = self.rapid("setup", "standards").stdout
        self.assertIn(".rapid-os/standards/security.md: sin la marca de Rapid OS", text)
        self.assertIn("rapid setup standards --regenerate", text)
        text = self.rapid("setup", "standards", "--regenerate").stdout
        self.assertIn("no se toca; el nuevo está en .rapid-os/standards/security.md.new", text)
        self.assertEqual(self.security.read_text("utf-8"), rc2)
        self.assertTrue(self.security.with_name("security.md.new").is_file())

    def test_after_renaming_the_new_file_the_agent_files_follow_and_doctor_says_so_until_then(self):
        # Review of PR #126: after renaming security.md.new, AGENTS.md kept the old text and nothing said so.
        rc2 = strip_standard_stamp(self.security.read_text("utf-8")).replace("uv", "pip")
        self.security.write_text(rc2, encoding="utf-8")
        self.rapid("setup", "standards", "--regenerate")  # brings AGENTS.md in line with the rc2 file
        text = self.rapid("setup", "standards", "--regenerate").stdout
        self.assertIn(
            "después de renombrarlo, vuelve a ejecutar `rapid setup standards --regenerate` para regenerar "
            "AGENTS.md/CLAUDE.md",
            text,
        )
        pending = [d for d in self.doctor_1444() if ".new sigue al lado" in d["message"]]
        self.assertEqual(len(pending), 1, self.doctor_1444())
        self.assertEqual(pending[0]["level"], "info")
        self.assertIn("compáralo y renómbralo, o bórralo", pending[0]["message"])

        new = self.security.with_name("security.md.new")
        new.replace(self.security)
        self.assertIn("pip", self.agents_md.read_text("utf-8"))  # still the old standard
        self.assertEqual(self.doctor_1444(), [])
        self.rapid("setup", "standards", "--regenerate")
        self.assertIn(strip_standard_stamp(self.security.read_text("utf-8")).strip()[-60:], self.agents_md.read_text("utf-8"))

    def test_a_missing_standard_is_written(self):
        rules = self.root / ".rapid-os" / "standards" / "coding-rules.md"
        rules.unlink()
        self.assertEqual(self.standards()[".rapid-os/standards/coding-rules.md"]["status"], "missing")
        self.assertEqual(self.standards("--regenerate")[".rapid-os/standards/coding-rules.md"]["action"], "written")
        self.assertTrue(rules.is_file())


if __name__ == "__main__":
    unittest.main()
