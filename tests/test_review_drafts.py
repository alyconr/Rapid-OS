"""F5: before closing the onboarding the person decides, document by document, whether a draft
becomes a rule or stays an assumption, knowing what each option means."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from rapid_os.domain.catalog import load_catalog, load_setup_doc_banks, load_stack_questions
from rapid_os.domain.project import ProjectModel
from rapid_os.domain.setup import (
    DocState,
    SetupActionKind,
    SetupState,
    SetupStateError,
    StackChoice,
)
from rapid_os.orchestration.setup_conductor import next_setup_action

ROOT = Path(__file__).resolve().parents[1]
TEMPLATES = ROOT / "templates"
CATALOG = load_catalog(TEMPLATES)
BANKS = load_setup_doc_banks(TEMPLATES)
STACK_QUESTIONS = load_stack_questions(TEMPLATES)
AGENT_IDS = ("antigravity", "claude", "codex", "cursor", "vscode")

CONFIRM_TEXT = (
    "Pasa a ser una regla del proyecto: el agente la cumple en cada run sin cuestionarla. "
    "Puedes devolverla a borrador con rapid setup doc <id> --reopen."
)
KEEP_DRAFT_TEXT = (
    "Queda como supuesto: el agente la recibe bajo el aviso 'Supuestos redactados por el agente, "
    "no confirmados por la persona', puede cuestionarla y preguntarte, y cada run te recuerda que "
    "está sin confirmar (RAPID1408). La confirmas cuando quieras con rapid setup doc <id> --confirm."
)

BRIEF = "## Problema\nAgendar talleres.\n\n## Usuarios\nOrganizadores.\n\n## Historias\n- [ ] H001: Listar talleres\n"
BUSINESS = (
    "## Objetivo\nVender entradas.\n\n## Reglas no negociables\nUn taller no se solapa con otro.\n\n"
    "## Restricciones\nSolo en español.\n\n## Supuestos\nHay un organizador por taller.\n\n## Glosario\nTaller: sesión con cupo.\n"
)


def decided(**docs) -> SetupState:
    """Every decision taken; `docs` maps a document id to its DocState."""
    return SetupState(
        stack=StackChoice("generic", "generic"),
        topology="fullstack-baas",
        archetype="mvp",
        agents=("codex",),
        test_command=(),
        docs={
            doc_id: docs.get(doc_id, DocState("skipped"))
            for doc_id in ("brief", "business", "data-model", "architecture")
        },
    )


def next_action(state):
    return next_setup_action(
        state, ProjectModel(root=Path(".")), CATALOG, BANKS,
        stack_questions=STACK_QUESTIONS, agent_ids=AGENT_IDS,
    )


DRAFT = DocState("drafted", False, "abc")


class ConductorTests(unittest.TestCase):
    def test_unconfirmed_drafts_come_before_finish(self):
        action = next_action(decided(brief=DRAFT, business=DocState("provided", True, "x")))
        self.assertEqual(action.kind, SetupActionKind.REVIEW_DRAFTS)
        self.assertEqual(action.kind.value, "review_drafts")

    def test_no_drafts_goes_straight_to_finish(self):
        for docs in ({}, {"brief": DocState("provided", True, "x")}, {"brief": DocState("drafted", True, "x")}):
            with self.subTest(docs=docs):
                self.assertEqual(next_action(decided(**docs)).kind, SetupActionKind.FINISH)

    def test_pending_documents_are_resolved_before_the_review(self):
        self.assertEqual(
            next_action(decided(brief=DRAFT, business=DocState())).kind, SetupActionKind.RESOLVE_DOC
        )

    def test_reviewed_drafts_go_to_finish_and_stay_unconfirmed(self):
        from dataclasses import replace

        action = next_action(replace(decided(brief=DRAFT), drafts_reviewed=True))
        self.assertEqual(action.kind, SetupActionKind.FINISH)
        self.assertEqual(action.payload["unconfirmed_docs"], ["brief"])

    def test_a_finished_setup_is_not_reopened_by_the_review(self):
        from dataclasses import replace

        self.assertEqual(
            next_action(replace(decided(brief=DRAFT), finished=True)).kind, SetupActionKind.DONE
        )

    def test_payload(self):
        payload = next_action(decided(brief=DRAFT, **{"data-model": DRAFT})).to_dict()
        self.assertEqual(payload["kind"], "review_drafts")
        self.assertEqual(
            payload["drafts"],
            [
                {"doc": "brief", "file": BANKS["brief"].file, "title": BANKS["brief"].title},
                {"doc": "data-model", "file": BANKS["data-model"].file, "title": BANKS["data-model"].title},
            ],
        )
        self.assertEqual(payload["consequences"], {"confirm": CONFIRM_TEXT, "keep_draft": KEEP_DRAFT_TEXT})
        self.assertEqual(
            payload["commands"],
            {"confirm": ["rapid", "setup", "doc", "<id>", "--confirm"], "done": ["rapid", "setup", "review", "--done"]},
        )
        # Like every action except `done`, it carries the command that resolves it.
        self.assertEqual(payload["command"], ["rapid", "setup", "review", "--done"])


class StateTests(unittest.TestCase):
    def test_an_old_setup_json_without_the_field_reads_as_false(self):
        data = decided(brief=DRAFT).to_dict()
        data.pop("drafts_reviewed", None)
        self.assertFalse(SetupState.from_dict(data).drafts_reviewed)

    def test_the_field_round_trips_and_is_omitted_while_false(self):
        from dataclasses import replace

        state = decided(brief=DRAFT)
        self.assertNotIn("drafts_reviewed", state.to_dict())
        reviewed = replace(state, drafts_reviewed=True)
        self.assertTrue(reviewed.to_dict()["drafts_reviewed"])
        self.assertTrue(SetupState.from_dict(reviewed.to_dict()).drafts_reviewed)

    def test_a_non_boolean_is_rejected(self):
        data = decided().to_dict()
        data["drafts_reviewed"] = "yes"
        with self.assertRaises(SetupStateError):
            SetupState.from_dict(data)


class CliCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)
        base = self.root.parent
        self.git_config = base / f"{self.root.name}-gitconfig"
        self.git_config.write_text("", encoding="utf-8")
        self.addCleanup(lambda: self.git_config.unlink(missing_ok=True))
        self.env = {
            **{k: v for k, v in os.environ.items() if k not in ("CLAUDECODE", "CLAUDE_CODE_CHILD_SESSION")},
            "GIT_CONFIG_GLOBAL": str(self.git_config),
            "GIT_CONFIG_NOSYSTEM": "1",
            "PYTHONPATH": str(ROOT),
            "PYTHONIOENCODING": "utf-8",
            "PYTHONDONTWRITEBYTECODE": "1",
        }

    def rapid(self, *argv, stdin=None):
        return subprocess.run(
            [sys.executable, "-m", "rapid_os.cli.main", *argv],
            cwd=self.root, input=stdin, capture_output=True, text=True, encoding="utf-8", env=self.env,
        )

    def decide(self):
        for key, value in (
            ("stack", "generic"), ("topology", "fullstack-baas"), ("archetype", "mvp"),
            ("agents", "claude"), ("test-command", "none"),
        ):
            result = self.rapid("setup", "set", key, value)
            self.assertEqual(result.returncode, 0, result.stderr)

    def draft(self, doc, body):
        result = self.rapid("setup", "doc", doc, "--source", "drafted", "--file", "-", stdin=body)
        self.assertEqual(result.returncode, 0, result.stderr)

    def skip(self, *docs):
        for doc in docs:
            self.assertEqual(self.rapid("setup", "doc", doc, "--skip").returncode, 0)

    def next_json(self):
        result = self.rapid("setup", "next", "--json")
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout)


class ReviewCommandTests(CliCase):
    def test_review_done_closes_the_review_and_leaves_the_draft_unconfirmed(self):
        self.decide()
        self.draft("brief", BRIEF)
        self.skip("business", "data-model", "architecture")
        self.assertEqual(self.next_json()["kind"], "review_drafts")

        done = self.rapid("setup", "review", "--done", "--json")
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertEqual(json.loads(done.stdout)["kind"], "finish")
        state = json.loads(self.rapid("setup", "show", "--json").stdout)["state"]
        self.assertTrue(state["drafts_reviewed"])
        self.assertEqual(state["docs"]["brief"]["confirmed"], False)
        text = (self.root / "docs" / "PRODUCT_BRIEF.md").read_text("utf-8")
        self.assertIn("status: draft", text)

    NOTHING_LEFT = "Todos los borradores quedaron confirmados; no hay nada más que revisar"

    def test_with_every_draft_confirmed_review_done_is_a_no_op_that_succeeds(self):
        self.decide()
        self.draft("brief", BRIEF)
        self.skip("business", "data-model", "architecture")
        self.assertEqual(self.rapid("setup", "doc", "brief", "--confirm").returncode, 0)
        self.assertEqual(self.next_json()["kind"], "finish")  # the conductor already moved on
        setup_json = self.root / ".rapid-os" / "setup.json"
        before = setup_json.read_text("utf-8")

        done = self.rapid("setup", "review", "--done")
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertNotIn("RAPID1413", done.stderr)
        self.assertIn(self.NOTHING_LEFT, done.stdout)
        self.assertIn("Setup next: finish", done.stdout)  # and the next action
        self.assertEqual(setup_json.read_text("utf-8"), before)  # the state did not change
        self.assertNotIn("drafts_reviewed", json.loads(before))

        as_json = self.rapid("setup", "review", "--done", "--json")
        self.assertEqual(as_json.returncode, 0, as_json.stderr)
        self.assertEqual(json.loads(as_json.stdout)["kind"], "finish")  # stdout stays the action alone
        self.assertEqual(self.rapid("setup", "finish").returncode, 0)

    def test_with_no_drafts_at_all_it_is_the_same_no_op(self):
        self.decide()
        self.skip("brief", "business", "data-model", "architecture")
        result = self.rapid("setup", "review", "--done")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn(self.NOTHING_LEFT, result.stdout)
        self.assertNotIn("Traceback", result.stderr)
        state = json.loads(self.rapid("setup", "show", "--json").stdout)["state"]
        self.assertNotIn("drafts_reviewed", state)

    def test_without_done_it_asks_for_it(self):
        self.decide()
        self.draft("brief", BRIEF)
        result = self.rapid("setup", "review")
        self.assertEqual(result.returncode, 1)
        self.assertIn("RAPID1413", result.stderr)
        self.assertIn("--done", result.stderr)

    def test_confirming_a_document_does_not_close_the_review(self):
        self.decide()
        self.draft("brief", BRIEF)
        self.draft("business", BUSINESS)
        self.skip("data-model", "architecture")
        confirmed = self.rapid("setup", "doc", "brief", "--confirm", "--json")
        self.assertEqual(confirmed.returncode, 0, confirmed.stderr)
        after = json.loads(confirmed.stdout)
        self.assertEqual(after["kind"], "review_drafts")
        self.assertEqual([d["doc"] for d in after["drafts"]], ["business"])  # only what is still a draft
        state = json.loads(self.rapid("setup", "show", "--json").stdout)["state"]
        self.assertNotIn("drafts_reviewed", state)

    def test_finish_with_the_review_pending_is_rapid1407_with_the_next_command(self):
        self.decide()
        self.draft("brief", BRIEF)
        self.skip("business", "data-model", "architecture")
        result = self.rapid("setup", "finish")
        self.assertEqual(result.returncode, 1)
        self.assertIn("RAPID1407", result.stderr)
        self.assertIn("review_drafts", result.stderr)
        self.assertIn("rapid setup review --done", result.stderr)
        self.assertFalse((self.root / ".rapid-os" / "standards" / "tech-stack.md").exists())

    def test_a_new_draft_after_the_review_asks_for_it_again(self):
        self.decide()
        self.draft("brief", BRIEF)
        self.skip("business", "data-model", "architecture")
        self.assertEqual(self.rapid("setup", "review", "--done").returncode, 0)
        self.assertEqual(self.next_json()["kind"], "finish")
        replaced = self.rapid(
            "setup", "doc", "brief", "--source", "drafted", "--replace", "--file", "-", stdin=BRIEF + "\nOtra.\n"
        )
        self.assertEqual(replaced.returncode, 0, replaced.stderr)
        self.assertEqual(self.next_json()["kind"], "review_drafts")


class EndToEndTests(CliCase):
    def test_two_drafts_confirm_one_review_done_finish(self):
        self.decide()
        self.draft("brief", BRIEF)
        self.draft("business", BUSINESS)
        self.skip("data-model", "architecture")

        review = self.next_json()
        self.assertEqual(review["kind"], "review_drafts")
        self.assertEqual({d["doc"] for d in review["drafts"]}, {"brief", "business"})

        self.assertEqual(self.rapid("setup", "doc", "brief", "--confirm").returncode, 0)
        self.assertEqual(self.rapid("setup", "review", "--done").returncode, 0)
        finished = self.rapid("setup", "finish", "--json")
        self.assertEqual(finished.returncode, 0, finished.stderr)
        done = json.loads(finished.stdout)
        self.assertEqual(done["kind"], "done")
        self.assertEqual(done["unconfirmed_docs"], ["business"])

        banner = "> Supuestos redactados por el agente, no confirmados por la persona."
        agent_file = (self.root / "CLAUDE.md").read_text("utf-8")
        self.assertEqual(agent_file.count(banner), 1)  # only the draft carries it
        brief_at = agent_file.index("Listar talleres")
        banner_at = agent_file.index(banner)
        business_at = agent_file.index("Vender entradas")
        # The confirmed brief enters as a rule, with no banner above it; the draft enters under the
        # banner, right below its own heading.
        self.assertLess(brief_at, banner_at)
        self.assertLess(banner_at, business_at)
        self.assertIn("REGLAS DE NEGOCIO\n" + banner, agent_file)

class ShortcutTemplateTests(unittest.TestCase):
    def test_init_shortcut_explains_the_review(self):
        text = (TEMPLATES / "shortcuts" / "rapid-init.md").read_text("utf-8")
        for expected in (
            "review_drafts",
            "consequences",
            "SOLO para los documentos que la persona confirme de forma explícita",
            "nunca infieras una confirmación",
            "rapid setup review --done",
            "--source drafted --replace",
        ):
            with self.subTest(expected=expected):
                self.assertIn(expected, text)


if __name__ == "__main__":
    unittest.main()
