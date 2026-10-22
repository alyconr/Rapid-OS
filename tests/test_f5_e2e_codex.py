"""F5: the path "empty folder -> init -> feature -> approve -> finish" ends in PASS on any harness."""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import tempfile
import unittest
from unittest import mock
from pathlib import Path

from rapid_os.adapters.evidence_registry import EvidenceRegistry
from rapid_os.adapters.run_registry import RunRegistry
from rapid_os.domain.catalog import load_setup_doc_banks
from rapid_os.domain.project_docs import has_lost_characters, mark_story_done
from rapid_os.orchestration.session import observed_changes

ROOT = Path(__file__).resolve().parents[1]
BRIEF_BANK = load_setup_doc_banks(ROOT / "templates")["brief"]
BRIEF_BODY = (
    "## Problema\nAgendar talleres.\n\n## Usuarios\nOrganizadores.\n\n"
    "## Historias\n- [x] H001: Crear taller\n- [ ] H002: Listar talleres\n- [ ] H003: Inscribirse\n\n"
    "## Notas\n- [ ] H002: esto no es una historia\n"
)
SMOKE_TEST = "import unittest\n\nclass Smoke(unittest.TestCase):\n    def test_smoke(self):\n        self.assertTrue(True)\n"
TEST_COMMAND = f'"{sys.executable}" -m unittest discover -s tests -t .'


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


def approve(root, gate):
    code = (
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
    return subprocess.run([sys.executable, "-c", code], cwd=root, capture_output=True, text=True, env=env)


class TempProject(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)


class ObservedChangesWithoutCommitsTests(TempProject):
    def test_untracked_and_staged_files_minus_the_ones_present_at_start(self):
        git(self.root, "init", "-q")
        (self.root / "old.txt").write_text("x", encoding="utf-8")
        (self.root / "app").mkdir()
        (self.root / "app" / "x.py").write_text("x = 1\n", encoding="utf-8")
        (self.root / "app" / "__pycache__").mkdir()
        (self.root / "app" / "__pycache__" / "x.cpython-312.pyc").write_bytes(b"\0")
        (self.root / ".rapid-os").mkdir()
        (self.root / ".rapid-os" / "session.json").write_text("{}", encoding="utf-8")
        git(self.root, "add", "app/x.py")
        self.assertEqual(observed_changes(self.root, None, ("old.txt",)), ["app/x.py"])

    def test_outside_a_repository_nothing_is_observed(self):
        self.assertEqual(observed_changes(self.root, None, ()), [])


class FinishInARepositoryWithoutCommitsTests(TempProject):
    def test_empty_repo_finish_records_the_file_change_and_passes(self):
        git(self.root, "init", "-q")
        self.assertEqual(
            rapid(self.root, "init", "--yes", "--skip-docs", "--test-command", TEST_COMMAND).returncode, 0
        )
        (self.root / "tests").mkdir()
        (self.root / "tests" / "__init__.py").write_text("", encoding="utf-8")
        (self.root / "tests" / "test_smoke.py").write_text(SMOKE_TEST, encoding="utf-8")
        spec = {
            "title": "App", "mode": "feature", "business_objective": "Tener la app",
            "problem_statement": "No hay app", "scope": ["app"], "acceptance_criteria": ["existe"],
            "tasks": ["T001: Crear"],
        }
        # Not yet written: `start` must see a repository with neither commits nor files of the run.
        shutil_rm(self.root / "tests")
        started = rapid(self.root, "start", "feature", "--spec-file", "-", "--json", stdin=json.dumps(spec))
        self.assertEqual(started.returncode, 0, started.stderr)
        self.assertIsNone(json.loads((self.root / ".rapid-os" / "session.json").read_text("utf-8"))["start_head"])
        (self.root / "app").mkdir()
        (self.root / "app" / "x.py").write_text("x = 1\n", encoding="utf-8")
        (self.root / "tests").mkdir()
        (self.root / "tests" / "__init__.py").write_text("", encoding="utf-8")
        (self.root / "tests" / "test_smoke.py").write_text(SMOKE_TEST, encoding="utf-8")
        gate = drive_to_approval(self, self.root)
        self.assertEqual(approve(self.root, gate).returncode, 0)
        finished = rapid(self.root, "finish", "--json")
        self.assertEqual(finished.returncode, 0, finished.stderr)
        self.assertEqual(json.loads(finished.stdout)["verdict"], "pass")
        run_id = finished_run_id(finished)
        records = EvidenceRegistry(self.root, self.root / ".rapid-os").list(run_id)
        paths = [
            p for record in records if record.kind.value == "file_change" for p in record.payload["paths"]
        ]
        self.assertIn("app/x.py", paths)


def finished_run_id(finished):
    return json.loads(finished.stdout)["run_id"]


def shutil_rm(path):
    import shutil

    shutil.rmtree(path, ignore_errors=True)


def drive_to_approval(case, root, on_implement=None):
    """Follow `rapid next` like an agent until a human gate is waiting; returns its id."""
    for _ in range(25):
        action = json.loads(rapid(root, "next", "--json").stdout)["action"]
        if action["kind"] == "await_human_approval":
            return action["gate_ids"][0]
        if action["kind"] == "implement_task" and on_implement:
            on_implement()
        for key in ("command", "after"):
            if action.get(key):
                result = rapid(root, *action[key][1:])
                case.assertEqual(result.returncode, 0, result.stderr + result.stdout)
    case.fail("the run never reached a human gate")


class HarnessFromConfigToolsTests(TempProject):
    def test_a_project_with_tools_codex_runs_as_codex(self):
        git(self.root, "init", "-q")
        self.assertEqual(
            rapid(self.root, "init", "--yes", "--skip-docs", "--test-command", TEST_COMMAND).returncode, 0
        )
        config_path = self.root / ".rapid-os" / "config.json"
        config = json.loads(config_path.read_text("utf-8"))
        config["tools"] = ["codex"]
        config_path.write_text(json.dumps(config), encoding="utf-8")
        (self.root / "app.py").write_text("x = 1\n", encoding="utf-8")
        spec = {
            "title": "Algo", "mode": "bugfix", "business_objective": "Arreglar",
            "problem_statement": "Falla", "scope": ["app"], "acceptance_criteria": ["no falla"],
            "tasks": ["T001: Arreglar"],
        }
        started = rapid(self.root, "start", "bugfix", "--spec-file", "-", "--json", stdin=json.dumps(spec))
        self.assertEqual(started.returncode, 0, started.stderr)
        self.assertNotIn("RAPID1300", started.stderr)
        session = json.loads((self.root / ".rapid-os" / "session.json").read_text("utf-8"))
        self.assertEqual(session["harness"], "codex")


class LostCharactersTests(unittest.TestCase):
    def test_detection(self):
        self.assertTrue(has_lost_characters("## ?xito\nTodo bien"))
        self.assertTrue(has_lost_characters("?xito"))
        self.assertFalse(has_lost_characters("¿?bien ¿Listo? Sí. ok ? no"))
        self.assertTrue(has_lost_characters("## Decisi?n\nvac?os"))
        self.assertTrue(has_lost_characters("## ?xito"[2:] + "a?b"))
        self.assertFalse(has_lost_characters("## Decisión\n¿Qué? Sí. Listo?\n"))
        self.assertFalse(has_lost_characters("Visita https://x.com/p?id=1 y `a?b` o\n```\nx?y\n```\n"))
        self.assertFalse(has_lost_characters("a ? b, 1?2, _?_"))


class SetupDocLostCharactersTests(TempProject):
    def doc(self, source, text):
        return rapid(self.root, "setup", "doc", "business", "--source", source, "--file", "-", stdin=text)

    def test_drafted_text_with_lost_accents_is_rejected_and_nothing_is_written(self):
        result = self.doc("drafted", "## Objetivo\nUsuarios vac?os\n")
        self.assertEqual(result.returncode, 1)
        self.assertIn("RAPID1415", result.stderr)
        self.assertNotIn("Traceback", result.stderr)
        self.assertFalse((self.root / "docs" / "BUSINESS_RULES.md").exists())

    def test_provided_text_with_lost_accents_is_stored_with_a_warning(self):
        result = self.doc("provided", "## Objetivo\nUsuarios vac?os\n")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("WARNING RAPID1415", result.stderr)
        self.assertIn("vac?os", (self.root / "docs" / "BUSINESS_RULES.md").read_text("utf-8"))

    def test_clean_text_is_written_without_warning(self):
        result = self.doc("provided", "## Objetivo\nUsuarios vacíos\n")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn("RAPID1415", result.stderr)


class ShortcutTemplateTests(unittest.TestCase):
    def test_init_shortcut_warns_about_powershell_pipes(self):
        text = (ROOT / "templates" / "shortcuts" / "rapid-init.md").read_text("utf-8")
        self.assertIn("En Windows PowerShell no envíes el documento por tubería", text)
        self.assertIn("Set-Content -Encoding utf8", text)

    def test_feature_shortcut_asks_for_the_story_tag(self):
        text = (ROOT / "templates" / "shortcuts" / "rapid-feature.md").read_text("utf-8")
        self.assertIn("`story:<ID>`", text)
        self.assertIn("story:H001", text)


class MarkStoryDoneTests(unittest.TestCase):
    DOC = "---\nrapid-doc: brief\nsource: drafted\nstatus: draft\nsha256: old\n---\n" + BRIEF_BODY

    def test_only_the_one_line_changes_and_the_digest_follows_the_body(self):
        new, outcome, written = mark_story_done(self.DOC, BRIEF_BANK, "h002")
        self.assertEqual((outcome, written), ("marked", "H002"))
        before, after = self.DOC.splitlines(), new.splitlines()
        changed = [(a, b) for a, b in zip(before, after) if a != b]
        self.assertEqual(len(before), len(after))
        self.assertEqual(
            changed[0], ("sha256: old", changed[0][1])
        )
        self.assertEqual(changed[1], ("- [ ] H002: Listar talleres", "- [x] H002: Listar talleres"))
        self.assertEqual(len(changed), 2)
        self.assertIn("source: drafted\nstatus: draft", new)
        import hashlib

        body = new.split("---\n", 2)[2]
        self.assertIn(f"sha256: {hashlib.sha256(body.encode('utf-8')).hexdigest()}", new)

    def test_already_done_missing_and_other_sections(self):
        self.assertEqual(mark_story_done(self.DOC, BRIEF_BANK, "H001")[1], "already_done")
        self.assertEqual(mark_story_done(self.DOC, BRIEF_BANK, "H777")[1], "not_found")
        notes_only = self.DOC.replace("- [ ] H002: Listar talleres", "- [ ] H010: Otra")
        self.assertEqual(mark_story_done(notes_only, BRIEF_BANK, "H002")[1], "not_found")

    def test_crlf_lines_keep_their_endings(self):
        crlf = self.DOC.replace("\n", "\r\n")
        new, outcome, _ = mark_story_done(crlf, BRIEF_BANK, "H003")
        self.assertEqual(outcome, "marked")
        self.assertIn("- [x] H003: Inscribirse\r\n", new)


class TickStoryAtFinishTests(TempProject):
    def setUp(self):
        super().setUp()
        for argv in (("init", "-q"), ("config", "user.name", "Rapid"), ("config", "user.email", "r@example.com")):
            git(self.root, *argv)
        (self.root / "tests").mkdir()
        (self.root / "tests" / "__init__.py").write_text("", encoding="utf-8")
        (self.root / "tests" / "test_ok.py").write_text(SMOKE_TEST, encoding="utf-8")
        git(self.root, "add", ".")
        git(self.root, "commit", "-q", "-m", "base")
        self.assertEqual(
            rapid(self.root, "init", "--yes", "--skip-docs", "--test-command", TEST_COMMAND).returncode, 0
        )
        self.brief = self.root / "docs" / "PRODUCT_BRIEF.md"

    def write_brief(self, header="rapid-doc: brief\nsource: drafted\nstatus: draft\nsha256: x\n"):
        self.brief.parent.mkdir(parents=True, exist_ok=True)
        self.brief.write_text(f"---\n{header}---\n{BRIEF_BODY}", encoding="utf-8")

    def run_to_gate(self, tags, work=True):
        spec = {
            "title": "Listar talleres", "mode": "feature", "business_objective": "Ver los talleres",
            "problem_statement": "No hay listado", "scope": ["listado"], "acceptance_criteria": ["se lista"],
            "tasks": ["T001: Listar"], "tags": tags,
        }
        started = rapid(self.root, "start", "feature", "--spec-file", "-", "--json", stdin=json.dumps(spec))
        self.assertEqual(started.returncode, 0, started.stderr)

        def implement():
            if work:
                (self.root / "app").mkdir(exist_ok=True)
                (self.root / "app" / "listado.py").write_text("def listar():\n    return []\n", encoding="utf-8")

        gate = drive_to_approval(self, self.root, implement)
        self.assertEqual(approve(self.root, gate).returncode, 0)

    def test_pass_ticks_only_that_line_keeps_status_and_backs_up(self):
        self.write_brief()
        before = self.brief.read_text("utf-8")
        self.run_to_gate(["story:H002"])
        finished = rapid(self.root, "finish")
        self.assertEqual(finished.returncode, 0, finished.stderr)
        self.assertIn("H002 marcada como hecha en docs/PRODUCT_BRIEF.md", finished.stdout)
        after = self.brief.read_text("utf-8")
        diff = [(a, b) for a, b in zip(before.splitlines(), after.splitlines()) if a != b]
        self.assertEqual([b for _a, b in diff if b.startswith("- ")], ["- [x] H002: Listar talleres"])
        self.assertEqual(len(diff), 2)  # that line and the digest
        self.assertIn("source: drafted\nstatus: draft", after)
        backups = list((self.root / ".rapid-os" / "backups").glob("PRODUCT_BRIEF*"))
        self.assertTrue(backups, "no backup of the brief in .rapid-os/backups")
        self.assertEqual(backups[0].read_text("utf-8"), before)

    def test_unverified_does_not_touch_the_brief_and_says_when_it_will(self):
        self.write_brief()
        before = self.brief.read_text("utf-8")
        self.run_to_gate(["story:H002"], work=False)
        finished = rapid(self.root, "finish")
        self.assertEqual(finished.returncode, 1, finished.stdout + finished.stderr)
        self.assertIn("H002 se marcará cuando el run pase", finished.stdout)
        self.assertEqual(self.brief.read_text("utf-8"), before)

    def test_no_tick_keeps_the_old_suggestion(self):
        self.write_brief()
        before = self.brief.read_text("utf-8")
        self.run_to_gate(["story:H002"])
        finished = rapid(self.root, "finish", "--no-tick")
        self.assertEqual(finished.returncode, 0, finished.stderr)
        self.assertIn("Marca H002 como hecha en docs/PRODUCT_BRIEF.md", finished.stdout)
        self.assertEqual(self.brief.read_text("utf-8"), before)

    def test_missing_story_and_unmanaged_brief_change_nothing(self):
        self.write_brief()
        before = self.brief.read_text("utf-8")
        self.run_to_gate(["story:H404"])
        finished = rapid(self.root, "finish")
        self.assertEqual(finished.returncode, 0, finished.stderr)
        self.assertIn("H404 no existe", finished.stdout)
        self.assertEqual(self.brief.read_text("utf-8"), before)

    def test_brief_without_rapid_doc_frontmatter_is_not_touched(self):
        self.brief.parent.mkdir(parents=True, exist_ok=True)
        self.brief.write_text(BRIEF_BODY, encoding="utf-8")
        self.run_to_gate(["story:H002"])
        finished = rapid(self.root, "finish")
        self.assertEqual(finished.returncode, 0, finished.stderr)
        self.assertIn("no tiene frontmatter rapid-doc", finished.stdout)
        self.assertEqual(self.brief.read_text("utf-8"), BRIEF_BODY)


class SetupAfterFinishTests(TempProject):
    def setup_everything(self, test_command):
        git(self.root, "init", "-q")
        for key, value in (
            ("stack", "generic"), ("topology", "fullstack-baas"), ("archetype", "mvp"), ("ai", "no"),
            ("agents", "codex"), ("test-command", test_command),
        ):
            result = rapid(self.root, "setup", "set", key, value)
            self.assertEqual(result.returncode, 0, result.stderr)
        for doc in ("brief", "business", "data-model", "architecture"):
            self.assertEqual(rapid(self.root, "setup", "doc", doc, "--skip").returncode, 0)
        finished = rapid(self.root, "setup", "finish")
        self.assertEqual(finished.returncode, 0, finished.stderr)

    def config(self):
        return json.loads((self.root / ".rapid-os" / "config.json").read_text("utf-8"))

    def test_set_test_command_after_finish_applies_now_and_stays_finished(self):
        self.setup_everything("none")
        self.assertFalse(self.config().get("test_command"))
        result = rapid(self.root, "setup", "set", "test-command", TEST_COMMAND)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.config()["test_command"][0], sys.executable)
        shown = json.loads(rapid(self.root, "setup", "show", "--json").stdout)
        self.assertTrue(shown["state"]["finished"])
        self.assertEqual(json.loads(rapid(self.root, "setup", "next", "--json").stdout)["kind"], "done")

    def test_scaffold_task_and_rapid1301_point_at_setup_set(self):
        self.setup_everything("none")
        spec = {
            "title": "App", "mode": "feature", "business_objective": "Tener la app",
            "problem_statement": "No hay app", "scope": ["app"], "acceptance_criteria": ["existe"],
            "tasks": ["T001: Crear"],
        }
        started = rapid(self.root, "start", "feature", "--spec-file", "-", "--json", stdin=json.dumps(spec))
        self.assertEqual(started.returncode, 0, started.stderr)
        run_id = json.loads((self.root / ".rapid-os" / "session.json").read_text("utf-8"))["active_run_id"]
        scaffold = RunRegistry(self.root, self.root / ".rapid-os").get_contract(run_id).tasks[0].description
        self.assertIn("Scaffold mínimo con un test que pase", scaffold)
        self.assertIn("Configura el comando con rapid setup set test-command <cmd> antes de cerrarla", scaffold)
        self.assertEqual(rapid(self.root, "task", "start", "T001").returncode, 0)
        done = rapid(self.root, "task", "done", "T001")
        self.assertEqual(done.returncode, 1)
        self.assertIn("RAPID1301", done.stderr)
        self.assertIn("rapid setup set test-command <cmd>", done.stderr)


class EmptyFolderEndToEndTests(SetupAfterFinishTests):
    def test_empty_folder_to_pass_with_codex_and_the_story_ticked(self):
        git(self.root, "init", "-q")  # no commit
        for key, value in (
            ("stack", "generic"), ("topology", "fullstack-baas"), ("archetype", "mvp"), ("ai", "no"),
            ("agents", "codex"), ("test-command", "none"),
        ):
            self.assertEqual(rapid(self.root, "setup", "set", key, value).returncode, 0)
        brief = "## Problema\nAgendar.\n\n## Usuarios\nOrganizadores.\n\n## Historias\n- [ ] H001: Listar talleres\n"
        written = rapid(self.root, "setup", "doc", "brief", "--source", "drafted", "--file", "-", stdin=brief)
        self.assertEqual(written.returncode, 0, written.stderr)
        for doc in ("business", "data-model", "architecture"):
            self.assertEqual(rapid(self.root, "setup", "doc", doc, "--skip").returncode, 0)
        self.assertEqual(rapid(self.root, "setup", "review", "--done").returncode, 0)  # the brief stays a draft
        self.assertEqual(rapid(self.root, "setup", "finish").returncode, 0)
        spec = {
            "title": "Listar talleres", "mode": "feature", "business_objective": "Ver los talleres",
            "problem_statement": "No hay listado", "scope": ["listado"], "acceptance_criteria": ["se lista"],
            "tasks": ["T001: Listar"], "tags": ["story:H001"],
        }
        started = rapid(self.root, "start", "feature", "--spec-file", "-", "--json", stdin=json.dumps(spec))
        self.assertEqual(started.returncode, 0, started.stderr)
        self.assertNotIn("RAPID1300", started.stderr)  # tools: ["codex"] names the harness
        session = json.loads((self.root / ".rapid-os" / "session.json").read_text("utf-8"))
        self.assertEqual(session["harness"], "codex")
        self.assertEqual(rapid(self.root, "setup", "set", "test-command", TEST_COMMAND).returncode, 0)

        def implement():
            (self.root / "app").mkdir(exist_ok=True)
            (self.root / "app" / "x.py").write_text("x = 1\n", encoding="utf-8")
            (self.root / "tests").mkdir(exist_ok=True)
            (self.root / "tests" / "__init__.py").write_text("", encoding="utf-8")
            (self.root / "tests" / "test_smoke.py").write_text(SMOKE_TEST, encoding="utf-8")

        gate = drive_to_approval(self, self.root, implement)
        self.assertEqual(approve(self.root, gate).returncode, 0)
        finished = rapid(self.root, "finish", "--no-tick")
        self.assertEqual(finished.returncode, 0, finished.stderr)
        self.assertIn("verdict PASS", finished.stdout)
        self.assertIn("Marca H001 como hecha en docs/PRODUCT_BRIEF.md", finished.stdout)
        brief_path = self.root / "docs" / "PRODUCT_BRIEF.md"
        self.assertIn("- [ ] H001: Listar talleres", brief_path.read_text("utf-8"))  # --no-tick
        again = rapid(self.root, "finish")  # on the ended run it ticks the story
        self.assertEqual(again.returncode, 0, again.stderr)
        self.assertIn("H001 marcada como hecha en docs/PRODUCT_BRIEF.md", again.stdout)
        text = brief_path.read_text("utf-8")
        self.assertIn("- [x] H001: Listar talleres", text)
        self.assertIn("source: drafted\nstatus: draft", text)


class StdinNulTests(unittest.TestCase):
    """Windows reports a stdin redirected to NUL as a terminal; approve must not believe it."""

    def probe(self, **kwargs):
        code = "from rapid_os.orchestration.lifecycle import stdin_is_windows_nul as f; print(f())"
        env = {**os.environ, "PYTHONPATH": str(ROOT)}
        return subprocess.run(
            [sys.executable, "-c", code], capture_output=True, text=True, env=env, **kwargs
        ).stdout.strip()

    @unittest.skipUnless(sys.platform == "win32", "NUL reports isatty() only on Windows")
    def test_nul_is_detected_on_windows(self):
        self.assertEqual(self.probe(stdin=subprocess.DEVNULL), "True")

    def test_a_pipe_is_never_nul(self):
        self.assertEqual(self.probe(input=""), "False")

    @unittest.skipUnless(sys.platform == "win32", "NUL reports isatty() only on Windows")
    def test_approve_on_nul_stdin_fails_before_touching_the_ledger(self):
        from rapid_os.core.ancestry import AncestryResult
        from rapid_os.orchestration.lifecycle import execute_approve

        with tempfile.TemporaryDirectory() as tmp, open(os.devnull, encoding="utf-8") as nul:
            # In process, with no agent among the ancestors: only the TTY check can refuse.
            with mock.patch("sys.stdin", nul):
                code, message = execute_approve(
                    Path(tmp), Path(tmp) / ".rapid-os", "gate.final-verification",
                    environ={}, ancestry=AncestryResult(()),
                )
        self.assertEqual(code, 1)
        self.assertIn("RAPID1310", message)
        self.assertIn("Stdin is not a TTY", message)

if __name__ == "__main__":
    unittest.main()
