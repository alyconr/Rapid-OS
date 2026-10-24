"""`rapid setup set|stack|doc|finish` and the `rapid init` that shares their state and writes."""

import contextlib
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from argparse import Namespace
from pathlib import Path
from unittest.mock import patch

from rapid_os.adapters.setup_store import read_setup_file
from rapid_os.cli import main as cli_main
from rapid_os.domain.project_docs import DRAFT_BANNER, body_sha256, parse_doc_frontmatter

REPO = Path(__file__).resolve().parent.parent

BUSINESS = (
    "## Objetivo\nx\n## Reglas no negociables\nx\n## Restricciones\nx\n## Supuestos\nx\n## Glosario\nx\n"
)
BRIEF = "## Problema\np\n## Usuarios\nu\n## Historias\n- [ ] H001: a\n"
FILES = {
    "brief": "docs/PRODUCT_BRIEF.md",
    "business": "docs/BUSINESS_RULES.md",
    "data-model": "docs/DATA_MODEL.md",
    "architecture": "docs/ARCHITECTURE.md",
    "deployment": "docs/DEPLOYMENT.md",
}


def rapid(cwd, *argv, stdin=None, env=None):
    return subprocess.run(
        [sys.executable, str(REPO / "rapid.py"), *argv],
        cwd=cwd,
        input=stdin,
        capture_output=True,
        text=True,
        encoding="utf-8",
        env={**os.environ, "CLAUDECODE": "", "PYTHONPATH": str(REPO), "PYTHONIOENCODING": "utf-8", **(env or {})},
    )


def decide_everything(cwd, *, agents="claude"):
    for argv in (
        ("set", "stack", "python-ai"),
        ("set", "topology", "fullstack-separated"),
        ("set", "stack", "react-vite"),
        ("set", "archetype", "mvp"),
        ("set", "agents", agents),
        ("set", "test-command", "python -m unittest"),
        ("set", "services", "none"),
    ):
        result = rapid(cwd, "setup", *argv)
        assert result.returncode == 0, result.stderr


def draft(cwd, doc_id, body):
    return rapid(cwd, "setup", "doc", doc_id, "--source", "drafted", "--file", "-", stdin=body)


class SetupWriteBase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)

    def next_json(self):
        result = rapid(self.root, "setup", "next", "--json")
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout)

    def setup_state(self):
        state, error = read_setup_file(self.root / ".rapid-os")
        self.assertIsNone(error)
        return state


class SetDecisionTests(SetupWriteBase):
    def test_set_creates_rapid_dir_and_returns_next_action(self):
        result = rapid(self.root, "setup", "set", "stack", "python-ai", "--json")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["kind"], "choose_topology")
        # `python-ai` is an id of before the component catalog: it maps to the backend stack and ai=yes
        self.assertEqual(self.setup_state().stack.id, "python-fastapi")
        self.assertEqual(self.setup_state().stack.source, "catalog")
        self.assertTrue(self.setup_state().ai)
        self.assertFalse((self.root / ".rapid-os" / "standards").exists())

    def test_invalid_key_or_value_is_rapid1413(self):
        for argv in (
            ("set", "color", "red"),
            ("set", "stack"),
            ("set", "stack", "no-such-stack"),
            ("set", "stack", "../escape"),
            ("set", "stack", "custom"),
            ("set", "archetype", "enterprise"),
            ("set", "agents", "emacs"),
            ("set", "topology", "no-such-topology"),
        ):
            with self.subTest(argv=argv):
                result = rapid(self.root, "setup", *argv)
                self.assertEqual(result.returncode, 1, result.stdout)
                self.assertIn("RAPID1413", result.stderr)
                self.assertNotIn("Traceback", result.stderr)

    def test_incompatible_stack_and_topology_is_rapid1402(self):
        self.assertEqual(rapid(self.root, "setup", "set", "stack", "python-ai").returncode, 0)
        result = rapid(self.root, "setup", "set", "topology", "doc-site")
        self.assertEqual(result.returncode, 1)
        self.assertIn("RAPID1402", result.stderr)
        self.assertIsNone(self.setup_state().topology)

    def test_changing_the_stack_reopens_an_incompatible_topology(self):
        rapid(self.root, "setup", "set", "stack", "docs-modern")
        rapid(self.root, "setup", "set", "topology", "doc-site")
        result = rapid(self.root, "setup", "set", "stack", "python-ai", "--json")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("doc-site", result.stderr)
        data = json.loads(result.stdout)
        self.assertEqual(data["kind"], "choose_topology")
        self.assertEqual(
            data["notes"][-1], "Topology 'doc-site' does not fit stack 'python-ai'; it is undecided again."
        )
        self.assertIn("python-fastapi", data["notes"][0])

    def test_notes_are_omitted_from_the_json_when_there_are_none(self):
        result = rapid(self.root, "setup", "set", "stack", "go", "--json")
        self.assertNotIn("notes", json.loads(result.stdout))

    def test_test_command_none_is_a_decision(self):
        decide_everything(self.root)
        rapid(self.root, "setup", "set", "test-command", "none")
        self.assertEqual(self.setup_state().test_command, ())


class CustomStackTests(SetupWriteBase):
    def test_custom_stack_needs_runtime_framework_and_testing(self):
        result = rapid(
            self.root, "setup", "stack", "--custom", "--file", "-", stdin="- **Runtime:** Go.\n"
        )
        self.assertEqual(result.returncode, 1)
        self.assertIn("RAPID1409", result.stderr)
        self.assertIn("Framework", result.stderr)
        self.assertFalse((self.root / ".rapid-os").exists())

    def test_custom_stack_is_written_and_survives_finish(self):
        text = "# TECH STACK: Custom\n- **Runtime:** Go 1.22.\n- **Framework:** chi.\n- **Testing:** go test.\n"
        result = rapid(self.root, "setup", "stack", "--custom", "--file", "-", stdin=text)
        self.assertEqual(result.returncode, 0, result.stderr)
        state = self.setup_state()
        self.assertEqual((state.stack.id, state.stack.source), ("custom", "custom"))
        rapid(self.root, "setup", "set", "topology", "fullstack-separated")
        for argv in (("archetype", "mvp"), ("ai", "no"), ("agents", "claude"), ("test-command", "none"), ("services", "none")):
            rapid(self.root, "setup", "set", *argv)
        for doc_id in FILES:
            self.assertEqual(rapid(self.root, "setup", "doc", doc_id, "--skip").returncode, 0)
        finish = rapid(self.root, "setup", "finish", "--json")
        self.assertEqual(finish.returncode, 0, finish.stderr)
        stack = (self.root / ".rapid-os" / "standards" / "tech-stack.md").read_text(encoding="utf-8")
        self.assertIn("Go 1.22", stack)

    def test_stack_without_custom_is_rapid1413(self):
        result = rapid(self.root, "setup", "stack", "--file", "-", stdin="x")
        self.assertEqual(result.returncode, 1)
        self.assertIn("RAPID1413", result.stderr)


class DocTests(SetupWriteBase):
    def test_drafted_doc_gets_frontmatter_and_is_a_draft(self):
        result = draft(self.root, "business", BUSINESS)
        self.assertEqual(result.returncode, 0, result.stderr)
        text = (self.root / FILES["business"]).read_text(encoding="utf-8")
        fields, body = parse_doc_frontmatter(text)
        self.assertEqual(
            {k: fields[k] for k in ("rapid-doc", "source", "status")},
            {"rapid-doc": "business", "source": "drafted", "status": "draft"},
        )
        self.assertEqual(fields["sha256"], body_sha256(body))
        self.assertEqual(body, BUSINESS)
        doc = self.setup_state().doc("business")
        self.assertEqual((doc.status, doc.confirmed, doc.sha256), ("drafted", False, fields["sha256"]))

    def test_provided_doc_is_stored_as_is_and_confirmed(self):
        pasted = "lo que pegó la persona, sin secciones ni límite\n" + "x" * 9000
        result = rapid(
            self.root, "setup", "doc", "business", "--source", "provided", "--file", "-", stdin=pasted
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        fields, body = parse_doc_frontmatter((self.root / FILES["business"]).read_text(encoding="utf-8"))
        self.assertEqual((fields["source"], fields["status"]), ("provided", "confirmed"))
        self.assertEqual(body.rstrip("\n"), pasted)
        self.assertEqual(self.setup_state().doc("business").confirmed, True)

    def test_drafted_without_required_section_is_rejected_and_writes_nothing(self):
        result = draft(self.root, "brief", "## Problema\np\n")
        self.assertEqual(result.returncode, 1)
        self.assertIn("RAPID1403", result.stderr)
        self.assertNotIn("Traceback", result.stderr)
        self.assertFalse((self.root / "docs").exists())
        self.assertFalse((self.root / ".rapid-os").exists())

    def test_drafted_over_limit_is_rapid1404(self):
        result = draft(self.root, "business", BUSINESS + "y" * 7000)
        self.assertEqual(result.returncode, 1)
        self.assertIn("RAPID1404", result.stderr)
        self.assertFalse((self.root / "docs").exists())

    def test_drafted_over_provided_needs_replace(self):
        rapid(self.root, "setup", "doc", "business", "--source", "provided", "--file", "-", stdin="mine\n")
        refused = draft(self.root, "business", BUSINESS)
        self.assertEqual(refused.returncode, 1)
        self.assertIn("RAPID1405", refused.stderr)
        self.assertEqual(
            parse_doc_frontmatter((self.root / FILES["business"]).read_text(encoding="utf-8"))[1], "mine\n"
        )
        replaced = rapid(
            self.root, "setup", "doc", "business", "--source", "drafted", "--file", "-", "--replace",
            stdin=BUSINESS,
        )
        self.assertEqual(replaced.returncode, 0, replaced.stderr)
        self.assertTrue(list((self.root / "docs").glob("BUSINESS_RULES.md.*.bak")))
        self.assertEqual(self.setup_state().doc("business").status, "drafted")

    def test_drafted_does_not_overwrite_a_hand_written_file_without_replace(self):
        (self.root / "docs").mkdir()
        (self.root / FILES["business"]).write_text("# escrito a mano\n", encoding="utf-8")
        result = draft(self.root, "business", BUSINESS)
        self.assertEqual(result.returncode, 1)
        self.assertIn("RAPID1405", result.stderr)

    def test_provided_over_a_draft_keeps_a_backup(self):
        draft(self.root, "business", BUSINESS)
        rapid(self.root, "setup", "doc", "business", "--source", "provided", "--file", "-", stdin="mine\n")
        self.assertTrue(list((self.root / "docs").glob("BUSINESS_RULES.md.*.bak")))

    def test_confirm_changes_only_the_status(self):
        draft(self.root, "business", BUSINESS)
        path = self.root / FILES["business"]
        before = path.read_text(encoding="utf-8")
        result = rapid(self.root, "setup", "doc", "business", "--confirm")
        self.assertEqual(result.returncode, 0, result.stderr)
        after = path.read_text(encoding="utf-8")
        self.assertEqual(after, before.replace("status: draft", "status: confirmed"))
        doc = self.setup_state().doc("business")
        self.assertEqual((doc.status, doc.confirmed), ("drafted", True))
        again = rapid(self.root, "setup", "doc", "business", "--confirm")
        self.assertEqual(again.returncode, 0)

    def test_confirm_without_a_document_is_rapid1413(self):
        result = rapid(self.root, "setup", "doc", "business", "--confirm")
        self.assertEqual(result.returncode, 1)
        self.assertIn("RAPID1413", result.stderr)

    def test_skip_and_reopen(self):
        self.assertEqual(rapid(self.root, "setup", "doc", "brief", "--skip").returncode, 0)
        self.assertEqual(self.setup_state().doc("brief").status, "skipped")
        self.assertEqual(rapid(self.root, "setup", "doc", "brief", "--reopen").returncode, 0)
        self.assertEqual(self.setup_state().doc("brief").status, "pending")

    def test_reopen_turns_a_confirmed_draft_back_into_a_draft(self):
        draft(self.root, "business", BUSINESS)
        rapid(self.root, "setup", "doc", "business", "--confirm")
        self.assertEqual(rapid(self.root, "setup", "doc", "business", "--reopen").returncode, 0)
        fields, _body = parse_doc_frontmatter((self.root / FILES["business"]).read_text(encoding="utf-8"))
        self.assertEqual(fields["status"], "draft")
        self.assertEqual(self.setup_state().doc("business").confirmed, False)

    def test_skip_does_not_hide_a_written_document(self):
        draft(self.root, "business", BUSINESS)
        result = rapid(self.root, "setup", "doc", "business", "--skip")
        self.assertEqual(result.returncode, 1)
        self.assertIn("RAPID1413", result.stderr)

    def test_invalid_doc_id_and_modes_are_rapid1413(self):
        for argv in (
            ("doc", "nope", "--skip"),
            ("doc", "business"),
            ("doc", "business", "--skip", "--confirm"),
            ("doc", "business", "--source", "drafted"),
            ("doc", "business", "--skip", "--replace"),
            ("doc", "brief", "--from-legacy"),
        ):
            with self.subTest(argv=argv):
                result = rapid(self.root, "setup", *argv, stdin=BUSINESS)
                self.assertEqual(result.returncode, 1, result.stdout)
                self.assertIn("RAPID1413", result.stderr)

    def test_doc_write_returns_the_next_action_as_json(self):
        result = draft(self.root, "business", BUSINESS)
        self.assertEqual(result.returncode, 0, result.stderr)
        result = rapid(
            self.root, "setup", "doc", "brief", "--source", "drafted", "--file", "-", "--json", stdin=BRIEF
        )
        data = json.loads(result.stdout)
        self.assertEqual(data["kind"], "choose_stack")

    def test_legacy_business_standard_is_offered_and_imported(self):
        standards = self.root / ".rapid-os" / "standards"
        standards.mkdir(parents=True)
        (standards / "business.md").write_text("# Reglas viejas\n- una regla\n", encoding="utf-8")
        decide_everything(self.root)
        for doc_id in ("brief", "data-model", "architecture", "deployment"):
            rapid(self.root, "setup", "doc", doc_id, "--skip")
        action = self.next_json()
        self.assertEqual(action["kind"], "resolve_doc")
        self.assertEqual(action["doc"], "business")
        self.assertEqual(action["legacy_source"], ".rapid-os/standards/business.md")

        result = rapid(self.root, "setup", "doc", "business", "--from-legacy")
        self.assertEqual(result.returncode, 0, result.stderr)
        fields, body = parse_doc_frontmatter((self.root / FILES["business"]).read_text(encoding="utf-8"))
        self.assertEqual((fields["source"], fields["status"]), ("provided", "confirmed"))
        self.assertIn("una regla", body)
        self.assertEqual(
            (standards / "business.md").read_text(encoding="utf-8"), "# Reglas viejas\n- una regla\n"
        )
        self.assertNotIn("legacy_source", self.next_json())

    def test_legacy_is_not_offered_for_other_documents_or_without_content(self):
        standards = self.root / ".rapid-os" / "standards"
        standards.mkdir(parents=True)
        (standards / "business.md").write_text("   \n", encoding="utf-8")
        self.assertNotIn("legacy_source", self.next_json())
        result = rapid(self.root, "setup", "doc", "business", "--from-legacy")
        self.assertEqual(result.returncode, 1)
        self.assertIn("RAPID1413", result.stderr)


class FinishTests(SetupWriteBase):
    def test_finish_with_open_decisions_is_rapid1407(self):
        result = rapid(self.root, "setup", "finish")
        self.assertEqual(result.returncode, 1)
        self.assertIn("RAPID1407", result.stderr)
        self.assertFalse((self.root / ".rapid-os").exists())

    def test_full_onboarding_with_only_setup_commands(self):
        decide_everything(self.root)
        self.assertEqual(draft(self.root, "business", BUSINESS).returncode, 0)
        self.assertEqual(draft(self.root, "brief", BRIEF).returncode, 0)
        self.assertEqual(rapid(self.root, "setup", "doc", "data-model", "--skip").returncode, 0)
        self.assertEqual(rapid(self.root, "setup", "doc", "deployment", "--skip").returncode, 0)
        provided = rapid(
            self.root, "setup", "doc", "architecture", "--source", "provided", "--file", "-", stdin="# Arq\n"
        )
        self.assertEqual(provided.returncode, 0, provided.stderr)
        self.assertEqual(rapid(self.root, "setup", "review", "--done").returncode, 0)  # two drafts stay drafts

        finish = rapid(self.root, "setup", "finish", "--json")
        self.assertEqual(finish.returncode, 0, finish.stderr)
        done = json.loads(finish.stdout)  # stdout is the JSON alone
        self.assertEqual(done["kind"], "done")
        self.assertEqual(done["unconfirmed_docs"], ["brief", "business"])

        standards = self.root / ".rapid-os" / "standards"
        for name in ("tech-stack.md", "topology.md", "coding-rules.md", "security.md"):
            self.assertTrue((standards / name).is_file(), name)
        config = json.loads((self.root / ".rapid-os" / "config.json").read_text(encoding="utf-8"))
        self.assertEqual(config["tools"], ["claude"])
        self.assertEqual(config["test_command"], ["python", "-m", "unittest"])
        claude = (self.root / "CLAUDE.md").read_text(encoding="utf-8")
        self.assertIn(DRAFT_BANNER, claude)
        self.assertTrue(self.setup_state().finished)

        report = rapid(self.root, "validate", "--json")
        self.assertEqual(report.returncode, 0, report.stdout + report.stderr)
        codes = [d["code"] for d in json.loads(report.stdout)["diagnostics"]]
        self.assertEqual(codes.count("RAPID1408"), 2)
        self.assertNotIn("RAPID1403", codes)

        # Confirming removes the warning and the banner from the context and from CLAUDE.md.
        for doc_id in ("brief", "business"):
            self.assertEqual(rapid(self.root, "setup", "doc", doc_id, "--confirm").returncode, 0)
        report = rapid(self.root, "validate", "--json")
        self.assertEqual(report.returncode, 0)
        self.assertNotIn("RAPID1408", [d["code"] for d in json.loads(report.stdout)["diagnostics"]])
        self.assertNotIn(DRAFT_BANNER, (self.root / "CLAUDE.md").read_text(encoding="utf-8"))
        context = rapid(self.root, "context", "--json")
        self.assertNotIn(DRAFT_BANNER, context.stdout)

    def test_finish_is_idempotent(self):
        decide_everything(self.root)
        for doc_id in FILES:
            rapid(self.root, "setup", "doc", doc_id, "--skip")
        first = rapid(self.root, "setup", "finish", "--json")
        self.assertEqual(first.returncode, 0, first.stderr)
        claude = self.root / "CLAUDE.md"
        before = claude.read_text(encoding="utf-8")
        baks = sorted(p.name for p in self.root.rglob("*.bak"))
        second = rapid(self.root, "setup", "finish", "--json")
        self.assertEqual(second.returncode, 0)
        # `added_files` tells what that run wrote (the CI workflow): a second run writes nothing.
        written, again = json.loads(first.stdout), json.loads(second.stdout)
        self.assertEqual(written.pop("added_files")[0]["file"], ".github/workflows/rapid-security-python.yml")
        self.assertNotIn("added_files", again)
        self.assertEqual(again, written)
        self.assertEqual(claude.read_text(encoding="utf-8"), before)
        self.assertEqual(sorted(p.name for p in self.root.rglob("*.bak")), baks)

    def test_doc_writes_regenerate_agent_files_once_the_project_has_standards(self):
        decide_everything(self.root)
        for doc_id in ("brief", "data-model", "architecture", "deployment"):
            rapid(self.root, "setup", "doc", doc_id, "--skip")
        draft(self.root, "business", BUSINESS)
        self.assertFalse((self.root / "CLAUDE.md").exists())  # finish builds it
        rapid(self.root, "setup", "review", "--done")
        rapid(self.root, "setup", "finish")
        self.assertIn(DRAFT_BANNER, (self.root / "CLAUDE.md").read_text(encoding="utf-8"))
        rapid(self.root, "setup", "doc", "business", "--confirm")
        self.assertNotIn(DRAFT_BANNER, (self.root / "CLAUDE.md").read_text(encoding="utf-8"))

    def test_finish_keeps_standards_the_project_already_has(self):
        standards = self.root / ".rapid-os" / "standards"
        standards.mkdir(parents=True)
        mine = "# TECH STACK: PYTHON AI AGENT\n- **Runtime:** edited by me, FastAPI.\n"
        (standards / "tech-stack.md").write_text(mine, encoding="utf-8")
        (self.root / ".rapid-os" / "config.json").write_text(
            json.dumps({"tools": ["claude"], "test_command": ["pytest"]}), encoding="utf-8"
        )
        rapid(self.root, "setup", "set", "topology", "fullstack-separated")
        rapid(self.root, "setup", "set", "stack", "react-vite")
        rapid(self.root, "setup", "set", "archetype", "mvp")
        rapid(self.root, "setup", "set", "ai", "no")
        rapid(self.root, "setup", "set", "services", "none")
        for doc_id in FILES:
            rapid(self.root, "setup", "doc", doc_id, "--skip")
        finish = rapid(self.root, "setup", "finish")
        self.assertEqual(finish.returncode, 0, finish.stderr)
        self.assertEqual((standards / "tech-stack.md").read_text(encoding="utf-8"), mine)
        self.assertTrue((standards / "topology.md").is_file())


class InitSharesTheSetupTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.project = Path(self._tmp.name)

    def run_init(self, args, answers=()):
        feed = iter(answers)
        out = io.StringIO()
        with contextlib.ExitStack() as stack:
            stack.enter_context(patch.object(cli_main, "CURRENT_DIR", self.project))
            stack.enter_context(patch.object(cli_main, "PROJECT_RAPID_DIR", self.project / ".rapid-os"))
            stack.enter_context(patch.object(cli_main, "CONFIG_FILE", self.project / ".rapid-os" / "config.json"))
            stack.enter_context(patch("builtins.input", lambda prompt="": next(feed)))
            stack.enter_context(contextlib.redirect_stdout(out))
            cli_main.init_project(args)
        return out.getvalue()

    def base_args(self, **extra):
        values = dict(
            stack="python-ai", archetype="mvp", agents="claude", no_scan=True, yes=False,
            topology=None, test_command=None, business_file=None, skip_docs=False,
        )
        values.update(extra)
        return Namespace(**values)

    def state(self):
        state, error = read_setup_file(self.project / ".rapid-os")
        self.assertIsNone(error)
        return state

    def test_interactive_init_offers_the_four_options_for_each_document(self):
        imported = self.project / "negocio.md"
        imported.write_text("# Reglas importadas\n", encoding="utf-8")
        answers = [
            "4",  # topology (fullstack-separated)
            "",  # research tools
            "1", "", str(self.project), str(imported),  # brief: import; Enter and a directory re-ask
            "2", "Regla uno", "Regla dos", "", "",  # business: typed here
            "3",  # data-model: leave it to the agent
            "4",  # architecture: skip
        ]
        output = self.run_init(self.base_args(), answers)

        brief = parse_doc_frontmatter((self.project / "docs/PRODUCT_BRIEF.md").read_text(encoding="utf-8"))
        self.assertEqual((brief[0]["source"], brief[0]["status"]), ("provided", "confirmed"))
        self.assertIn("Reglas importadas", brief[1])
        business = parse_doc_frontmatter((self.project / "docs/BUSINESS_RULES.md").read_text(encoding="utf-8"))
        self.assertEqual(business[1], "Regla uno\nRegla dos\n")
        self.assertFalse((self.project / "docs/DATA_MODEL.md").exists())
        self.assertFalse((self.project / "docs/ARCHITECTURE.md").exists())
        self.assertFalse((self.project / "docs/SPECS.md").exists())

        state = self.state()
        self.assertEqual(
            {d: state.doc(d).status for d in ("brief", "business", "data-model", "architecture", "deployment")},
            {"brief": "provided", "business": "provided", "data-model": "pending", "architecture": "skipped",
             "deployment": "pending"},
        )
        self.assertFalse(state.finished)
        self.assertEqual(
            (state.stack.id, state.topology, state.archetype), ("python-fastapi", "fullstack-separated", "mvp")
        )
        self.assertTrue(output.rstrip().endswith("Completa la documentación con /rapid-init o rapid setup next"))
        self.assertIn("directorio", output)

    def test_enter_on_an_empty_path_asks_again_without_an_error(self):
        answers = ["4", "", "1", "", "/no/such/file.md", "0", "4", "4", "4", "4"]
        output = self.run_init(self.base_args(), answers)  # must not raise
        self.assertIn("vacía", output)
        self.assertNotIn("Is a directory", output)
        self.assertEqual(self.state().doc("brief").status, "skipped")

    def test_init_yes_leaves_documents_pending(self):
        output = self.run_init(self.base_args(yes=True))
        state = self.state()
        self.assertTrue(all(state.doc(d).status == "pending" for d in ("brief", "business", "data-model", "architecture", "deployment")))
        self.assertFalse(state.finished)
        self.assertTrue(output.rstrip().endswith("Completa la documentación con /rapid-init o rapid setup next"))
        self.assertFalse((self.project / "docs").exists())
        result = rapid(self.project, "setup", "next", "--json")
        # `init` takes one stack: the other component of the topology is still to be chosen.
        action = json.loads(result.stdout)
        self.assertEqual((action["kind"], action["component"]), ("choose_stack", "frontend"))

    def test_business_file_flag_is_provided_and_other_docs_stay_pending(self):
        source = self.project / "reglas.md"
        source.write_text("# Reglas\n- una\n", encoding="utf-8")
        self.run_init(self.base_args(yes=True, business_file=str(source)))
        fields, body = parse_doc_frontmatter((self.project / "docs/BUSINESS_RULES.md").read_text(encoding="utf-8"))
        self.assertEqual((fields["source"], fields["status"]), ("provided", "confirmed"))
        self.assertIn("- una", body)
        state = self.state()
        self.assertEqual(state.doc("business").status, "provided")
        self.assertEqual(state.doc("brief").status, "pending")

    def test_business_file_that_is_not_a_file_is_rapid1413(self):
        with self.assertRaises(SystemExit) as raised:
            self.run_init(self.base_args(yes=True, business_file=str(self.project)))
        self.assertEqual(raised.exception.code, 1)
        self.assertFalse((self.project / ".rapid-os" / "standards" / "tech-stack.md").exists())

    def test_skip_docs_flag_skips_all_four_and_finishes_the_state(self):
        output = self.run_init(self.base_args(yes=True, skip_docs=True))
        state = self.state()
        self.assertTrue(all(state.doc(d).status == "skipped" for d in ("brief", "business", "data-model", "architecture", "deployment")))
        self.assertTrue(state.finished)
        self.assertNotIn("Completa la documentación", output)

    def test_init_and_setup_leave_the_same_standards_and_config(self):
        self.run_init(self.base_args(yes=True, skip_docs=True, topology="fullstack-separated", test_command="python -m unittest"))
        other = Path(tempfile.mkdtemp())
        self.addCleanup(lambda: __import__("shutil").rmtree(other, ignore_errors=True))
        decide_everything(other)
        rapid(other, "setup", "set", "services", "database:postgresql")  # what the stack template says
        for doc_id in FILES:
            rapid(other, "setup", "doc", doc_id, "--skip")
        self.assertEqual(rapid(other, "setup", "finish").returncode, 0)
        def standard(root, name):
            text = (root / ".rapid-os" / "standards" / name).read_text(encoding="utf-8")
            # The database lines follow the services decision (setup) or the template (init).
            if name == "tech-stack.md":
                text = text.split("\n\n# ")[0]  # `init` takes one stack: compare the backend's block
            return "\n".join(
                l for l in text.strip().split("\n") if not l.startswith(("- **Database:**", "- **ORM:**"))
            )

        for name in ("tech-stack.md", "topology.md", "coding-rules.md", "security.md"):
            self.assertEqual(standard(self.project, name), standard(other, name), name)
        self.assertEqual(
            json.loads((self.project / ".rapid-os" / "config.json").read_text(encoding="utf-8")),
            json.loads((other / ".rapid-os" / "config.json").read_text(encoding="utf-8")),
        )

    def test_reinit_keeps_documents_a_person_already_resolved(self):
        self.run_init(self.base_args(yes=True, business_file=str(self._write("r.md", "# mia\n"))))
        before = (self.project / "docs/BUSINESS_RULES.md").read_text(encoding="utf-8")
        output = self.run_init(self.base_args(yes=True))
        self.assertEqual((self.project / "docs/BUSINESS_RULES.md").read_text(encoding="utf-8"), before)
        self.assertEqual(self.state().doc("business").status, "provided")
        self.assertIn("se conserva", output)

    def _write(self, name, text):
        path = self.project / name
        path.write_text(text, encoding="utf-8")
        return path


class RapidOnPathTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.project = Path(self._tmp.name)

    def init(self, which, **extra):
        values = dict(
            stack="python-ai", archetype="mvp", agents="claude", no_scan=True, yes=True,
            topology="fullstack-separated", test_command=None, business_file=None, skip_docs=True,
            shortcuts=True, hooks=False,
        )
        values.update(extra)
        out = io.StringIO()
        with contextlib.ExitStack() as stack:
            stack.enter_context(patch.object(cli_main, "CURRENT_DIR", self.project))
            stack.enter_context(patch.object(cli_main, "PROJECT_RAPID_DIR", self.project / ".rapid-os"))
            stack.enter_context(patch.object(cli_main, "CONFIG_FILE", self.project / ".rapid-os" / "config.json"))
            stack.enter_context(patch("shutil.which", which))
            stack.enter_context(contextlib.redirect_stdout(out))
            cli_main.init_project(Namespace(**values))
        return out.getvalue()

    def test_warns_when_shortcuts_are_installed_and_rapid_is_not_on_path(self):
        output = self.init(lambda name, *a, **k: None)
        self.assertIn("RAPID1414", output)
        self.assertIn("pipx", output)
        self.assertTrue((self.project / ".claude").exists())  # the init still succeeded

    def test_no_warning_when_rapid_is_on_path(self):
        output = self.init(lambda name, *a, **k: "/usr/bin/rapid")
        self.assertNotIn("RAPID1414", output)

    def test_no_warning_without_shortcuts_or_hooks(self):
        output = self.init(lambda name, *a, **k: None, shortcuts=False)
        self.assertNotIn("RAPID1414", output)

    def test_hooks_also_trigger_the_warning(self):
        output = self.init(lambda name, *a, **k: None, shortcuts=False, hooks=True)
        self.assertEqual(output.count("RAPID1414"), 1)

    def test_doctor_reports_the_same_warning(self):
        self.init(lambda name, *a, **k: "/usr/bin/rapid")
        out = io.StringIO()
        with contextlib.ExitStack() as stack:
            stack.enter_context(patch.object(cli_main, "CURRENT_DIR", self.project))
            stack.enter_context(patch.object(cli_main, "PROJECT_RAPID_DIR", self.project / ".rapid-os"))
            stack.enter_context(patch.object(cli_main, "CONFIG_FILE", self.project / ".rapid-os" / "config.json"))
            stack.enter_context(patch("shutil.which", lambda name, *a, **k: None))
            stack.enter_context(contextlib.redirect_stdout(out))
            with self.assertRaises(SystemExit) as raised:
                cli_main.doctor_command(Namespace(json=False, strict=False))
        self.assertEqual(raised.exception.code, 0)
        self.assertIn("RAPID1414", out.getvalue())


if __name__ == "__main__":
    unittest.main()
