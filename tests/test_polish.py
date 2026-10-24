"""F5 polish: the small leftovers of 5.13 to 5.15 (finished projects, workflow names, contract rows,
backups of --refresh, service images and the text of RAPID1301)."""

from __future__ import annotations

import json
import re
import unittest
from pathlib import Path

from rapid_os.core.context import compose_project_context
from rapid_os.domain.architecture import (
    ArchitectureConfig,
    check_architecture,
    default_config,
    render_architecture_markdown,
    rules_for,
)
from rapid_os.domain.catalog import load_catalog, load_setup_doc_banks
from rapid_os.domain.execution import TEST_COMMAND_FIX
from rapid_os.domain.security import ci_workflow_path, render_ci_workflow
from rapid_os.domain.services import render_compose, render_tech_stack
from rapid_os.domain.setup import DocState, ServiceChoice, SetupActionKind, SetupState
from rapid_os.orchestration.conductor import NO_TEST_COMMAND_NOTICE
from rapid_os.orchestration.setup_conductor import next_setup_action
from tests.stack_helpers import complete_stacks
from tests.test_no_git import GitIsolated

ROOT = Path(__file__).resolve().parents[1]
TEMPLATES = ROOT / "templates"
CATALOG = load_catalog(TEMPLATES)
BANKS = load_setup_doc_banks(TEMPLATES)
DEPLOYMENT_BODY = (
    "## Destino\nRailway.\n\n## Configuración y secretos\nVariables del servicio.\n\n"
    "## Servicios gestionados\nPostgreSQL.\n\n## Verificación y reversión\nRollback del despliegue.\n"
)


class FinishedProjectTests(GitIsolated):
    """A project finished before a document existed does not get asked for it."""

    def write_finished(self, **extra):
        state = SetupState(
            stacks=complete_stacks("python-fastapi"), topology="fullstack-separated", archetype="mvp",
            agents=("codex",), test_command=(), finished=True, ai=False, services=(),
            docs={doc: DocState("skipped") for doc in ("brief", "business", "data-model", "architecture")},
            **extra,
        )
        path = self.root / ".rapid-os" / "setup.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        data = state.to_dict()
        for legacy_gap in ("services", "ai"):  # a file of before has neither the services nor the answer
            data.pop(legacy_gap, None)
        path.write_text(json.dumps(data), encoding="utf-8")
        return state

    def test_next_says_done_not_resolve_doc_deployment(self):
        self.write_finished()
        action = json.loads(self.rapid("setup", "next", "--json").stdout)
        self.assertEqual(action["kind"], "done")

    def test_the_pure_conductor_agrees(self):
        state = SetupState(
            stacks=complete_stacks("python-fastapi"), topology="fullstack-separated", archetype="mvp",
            agents=("codex",), test_command=(), finished=True, ai=False, services=(),
            docs={doc: DocState("skipped") for doc in ("brief", "business", "data-model", "architecture")},
        )
        action = next_setup_action(state, None or __import__("rapid_os.domain.project", fromlist=["x"]).ProjectModel(root=Path(".")), CATALOG, BANKS)
        self.assertEqual(action.kind, SetupActionKind.DONE)
        # ...while an onboarding that is still open asks for the document
        open_state = SetupState(**{**state.__dict__, "finished": False})
        self.assertEqual(
            next_setup_action(open_state, __import__("rapid_os.domain.project", fromlist=["x"]).ProjectModel(root=Path(".")), CATALOG, BANKS).to_dict()["doc"],
            "deployment",
        )

    def test_the_document_can_still_be_written_afterwards(self):
        self.write_finished()
        written = self.rapid("setup", "doc", "deployment", "--source", "drafted", "--file", "-", stdin=DEPLOYMENT_BODY)
        self.assertEqual(written.returncode, 0, written.stderr)
        self.assertTrue((self.root / "docs" / "DEPLOYMENT.md").is_file())
        state = json.loads((self.root / ".rapid-os" / "setup.json").read_text(encoding="utf-8"))
        self.assertEqual(state["docs"]["deployment"]["status"], "drafted")
        action = json.loads(self.rapid("setup", "next", "--json").stdout)
        self.assertEqual(action["kind"], "done")
        self.assertIn("deployment", action["unconfirmed_docs"])  # a draft is not a confirmation

    def test_deploy_prints_the_template_in_a_finished_project(self):
        self.write_finished()
        result = self.rapid("deploy", "--target", "railway")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("rapid setup doc deployment --reopen", result.stdout)


class WorkflowNameTests(unittest.TestCase):
    def test_each_workflow_is_named_after_its_language(self):
        for language in ("go", "typescript", "python"):
            text = render_ci_workflow(
                (TEMPLATES / "ci" / f"{language}-security.yml").read_text(encoding="utf-8"),
                archetype="mvp", language=language,
            )
            self.assertIn(f"\nname: rapid-security ({language})\n", text)
            self.assertEqual(ci_workflow_path(language), f".github/workflows/rapid-security-{language}.yml")

    def test_the_two_components_get_two_distinct_names_and_files(self):
        names = {
            re.search(r"^name: (.+)$", render_ci_workflow(
                (TEMPLATES / "ci" / f"{lang}-security.yml").read_text(encoding="utf-8"), archetype="mvp", language=lang
            ), re.MULTILINE).group(1)
            for lang in ("go", "typescript")
        }
        self.assertEqual(names, {"rapid-security (go)", "rapid-security (typescript)"})


class ContractRowTests(unittest.TestCase):
    TEMPLATE = (TEMPLATES / "architecture" / "modular-monolith.md").read_text(encoding="utf-8")

    def test_go_ends_its_table_with_the_public_contract(self):
        text = render_architecture_markdown(self.TEMPLATE, rules_for({"backend": "go"}))
        self.assertIn(
            "| paquete raíz del módulo (identificadores exportados) | Contrato público del módulo |", text
        )

    def test_every_stack_with_a_package_contract_has_its_row(self):
        for stack in ("go", "java-spring-boot", "kotlin-spring-boot", "rust-axum", "dotnet-aspnetcore", "php-laravel"):
            text = render_architecture_markdown(self.TEMPLATE, rules_for({"backend": stack}))
            self.assertIn("| Contrato público del módulo |", text.replace(" | Contrato público del módulo |", " | Contrato público del módulo |") ) if False else None
            table = text.split("| Nombre en este stack | Responsabilidad canónica |")[1]
            self.assertIn("| Contrato público del módulo |", table, stack)

    def test_rapid1420_shows_a_single_pair_of_parentheses(self):
        config = ArchitectureConfig.from_dict({"schema_version": 1, **default_config("go")})
        report = check_architecture(config, {
            "internal/pay/app/service.go": 'package app\n\nimport "example.com/app/internal/orders/store"\n',
        })
        (violation,) = report.violations
        self.assertIn("(paquete raíz del módulo)", violation.message)
        self.assertNotIn("((", violation.message)
        self.assertNotIn("))", violation.message)
        python = check_architecture(
            ArchitectureConfig.from_dict({"schema_version": 1, **default_config("python-fastapi")}),
            {"app/modules/a/api/x.py": "from app.modules.b.domain import y\n"},
        )
        self.assertIn("(public.py)", python.violations[0].message)


class BackupsOfRefreshTests(GitIsolated):
    def finish(self):
        for step in (
            ("stack", "python-fastapi"), ("topology", "fullstack-separated"), ("stack", "react-vite"),
            ("archetype", "mvp"), ("ai", "no"), ("agents", "codex"), ("test-command", "none"), ("services", "none"),
        ):
            self.assertEqual(self.rapid("setup", "set", *step).returncode, 0)
        for doc in ("brief", "business", "data-model", "architecture", "deployment"):
            self.assertEqual(self.rapid("setup", "doc", doc, "--skip").returncode, 0)
        self.assertEqual(self.rapid("setup", "finish").returncode, 0)

    def test_refresh_leaves_its_backups_in_rapid_os_backups(self):
        self.finish()
        standards = self.root / ".rapid-os" / "standards"
        (standards / "security.md").write_text("old security\n", encoding="utf-8")
        (standards / "coding-rules.md").write_text("old rules\n", encoding="utf-8")
        self.assertEqual(self.rapid("setup", "set", "archetype", "mvp", "--refresh").returncode, 0)
        self.assertEqual(sorted(p.name for p in standards.glob("*.bak")), [])
        backups = self.root / ".rapid-os" / "backups"
        names = sorted(p.name for p in backups.glob("*.bak"))
        self.assertTrue(any(n.startswith("security.md.") for n in names), names)
        self.assertTrue(any(n.startswith("coding-rules.md.") for n in names), names)

    def test_refresh_keeps_at_most_five_copies_of_each(self):
        from rapid_os.adapters.agents.base import AGENT_BACKUPS_KEPT

        self.finish()
        standards = self.root / ".rapid-os" / "standards"
        for index in range(AGENT_BACKUPS_KEPT + 3):
            (standards / "security.md").write_text(f"edited {index}\n", encoding="utf-8")
            self.assertEqual(self.rapid("setup", "set", "archetype", "mvp", "--refresh").returncode, 0)
        copies = list((self.root / ".rapid-os" / "backups").glob("security.md.*.bak"))
        self.assertEqual(len(copies), AGENT_BACKUPS_KEPT)

    def test_no_backup_reaches_the_agent_context(self):
        self.finish()
        standards = self.root / ".rapid-os" / "standards"
        (standards / "security.md.20260101T000000Z.bak").write_text("SENTINEL-BAK-STANDARDS\n", encoding="utf-8")
        (standards / "tech-stack.md.old.bak").write_text("SENTINEL-BAK-STACK\n", encoding="utf-8")
        (standards / "security.md").write_text("old security\n", encoding="utf-8")
        self.assertEqual(self.rapid("setup", "set", "archetype", "mvp", "--refresh").returncode, 0)
        backups = self.root / ".rapid-os" / "backups"
        (backups / "extra.md.bak").write_text("SENTINEL-BAK-BACKUPS\n", encoding="utf-8")
        context = compose_project_context(self.root / ".rapid-os", self.root)
        for sentinel in ("SENTINEL-BAK-STANDARDS", "SENTINEL-BAK-STACK", "SENTINEL-BAK-BACKUPS", "old security"):
            self.assertNotIn(sentinel, context)
        for name in ("AGENTS.md",):
            self.assertNotIn("SENTINEL-BAK", (self.root / name).read_text(encoding="utf-8"))


class ServicesPolishTests(unittest.TestCase):
    def test_mysql_pins_the_lts_line(self):
        self.assertEqual(CATALOG.services["mysql"].image, "mysql:9.7")
        self.assertTrue(CATALOG.services["mysql"].lts)
        self.assertIn("image: mysql:9.7", render_compose((ServiceChoice("database", "mysql", "now"),), CATALOG))
        self.assertTrue(any("mysql-server-versions" in url for url in CATALOG.services["mysql"].sources))

    def test_tech_stack_says_mysql_9_7_lts(self):
        template = (TEMPLATES / "stacks" / "backend" / "python-fastapi.md").read_text(encoding="utf-8")
        text = render_tech_stack(template, "python", (ServiceChoice("database", "mysql", "now"),), CATALOG)
        self.assertIn("- **Database:** MySQL 9.7 LTS + asyncmy.", text)
        other = render_tech_stack(template, "python", (ServiceChoice("database", "postgresql", "now"),), CATALOG)
        self.assertNotIn("LTS", other)

    def test_kafka_waits_for_the_jvm(self):
        compose = render_compose((ServiceChoice("stream", "kafka", "now"),), CATALOG)
        self.assertIn("start_period: 30s", compose)
        self.assertNotIn("start_period", render_compose((ServiceChoice("cache", "redis", "now"),), CATALOG))

    def test_azure_template_says_when_mariadb_was_retired(self):
        text = (TEMPLATES / "deploy" / "azure.md").read_text(encoding="utf-8")
        self.assertIn("19 de septiembre de 2025", text)
        self.assertIn("learn.microsoft.com/en-us/azure/mariadb/overview", text)
        self.assertIn("azure-database-for-mariadb-is-being-retired-on-19-september-2025", text)


class TestCommandNoticeTests(unittest.TestCase):
    def test_the_five_messages_of_the_conductor_share_one_text(self):
        source = (ROOT / "rapid_os" / "orchestration" / "conductor.py").read_text(encoding="utf-8")
        self.assertEqual(source.count("{NO_TEST_COMMAND_NOTICE}"), 5)
        self.assertNotIn("configure test_command in .rapid-os/config.json", source)
        self.assertNotIn("pass --test-command", source)

    def test_the_text_sends_to_rapid_setup_set_test_command(self):
        self.assertIn("rapid setup set test-command <cmd>", NO_TEST_COMMAND_NOTICE)
        self.assertIn("RAPID1301", NO_TEST_COMMAND_NOTICE)
        self.assertTrue(NO_TEST_COMMAND_NOTICE.startswith("No test_command configured (RAPID1301). Configura el comando"))
        self.assertIn(TEST_COMMAND_FIX, NO_TEST_COMMAND_NOTICE)


if __name__ == "__main__":
    unittest.main()
