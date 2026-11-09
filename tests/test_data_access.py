"""Data access per stack (the ORM is data, not a line of a Markdown file), the Hono stack and Cloudflare."""

from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

from rapid_os.domain.catalog import (
    DATA_ACCESS_MODELS,
    ENGINE_DATA_MODEL,
    RUNTIMES,
    CatalogError,
    load_catalog,
    load_setup_doc_banks,
)
from rapid_os.domain.data_access import (
    chosen_option,
    effective_stack,
    needs_data_access_choice,
    CLOUDFLARE_SERVICE_ALTERNATIVES,
    platform_notes,
    reconcile_data_access,
)
from rapid_os.domain.project import ProjectModel
from rapid_os.domain.scanner import scan_project, suggest_init_choices
from rapid_os.domain.services import ServiceInputError, check_stack_compatibility, render_tech_stack
from rapid_os.domain.setup import (
    DataAccessChoice,
    DocState,
    ServiceChoice,
    SetupActionKind,
    SetupState,
    SetupStateError,
    StackChoice,
)
from rapid_os.orchestration.setup_apply import SetupApplyError, set_decision
from rapid_os.orchestration.setup_conductor import next_setup_action
from tests.test_infrastructure_services import Project

ROOT = Path(__file__).resolve().parents[1]
TEMPLATES = ROOT / "templates"
CATALOG = load_catalog(TEMPLATES)
BANKS = load_setup_doc_banks(TEMPLATES)
BACKENDS = sorted(p.stem for p in (TEMPLATES / "stacks" / "backend").glob("*.json"))
AGENTS = ("claude", "codex")


def state_for(stack="node-fastify", engine="postgresql", choice=None, finished=False) -> SetupState:
    return SetupState(
        stacks={"backend": StackChoice(stack, "catalog")},
        topology="backend-only",
        archetype="mvp",
        ai=False,
        agents=("codex",),
        test_command=(),
        services=(ServiceChoice("database", engine),) if engine else (),
        data_access={"backend": DataAccessChoice(choice)} if choice else {},
        docs={"brief": DocState("skipped"), "business": DocState("skipped")},
        finished=finished,
    )


def next_action(state):
    return next_setup_action(state, ProjectModel(root=Path(".")), CATALOG, BANKS, agent_ids=AGENTS)


class CatalogDataTests(unittest.TestCase):
    def test_every_backend_declares_data_access_with_its_sources(self):
        self.assertIn("hono", BACKENDS)
        for stack_id in BACKENDS:
            access = CATALOG.stacks[stack_id].data_access
            self.assertIsNotNone(access, stack_id)
            for option in access.options:
                self.assertTrue(option.sources, option.id)
                self.assertTrue(set(option.runtimes) <= set(RUNTIMES), option.id)

    def test_every_database_a_backend_supports_has_an_option(self):
        for stack_id in BACKENDS:
            entry = CATALOG.stacks[stack_id]
            for engine in entry.supported_services:
                if engine in ENGINE_DATA_MODEL:
                    self.assertTrue(entry.data_access.for_engine(engine), f"{stack_id} + {engine}")

    def test_defaults_fit_their_model_and_frontends_declare_nothing(self):
        for stack_id in BACKENDS:
            access = CATALOG.stacks[stack_id].data_access
            for model, option_id in access.default.items():
                self.assertIn(model, DATA_ACCESS_MODELS)
                self.assertIn(model, access.option(option_id).models)
        self.assertIsNone(CATALOG.stacks["nextjs"].data_access)
        self.assertIsNone(CATALOG.stacks["supabase"].data_access)

    def test_document_options_say_how_the_shape_is_validated(self):
        for stack_id in BACKENDS:
            for option in CATALOG.stacks[stack_id].data_access.options:
                if "document" in option.models:
                    self.assertTrue(option.schema_validation, option.id)

    def test_no_stack_template_leaves_the_orm_undecided(self):
        for stack_id in BACKENDS:
            text = (TEMPLATES / "stacks" / "backend" / f"{stack_id}.md").read_text(encoding="utf-8")
            for line in text.splitlines():
                if line.startswith(("- **ORM:**", "- **Data access:**")):
                    self.assertNotIn(" / ", line, stack_id)

    def test_prisma_stays_on_the_stable_commands(self):
        prisma = CATALOG.stacks["node-fastify"].data_access.option("prisma")
        self.assertEqual(prisma.migrations.apply, ("pnpm", "prisma", "migrate", "deploy"))
        self.assertNotIn("mongodb", prisma.engines)
        self.assertIn("8.0.0-rc", prisma.notes)

    def test_sqlalchemy_variants_follow_cloudflare(self):
        access = CATALOG.stacks["python-fastapi"].data_access
        self.assertEqual(access.default["relational"], "sqlalchemy-async")
        self.assertEqual(access.option("sqlalchemy-async").runtimes, ("python",))
        self.assertIn("python-workers", access.option("sqlalchemy-sync").runtimes)


class CatalogValidationTests(unittest.TestCase):
    def broken(self, mutate, stack="go"):
        with tempfile.TemporaryDirectory() as tmp:
            templates = Path(tmp) / "templates"
            shutil.copytree(TEMPLATES, templates)
            path = templates / "stacks" / "backend" / f"{stack}.json"
            data = json.loads(path.read_text(encoding="utf-8"))
            mutate(data["data_access"], data)
            path.write_text(json.dumps(data), encoding="utf-8")
            with self.assertRaises(CatalogError) as caught:
                load_catalog(templates)
        self.assertIn("RAPID1401", str(caught.exception))
        return str(caught.exception)

    def test_default_outside_the_options(self):
        self.assertIn("not among the options", self.broken(lambda a, d: a["default"].update(relational="nope")))

    def test_default_of_another_model(self):
        self.assertIn("is not a relational option", self.broken(lambda a, d: a["default"].update(relational="mongo-go-driver")))

    def test_a_model_without_default(self):
        self.assertIn("must name the document option", self.broken(lambda a, d: a["default"].pop("document")))

    def test_engine_the_stack_does_not_support(self):
        def mutate(access, data):
            data["supported_services"].pop("mysql")
        self.assertIn("outside the stack's supported_services", self.broken(mutate))

    def test_engine_of_another_model(self):
        self.assertIn("does not fit the models", self.broken(lambda a, d: a["options"][0]["engines"].append("mongodb")))

    def test_engine_that_is_not_a_database(self):
        message = self.broken(lambda a, d: a["options"][0].update(engines=["postgresql", "redis"]))
        self.assertIn("does not fit the models", message)

    def test_unknown_runtime(self):
        self.assertIn("unknown runtime", self.broken(lambda a, d: a["options"][0].update(runtimes=["cobol"])))

    def test_argv_with_shell_metacharacters(self):
        for token in ("up;rm", "$DATABASE_URL", "a|b", "a&&b", "`x`", "a b", "<Bad Name>"):
            message = self.broken(lambda a, d: a["options"][0]["migrations"].update(apply=["goose", token]))
            self.assertIn("shell metacharacters", message, token)

    def test_unknown_kind_and_document_without_validation(self):
        self.assertIn("kind must be", self.broken(lambda a, d: a["options"][0].update(kind="magic")))
        self.assertIn("schema_validation", self.broken(lambda a, d: a["options"][-1].update(schema_validation=None)))

    def test_alternative_for_an_engine_the_stack_supports(self):
        def mutate(access, data):
            data["service_alternatives"] = {"postgresql": "something else"}
        self.assertIn("service_alternatives", self.broken(mutate))


class OnboardingTests(unittest.TestCase):
    def test_choose_data_access_with_several_options(self):
        action = next_action(state_for("node-fastify", "postgresql"))
        self.assertEqual(action.kind, SetupActionKind.CHOOSE_DATA_ACCESS)
        payload = action.to_dict()
        self.assertEqual([o["id"] for o in payload["options"]], ["drizzle", "prisma", "kysely"])
        self.assertEqual(payload["recommended"], "drizzle")
        self.assertTrue(all(o["notes"] and o["sources"] for o in payload["options"]))
        self.assertEqual(payload["command"], ["rapid", "setup", "set", "data-access", "<id>", "--component", "backend"])
        self.assertIn("--recommended", payload["alt_command"])

    def test_the_options_are_those_of_the_engine_and_the_recommended_one_fits_it(self):
        payload = next_action(state_for("node-fastify", "mongodb")).to_dict()
        self.assertEqual([o["id"] for o in payload["options"]], ["mongodb-driver", "mongoose"])
        self.assertEqual(payload["model"], "document")
        payload = next_action(state_for("go", "mysql")).to_dict()
        self.assertEqual(payload["recommended"], "gorm")  # pgx is PostgreSQL only

    def test_a_single_compatible_option_is_fixed_and_reported(self):
        state = state_for("php-laravel", engine=None)
        new, notes = set_decision(state, "services", "database:mysql", CATALOG, AGENTS)
        self.assertEqual(new.data_access["backend"], DataAccessChoice("eloquent", "auto"))
        self.assertTrue(any("Eloquent" in note for note in notes))
        self.assertNotEqual(next_action(new).kind, SetupActionKind.CHOOSE_DATA_ACCESS)

    def test_no_database_no_stack_options_and_baas_do_not_ask(self):
        self.assertFalse(needs_data_access_choice(state_for("node-fastify", engine=None), CATALOG))
        baas = replace(state_for(), stacks={"frontend": StackChoice("nextjs", "catalog"), "baas": StackChoice("supabase", "catalog")})
        self.assertFalse(needs_data_access_choice(baas, CATALOG))
        generic = replace(state_for(), stacks={"backend": StackChoice("generic", "generic")})
        self.assertFalse(needs_data_access_choice(generic, CATALOG))

    def test_set_rejects_what_does_not_fit(self):
        state = state_for("node-fastify", "mariadb")
        with self.assertRaises(SetupApplyError) as caught:
            set_decision(state, "data-access", "drizzle", CATALOG, AGENTS)
        self.assertIn("RAPID1402", str(caught.exception))
        self.assertIn("prisma", str(caught.exception))
        with self.assertRaises(SetupApplyError) as caught:
            set_decision(state, "data-access", "nope", CATALOG, AGENTS)
        self.assertIn("RAPID1413", str(caught.exception))
        with self.assertRaises(SetupApplyError) as caught:
            set_decision(state_for("node-fastify", engine=None), "data-access", "drizzle", CATALOG, AGENTS)
        self.assertIn("database service", str(caught.exception))

    def test_a_choice_that_no_longer_fits_is_undecided_again(self):
        state = state_for("node-fastify", "postgresql", choice="drizzle")
        new, notes = set_decision(state, "services", "database:mongodb", CATALOG, AGENTS)
        self.assertEqual(new.data_access, {})
        self.assertTrue(any("drizzle" in note for note in notes))
        new, _notes = set_decision(state, "stack", "go", CATALOG, AGENTS, component="backend")
        self.assertEqual(new.data_access, {})

    def test_an_agent_decision_is_recorded_as_such(self):
        new, _ = set_decision(state_for(), "data-access", "prisma", CATALOG, AGENTS, decided_by="agent")
        self.assertEqual(new.data_access["backend"], DataAccessChoice("prisma", "agent"))

    def test_setup_json_without_data_access_is_valid_and_keeps_the_shape(self):
        data = state_for().to_dict()
        self.assertNotIn("data_access", data)
        self.assertEqual(SetupState.from_dict(data).data_access, {})
        finished = SetupState.from_dict({**state_for().to_dict(), "finished": True})
        self.assertFalse(needs_data_access_choice(finished, CATALOG))
        self.assertNotEqual(next_action(finished).kind, SetupActionKind.CHOOSE_DATA_ACCESS)

    def test_setup_json_round_trip_and_invalid_values(self):
        state = state_for(choice="prisma")
        self.assertEqual(SetupState.from_dict(state.to_dict()).data_access, state.data_access)
        for bad in ([], {"mobile": {"id": "x"}}, {"backend": {"id": ""}}, {"backend": {"id": "x", "decided_by": "cat"}}):
            with self.assertRaises(SetupStateError, msg=str(bad)):
                SetupState.from_dict({**state.to_dict(), "data_access": bad})


class EffectsTests(unittest.TestCase):
    TEMPLATE = "- **ORM:** Drizzle ORM + drizzle-kit (migrations).\n- **Database:** PostgreSQL + pg.\n- **Version Control:** Git.\n"

    def render(self, stack, engine, option_id, template=TEMPLATE):
        entry = CATALOG.stacks[stack]
        state = state_for(stack, engine, choice=option_id)
        return render_tech_stack(
            template, "typescript", state.services, CATALOG, effective_stack(entry, state), chosen_option(state, CATALOG)
        )

    def test_the_standard_names_the_option_chosen(self):
        text = self.render("node-fastify", "postgresql", "prisma")
        self.assertIn("- **ORM:** Prisma ORM 7 + prisma migrate (migrations).", text)
        self.assertNotIn("Drizzle", text)

    def test_go_replaces_its_data_access_line(self):
        text = self.render("go", "postgresql", "gorm", "- **Data access:** pgx + sqlc + goose (migrations).\n- **Database:** x\n")
        self.assertIn("- **ORM:** GORM + goose (migrations).", text)
        self.assertNotIn("sqlc", text)

    def test_documents_name_the_schema_validation(self):
        text = self.render("node-fastify", "mongodb", "mongoose")
        self.assertIn("- **ODM:** Mongoose.", text)
        self.assertIn("- **Schema validation:** Esquemas de Mongoose", text)

    def test_the_sync_variant_changes_the_driver_and_the_url(self):
        state = state_for("python-fastapi", "postgresql", choice="sqlalchemy-sync")
        entry = effective_stack(CATALOG.stacks["python-fastapi"], state)
        self.assertEqual(entry.supported_services["postgresql"]["driver"], "psycopg")
        self.assertIn("+psycopg", entry.supported_services["postgresql"]["url"])
        self.assertEqual(CATALOG.stacks["python-fastapi"].supported_services["postgresql"]["driver"], "asyncpg")

    def test_the_data_model_document_carries_the_commands(self):
        payload = next_action(state_for("node-fastify", "postgresql", choice="drizzle")).to_dict()
        self.assertEqual(payload["doc"], "data-model")
        self.assertEqual(payload["data_access"]["migrations"]["tool"], "drizzle-kit")
        self.assertEqual(payload["data_access"]["migrations"]["apply"], ["pnpm", "drizzle-kit", "migrate"])

    def test_the_data_model_document_carries_the_schema_validation(self):
        payload = next_action(state_for("node-fastify", "mongodb", choice="mongoose")).to_dict()
        self.assertIsNone(payload["data_access"]["migrations"])
        self.assertIn("Mongoose", payload["data_access"]["schema_validation"])


class HonoTests(unittest.TestCase):
    def test_stack_shape(self):
        entry = CATALOG.stacks["hono"]
        self.assertEqual(entry.compatible_topologies, ("backend-only", "fullstack-separated"))
        self.assertEqual(entry.test_command(), ["pnpm", "test"])
        self.assertEqual(entry.data_access.default, {"relational": "drizzle"})
        self.assertEqual(set(entry.supported_services), {"postgresql", "mysql"})
        for item in ("node_modules/", "dist/", ".wrangler/", ".dev.vars*", ".env"):
            self.assertIn(item, entry.gitignore)
        self.assertEqual(entry.factors["hosting_fit"], "edge, serverless")
        for runtime in ("Node.js", "Bun", "Deno"):
            self.assertIn(runtime, (TEMPLATES / "stacks" / "backend" / "hono.md").read_text(encoding="utf-8"))

    def test_rabbitmq_is_rejected_naming_queues(self):
        with self.assertRaises(ServiceInputError) as caught:
            check_stack_compatibility((ServiceChoice("queue", "rabbitmq"),), "hono", CATALOG)
        self.assertEqual(caught.exception.code, "RAPID1402")
        self.assertIn("Cloudflare Queues", caught.exception.message)

    def test_kafka_mongodb_and_redis_are_rejected_with_an_alternative(self):
        for role, engine in (("stream", "kafka"), ("database", "mongodb"), ("cache", "redis")):
            with self.assertRaises(ServiceInputError) as caught:
                check_stack_compatibility((ServiceChoice(role, engine),), "hono", CATALOG)
            self.assertIn("Alternative:", caught.exception.message, engine)

    def test_postgresql_and_mysql_are_accepted(self):
        for engine in ("postgresql", "mysql"):
            check_stack_compatibility((ServiceChoice("database", engine),), "hono", CATALOG)

    def test_prisma_only_on_postgresql_from_workers(self):
        options = CATALOG.stacks["hono"].data_access
        self.assertEqual(options.option("prisma").engines, ("postgresql",))
        self.assertEqual([o.id for o in options.for_engine("mysql")], ["drizzle", "kysely"])


class CloudflareTests(Project):
    def test_compatibility_note_for_async_sqlalchemy(self):
        notes = platform_notes(state_for("python-fastapi", "postgresql", choice="sqlalchemy-async"), CATALOG)
        self.assertIn("no corre en Python Workers", notes["cloudflare"]["note"])
        self.assertIn("sqlalchemy-sync", notes["cloudflare"]["note"])
        self.assertTrue(all(s.startswith("https://developers.cloudflare.com/") for s in notes["cloudflare"]["sources"]))

    def test_no_note_when_it_fits(self):
        self.assertEqual(platform_notes(state_for("hono", "postgresql", choice="drizzle"), CATALOG), {})
        self.assertEqual(platform_notes(state_for("python-fastapi", "postgresql", choice="sqlalchemy-sync"), CATALOG), {})

    def test_note_for_a_stack_that_is_not_documented_in_workers(self):
        note = platform_notes(state_for("go", "postgresql", choice="pgx-sqlc"), CATALOG)["cloudflare"]["note"]
        self.assertIn("Containers", note)
        beanie = platform_notes(state_for("python-fastapi", "mongodb", choice="beanie"), CATALOG)["cloudflare"]["note"]
        self.assertNotIn("sqlalchemy", beanie)

    def test_a_project_finished_without_a_choice_is_judged_by_its_recommended_option(self):
        finished = replace(state_for("python-fastapi", "postgresql"), finished=True)
        note = platform_notes(finished, CATALOG)["cloudflare"]["note"]
        self.assertIn("SQLAlchemy 2 (async)", note)
        self.assertIn("no corre en Python Workers", note)
        sync = replace(finished, data_access={"backend": DataAccessChoice("sqlalchemy-sync")})
        self.assertEqual(platform_notes(sync, CATALOG), {})
        # Without a database the stack is judged as a whole: FastAPI does run in Python Workers.
        self.assertEqual(platform_notes(replace(finished, services=()), CATALOG), {})

    def test_a_service_without_an_equivalent_adds_a_line_with_the_alternative(self):
        state = replace(
            state_for("python-fastapi", "postgresql", choice="sqlalchemy-sync"),
            services=(ServiceChoice("database", "postgresql"), ServiceChoice("queue", "rabbitmq")),
        )
        note = platform_notes(state, CATALOG)["cloudflare"]
        self.assertEqual(len(note["lines"]), 1)
        self.assertIn("queue:rabbitmq@now", note["note"])
        self.assertIn("Cloudflare Queues", note["note"])
        self.assertIn("idempotente", note["note"])

    def test_a_later_service_counts_too_and_each_engine_has_its_line(self):
        state = replace(
            state_for("python-fastapi", "postgresql", choice="sqlalchemy-async"),
            services=(ServiceChoice("database", "postgresql"), ServiceChoice("cache", "redis", "later"),
                      ServiceChoice("stream", "kafka", "later")),
        )
        note = platform_notes(state, CATALOG)["cloudflare"]
        self.assertEqual(len(note["lines"]), 3)  # the ORM, redis and kafka
        self.assertIn("cache:redis@later", note["note"])
        self.assertIn("no es Redis", note["note"])
        self.assertIn("stream:kafka@later", note["note"])

    def test_hono_with_postgresql_has_no_note(self):
        self.assertEqual(platform_notes(state_for("hono", "postgresql"), CATALOG), {})

    def test_the_stack_and_the_template_say_the_same_as_the_note(self):
        hono = CATALOG.stacks["hono"].service_alternatives
        template = (TEMPLATES / "deploy" / "cloudflare.md").read_text(encoding="utf-8")
        self.assertEqual(set(hono), set(CLOUDFLARE_SERVICE_ALTERNATIVES))
        for engine, alternative in CLOUDFLARE_SERVICE_ALTERNATIVES.items():
            self.assertTrue(hono[engine].startswith(alternative), engine)
            self.assertIn(alternative.rstrip("."), template, engine)
        engines = [s for s in CATALOG.services if CATALOG.services[s].role != "database" or s in ("mongodb", "mariadb")]
        self.assertEqual(set(engines), set(CLOUDFLARE_SERVICE_ALTERNATIVES))

    def test_the_deployment_action_carries_the_note_without_blocking(self):
        state = replace(
            state_for("python-fastapi", "postgresql", choice="sqlalchemy-async"),
            docs={doc: DocState("skipped") for doc in ("brief", "business", "data-model", "architecture")},
        )
        payload = next_action(state).to_dict()
        self.assertEqual(payload["doc"], "deployment")
        self.assertIn("cloudflare", payload["platform_notes"])

    def test_platform_is_an_option_of_the_document(self):
        deployment = json.loads((TEMPLATES / "setup" / "docs" / "deployment.json").read_text(encoding="utf-8"))
        platforms = next(q for q in deployment["questions"] if q["id"] == "platform")["options"]
        self.assertIn("cloudflare", platforms)
        self.assertIn("cloudflare", (TEMPLATES / "shortcuts" / "rapid-init.md").read_text(encoding="utf-8"))

    def test_rapid_deploy_prints_the_template(self):
        result = self.rapid("deploy", "--target", "cloudflare")
        self.assertEqual(result.returncode, 0, result.stderr)
        for section in ("## Destino", "## Configuración y secretos", "## Servicios gestionados", "## Con Supabase",
                        "## Verificación y reversión", "## Fuentes oficiales"):
            self.assertIn(section, result.stdout)
        self.assertIn("Hyperdrive", result.stdout)

    def test_scanner_detects_every_wrangler_file(self):
        for name in ("wrangler.toml", "wrangler.json", "wrangler.jsonc"):
            with tempfile.TemporaryDirectory() as tmp:
                (Path(tmp) / name).write_text("{}\n", encoding="utf-8")
                model = scan_project(Path(tmp))
            self.assertIn("cloudflare", model.values("deploy_provider"), name)

    def test_scanner_suggests_hono(self):
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "package.json").write_text('{"dependencies": {"hono": "^4"}}', encoding="utf-8")
            suggestions = suggest_init_choices(scan_project(Path(tmp)))
        self.assertEqual(suggestions.stack.value, "hono")


class CommandTests(Project):
    def decide(self, stack="node-fastify"):
        for key, value in (("stack", stack), ("topology", "backend-only"), ("archetype", "mvp"), ("ai", "no"),
                           ("agents", "codex"), ("test-command", "none")):
            self.assertEqual(self.rapid("setup", "set", key, value).returncode, 0)
        for doc in ("brief", "business"):
            self.assertEqual(self.rapid("setup", "doc", doc, "--skip").returncode, 0)

    def setup_json(self):
        return json.loads((self.root / ".rapid-os" / "setup.json").read_text(encoding="utf-8"))

    def finish(self):
        for doc in ("data-model", "architecture", "deployment"):
            self.assertEqual(self.rapid("setup", "doc", doc, "--skip").returncode, 0)
        result = self.rapid("setup", "finish")
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_the_whole_decision(self):
        self.decide()
        self.assertEqual(self.rapid("setup", "set", "services", "database:postgresql").returncode, 0)
        payload = json.loads(self.rapid("setup", "next", "--json").stdout)
        self.assertEqual(payload["kind"], "choose_data_access")
        self.assertIn("Setup next: choose_data_access", self.rapid("setup", "next").stdout)
        self.assertEqual(self.rapid("setup", "set", "data-access", "--recommended").returncode, 0)
        self.assertEqual(self.setup_json()["data_access"], {"backend": {"id": "drizzle", "decided_by": "person"}})
        self.assertEqual(json.loads(self.rapid("setup", "next", "--json").stdout)["doc"], "data-model")
        self.finish()
        standard = self.root / ".rapid-os" / "standards" / "tech-stack.md"
        self.assertIn("Drizzle ORM + drizzle-kit", standard.read_text(encoding="utf-8"))
        # After the onboarding it follows the rules of the stack: it applies at once, without reopening.
        result = self.rapid("setup", "set", "data-access", "prisma", "--component", "backend")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Prisma ORM 7", standard.read_text(encoding="utf-8"))
        self.assertNotIn("Drizzle", standard.read_text(encoding="utf-8"))
        self.assertTrue(self.setup_json()["finished"])

    def test_a_project_finished_before_data_access_is_not_reopened(self):
        self.decide()
        self.assertEqual(self.rapid("setup", "set", "services", "database:postgresql").returncode, 0)
        path = self.root / ".rapid-os" / "setup.json"
        data = self.setup_json()
        data["docs"].update({d: {"status": "skipped", "confirmed": False, "sha256": ""} for d in ("data-model", "architecture", "deployment")})
        path.write_text(json.dumps({**data, "finished": True}), encoding="utf-8")
        result = self.rapid("setup", "set", "archetype", "corporate")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(self.setup_json()["finished"])
        self.assertNotIn("data_access", self.setup_json())

    def test_recommended_takes_no_value_and_needs_a_database(self):
        self.decide()
        self.assertEqual(self.rapid("setup", "set", "services", "none").returncode, 0)
        result = self.rapid("setup", "set", "data-access", "--recommended")
        self.assertEqual(result.returncode, 1)
        self.assertIn("RAPID1413", result.stderr)

    def test_hono_rabbitmq_through_the_command(self):
        self.decide("hono")
        result = self.rapid("setup", "set", "services", "database:postgresql,queue:rabbitmq")
        self.assertEqual(result.returncode, 1)
        self.assertIn("RAPID1402", result.stderr)
        self.assertIn("Cloudflare Queues", result.stderr)


class ReconcileTests(unittest.TestCase):
    def test_nothing_changes_when_it_still_fits(self):
        state = state_for(choice="prisma")
        self.assertEqual(reconcile_data_access(state, CATALOG), (state, ()))


if __name__ == "__main__":
    unittest.main()
