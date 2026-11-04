"""BaaS providers (Supabase, Firebase) as the `baas` component of fullstack-baas: the catalog, the onboarding
decision (`decided_by`), the topology guide by frontend and provider, the architecture rule, the security
baseline, the local environment, the test command, the scanner, MCP and deployment, and the rehearsal of
`/rapid-init` in an empty folder."""

from __future__ import annotations

import json
import os
import re
import stat
import sys
import tempfile
import unittest
from pathlib import Path

from rapid_os.adapters.setup_store import _derive_stacks
from rapid_os.domain import baas
from rapid_os.domain.architecture import (
    ArchitectureConfigError,
    architecture_document,
    architecture_standard,
    check_architecture,
    load_rules,
)
from rapid_os.domain.catalog import BAAS_FACTOR_KEYS, FACTOR_KEYS, CatalogError, load_catalog
from rapid_os.domain.mcp import build_mcp_config
from rapid_os.domain.project import Confidence, Evidence, ProjectFact, ProjectModel
from rapid_os.domain.scanner import suggest_init_choices
from rapid_os.domain.security import ci_language, has_api, render_ci_workflow, render_security_standard
from rapid_os.domain.setup import DECIDED_BY, SetupState, SetupStateError, StackChoice
from rapid_os.domain.topology_guide import render_topology, topology_conditions
from rapid_os.orchestration.setup_conductor import catalog_test_commands
from tests.test_onboarding_templates import Project

ROOT = Path(__file__).resolve().parents[1]
TEMPLATES = ROOT / "templates"
PROVIDERS = ("supabase", "firebase")
SSR = ("nextjs", "nuxt", "sveltekit")
SPA = ("react-vite", "vue-vite", "svelte-vite", "angular")
SECRET_SHAPES = re.compile(r"(sb_secret_\w{8,}|eyJ[A-Za-z0-9_-]{20,}|AIza[0-9A-Za-z_-]{20,}|-----BEGIN)")


def _catalog():
    return load_catalog(TEMPLATES)


class CatalogTests(unittest.TestCase):
    def test_both_providers_are_catalog_stacks_of_the_baas_component(self):
        catalog = _catalog()
        for provider in PROVIDERS:
            with self.subTest(provider=provider):
                entry = catalog.stacks[provider]
                self.assertEqual((entry.component, entry.covers), ("baas", ("baas",)))
                self.assertEqual(entry.compatible_topologies, ("fullstack-baas",))
                self.assertEqual(set(entry.factors), {*FACTOR_KEYS, *BAAS_FACTOR_KEYS})
                self.assertEqual(set(entry.factor_sources), set(entry.factors))
                for urls in entry.factor_sources.values():
                    self.assertTrue(all(url.startswith("https://") for url in urls))
                self.assertTrue(entry.fits and entry.avoid_if)
        self.assertEqual({s.id for s in catalog.options_for("baas") if s.component == "baas"}, set(PROVIDERS))

    def test_the_baas_specific_factors_say_what_the_task_asks_for(self):
        supabase, firebase = (_catalog().stacks[p].factors for p in PROVIDERS)
        self.assertIn("relacional", supabase["data_model"])
        self.assertIn("documentos", firebase["data_model"])
        self.assertIn("RLS", supabase["auth"])
        self.assertIn("Edge Functions", supabase["server_functions"])
        self.assertIn("Cloud Functions", firebase["server_functions"])
        self.assertIn("supabase start", supabase["local_development"])
        self.assertIn("emulators:start", firebase["local_development"])
        self.assertIn("autoalojamiento", supabase["exit_strategy"])
        self.assertIn("sin autoalojamiento", firebase["exit_strategy"])

    def test_a_baas_sidecar_without_the_baas_factors_is_rapid1401(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "templates"
            for folder in ("stacks", "topologies", "services"):
                import shutil

                shutil.copytree(TEMPLATES / folder, target / folder)
            path = target / "stacks" / "baas" / "supabase.json"
            data = json.loads(path.read_text(encoding="utf-8"))
            del data["factors"]["exit_strategy"]
            path.write_text(json.dumps(data), encoding="utf-8")
            with self.assertRaises(CatalogError) as raised:
                load_catalog(target)
            self.assertIn("RAPID1401", str(raised.exception))

    def test_every_template_names_its_official_sources_in_a_comment(self):
        for provider in PROVIDERS:
            text = (TEMPLATES / "stacks" / "baas" / f"{provider}.md").read_text(encoding="utf-8")
            with self.subTest(provider=provider):
                self.assertIn("<!-- Fuentes", text)
                self.assertRegex(text, r"https://(supabase\.com|firebase\.google\.com)/docs")


class DecidedByTests(unittest.TestCase):
    def test_a_decision_is_the_persons_unless_the_agent_took_it(self):
        self.assertEqual(DECIDED_BY, ("person", "agent"))
        self.assertEqual(StackChoice("supabase", "catalog").to_dict()["decided_by"], "person")
        state = SetupState(stacks={"baas": StackChoice("supabase", "catalog", None, "agent")})
        again = SetupState.from_dict(json.loads(json.dumps(state.to_dict())))
        self.assertEqual(again.stacks["baas"].decided_by, "agent")

    def test_a_file_from_before_the_field_reads_as_the_persons(self):
        data = SetupState(stacks={"frontend": StackChoice("react-vite", "catalog")}).to_dict()
        del data["stacks"]["frontend"]["decided_by"]
        self.assertEqual(SetupState.from_dict(data).stacks["frontend"].decided_by, "person")

    def test_an_unknown_decider_is_rapid1406(self):
        data = SetupState(stacks={"frontend": StackChoice("react-vite", "catalog")}).to_dict()
        data["stacks"]["frontend"]["decided_by"] = "robot"
        with self.assertRaises(SetupStateError) as raised:
            SetupState.from_dict(data)
        self.assertIn("RAPID1406", str(raised.exception))

    def test_the_marker_of_tech_stack_carries_an_agent_decision(self):
        catalog = _catalog()
        marker = "<!-- rapid-stack: frontend=react-vite baas=firebase decided_by.baas=agent -->"
        stacks = _derive_stacks(f"# x\n{marker}\n", catalog)
        self.assertEqual(stacks["baas"].decided_by, "agent")
        self.assertEqual(stacks["frontend"].decided_by, "person")


class ConductorTests(unittest.TestCase):
    def setUp(self):
        self.catalog = _catalog()

    def _commands(self, frontend, provider):
        state = SetupState(
            topology="fullstack-baas",
            stacks={"frontend": StackChoice(frontend, "catalog"), "baas": StackChoice(provider, "catalog")},
        )
        return catalog_test_commands(state, self.catalog)

    def test_the_test_command_is_only_the_frontends_so_gate_tests_needs_no_docker(self):
        for frontend, provider in (("nextjs", "supabase"), ("react-vite", "firebase"),
                                   ("react-vite", "supabase"), ("nextjs", "firebase")):
            items = self._commands(frontend, provider)
            with self.subTest(frontend=frontend, provider=provider):
                self.assertEqual([i["component"] for i in items], ["frontend"])
                self.assertEqual(items[0]["command"][:3], ["pnpm", "exec", "vitest"])
                flat = " ".join(" ".join(i["command"]) for i in items)
                self.assertNotIn("supabase", flat)
                self.assertNotIn("emulators", flat)

    def test_the_rules_test_is_offered_apart_from_the_test_command(self):

        self.assertEqual(baas.rules_test_command("supabase", ["pnpm", "exec", "vitest", "run"]), "supabase test db")
        self.assertEqual(
            baas.rules_test_command("firebase", ["pnpm", "exec", "vitest", "run"]),
            'firebase emulators:exec "pnpm run test:rules"',
        )
        self.assertEqual(baas.rules_test_command("firebase", None), 'firebase emulators:exec "npm run test:rules"')
        actions = baas.local_actions("firebase", initialized=True, frontend_test=["pnpm", "exec", "vitest", "run"])
        self.assertEqual([a["id"] for a in actions], ["baas-local", "baas-rules-test"])
        self.assertIn("gate.tests", actions[-1]["why"])

    def test_a_provider_sidecar_with_a_test_command_is_rapid1401(self):
        import shutil

        with tempfile.TemporaryDirectory() as tmp:
            templates = Path(tmp) / "templates"
            shutil.copytree(TEMPLATES, templates)
            path = templates / "stacks" / "baas" / "supabase.json"
            data = json.loads(path.read_text(encoding="utf-8"))
            data["default_test_command"] = ["supabase", "test", "db"]
            path.write_text(json.dumps(data), encoding="utf-8")
            with self.assertRaises(CatalogError) as ctx:
                load_catalog(templates)
            self.assertIn("gate.tests", str(ctx.exception))

    def test_choose_stack_of_baas_offers_only_the_providers(self):
        from rapid_os.domain.project import ProjectModel
        from rapid_os.orchestration.setup_conductor import _choose_stack

        state = SetupState(topology="fullstack-baas", stacks={"frontend": StackChoice("react-vite", "catalog")})
        action = _choose_stack(ProjectModel(facts=()), self.catalog, (), "baas", state).to_dict()
        self.assertEqual(sorted(o["id"] for o in action["options"]), sorted(PROVIDERS))
        self.assertNotIn("alt_command", action)

    def test_services_of_a_baas_project_do_not_offer_a_database(self):
        from rapid_os.orchestration.setup_conductor import BAAS_SERVICES_INSTRUCTION, _choose_services

        state = SetupState(
            topology="fullstack-baas",
            stacks={"frontend": StackChoice("react-vite", "catalog"), "baas": StackChoice("supabase", "catalog")},
        )
        action = _choose_services(state, self.catalog).to_dict()
        self.assertNotIn("database", action["roles"])
        self.assertFalse([s for s in action["catalog"] if s["role"] == "database"])
        self.assertIn("cache", action["roles"])
        self.assertEqual(action["suggested_services"], [])
        self.assertEqual(action["instruction"], BAAS_SERVICES_INSTRUCTION)


class TopologyGuideTests(unittest.TestCase):
    TEMPLATE = (TEMPLATES / "topologies" / "fullstack-baas.md").read_text(encoding="utf-8")

    def render(self, frontend, provider=None):
        stacks = {"frontend": frontend, **({"baas": provider} if provider else {})}
        return render_topology(self.TEMPLATE, "fullstack-baas", stacks)

    def test_a_server_rendered_frontend_mutates_from_the_server(self):
        for frontend in SSR:
            with self.subTest(frontend=frontend):
                text = self.render(frontend, "supabase")
                self.assertIn("runs the mutations", text)
                self.assertIn("from the server", text)
                self.assertNotIn("ONLY barrier", text)

    def test_a_spa_leaves_the_provider_rules_as_the_only_barrier(self):
        for frontend in SPA:
            with self.subTest(frontend=frontend):
                text = self.render(frontend, "firebase")
                self.assertIn("ONLY barrier", text)
                self.assertIn("server functions", text)
                self.assertNotIn("Server Actions", text)
                self.assertNotIn("RSC", text)

    def test_the_text_no_longer_assumes_nextjs(self):
        for frontend in (*SSR, *SPA):
            for provider in PROVIDERS:
                text = self.render(frontend, provider)
                self.assertNotIn("Next.js", text)
                self.assertNotIn("Server Actions", text)

    def test_each_provider_gets_its_own_rules_and_never_the_other_ones(self):
        supabase, firebase = self.render("react-vite", "supabase"), self.render("react-vite", "firebase")
        self.assertIn("Row Level Security", supabase)
        self.assertIn("sb_secret_", supabase)
        self.assertNotIn("firebase", supabase.lower())
        self.assertIn("App Check", firebase)
        self.assertIn("allow read, write: if false;", firebase)
        self.assertNotIn("supabase", firebase.lower())
        self.assertNotIn("postgres", firebase.lower())

    def test_without_a_provider_the_guide_says_it_is_undecided(self):
        text = self.render("react-vite")
        self.assertIn("not decided yet", text)
        self.assertNotIn("Row Level Security", text)
        self.assertEqual(topology_conditions({"frontend": "react-vite"}), frozenset({"spa", "provider-undecided"}))

    def test_other_topologies_are_copied_as_they_are(self):
        template = (TEMPLATES / "topologies" / "front-end-only.md").read_text(encoding="utf-8")
        self.assertEqual(render_topology(template, "front-end-only", {"frontend": "react-vite"}), template)

    def test_the_guide_is_still_recognised_as_fullstack_baas(self):
        from rapid_os.domain.validation import infer_topology

        for frontend in (SSR[0], SPA[0]):
            for provider in PROVIDERS:
                self.assertEqual(infer_topology(self.render(frontend, provider)), "fullstack-baas")


class ArchitectureTests(unittest.TestCase):
    def rules(self, frontend, provider, backend=None):
        stacks = {"frontend": frontend, "baas": provider, **({"backend": backend} if backend else {})}
        return load_rules(architecture_document(stacks))

    def test_a_project_on_a_baas_gets_a_frontend_rule_and_a_function_rule_at_the_root(self):
        supabase = self.rules("react-vite", "supabase")
        self.assertEqual([(r.component, r.modules_root) for r in supabase], [("frontend", "src/features"), ("baas", "supabase/functions")])
        self.assertEqual(supabase[1].shared_root, "supabase/functions/_shared")
        firebase = self.rules("react-vite", "firebase")
        self.assertEqual([(r.component, r.modules_root) for r in firebase], [("frontend", "src/features"), ("baas", "functions/src")])
        self.assertEqual({r.root for r in supabase + firebase}, {""})

    def test_a_framework_that_also_hosts_a_backend_gets_no_backend_rule_on_a_baas(self):
        rules = self.rules("nextjs", "supabase", backend="nextjs")
        self.assertEqual([r.component for r in rules], ["frontend", "baas"])

    def test_the_standard_lists_the_functions_per_component(self):
        standard = architecture_standard({"frontend": "react-vite", "baas": "supabase"})
        self.assertEqual([item["component"] for item in standard], ["frontend", "baas"])
        self.assertEqual(standard[1]["modules_root"], "supabase/functions")
        self.assertEqual(standard[1]["public_entry"], "index.ts")

    def test_the_sdk_is_restricted_to_data_access_and_one_client_in_shared(self):
        for provider, library, client in (
            ("supabase", "@supabase/supabase-js", "supabase-client"),
            ("firebase", "firebase/firestore", "firebase-client"),
        ):
            with self.subTest(provider=provider):
                frontend = self.rules("react-vite", provider)[0]
                self.assertEqual(frontend.restricted_imports[0].provider, provider)
                source = f"import {{ x }} from '{library}'\n"
                sources = {
                    "src/features/orders/data-access/api.ts": source,
                    f"src/shared/{client}.ts": source,
                    "src/features/orders/ui/List.tsx": source,
                    "src/features/orders/state/store.ts": source,
                    "src/shared/other.ts": source,
                    "src/main.tsx": source,
                    "src/features/orders/ui/List.test.tsx": source,
                }
                report = check_architecture(frontend, sources)
                self.assertEqual(
                    sorted({v.file for v in report.violations}),
                    ["src/features/orders/state/store.ts", "src/features/orders/ui/List.tsx", "src/main.tsx", "src/shared/other.ts"],
                )
                self.assertTrue(all(v.rule == "restricted_import" for v in report.violations))
                self.assertIn(provider, report.violations[0].message)

    def test_a_server_rendered_frontend_may_also_keep_a_server_client_in_shared(self):
        ssr = self.rules("nextjs", "supabase", backend="nextjs")[0]
        spa = self.rules("react-vite", "supabase")[0]
        source = "import { createServerClient } from '@supabase/ssr'\n"
        self.assertEqual(check_architecture(ssr, {"src/shared/supabase-server.ts": source}).violations, ())
        self.assertEqual(len(check_architecture(spa, {"src/shared/supabase-server.ts": source}).violations), 1)

    def test_functions_follow_the_module_rule(self):
        functions = self.rules("react-vite", "supabase")[1]
        sources = {
            "supabase/functions/pay/index.ts": "import { handle } from './api/handler.ts'\n",
            "supabase/functions/pay/api/handler.ts": (
                "import { repo } from '../infrastructure/repo.ts'\nimport { z } from '../../refund/domain/z.ts'\n"
            ),
            "supabase/functions/pay/domain/rule.ts": "import { createClient } from 'npm:@supabase/supabase-js@2'\n",
            "supabase/functions/_shared/client.ts": "import { x } from '../pay/index.ts'\n",
            "supabase/functions/pay/infrastructure/repo.ts": "import { createClient } from 'npm:@supabase/supabase-js@2'\n",
        }
        report = check_architecture(functions, sources)
        found = {(v.file, v.rule) for v in report.violations}
        self.assertIn(("supabase/functions/pay/api/handler.ts", "layer"), found)
        self.assertIn(("supabase/functions/pay/api/handler.ts", "cross_module"), found)
        self.assertIn(("supabase/functions/pay/domain/rule.ts", "domain_forbidden_import"), found)
        self.assertIn(("supabase/functions/_shared/client.ts", "shared"), found)
        self.assertNotIn("supabase/functions/pay/infrastructure/repo.ts", {v.file for v in report.violations})

    def test_firebase_functions_live_in_functions_src(self):
        functions = self.rules("react-vite", "firebase")[1]
        sources = {
            "functions/src/index.ts": "export { pay } from './pay'\n",
            "functions/src/pay/index.ts": "export {}\n",
            "functions/src/pay/domain/rule.ts": "import * as admin from 'firebase-admin'\n",
        }
        report = check_architecture(functions, sources)
        self.assertEqual([v.rule for v in report.violations], ["domain_forbidden_import"])

    def test_a_malformed_restriction_is_rapid1420(self):
        document = architecture_document({"frontend": "react-vite", "baas": "supabase"})
        document["rules"][0]["restricted_imports"][0]["allowed_layers"] = ["nope"]
        with self.assertRaises(ArchitectureConfigError):
            load_rules(document)


class SecurityTests(unittest.TestCase):
    BASELINE = (TEMPLATES / "security" / "baseline.md").read_text(encoding="utf-8")

    def render(self, *stack_ids, archetype="mvp"):
        return render_security_standard(self.BASELINE, archetype=archetype, stack_id=list(stack_ids), ai=False)

    def test_supabase_gets_rls_policies_tests_and_key_rules(self):
        text = self.render("react-vite", "supabase")
        self.assertIn("## Backend como servicio: Supabase", text)
        for needle in ("enable row level security", "supabase test db", "service_role", "sb_secret_", "auth.uid()", "OWASP ASVS V8"):
            with self.subTest(needle=needle):
                self.assertIn(needle, text)
        self.assertNotIn("Firebase", text.split("## NIST SSDF")[0])

    def test_firebase_gets_deny_by_default_rules_app_check_and_server_credentials(self):
        text = self.render("react-vite", "firebase")
        self.assertIn("## Backend como servicio: Firebase", text)
        for needle in ("allow read, write: if false;", "@firebase/rules-unit-testing", "App Check", "apiKey", "cuenta de servicio", "OWASP ASVS V13"):
            with self.subTest(needle=needle):
                self.assertIn(needle, text)
        self.assertNotIn("Supabase", text)

    def test_other_projects_keep_the_baseline_without_the_provider_sections(self):
        text = self.render("python-fastapi", "react-vite")
        self.assertNotIn("Backend como servicio", text)

    def test_a_baas_exposes_an_api_and_its_workflow_is_typescript(self):
        for provider in PROVIDERS:
            self.assertTrue(has_api(provider))
            self.assertEqual(ci_language(provider), "typescript")

    def test_the_workflow_follows_the_lockfile_and_never_needs_package_lock(self):
        template = (TEMPLATES / "ci" / "typescript-security.yml").read_text(encoding="utf-8")
        for provider, job in (("supabase", "rls-tests"), ("firebase", "rules-tests")):
            text = render_ci_workflow(template, archetype="mvp", stack_ids=["react-vite", provider])
            with self.subTest(provider=provider):
                # No step is skipped for lack of package-lock.json: the manager comes from the lockfile.
                self.assertNotIn("[ -f package-lock.json ] &&", text)
                self.assertNotIn("if [ -f package-lock.json ]; then\n            npm", text)
                self.assertIn("pnpm/action-setup@", text)
                self.assertRegex(text, r"pnpm/action-setup@[0-9a-f]{40} # v\d")
                self.assertIn("pnpm install --frozen-lockfile", text)
                self.assertIn("pnpm audit --audit-level high", text)
                self.assertIn("yarn install --immutable", text)
                self.assertIn("npm ci", text)
                job_text = text.split(f"  {job}:")[1].split("\n# endif")[0]
                self.assertIn("steps.pm.outputs.manager", job_text)
                self.assertIn('run="pnpm exec"', job_text)
                self.assertIn("pnpm install --frozen-lockfile", job_text)

    def test_the_workflow_runs_the_rules_tests_of_the_provider(self):
        template = (TEMPLATES / "ci" / "typescript-security.yml").read_text(encoding="utf-8")
        supabase = render_ci_workflow(template, archetype="mvp", stack_ids=["react-vite", "supabase"])
        firebase = render_ci_workflow(template, archetype="mvp", stack_ids=["react-vite", "firebase"])
        plain = render_ci_workflow(template, archetype="mvp", stack_ids=["react-vite"])
        self.assertIn("$run supabase test db", supabase)
        self.assertNotIn("emulators:exec", supabase)
        self.assertIn('$run firebase emulators:exec "$script"', firebase)
        self.assertNotIn("supabase test db", firebase)
        self.assertNotIn("rls-tests", plain)
        self.assertNotIn("rules-tests", plain)
        for text in (supabase, firebase):
            for line in re.findall(r"uses:\s*(\S+)", text):
                self.assertRegex(line, r"@[0-9a-f]{40}$")

    def test_every_standard_reference_of_the_provider_sections_is_a_full_citation(self):
        for provider in PROVIDERS:
            text = self.render("react-vite", provider)
            section = text.split(f"## Backend como servicio: {provider.capitalize()}")[1].split("\n## ")[0]
            for group in re.findall(r"\[([^\]]+)\]", section):
                for item in (part.strip() for part in group.split(",")):
                    self.assertTrue(item.startswith(("OWASP", "CWE")), item)

    def test_document_databases_get_nosql_injection_and_relational_ones_do_not(self):
        firestore = self.render("react-vite", "firebase")
        mongodb = render_security_standard(
            self.BASELINE, archetype="mvp", stack_id=["python-fastapi"], ai=False, engines=["mongodb"]
        )
        for text in (firestore, mongodb):
            section = text.split("## Bases de datos de documentos (Firestore, MongoDB)")[1].split("\n## ")[0]
            for needle in ("CWE-943", "OWASP A05:2025", "$where", "$gt", "OWASP ASVS V1"):
                with self.subTest(needle=needle):
                    self.assertIn(needle, section)
            for group in re.findall(r"\[([^\]]+)\]", section):
                for item in (part.strip() for part in group.split(",")):
                    self.assertTrue(item.startswith(("OWASP", "CWE")), item)
        self.assertIn("## MongoDB", mongodb)
        self.assertIn("127.0.0.1", mongodb.split("## MongoDB")[1])
        self.assertNotIn("## MongoDB", firestore)
        for relational in (self.render("react-vite", "supabase"),
                           render_security_standard(self.BASELINE, archetype="mvp", stack_id=["python-fastapi"],
                                                    ai=False, engines=["postgresql"])):
            self.assertNotIn("CWE-943", relational)


class LocalEnvironmentTests(unittest.TestCase):
    def test_the_variables_carry_the_prefix_of_the_frontend_and_no_real_secret(self):
        expectations = {"nextjs": "NEXT_PUBLIC_", "react-vite": "VITE_", "sveltekit": "PUBLIC_", "nuxt": "NUXT_PUBLIC_", "angular": ""}
        for frontend, prefix in expectations.items():
            for provider in PROVIDERS:
                with self.subTest(frontend=frontend, provider=provider):
                    text = baas.render_env(provider, frontend)
                    self.assertIn(f"{prefix}{'SUPABASE_URL' if provider == 'supabase' else 'FIREBASE_PROJECT_ID'}=", text)
                    self.assertIsNone(SECRET_SHAPES.search(text))
        text = baas.render_env("supabase", "nextjs")
        self.assertIn("SUPABASE_SECRET_KEY=\n", text)  # never with the client prefix, never with a value
        self.assertNotIn("NEXT_PUBLIC_SUPABASE_SECRET", text)
        self.assertIn("http://127.0.0.1:54321", text)
        self.assertIn("127.0.0.1:8080", baas.render_env("firebase", "react-vite"))

    def test_merging_adds_what_is_missing_and_never_edits_a_line(self):
        existing = "SUPABASE_DB_URL=postgresql://me:mine@db/mine\nOTHER=1\n"
        merged = baas.merge_env(existing, "supabase", "react-vite")
        self.assertTrue(merged.startswith(existing.rstrip("\n")))
        self.assertIn("VITE_SUPABASE_URL=http://127.0.0.1:54321", merged)
        self.assertEqual(merged.count("SUPABASE_DB_URL="), 1)
        self.assertEqual(baas.merge_env(merged, "supabase", "react-vite"), merged)

    def test_the_person_runs_the_cli_commands(self):
        init = baas.local_actions("supabase", initialized=False)
        # The rules test closes the list: the person runs it with the provider up (it is not gate.tests).
        self.assertEqual([a["command"] for a in init], ["supabase init", "supabase start", "supabase test db"])
        self.assertEqual(
            [a["command"] for a in baas.local_actions("supabase", initialized=True)], ["supabase start", "supabase test db"]
        )
        firebase = baas.local_actions("firebase", initialized=False)
        self.assertEqual(
            [a["command"] for a in firebase],
            ["firebase init", "firebase emulators:start", 'firebase emulators:exec "npm run test:rules"'],
        )
        self.assertEqual(baas.local_actions("firebase", initialized=True)[0]["command"], "firebase emulators:start")
        self.assertEqual(baas.local_actions(None, initialized=False), [])


class DocumentBankTests(unittest.TestCase):
    def test_the_conditions_follow_the_provider(self):
        from rapid_os.domain.services import active_conditions

        stacks = {"baas": StackChoice("firebase", "catalog")}
        self.assertEqual(active_conditions((), stacks), frozenset({"stack:baas", "stack:firebase", "model:documents"}))
        self.assertEqual(active_conditions((), {}), frozenset())

    def test_data_model_asks_collections_for_firebase_and_tables_for_supabase(self):
        from rapid_os.domain.catalog import load_setup_doc_banks

        banks = load_setup_doc_banks(TEMPLATES)
        by_condition = {}
        for section in banks["data-model"].conditional_sections:
            by_condition.setdefault(section.when, []).append(section.titles[0])
        self.assertEqual(by_condition["model:relational"], ["Tablas", "Migraciones"])
        self.assertEqual(by_condition["model:documents"], ["Colecciones y documentos", "Índices", "Validación del esquema"])
        self.assertEqual(by_condition["stack:supabase"], ["Políticas RLS"])
        self.assertEqual(by_condition["stack:firebase"], ["Reglas de seguridad"])
        for doc in ("architecture", "deployment"):
            self.assertEqual([s.titles[0] for s in banks[doc].conditional_sections if s.when == "stack:baas"], ["Proveedor BaaS"])

    def test_the_data_model_follows_the_store_not_only_the_baas(self):
        from rapid_os.domain.services import active_conditions, data_model
        from rapid_os.domain.setup import ServiceChoice

        cases = {
            "relational": [({}, "postgresql"), ({}, "mysql"), ({}, "mariadb"), ({"baas": StackChoice("supabase", "catalog")}, None)],
            "documents": [({}, "mongodb"), ({"baas": StackChoice("firebase", "catalog")}, None)],
        }
        for expected, variants in cases.items():
            for stacks, engine in variants:
                services = (ServiceChoice("database", engine),) if engine else ()
                with self.subTest(expected=expected, engine=engine, stacks=stacks):
                    self.assertEqual(data_model(services, stacks), expected)
                    self.assertIn(f"model:{expected}", active_conditions(services, stacks))
        self.assertIsNone(data_model((ServiceChoice("cache", "redis"),), {}))

    def test_the_questions_follow_the_data_model(self):
        from rapid_os.domain.catalog import load_catalog
        from rapid_os.domain.setup import ServiceChoice
        from rapid_os.orchestration.setup_conductor import _resolve_doc
        from rapid_os.domain.catalog import load_setup_doc_banks

        bank = load_setup_doc_banks(TEMPLATES)["data-model"]
        catalog = load_catalog(TEMPLATES)
        state = SetupState(services=(ServiceChoice("database", "mongodb"),))
        asked = {q["id"] for q in _resolve_doc("data-model", bank, None, state, catalog).payload["questions"]}
        self.assertTrue({"collections", "indexes", "schema_validation", "local_database"} <= asked)
        self.assertFalse({"tables", "migrations", "rls", "firebase_rules"} & asked)
        state = SetupState(services=(ServiceChoice("database", "postgresql"),))
        asked = {q["id"] for q in _resolve_doc("data-model", bank, None, state, catalog).payload["questions"]}
        self.assertTrue({"tables", "migrations"} <= asked)
        self.assertFalse({"collections", "indexes", "schema_validation"} & asked)

    def test_the_scaffold_hint_follows_the_data_model(self):
        from rapid_os.orchestration.lifecycle import with_scaffold_task

        relational = with_scaffold_task([], services=True, data_model="relational")[0]
        documents = with_scaffold_task([], services=True, data_model="documents")[0]
        baas_only = with_scaffold_task([], data_model="documents")[0]
        self.assertIn("migraciones versionadas", relational)
        self.assertIn("no hay migraciones", documents)
        self.assertIn("índices", documents)
        self.assertIn("no hay migraciones", baas_only)
        self.assertEqual(with_scaffold_task([], services=True)[0], with_scaffold_task([], services=True, data_model="relational")[0])


def _fact(category, value):
    return ProjectFact(category, value, Confidence.HIGH, (Evidence(Path("marker"), "test"),))


class ScannerTests(unittest.TestCase):
    def suggestions(self, *facts):
        return suggest_init_choices(ProjectModel(root=Path("."), facts=tuple(_fact(c, v) for c, v in facts)))

    def test_firebase_and_a_frontend_suggest_the_baas_topology_and_provider(self):
        result = self.suggestions(("framework", "react"), ("framework", "vite"), ("database", "firebase"))
        self.assertEqual(result.topology.value, "fullstack-baas")
        self.assertEqual(result.stacks["baas"].value, "firebase")
        self.assertEqual(result.stacks["frontend"].value, "react-vite")

    def test_supabase_works_with_any_frontend_not_only_nextjs(self):
        result = self.suggestions(("framework", "vue"), ("database", "supabase"))
        self.assertEqual((result.topology.value, result.stacks["baas"].value), ("fullstack-baas", "supabase"))

    def test_nextjs_with_supabase_keeps_its_suggestion(self):
        result = self.suggestions(("framework", "nextjs"), ("database", "supabase"))
        self.assertEqual((result.topology.value, result.stacks["baas"].value), ("fullstack-baas", "supabase"))

    def test_two_providers_or_a_backend_of_its_own_suggest_no_baas(self):
        both = self.suggestions(("framework", "react"), ("framework", "vite"), ("database", "supabase"), ("database", "firebase"))
        self.assertNotIn("baas", both.stacks or {})
        own = self.suggestions(("framework", "react"), ("framework", "vite"), ("framework", "fastapi"), ("language", "python"), ("database", "firebase"))
        self.assertNotIn("baas", own.stacks or {})
        self.assertEqual(own.topology.value, "fullstack-separated")

    def test_the_files_and_dependencies_of_firebase_are_detected(self):
        from rapid_os.domain.scanner import scan_project

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "firebase.json").write_text("{}", encoding="utf-8")
            (root / "package.json").write_text(json.dumps({"dependencies": {"firebase": "^11.0.0", "react": "^19.0.0", "vite": "^7.0.0"}}), encoding="utf-8")
            scan = scan_project(root)
            self.assertIn("firebase", scan.values("database"))
            result = suggest_init_choices(scan)
            self.assertEqual(result.stacks["baas"].value, "firebase")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".firebaserc").write_text("{}", encoding="utf-8")
            self.assertIn("firebase", scan_project(root).values("database"))
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".env").write_text("VITE_FIREBASE_PROJECT_ID=demo\n", encoding="utf-8")
            self.assertIn("firebase", scan_project(root).values("database"))


class McpAndDeployTests(unittest.TestCase):
    def servers(self, frontend, provider):
        guide = render_topology((TEMPLATES / "topologies" / "fullstack-baas.md").read_text(encoding="utf-8"), "fullstack-baas", {"frontend": frontend, "baas": provider})
        return build_mcp_config(guide, [], Path("."), TEMPLATES).server_ids()

    def test_each_provider_offers_its_own_mcp_server_and_never_the_other(self):
        self.assertEqual(self.servers("react-vite", "supabase"), ("filesystem", "supabase"))
        self.assertEqual(self.servers("react-vite", "firebase"), ("filesystem", "firebase"))

    def test_the_firebase_mcp_template_has_no_placeholder(self):
        data = json.loads((TEMPLATES / "mcp" / "firebase.json").read_text(encoding="utf-8"))
        self.assertEqual(data["firebase"]["args"], ["-y", "firebase-tools@latest", "mcp"])
        from rapid_os.domain.mcp import PLACEHOLDER_VALUES

        self.assertFalse([p for p in PLACEHOLDER_VALUES if p in json.dumps(data)])

    def test_the_new_deployment_templates_follow_the_contract(self):
        for platform in ("netlify", "firebase-hosting", "vercel"):
            text = (TEMPLATES / "deploy" / f"{platform}.md").read_text(encoding="utf-8")
            with self.subTest(platform=platform):
                self.assertIn("## Fuentes oficiales", text)
                for section in ("Destino", "Configuración y secretos", "Servicios gestionados", "Verificación y reversión"):
                    self.assertIn(f"## {section}", text)
        self.assertIn("## Con Supabase", (TEMPLATES / "deploy" / "vercel.md").read_text(encoding="utf-8"))
        self.assertIn("Supabase", (TEMPLATES / "deploy" / "netlify.md").read_text(encoding="utf-8"))
        hosting = (TEMPLATES / "deploy" / "firebase-hosting.md").read_text(encoding="utf-8")
        self.assertIn("firebase deploy --only hosting", hosting)
        self.assertIn('"rewrites"', hosting)
        deployment = json.loads((TEMPLATES / "setup" / "docs" / "deployment.json").read_text(encoding="utf-8"))
        platforms = next(q for q in deployment["questions"] if q["id"] == "platform")["options"]
        self.assertTrue({"netlify", "firebase-hosting"} <= set(platforms))


class RehearsalTests(Project):
    """`/rapid-init` in an empty folder: the loop of the shortcut, driven by `rapid setup`."""

    def setUp(self):
        super().setUp()
        bin_dir = self.base / "bin"
        bin_dir.mkdir()
        # The CLIs of the providers are installed by the person; the rehearsal only needs them found on the PATH.
        for name in ("firebase", "supabase"):
            if os.name == "nt":
                (bin_dir / f"{name}.cmd").write_text("@echo off\r\nexit /b 0\r\n", encoding="utf-8")
            else:
                script = bin_dir / name
                script.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
                script.chmod(script.stat().st_mode | stat.S_IEXEC)
        self.env = {**self.env, "PATH": f"{bin_dir}{os.pathsep}{self.env.get('PATH', '')}"}

    def draft(self, action):
        """A body with every required section of the action (what the agent drafts from the questions)."""
        titles = [s["titles"][0] for s in action["required_sections"]]
        titles += [s["titles"][0] for s in action.get("conditional_sections", [])]
        return "\n".join(f"## {title}\nDecisión registrada en el ensayo para {title}.\n" for title in titles)

    def rehearse(self, frontend, provider, delegate):
        flags = ["--decided-by", "agent"] if delegate else []
        self.ok("setup", "set", "topology", "fullstack-baas")
        first = self.next_json()
        self.assertEqual((first["kind"], first["component"]), ("choose_stack", "frontend"))
        self.ok("setup", "set", "stack", frontend, "--component", "frontend", *flags)
        action = self.next_json()
        self.assertEqual((action["kind"], action["component"]), ("choose_stack", "baas"))
        self.assertEqual({o["id"] for o in action["options"] if o.get("component") == "baas"}, set(PROVIDERS))
        self.ok("setup", "set", "stack", provider, "--component", "baas", *flags)
        self.ok("setup", "set", "archetype", "mvp")
        self.ok("setup", "set", "ai", "no")
        self.ok("setup", "set", "agents", "claude")
        self.assertEqual(self.next_json()["kind"], "set_test_command")
        test_action = self.next_json()
        self.assertEqual(test_action["recommended"][:3], ["pnpm", "exec", "vitest"])
        self.assertEqual(test_action["rules_test"]["command"], baas.rules_test_command(provider, test_action["recommended"]))
        self.ok("setup", "set", "test-command", "--recommended")
        self.ok("setup", "set", "services", "none")
        self.ok("setup", "doc", "brief", "--skip")
        for doc in ("business", "data-model", "architecture", "deployment"):
            action = self.next_json()
            self.assertEqual((action["kind"], action["doc"]), ("resolve_doc", doc))
            if doc in ("data-model", "architecture", "deployment"):
                self.assertTrue(action["conditional_sections"], doc)
            self.ok("setup", "doc", doc, "--source", "drafted", "--file", "-", stdin=self.draft(action))
            self.ok("setup", "doc", doc, "--confirm")
        return self.ok("setup", "finish")

    def check(self, frontend, provider, delegate):
        self.rehearse(frontend, provider, delegate)
        standards = self.root / ".rapid-os" / "standards"
        setup = json.loads((self.root / ".rapid-os" / "setup.json").read_text(encoding="utf-8"))
        decided = "agent" if delegate else "person"
        self.assertEqual(setup["stacks"]["baas"]["decided_by"], decided)
        self.assertEqual(setup["stacks"]["frontend"]["decided_by"], decided)
        tech_stack = (standards / "tech-stack.md").read_text(encoding="utf-8")
        self.assertIn(f"baas={provider}", tech_stack)
        self.assertEqual("decided_by.baas=agent" in tech_stack, delegate)
        self.assertEqual("porque la persona delegó" in tech_stack, delegate)
        topology = (standards / "topology.md").read_text(encoding="utf-8")
        self.assertIn("ONLY barrier" if frontend in SPA else "runs the mutations", topology)
        rules = json.loads((standards / "architecture.json").read_text(encoding="utf-8"))
        self.assertEqual([r["component"] for r in rules["rules"]], ["frontend", "baas"])
        self.assertEqual(rules["rules"][0]["restricted_imports"][0]["provider"], provider)
        security = (standards / "security.md").read_text(encoding="utf-8")
        self.assertIn(f"Backend como servicio: {provider.capitalize()}", security)
        # Firestore is a document store: NoSQL injection; Supabase is Postgres: not.
        self.assertEqual("CWE-943" in security, provider == "firebase")
        data_model = (self.root / "docs" / "DATA_MODEL.md").read_text(encoding="utf-8")
        for title in (("Colecciones y documentos", "Índices", "Validación del esquema") if provider == "firebase"
                      else ("Tablas", "Migraciones", "Políticas RLS")):
            self.assertIn(f"## {title}", data_model)
        env = (self.root / ".env.example").read_text(encoding="utf-8")
        self.assertIsNone(SECRET_SHAPES.search(env))
        self.assertIn("SUPABASE_URL" if provider == "supabase" else "FIREBASE_PROJECT_ID", env)
        workflow = (self.root / ".github" / "workflows" / "rapid-security-typescript.yml").read_text(encoding="utf-8")
        self.assertIn("rls-tests" if provider == "supabase" else "rules-tests", workflow)
        done = self.next_json()
        self.assertEqual(done["kind"], "done")
        commands = [a["command"] for a in done["person_actions"] if a["id"].startswith("baas")]
        self.assertEqual(
            commands,
            ["supabase init", "supabase start", "supabase test db"] if provider == "supabase"
            else ["firebase init", "firebase emulators:start", 'firebase emulators:exec "pnpm run test:rules"'],
        )
        config = json.loads((self.root / ".rapid-os" / "config.json").read_text(encoding="utf-8"))
        self.assertEqual(config["test_command"][:3], ["pnpm", "exec", "vitest"])
        show = self.ok("setup", "show")
        self.assertEqual("(agente)" in show, delegate)
        code, out, err = self.run_text("validate", "--strict")
        self.assertEqual(code, 0, f"validate --strict: {out}{err}")
        code, out, err = self.run_text("arch", "check")
        self.assertEqual(code, 0, f"arch check: {out}{err}")
        return rules

    def test_nextjs_and_supabase_chosen_by_the_person(self):
        self.check("nextjs", "supabase", delegate=False)

    def test_nextjs_and_supabase_delegated_to_the_agent(self):
        self.check("nextjs", "supabase", delegate=True)

    def test_react_vite_and_firebase_chosen_by_the_person(self):
        self.check("react-vite", "firebase", delegate=False)

    def test_react_vite_and_firebase_delegated_to_the_agent(self):
        self.check("react-vite", "firebase", delegate=True)

    def test_the_rule_is_enforced_on_real_files(self):
        self.check("react-vite", "supabase", delegate=False)
        feature = self.root / "src" / "features" / "orders" / "ui"
        feature.mkdir(parents=True)
        (feature / "List.tsx").write_text("import { createClient } from '@supabase/supabase-js'\n", encoding="utf-8")
        code, out, err = self.run_text("arch", "check")
        self.assertEqual(code, 1, out + err)
        self.assertIn("el SDK de supabase", out + err)

    def test_asking_for_a_database_on_a_baas_is_allowed_with_a_warning(self):
        self.ok("setup", "set", "topology", "fullstack-baas")
        # Next.js may use a database (a SPA cannot: that is RAPID1402 already).
        self.ok("setup", "set", "stack", "nextjs", "--component", "frontend")
        self.ok("setup", "set", "stack", "supabase", "--component", "baas")
        code, out, err = self.run_text("setup", "set", "services", "database:postgresql@now")
        self.assertEqual(code, 0, out + err)
        self.assertIn("segunda fuente de datos", out + err)
        code, out, err = self.run_text("setup", "set", "services", "cache:redis@later")
        self.assertEqual(code, 0, out + err)
        self.assertNotIn("segunda fuente de datos", out + err)

    def test_decided_by_only_goes_with_a_stack(self):
        code, out, err = self.run_text("setup", "set", "archetype", "mvp", "--decided-by", "agent")
        self.assertEqual(code, 1)
        self.assertIn("RAPID1413", out + err)
        self.assertIn("--decided-by", out + err)

    def test_a_person_decision_after_a_delegated_one_drops_the_note(self):
        self.rehearse("react-vite", "firebase", delegate=True)
        self.ok("setup", "set", "stack", "supabase", "--component", "baas")
        self.ok("setup", "finish")
        tech_stack = (self.root / ".rapid-os" / "standards" / "tech-stack.md").read_text(encoding="utf-8")
        self.assertIn("baas=supabase", tech_stack)
        self.assertNotIn("decided_by.baas=agent", tech_stack)
        self.assertIn("decided_by.frontend=agent", tech_stack)


if __name__ == "__main__":
    unittest.main()
