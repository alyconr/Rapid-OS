"""F5: infrastructure services come from a recorded decision (not from the stack), run in
containers to test the data model from the first feature, and the gate never depends on Docker."""

from __future__ import annotations

import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

from rapid_os.domain.catalog import CatalogError, load_catalog, load_setup_doc_banks, load_stack_questions
from rapid_os.domain.project import ProjectModel
from rapid_os.domain.project_docs import validate_doc_body
from rapid_os.domain.services import (
    ServiceInputError,
    active_conditions,
    merge_compose,
    parse_services,
    render_compose,
    render_env_example,
    render_tech_stack,
)
from rapid_os.domain.setup import DocState, ServiceChoice, SetupActionKind, SetupState, StackChoice
from rapid_os.orchestration.setup_conductor import next_setup_action
from tests.stack_helpers import complete_stacks
from tests.test_no_git import GitIsolated, approve

ROOT = Path(__file__).resolve().parents[1]
TEMPLATES = ROOT / "templates"
CATALOG = load_catalog(TEMPLATES)
BANKS = load_setup_doc_banks(TEMPLATES)
STACK_QUESTIONS = load_stack_questions(TEMPLATES)
ENGINES = ("postgresql", "mysql", "mariadb", "mongodb", "redis", "valkey", "rabbitmq", "kafka")
ALL_DOCS = ("brief", "business", "data-model", "architecture", "deployment")


def next_action(state):
    return next_setup_action(
        state, ProjectModel(root=Path(".")), CATALOG, BANKS,
        stack_questions=STACK_QUESTIONS, agent_ids=("claude", "codex"),
    )


def decided(services=None, skipped=("brief", "business"), stack="python-api") -> SetupState:
    return SetupState(
        stacks=complete_stacks(stack), topology="fullstack-separated", archetype="mvp", ai=False,
        agents=("codex",), test_command=(), services=services,
        docs={doc: DocState("skipped") for doc in skipped},
    )


class CatalogTests(unittest.TestCase):
    def test_the_eight_engines_are_valid_and_pinned(self):
        self.assertEqual(set(CATALOG.services), set(ENGINES))
        for engine in ENGINES:
            entry = CATALOG.services[engine]
            with self.subTest(engine=engine):
                self.assertNotEqual(entry.image.rpartition(":")[2], "latest")
                self.assertTrue(entry.sources and all(s.startswith("https://") for s in entry.sources))
                self.assertEqual(set(entry.drivers), {"python", "typescript"})
                self.assertTrue(entry.ports)
                self.assertTrue(entry.connection_env)

    def test_kafka_is_a_complete_kraft_node_whose_data_survives_the_container(self):
        kafka = CATALOG.services["kafka"]
        # Defining KAFKA_* replaces the image's default configuration: all of it must be here.
        for name in ("KAFKA_NODE_ID", "KAFKA_PROCESS_ROLES", "KAFKA_LISTENERS", "KAFKA_ADVERTISED_LISTENERS",
                     "KAFKA_CONTROLLER_LISTENER_NAMES", "KAFKA_LISTENER_SECURITY_PROTOCOL_MAP",
                     "KAFKA_CONTROLLER_QUORUM_VOTERS", "KAFKA_INTER_BROKER_LISTENER_NAME", "CLUSTER_ID"):
            self.assertIn(name, kafka.fixed_env)
        # The default log.dirs is /tmp/kraft-combined-logs, lost without a volume.
        self.assertEqual(kafka.fixed_env["KAFKA_LOG_DIRS"], "/var/lib/kafka/data")
        self.assertEqual(kafka.volume, {"name": "kafka-data", "path": "/var/lib/kafka/data"})
        self.assertIn("kafka-broker-api-versions.sh", kafka.healthcheck["test"][1])
        self.assertTrue(any("docker/examples" in s for s in kafka.sources))

    def test_mariadb_uses_the_documented_healthcheck(self):
        self.assertEqual(
            CATALOG.services["mariadb"].healthcheck["test"],
            ["CMD", "healthcheck.sh", "--connect", "--innodb_initialized"],
        )

    def test_no_template_says_not_confirmed(self):
        for path in (TEMPLATES / "deploy").glob("*.md"):
            self.assertNotIn("No confirmado", path.read_text(encoding="utf-8"), path.name)

    def test_an_invalid_service_is_rapid1401(self):
        with tempfile.TemporaryDirectory() as tmp:
            copy = Path(tmp) / "templates"
            shutil.copytree(TEMPLATES, copy)
            path = copy / "services" / "redis.json"
            data = json.loads(path.read_text(encoding="utf-8"))
            for broken in ({"image": "redis"}, {"image": "redis:latest"}, {"sources": []}, {"role": "nope"}):
                path.write_text(json.dumps({**data, **broken}), encoding="utf-8")
                with self.subTest(broken=broken), self.assertRaises(CatalogError) as ctx:
                    load_catalog(copy)
                self.assertIn("RAPID1401", str(ctx.exception))


class ParseTests(unittest.TestCase):
    def test_valid_forms(self):
        self.assertEqual(parse_services("none", CATALOG), ())
        self.assertEqual(
            parse_services("database:mysql@now, queue:rabbitmq@later,cache:redis", CATALOG),
            (ServiceChoice("database", "mysql", "now"), ServiceChoice("queue", "rabbitmq", "later"),
             ServiceChoice("cache", "redis", "now")),
        )

    def test_invalid_inputs_are_rapid1413(self):
        for value in ("", "database", "banana:mysql", "database:oracle", "cache:mysql",
                      "database:mysql@soon", "database:mysql,database:mysql"):
            with self.subTest(value=value), self.assertRaises(ServiceInputError) as ctx:
                parse_services(value, CATALOG)
            self.assertEqual(ctx.exception.code, "RAPID1413")


class ConductorTests(unittest.TestCase):
    def test_services_come_after_brief_and_business_and_before_the_other_documents(self):
        pending_brief = next_action(decided(skipped=()))
        self.assertEqual((pending_brief.kind, pending_brief.to_dict()["doc"]), (SetupActionKind.RESOLVE_DOC, "brief"))
        action = next_action(decided())
        self.assertEqual(action.kind, SetupActionKind.CHOOSE_SERVICES)
        data = action.to_dict()
        self.assertEqual(data["suggested_services"], ["database:postgresql"])
        self.assertEqual({e["id"] for e in data["catalog"]}, set(ENGINES))
        after = next_action(decided(services=(ServiceChoice("database", "mysql", "now"),)))
        self.assertEqual(after.to_dict()["doc"], "data-model")
        self.assertEqual(after.to_dict()["services"][0]["engine"], "mysql")
        self.assertEqual(
            [s["id"] for s in after.to_dict()["conditional_sections"]], ["local_database"]
        )

    def test_none_is_a_decision(self):
        self.assertEqual(next_action(decided(services=())).to_dict()["doc"], "data-model")

    def test_deployment_is_the_last_document(self):
        services = (ServiceChoice("database", "mysql", "now"),)
        skipped = ("brief", "business", "data-model", "architecture")
        self.assertEqual(next_action(decided(services, skipped)).to_dict()["doc"], "deployment")


class ComposeTests(unittest.TestCase):
    CHOICES = (ServiceChoice("database", "postgresql", "now"), ServiceChoice("queue", "rabbitmq", "later"))

    def test_one_service_per_now_pinned_with_healthcheck_volume_and_loopback_ports(self):
        text = render_compose(self.CHOICES, CATALOG)
        self.assertIn("postgresql:", text)
        self.assertNotIn("rabbitmq:", text)
        self.assertIn("image: postgres:18", text)
        self.assertIn("healthcheck:", text)
        self.assertIn("127.0.0.1:5432:5432", text)
        self.assertIn("postgresql-data", text)
        self.assertNotIn(":latest", text)

    def test_env_example_has_the_connection_variable(self):
        self.assertIn("DATABASE_URL=", render_env_example(self.CHOICES, CATALOG, "python"))

    def test_merge_adds_only_the_missing_service_and_keeps_everything_else(self):
        existing = render_compose((ServiceChoice("database", "postgresql", "now"),), CATALOG)
        merged = merge_compose(existing, (*self.CHOICES[:1], ServiceChoice("queue", "rabbitmq", "now")), CATALOG)
        self.assertIsNone(merged.warning)
        self.assertEqual(merged.added, ("rabbitmq",))
        head, _, _ = existing.partition("\nvolumes:")
        self.assertIn(head, merged.text)  # the existing service is untouched
        self.assertIn("  postgresql-data:", merged.text)
        self.assertEqual(merged.text.count("\nvolumes:"), 1)
        self.assertIn("rabbitmq:", merged.text)

    def test_nothing_to_add_changes_nothing(self):
        existing = render_compose(self.CHOICES[:1], CATALOG)
        merged = merge_compose(existing, self.CHOICES[:1], CATALOG)
        self.assertEqual(merged.added, ())

    def test_unreadable_yaml_is_left_alone_with_a_warning(self):
        broken = "services:\n  web:\n\timage: [oops\n"
        merged = merge_compose(broken, self.CHOICES, CATALOG)
        self.assertEqual(merged.text, broken)
        self.assertTrue(merged.warning)


class TechStackTests(unittest.TestCase):
    def test_database_lines_follow_the_decision(self):
        template = (TEMPLATES / "stacks" / "backend" / "python-fastapi.md").read_text(encoding="utf-8")
        mysql = render_tech_stack(template, "python", (ServiceChoice("database", "mysql", "now"),), CATALOG)
        self.assertIn("asyncmy", mysql)
        self.assertNotIn("asyncpg", mysql)
        none = render_tech_stack(template, "python", (), CATALOG)
        self.assertNotIn("asyncpg", none)


class BodyValidationTests(unittest.TestCase):
    def test_architecture_needs_the_services_section(self):
        bank = BANKS["architecture"]
        body = "## Módulos\nx\n\n## Reglas de dependencia\nx\n"
        codes = [i.code for i in validate_doc_body(body, bank)]
        self.assertIn("RAPID1403", codes)
        ok = body + "\n## Servicios de infraestructura\nx\n"
        self.assertNotIn("services", " ".join(i.message for i in validate_doc_body(ok, bank)))

    def test_the_local_database_section_is_required_only_with_a_database(self):
        bank = BANKS["data-model"]
        body = "".join(f"## {t.titles[0]}\nx\n\n" for t in bank.required_sections)
        self.assertEqual(validate_doc_body(body, bank), ())
        conditions = active_conditions((ServiceChoice("database", "mysql", "now"),))
        self.assertEqual([i.code for i in validate_doc_body(body, bank, conditions)], ["RAPID1403"])


class Project(GitIsolated):
    def write_state(self, services, stack="python-api"):
        state = SetupState(
            stacks=complete_stacks(stack), topology="fullstack-separated", archetype="mvp", ai=False,
            agents=("codex",), test_command=(), services=tuple(ServiceChoice(**s) for s in services),
            docs={doc: DocState("skipped") for doc in ALL_DOCS},
        )
        path = self.root / ".rapid-os" / "setup.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(state.to_dict(), indent=2), encoding="utf-8")

    def finish(self, services, stack="python-api"):
        self.write_state(services, stack)
        result = self.rapid("setup", "finish", "--json")
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout)


class SetServicesCommandTests(Project):
    def decide(self):
        for key, value in (("stack", "python-api"), ("topology", "fullstack-separated"), ("stack", "react-vite"),
                           ("archetype", "mvp"), ("ai", "no"), ("agents", "codex"), ("test-command", "none")):
            self.assertEqual(self.rapid("setup", "set", key, value).returncode, 0)

    def test_valid_and_invalid_decisions(self):
        self.decide()
        ok = self.rapid("setup", "set", "services", "database:mysql@now,queue:rabbitmq@later")
        self.assertEqual(ok.returncode, 0, ok.stderr)
        state = json.loads((self.root / ".rapid-os" / "setup.json").read_text(encoding="utf-8"))
        self.assertEqual(state["services"][0], {"role": "database", "engine": "mysql", "when": "now"})
        self.assertEqual(self.rapid("setup", "set", "services", "none").returncode, 0)
        bad = self.rapid("setup", "set", "services", "database:oracle")
        self.assertEqual(bad.returncode, 1)
        self.assertIn("RAPID1413", bad.stderr)

    def test_a_stack_that_does_not_use_services_is_rapid1402(self):
        for key, value in (("stack", "docs-modern"),):
            self.assertEqual(self.rapid("setup", "set", key, value).returncode, 0)
        bad = self.rapid("setup", "set", "services", "database:postgresql")
        self.assertEqual(bad.returncode, 1)
        self.assertIn("RAPID1402", bad.stderr)
        self.assertEqual(self.rapid("setup", "set", "services", "none").returncode, 0)

    def test_next_asks_for_the_services(self):
        self.decide()
        for doc in ("brief", "business"):
            self.assertEqual(self.rapid("setup", "doc", doc, "--skip").returncode, 0)
        payload = json.loads(self.rapid("setup", "next", "--json").stdout)
        self.assertEqual(payload["kind"], "choose_services")
        self.assertEqual(payload["suggested_services"], ["database:postgresql"])


class FinishWritesTheLocalEnvironmentTests(Project):
    def test_compose_env_example_and_gitignore_in_an_empty_repository(self):
        payload = self.finish([{"role": "database", "engine": "mysql", "when": "now"},
                               {"role": "queue", "engine": "rabbitmq", "when": "later"}])
        compose = (self.root / "compose.yaml").read_text(encoding="utf-8")
        self.assertIn("mysql:9", compose)
        self.assertNotIn("rabbitmq", compose)
        self.assertIn("DATABASE_URL", (self.root / ".env.example").read_text(encoding="utf-8"))
        self.assertIn(".env", (self.root / ".gitignore").read_text(encoding="utf-8").splitlines())
        files = {item["file"] for item in payload["added_files"]}
        self.assertTrue({"compose.yaml", ".env.example"} <= files)
        self.assertIn("local-services", [a["id"] for a in payload["person_actions"]])
        self.assertIn("asyncmy", (self.root / ".rapid-os" / "standards" / "tech-stack.md").read_text(encoding="utf-8"))

    def test_later_becomes_now_adds_only_what_is_missing(self):
        self.finish([{"role": "database", "engine": "postgresql", "when": "now"}])
        compose = self.root / "compose.yaml"
        before = compose.read_text(encoding="utf-8")
        result = self.rapid("setup", "set", "services", "database:postgresql@now,queue:rabbitmq@now")
        self.assertEqual(result.returncode, 0, result.stderr)
        after = compose.read_text(encoding="utf-8")
        self.assertIn(before.partition("\nvolumes:")[0], after)  # nothing that was there changed
        self.assertIn("rabbitmq:", after)

    def test_no_services_writes_no_compose(self):
        payload = self.finish([])
        self.assertFalse((self.root / "compose.yaml").exists())
        self.assertNotIn("person_actions", payload)

    def test_the_review_announces_the_files_beforehand(self):
        self.write_state([{"role": "database", "engine": "postgresql", "when": "now"}])
        for doc in ("architecture", "deployment"):
            path = self.root / ".rapid-os" / "setup.json"
            data = json.loads(path.read_text(encoding="utf-8"))
            data["docs"].pop(doc)
            path.write_text(json.dumps(data), encoding="utf-8")
        body = "".join(f"## {s.titles[0]}\n\nx\n\n" for s in BANKS["architecture"].required_sections)
        written = self.rapid("setup", "doc", "architecture", "--source", "drafted", "--file", "-", stdin=body)
        self.assertEqual(written.returncode, 0, written.stderr)
        self.assertEqual(self.rapid("setup", "doc", "deployment", "--skip").returncode, 0)
        shown = json.loads(self.rapid("setup", "next", "--json").stdout)
        self.assertEqual(shown["kind"], "review_drafts")
        self.assertIn("compose.yaml", [p["file"] for p in shown["planned_files"]])
        self.assertFalse((self.root / "compose.yaml").exists())  # nothing is written until the onboarding closes

    def test_status_keeps_offering_the_action_while_compose_exists(self):
        self.finish([{"role": "database", "engine": "postgresql", "when": "now"}])
        status = json.loads(self.rapid("status", "--json").stdout)
        self.assertEqual([a["id"] for a in status["person_actions"]], ["local-services"])
        self.assertEqual(status["person_actions"][0]["command"], "docker compose up -d")
        (self.root / "compose.yaml").unlink()
        self.assertNotIn("person_actions", json.loads(self.rapid("status", "--json").stdout))


class DeployCommandTests(Project):
    def test_target_prints_the_template_and_writes_nothing(self):
        result = self.rapid("deploy", "--target", "railway")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Railway", result.stdout)
        self.assertIn("rapid setup doc deployment --reopen", result.stdout)
        self.assertFalse((self.root / "DEPLOY.md").exists())

    def test_every_platform_has_a_template_with_official_sources(self):
        for platform in ("aws", "azure", "vercel", "render", "railway", "dokploy"):
            text = (TEMPLATES / "deploy" / f"{platform}.md").read_text(encoding="utf-8")
            with self.subTest(platform=platform):
                self.assertIn("## Fuentes oficiales", text)
                self.assertIn("https://", text)
                for section in ("Destino", "Configuración y secretos", "Servicios gestionados",
                                "Verificación y reversión"):
                    self.assertIn(f"## {section}", text)

    def test_unknown_target_is_rapid1413(self):
        result = self.rapid("deploy", "--target", "heroku")
        self.assertEqual(result.returncode, 1)
        self.assertIn("RAPID1413", result.stderr)


class EmptyRepositoryEndToEndTests(Project):
    """python-api in an empty repository with database:mysql@now reaches PASS without Docker."""

    TEST_COMMAND = f'"{sys.executable}" -m unittest discover -s tests -t .'
    SPEC = {
        "title": "Listar talleres", "mode": "feature", "business_objective": "Ver los talleres",
        "problem_statement": "No hay listado", "scope": ["listado"], "acceptance_criteria": ["se lista"],
        "tasks": ["T001: Listar"],
    }
    CONFIG = """from pathlib import Path


def database_url(path=".env.example"):
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        if line.startswith("DATABASE_URL="):
            return line.split("=", 1)[1]
    raise KeyError("DATABASE_URL")
"""
    TEST = """import unittest

from app.config import database_url


class ConfigTests(unittest.TestCase):
    def test_the_url_comes_from_the_example_file_and_needs_no_server(self):
        self.assertTrue(database_url().startswith("mysql"))
"""

    def drive(self, implement):
        for _ in range(30):
            action = json.loads(self.rapid("next", "--json").stdout)["action"]
            if action["kind"] == "await_human_approval":
                return action["gate_ids"][0]
            if action["kind"] == "implement_task":
                implement()
            for key in ("command", "after"):
                if action.get(key):
                    result = self.rapid(*action[key][1:])
                    self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        self.fail("the run never reached a human gate")

    def onboard(self):
        for key, value in (
            ("stack", "python-api"), ("topology", "fullstack-separated"), ("stack", "react-vite"),
            ("archetype", "mvp"), ("ai", "no"),
            ("agents", "codex"), ("test-command", self.TEST_COMMAND), ("services", "database:mysql@now"),
        ):
            self.assertEqual(self.rapid("setup", "set", key, value).returncode, 0)
        for doc in ALL_DOCS:
            self.assertEqual(self.rapid("setup", "doc", doc, "--skip").returncode, 0)
        finished = self.rapid("setup", "finish")
        self.assertEqual(finished.returncode, 0, finished.stderr)
        self.assertIn("docker compose up -d", finished.stdout)

    def test_from_an_empty_folder_to_pass_without_docker(self):
        self.onboard()
        self.assertIn("mysql:9", (self.root / "compose.yaml").read_text(encoding="utf-8"))
        started = self.rapid("start", "feature", "--spec-file", "-", "--json", stdin=json.dumps(self.SPEC))
        self.assertEqual(started.returncode, 0, started.stderr)
        scaffold = json.loads(self.rapid("status", "--json").stdout)["run"]["tasks"][0]
        text = json.dumps(scaffold, ensure_ascii=False)
        for expected in (".env.example", "migraciones", "gate.tests pasa sin Docker", "healthcheck"):
            self.assertIn(expected, text)

        def implement():
            for relative in ("app/__init__.py", "app/modules/__init__.py", "app/shared/__init__.py",
                             "tests/__init__.py"):
                (self.root / relative).parent.mkdir(parents=True, exist_ok=True)
                (self.root / relative).write_text("", encoding="utf-8")
            (self.root / "app" / "config.py").write_text(self.CONFIG, encoding="utf-8")
            (self.root / "tests" / "test_config.py").write_text(self.TEST, encoding="utf-8")

        gate = self.drive(implement)  # gate.tests and gate.architecture ran as machine gates
        self.assertEqual(approve(self.root, gate, self.env).returncode, 0)
        done = self.rapid("finish")
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        self.assertIn("verdict PASS", done.stdout)


class IsolationWaiverTests(Project):
    """A repository without commits has no worktree to give: the run goes in the current workspace
    and the human gates stay. With commits nothing changes."""

    SPEC = {
        "title": "Crear tabla", "mode": "feature", "business_objective": "Guardar datos",
        "problem_statement": "No hay esquema", "scope": ["migrations/0001_init.sql"], "acceptance_criteria": ["existe"],
        "tasks": ["T001: Migrar"], "tags": ["database-migration"],
    }

    def project_with_a_migration(self):
        self.finish([{"role": "database", "engine": "postgresql", "when": "now"}])
        (self.root / "migrations").mkdir()
        (self.root / "migrations" / "0001_init.sql").write_text("create table t (id int);\n", encoding="utf-8")
        (self.root / "app.py").write_text("print('hi')\n", encoding="utf-8")

    def start(self):
        return self.rapid("start", "feature", "--spec-file", "-", "--json", stdin=json.dumps(self.SPEC))

    def test_no_commits_waives_the_isolation_and_keeps_the_human_gates(self):
        self.project_with_a_migration()
        self.assertNotEqual(self.git("rev-parse", "--verify", "HEAD").returncode, 0)
        started = self.start()
        self.assertEqual(started.returncode, 0, started.stderr)
        self.assertNotIn("RAPID1334", started.stdout + started.stderr)
        self.assertNotEqual(json.loads(started.stdout)["action"]["kind"], "blocked")
        run = json.loads(self.rapid("status", "--json").stdout)["run"]
        self.assertEqual(run["isolation_waived"], "no_commits")
        gates = [g["id"] for g in run["gates"]]
        self.assertNotIn("gate.workspace-isolation", gates)
        self.assertIn("gate.migration-review", gates)
        self.assertIn("gate.final-verification", gates)
        self.assertIn("Sin aislamiento", self.rapid("status").stdout)

    def test_a_repository_with_commits_is_not_weakened(self):
        self.project_with_a_migration()
        self.git("add", "-A")
        committed = self.git("-c", "user.email=a@b.c", "-c", "user.name=t", "commit", "-q", "-m", "init")
        self.assertEqual(committed.returncode, 0, committed.stderr)
        started = self.start()
        self.assertEqual(started.returncode, 0, started.stderr)
        run = json.loads(self.rapid("status", "--json").stdout)["run"]
        self.assertNotIn("isolation_waived", run)
        self.assertIn("gate.workspace-isolation", [g["id"] for g in run["gates"]])


if __name__ == "__main__":
    unittest.main()
