"""Seed of the first feature from the product brief, and the story hint of `rapid finish`."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from rapid_os.adapters.project_docs import build_brief_seed
from rapid_os.domain.catalog import load_setup_doc_banks
from rapid_os.domain.project_docs import open_stories

ROOT = Path(__file__).resolve().parents[1]
TEMPLATES = ROOT / "templates"
BRIEF_BANK = load_setup_doc_banks(TEMPLATES)["brief"]

BRIEF_BODY = (
    "## Problema\nAgendar talleres.\n\n## Usuarios\nOrganizadores.\n\n"
    "## Historias\n- [x] H001: Crear taller\n- [ ] H002: Listar talleres\n- [ ] H003: Inscribirse\n\n"
    "## Notas\n- [ ] H099: esto no es una historia\n"
)


def rapid(cwd, *argv, stdin=None):
    env = {
        **{k: v for k, v in os.environ.items() if k not in ("CLAUDECODE", "CLAUDE_CODE_CHILD_SESSION")},
        "PYTHONPATH": str(ROOT),
        "PYTHONIOENCODING": "utf-8",
    }
    return subprocess.run(
        [sys.executable, "-m", "rapid_os.cli.main", *argv],
        cwd=cwd, input=stdin, capture_output=True, text=True, encoding="utf-8", env=env,
    )


def write_doc(root: Path, relative: str, doc_id: str, body: str, *, source="drafted", status="draft"):
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        f"---\nrapid-doc: {doc_id}\nsource: {source}\nstatus: {status}\nsha256: x\n---\n{body}", encoding="utf-8"
    )


class OpenStoriesTests(unittest.TestCase):
    def test_only_unchecked_stories_of_the_stories_section_in_order(self):
        stories = open_stories(BRIEF_BODY, BRIEF_BANK)
        self.assertEqual(
            stories,
            ({"id": "H002", "text": "Listar talleres"}, {"id": "H003", "text": "Inscribirse"}),
        )

    def test_english_section_and_loose_formats(self):
        body = "## Stories\n* [ ] H1 - First\n- [ ]  H2.  Second\n- [X] H3: done\n- plain line\n"
        self.assertEqual(
            [s["id"] for s in open_stories(body, BRIEF_BANK)],
            ["H1", "H2"],
        )

    def test_no_stories_section_or_everything_done(self):
        self.assertEqual(open_stories("## Problema\n- [ ] H001: x\n", BRIEF_BANK), ())
        self.assertEqual(open_stories("## Historias\n- [x] H001: x\n", BRIEF_BANK), ())


class SeedTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)

    def author_spec(self, *argv):
        result = rapid(self.root, *(argv or ("next", "--json")))
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout)

    def test_draft_brief_gives_the_open_stories_and_confirmed_false(self):
        write_doc(self.root, "docs/PRODUCT_BRIEF.md", "brief", BRIEF_BODY)
        action = self.author_spec()["action"]
        self.assertEqual(action["kind"], "author_spec")
        self.assertEqual(
            action["seed"],
            {
                "source": "docs/PRODUCT_BRIEF.md",
                "confirmed": False,
                "stories": [
                    {"id": "H002", "text": "Listar talleres"},
                    {"id": "H003", "text": "Inscribirse"},
                ],
                "business_doc": None,
                "data_model_doc": None,
            },
        )

    def test_confirmed_or_provided_brief_is_confirmed_and_docs_are_named(self):
        write_doc(self.root, "docs/PRODUCT_BRIEF.md", "brief", BRIEF_BODY, source="provided", status="confirmed")
        write_doc(self.root, "docs/BUSINESS_RULES.md", "business", "## Objetivo\nx\n")
        write_doc(self.root, "docs/DATA_MODEL.md", "data-model", "## Entidades\nx\n")
        seed = self.author_spec()["action"]["seed"]
        self.assertTrue(seed["confirmed"])
        self.assertEqual(seed["business_doc"], "docs/BUSINESS_RULES.md")
        self.assertEqual(seed["data_model_doc"], "docs/DATA_MODEL.md")

    def test_without_a_brief_the_action_is_exactly_what_it_was(self):
        action = self.author_spec()["action"]
        self.assertNotIn("seed", action)
        self.assertEqual(
            sorted(action),
            ["after", "command", "instructions", "kind", "spec_template"],
        )

    def test_brief_without_open_stories_or_unmanaged_brief_has_no_seed(self):
        write_doc(self.root, "docs/PRODUCT_BRIEF.md", "brief", "## Historias\n- [x] H001: hecha\n")
        self.assertNotIn("seed", self.author_spec()["action"])
        (self.root / "docs" / "PRODUCT_BRIEF.md").write_text(BRIEF_BODY, encoding="utf-8")  # no frontmatter
        self.assertNotIn("seed", self.author_spec()["action"])

    def test_start_without_a_spec_carries_the_seed_and_other_modes_do_not(self):
        write_doc(self.root, "docs/PRODUCT_BRIEF.md", "brief", BRIEF_BODY)
        subprocess.run(["git", "init", "-q"], cwd=self.root, check=True)
        self.assertEqual(rapid(self.root, "init", "--yes", "--skip-docs").returncode, 0)
        started = rapid(self.root, "start", "feature", "--json")
        self.assertEqual(started.returncode, 0, started.stderr)
        self.assertEqual(len(json.loads(started.stdout)["action"]["seed"]["stories"]), 2)
        (self.root / "app.py").write_text("print('hi')\n", encoding="utf-8")  # bugfix needs code to fix
        bugfix = rapid(self.root, "start", "bugfix", "--json")
        self.assertEqual(bugfix.returncode, 0, bugfix.stderr)
        self.assertNotIn("seed", json.loads(bugfix.stdout)["action"])

    def test_adapter_returns_none_without_a_brief(self):
        self.assertIsNone(build_brief_seed(self.root, self.root / ".rapid-os", TEMPLATES))


class FinishStoryHintTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)
        for argv in (("init", "-q"), ("config", "user.name", "Rapid"), ("config", "user.email", "r@example.com")):
            subprocess.run(["git", *argv], cwd=self.root, check=True, capture_output=True)
        (self.root / "tests").mkdir()
        (self.root / "tests" / "__init__.py").write_text("", encoding="utf-8")
        (self.root / "tests" / "test_ok.py").write_text(
            "import unittest\n\nclass T(unittest.TestCase):\n    def test_ok(self):\n        self.assertTrue(True)\n",
            encoding="utf-8",
        )
        subprocess.run(["git", "add", "."], cwd=self.root, check=True, capture_output=True)
        subprocess.run(["git", "commit", "-q", "-m", "base"], cwd=self.root, check=True, capture_output=True)
        command = f'"{sys.executable}" -m unittest discover -s tests -t .'
        self.assertEqual(rapid(self.root, "init", "--yes", "--skip-docs", "--test-command", command).returncode, 0)

    def run_to_the_end(self, tags):
        spec = {
            "title": "Listar talleres", "mode": "feature", "business_objective": "Ver los talleres",
            "problem_statement": "No hay listado", "scope": ["listado"], "acceptance_criteria": ["se lista"],
            "tasks": ["T001: Listar"], "tags": tags,
        }
        started = rapid(self.root, "start", "feature", "--spec-file", "-", "--json", stdin=json.dumps(spec))
        self.assertEqual(started.returncode, 0, started.stderr)
        gate = None
        for _ in range(20):
            output = json.loads(rapid(self.root, "next", "--json").stdout)
            action = output["action"]
            if action["kind"] == "await_human_approval":
                gate = action["gate_ids"][0]
                break
            if action["kind"] == "implement_task":
                # Do the task like an agent would: change a real project file (the run records it
                # at `finish`; do not rely on `rapid check` leaving bytecode behind).
                feature = self.root / "app" / "listado.py"
                feature.parent.mkdir(parents=True, exist_ok=True)
                feature.write_text("def listar():\n    return []\n", encoding="utf-8")
            for key in ("command", "after"):
                if action.get(key):
                    self.assertEqual(rapid(self.root, *action[key][1:]).returncode, 0)
        self.assertIsNotNone(gate)
        approve = (
            "import sys, unittest.mock as mock, rapid_os.cli.main as m; "
            f"sys.argv = ['rapid', 'approve', '{gate}']; "
            "mock.patch('sys.stdin.isatty', return_value=True).start(); "
            "mock.patch('rapid_os.orchestration.lifecycle.stdin_is_windows_nul', return_value=False).start(); "
            "mock.patch('rapid_os.orchestration.lifecycle.read_ancestry', "
            "return_value=__import__('rapid_os.core.ancestry', fromlist=['x']).AncestryResult(())).start(); "
            f"mock.patch('builtins.input', return_value='aprobar {gate}').start(); sys.exit(m.main())"
        )
        env = {k: v for k, v in os.environ.items() if k not in ("CLAUDECODE", "CLAUDE_CODE_CHILD_SESSION")}
        env["PYTHONPATH"] = str(ROOT)
        result = subprocess.run([sys.executable, "-c", approve], cwd=self.root, capture_output=True, text=True, env=env)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_finish_ticks_the_story_of_a_passing_run(self):
        write_doc(self.root, "docs/PRODUCT_BRIEF.md", "brief", BRIEF_BODY)
        self.run_to_the_end(["story:H002"])
        finished = rapid(self.root, "finish")
        self.assertEqual(finished.returncode, 0, finished.stderr)
        self.assertIn("H002 marcada como hecha en docs/PRODUCT_BRIEF.md", finished.stdout)
        text = (self.root / "docs" / "PRODUCT_BRIEF.md").read_text(encoding="utf-8")
        self.assertIn("- [x] H002: Listar talleres", text)
        self.assertIn("- [ ] H003: Inscribirse", text)

    def test_no_tick_only_suggests_and_never_edits_the_brief(self):
        write_doc(self.root, "docs/PRODUCT_BRIEF.md", "brief", BRIEF_BODY)
        before = (self.root / "docs" / "PRODUCT_BRIEF.md").read_text(encoding="utf-8")
        self.run_to_the_end(["story:H002"])
        finished = rapid(self.root, "finish", "--no-tick")
        self.assertEqual(finished.returncode, 0, finished.stderr)
        self.assertIn("Marca H002 como hecha en docs/PRODUCT_BRIEF.md", finished.stdout)
        self.assertEqual((self.root / "docs" / "PRODUCT_BRIEF.md").read_text(encoding="utf-8"), before)

    def test_json_keeps_stdout_as_the_report_and_the_hint_goes_to_stderr(self):
        self.run_to_the_end(["story:H002"])  # no brief: nothing to tick, the person is told
        as_json = rapid(self.root, "finish", "--json")
        self.assertEqual(json.loads(as_json.stdout)["verdict"], "pass")
        self.assertIn("H002", as_json.stderr)

    def test_after_a_finished_run_next_offers_the_next_open_story(self):
        write_doc(self.root, "docs/PRODUCT_BRIEF.md", "brief", BRIEF_BODY)
        self.run_to_the_end(["story:H002"])
        finished = rapid(self.root, "finish")
        self.assertEqual(finished.returncode, 0, finished.stderr)
        self.assertIn("Rapid OS no hace commit: revisa los cambios y haz commit tú", finished.stdout)
        # The session still points at the closed run, yet `next` moves on to the open story (H003).
        action = json.loads(rapid(self.root, "next", "--json").stdout)
        self.assertEqual(action["action"]["kind"], "author_spec")
        self.assertEqual([story["id"] for story in action["action"]["seed"]["stories"]], ["H003"])
        self.assertIn("ya terminó", action["notes"][0])

    def test_with_every_story_done_next_still_says_done(self):
        self.run_to_the_end(["story:H002"])  # no brief: nothing to offer
        self.assertEqual(rapid(self.root, "finish").returncode, 0)
        self.assertEqual(json.loads(rapid(self.root, "next", "--json").stdout)["action"]["kind"], "done")

    def test_finish_json_keeps_the_no_commit_line_on_stderr(self):
        self.run_to_the_end(["backend"])
        as_json = rapid(self.root, "finish", "--json")
        self.assertEqual(json.loads(as_json.stdout)["verdict"], "pass")
        self.assertIn("Rapid OS no hace commit", as_json.stderr)

    def test_setup_story_reopen_changes_only_that_line(self):
        write_doc(self.root, "docs/PRODUCT_BRIEF.md", "brief", BRIEF_BODY)
        self.run_to_the_end(["story:H002"])
        self.assertEqual(rapid(self.root, "finish").returncode, 0)
        brief = self.root / "docs" / "PRODUCT_BRIEF.md"
        done = brief.read_text(encoding="utf-8")
        self.assertIn("- [x] H002: Listar talleres", done)
        reopened = rapid(self.root, "setup", "story", "h002", "--reopen")
        self.assertEqual(reopened.returncode, 0, reopened.stderr)
        self.assertIn("H002 reabierta", reopened.stdout)
        text = brief.read_text(encoding="utf-8")
        self.assertEqual(
            # the frontmatter sha256 follows the body, as it does when `finish` ticks the line
            [line for line in done.splitlines() if line not in text.splitlines() and not line.startswith("sha256:")],
            ["- [x] H002: Listar talleres"],
        )
        self.assertIn("- [ ] H002: Listar talleres", text)
        self.assertIn("- [x] H001: Crear taller", text)  # a done story that was not named stays done
        self.assertIn("rapid-doc: brief", text)
        self.assertIn("status: draft", text)  # a draft stays a draft
        # Reopening twice is harmless; an unknown story and a missing flag are RAPID1413.
        again = rapid(self.root, "setup", "story", "H002", "--reopen")
        self.assertEqual(again.returncode, 0)
        self.assertIn("ya estaba sin marcar", again.stdout)
        unknown = rapid(self.root, "setup", "story", "H077", "--reopen")
        self.assertEqual(unknown.returncode, 1)
        self.assertIn("RAPID1413", unknown.stderr)
        self.assertEqual(rapid(self.root, "setup", "story", "H002").returncode, 1)
        # And the story is offered again.
        next_action = json.loads(rapid(self.root, "next", "--json").stdout)["action"]
        self.assertEqual([s["id"] for s in next_action["seed"]["stories"]], ["H002", "H003"])

    def test_evidence_artifacts_are_stored_with_a_short_name_and_keep_their_source(self):
        self.run_to_the_end(["backend"])
        records = sorted((self.root / ".rapid-os" / "evidence").glob("*/records/E*.json"))
        artifacts = [a for record in records for a in json.loads(record.read_text("utf-8"))["artifacts"]]
        self.assertTrue(artifacts)
        for artifact in artifacts:
            parts = artifact["path"].split("/")
            self.assertEqual(len(parts), 6, artifact["path"])  # .rapid-os/evidence/<run>/artifacts/<E>/<name>
            self.assertRegex(parts[-1], r"^\d+\.log$")
            self.assertRegex(artifact["source"], r"^\.rapid-os/scratch/checks/[^/]+/\d+\.log$")
            self.assertTrue((self.root / artifact["path"]).is_file())
        evidence_dir = self.root / ".rapid-os" / "evidence"
        longest = max(len(path.relative_to(self.root).as_posix()) for path in evidence_dir.rglob("*") if path.is_file())
        self.assertLess(longest, 120)  # it was ~191 characters with the source path copied inside

    def test_a_spec_without_a_story_tag_gets_no_hint(self):
        self.run_to_the_end(["backend"])
        finished = rapid(self.root, "finish")
        self.assertEqual(finished.returncode, 0, finished.stderr)
        self.assertNotIn("Marca", finished.stdout)


if __name__ == "__main__":
    unittest.main()
