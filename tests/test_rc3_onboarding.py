"""The onboarding and run findings of the rc.2 end-to-end run on Windows with Codex (H-40 to H-50)."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from rapid_os.adapters.agents.base import AGENT_BACKUPS_KEPT
from rapid_os.adapters.project_docs import load_banks
from rapid_os.domain.project_docs import bank_fingerprint, render_managed_doc
from rapid_os.orchestration.setup_conductor import REVIEW_CONSEQUENCES

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


class ResearchTaskDoneTests(Sandbox):
    """H-42: closing a research task never runs the test command, which often cannot pass yet."""

    SPEC = {
        "title": "Comparar opciones",
        "mode": "research",
        "business_objective": "Decidir",
        "problem_statement": "No hay datos",
        "scope": ["opciones"],
        "acceptance_criteria": ["Hay una recomendación"],
        "tasks": ["T001: Comparar", "T002: Concluir"],
    }

    def setUp(self):
        super().setUp()
        self.onboard()
        config = self.root / ".rapid-os" / "config.json"
        data = json.loads(config.read_text(encoding="utf-8"))
        data["test_command"] = [sys.executable, "-c", "raise SystemExit(2)"]
        config.write_text(json.dumps(data), encoding="utf-8")

    def start(self, mode="research"):
        spec = {**self.SPEC, "mode": mode}
        self.ok("start", mode, "--spec-file", "-", "--json", stdin=json.dumps(spec, ensure_ascii=False))

    def run_id(self):
        return next((self.root / ".rapid-os" / "runs").iterdir()).name

    def check_records(self):
        return [
            record for record in json.loads(self.ok("evidence", "list", "--run", self.run_id(), "--json").stdout)["records"]
            if record["producer"] == "rapid:check"
        ]

    def task(self, task_id):
        state = json.loads(self.ok("run", "show", self.run_id(), "--json").stdout)["state"]
        task = next(t for t in state["tasks"] if t["id"] == task_id)
        return {key: value for key, value in task.items() if key != "id"}

    def test_without_the_flag_it_is_the_same_record_as_with_it(self):
        self.start()
        self.ok("task", "start", "T001")
        plain = self.ok("task", "done", "T001")
        self.assertIn("research", plain.stderr)
        self.assertIn("UNVERIFIED", plain.stderr)
        self.assertEqual(len(plain.stderr.strip().splitlines()), 1, plain.stderr)
        self.ok("task", "start", "T002")
        flagged = self.ok("task", "done", "T002", "--no-check")
        self.assertIn("UNVERIFIED", flagged.stderr)
        self.assertEqual(self.task("T001")["status"], "done")
        self.assertEqual(self.check_records(), [])
        self.assertEqual(self.task("T001").keys(), self.task("T002").keys())
        for key in self.task("T001").keys() - {"description"}:
            self.assertEqual(
                str(self.task("T001")[key]).replace("T001", "T00N"), str(self.task("T002")[key]).replace("T002", "T00N"), key
            )

    def test_existing_check_evidence_is_kept_and_the_tests_do_not_run_again(self):
        self.start()
        self.ok("task", "start", "T001")
        self.ok("check", "--task", "T001", "--", sys.executable, "-c", "pass")
        self.assertEqual(len(self.check_records()), 1)
        done = self.ok("task", "done", "T001")
        self.assertIn("rapid check", done.stderr)
        self.assertNotIn("UNVERIFIED", done.stderr)
        self.assertEqual(len(self.check_records()), 1)

    def test_a_feature_run_still_runs_the_tests(self):
        self.start("feature")
        self.ok("task", "start", "T001")
        done = self.rapid("task", "done", "T001")
        self.assertEqual(done.returncode, 2, done.stdout + done.stderr)
        self.assertIn("Verification tests failed", done.stderr)


class InitShortcutTests(unittest.TestCase):
    """H-43: the decisions of a project are not taken from what the agent remembers of other projects."""

    def test_the_decisions_are_the_persons_in_each_project(self):
        text = (ROOT / "templates" / "shortcuts" / "rapid-init.md").read_text(encoding="utf-8")
        self.assertIn("Agentes, arquetipo, topología, IA y comando de test son decisiones de la persona", text)
        self.assertIn("memorias u otros proyectos solo puedes ofrecerlo como opción recomendada", text)
        self.assertIn("diciendo de dónde sale", text)
        self.assertIn("distinto de lo que recomienda el catálogo", text)
        self.assertIn("ofrece primero `rapid setup set test-command --recommended`", text)


class UnconfirmedDocsDuringRunsTests(Sandbox):
    """H-47: `rapid start` and `rapid next` say which drafts no person has confirmed."""

    SPEC = {
        "title": "Crear taller",
        "mode": "research",
        "business_objective": "Decidir",
        "problem_statement": "No hay datos",
        "scope": ["talleres"],
        "acceptance_criteria": ["Hay una recomendación"],
        "tasks": ["T001: Comparar"],
    }
    EXPECTED = [{"id": "business", "file": "docs/BUSINESS_RULES.md"}]

    def start(self, *extra):
        return self.ok("start", "research", "--spec-file", "-", *extra, stdin=json.dumps(self.SPEC, ensure_ascii=False))

    def test_start_and_next_list_a_draft(self):
        self.onboard(drafted=("business",))
        action = json.loads(self.start("--json").stdout)["action"]
        self.assertEqual(action["unconfirmed_docs"], self.EXPECTED)
        action = json.loads(self.ok("next", "--json").stdout)["action"]
        self.assertEqual(action["unconfirmed_docs"], self.EXPECTED)

    def test_the_author_spec_action_lists_it_too(self):
        self.onboard(drafted=("business",))
        action = json.loads(self.ok("next", "--json").stdout)["action"]
        self.assertEqual(action["kind"], "author_spec")
        self.assertEqual(action["unconfirmed_docs"], self.EXPECTED)

    def test_the_text_output_says_it_in_one_line_with_the_command(self):
        self.onboard(drafted=("business",))
        for output in (self.start().stdout, self.ok("next").stdout):
            [line] = [line for line in output.splitlines() if "sin confirmar" in line]
            self.assertIn("business (docs/BUSINESS_RULES.md)", line)
            self.assertIn("rapid setup doc <id> --confirm", line)

    def test_a_confirmed_document_is_not_listed(self):
        self.onboard(drafted=("business",))
        self.ok("setup", "doc", "business", "--confirm")
        self.assertNotIn("unconfirmed_docs", json.loads(self.start("--json").stdout)["action"])
        self.assertNotIn("unconfirmed_docs", json.loads(self.ok("next", "--json").stdout)["action"])
        self.assertNotIn("sin confirmar", self.ok("next").stdout)

    def test_the_review_describes_what_happens(self):
        text = REVIEW_CONSEQUENCES["keep_draft"]
        self.assertNotIn("cada run te recuerda", text)
        for needle in ("rapid start", "rapid next", "RAPID1408", "rapid setup doc <id> --confirm"):
            self.assertIn(needle, text)

    def test_the_work_shortcuts_ask_and_never_confirm(self):
        for mode in ("feature", "bugfix", "refactor", "hardening", "research", "next"):
            text = (ROOT / "templates" / "shortcuts" / f"rapid-{mode}.md").read_text(encoding="utf-8")
            with self.subTest(mode=mode):
                self.assertIn("`action.unconfirmed_docs`", text)
                self.assertIn("una vez al empezar el run", text)
                self.assertIn("No los trates como reglas ni los confirmes por tu cuenta", text)


class DefaultRunTests(Sandbox):
    """H-48: the read-only commands find the run by themselves."""

    def start_and_abort(self, title):
        spec = {
            "title": title,
            "mode": "research",
            "business_objective": "Decidir",
            "problem_statement": "No hay datos",
            "scope": ["talleres"],
            "acceptance_criteria": ["Hay una recomendación"],
            "tasks": ["T001: Comparar"],
        }
        self.start(spec)
        session = json.loads((self.root / ".rapid-os" / "session.json").read_text(encoding="utf-8"))
        self.ok("abort", "--reason", "fin de la prueba")
        return session["active_run_id"]

    def start(self, spec):
        self.ok("start", "research", "--spec-file", "-", "--json", stdin=json.dumps(spec, ensure_ascii=False))

    COMMANDS = (("evidence", "list"), ("evidence", "verify"))

    def test_a_closed_run_is_found_and_named(self):
        self.onboard()
        run_id = self.start_and_abort("Zeta primero")
        for command in self.COMMANDS:
            result = self.ok(*command)
            self.assertEqual(result.stdout.splitlines()[0], f"Run: {run_id}", command)

    def test_eval_show_finds_the_closed_run(self):
        self.onboard()
        run_id = self.start_and_abort("Zeta primero")
        result = self.rapid("eval", "show")
        self.assertNotIn("required: --run", result.stderr)
        self.assertEqual(result.stdout.splitlines()[0], f"Run: {run_id}", result.stderr)

    def test_with_run_the_output_is_as_it_was(self):
        self.onboard()
        run_id = self.start_and_abort("Zeta primero")
        result = self.ok("evidence", "list", "--run", run_id)
        self.assertNotIn("Run: ", result.stdout)

    def test_the_json_output_stays_json(self):
        self.onboard()
        run_id = self.start_and_abort("Zeta primero")
        self.assertEqual(json.loads(self.ok("evidence", "verify", "--json").stdout)["run_id"], run_id)

    def test_the_active_run_comes_first(self):
        self.onboard()
        self.start_and_abort("Zeta primero")
        self.start({
            "title": "Alfa activo", "mode": "research", "business_objective": "Decidir", "problem_statement": "No hay datos",
            "scope": ["talleres"], "acceptance_criteria": ["Hay una recomendación"], "tasks": ["T001: Comparar"],
        })
        active = json.loads((self.root / ".rapid-os" / "session.json").read_text(encoding="utf-8"))["active_run_id"]
        self.assertEqual(self.ok("evidence", "list").stdout.splitlines()[0], f"Run: {active}")

    def test_the_last_closed_run_wins_whatever_its_id_says(self):
        self.onboard()
        self.start_and_abort("Zeta primero")
        last = self.start_and_abort("Alfa después")  # sorts first by id, closed last
        self.assertEqual(self.ok("evidence", "list").stdout.splitlines()[0], f"Run: {last}")

    def test_without_runs_the_error_is_clear(self):
        self.onboard()
        for command, code in ((("evidence", "list"), "RAPID1202"), (("evidence", "verify"), "RAPID1202"), (("eval", "show"), "RAPID1221")):
            result = self.rapid(*command)
            with self.subTest(command=command):
                self.assertEqual(result.returncode, 1, result.stderr)
                self.assertTrue(result.stderr.startswith(code), result.stderr)
                self.assertIn("rapid start", result.stderr)


class DraftBackupTests(Sandbox):
    """H-50: the copy of a replaced draft stays out of the first commit; a person's content stays in sight."""

    def setUp(self):
        super().setUp()
        self.bank = load_banks(None)["business"]
        self.document = self.root / self.bank.file
        self.body = draft_body(self.bank.required_sections)

    def write(self, source, *extra, body=None):
        return self.ok("setup", "doc", "business", "--source", source, "--file", "-", *extra, stdin=body or self.body)

    def beside(self):
        return sorted(p.name for p in self.document.parent.glob("*.bak"))

    def in_backups(self):
        return sorted(p.name for p in (self.root / ".rapid-os" / "backups").glob("*.bak"))

    def test_a_replaced_draft_goes_to_the_backups(self):
        self.write("drafted")
        self.write("drafted", "--replace", body=self.body + "\nOtra línea.\n")
        self.assertEqual(self.beside(), [])
        self.assertEqual(len(self.in_backups()), 1, self.in_backups())

    def test_at_most_the_kept_number_of_copies_stay(self):
        self.write("drafted")
        for number in range(AGENT_BACKUPS_KEPT + 2):
            self.write("drafted", "--replace", body=f"{self.body}\nVersión {number}.\n")
        self.assertEqual(self.beside(), [])
        self.assertEqual(len(self.in_backups()), AGENT_BACKUPS_KEPT)

    def test_a_provided_document_keeps_its_copy_beside_it(self):
        self.write("provided")
        self.write("drafted", "--replace")
        self.assertEqual(len(self.beside()), 1, self.beside())
        self.assertEqual(self.in_backups(), [])

    def test_a_file_rapid_did_not_write_keeps_its_copy_beside_it(self):
        self.document.parent.mkdir(parents=True, exist_ok=True)
        self.document.write_text("# Mis reglas\n", encoding="utf-8")
        self.write("drafted", "--replace")
        self.assertEqual(len(self.beside()), 1, self.beside())
        self.assertEqual(self.in_backups(), [])


if __name__ == "__main__":
    unittest.main()
