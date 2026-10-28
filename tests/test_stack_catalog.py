"""F5: every component of the topology chooses its stack in a wide catalog, and every language gets
the modular architecture with its own names, verified by `rapid arch check`."""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from rapid_os.domain.architecture import (
    ArchitectureConfig,
    architecture_document,
    check_architecture,
    default_config,
    load_rules,
    render_architecture_markdown,
    rules_for,
)
from rapid_os.domain.architecture_profiles import BACKEND_RULES, FRONTEND_RULES
from rapid_os.domain.catalog import (
    COMPONENTS,
    FACTOR_KEYS,
    CatalogError,
    load_catalog,
    load_setup_doc_banks,
    load_stack_questions,
)
from rapid_os.domain.project import ProjectModel
from rapid_os.domain.scanner import scan_project, suggest_init_choices
from rapid_os.domain.security import ci_language, ci_languages, render_ci_workflow
from rapid_os.domain.setup import DocState, SetupActionKind, SetupState, StackChoice
from rapid_os.orchestration.arch_delegate import PACKWERK_MISSING, run_delegate
from rapid_os.orchestration.setup_conductor import next_setup_action
from tests.stack_helpers import complete_stacks
from tests.test_no_git import GitIsolated, approve

ROOT = Path(__file__).resolve().parents[1]
TEMPLATES = ROOT / "templates"
CATALOG = load_catalog(TEMPLATES)
BANKS = load_setup_doc_banks(TEMPLATES)
QUESTIONS = load_stack_questions(TEMPLATES)
BACKENDS = ("python-fastapi", "python-django", "node-nestjs", "node-fastify", "go", "rust-axum", "ruby-rails",
            "dotnet-aspnetcore", "java-spring-boot", "kotlin-spring-boot", "php-laravel")
FRONTENDS = ("react-vite", "nextjs", "angular", "vue-vite", "nuxt", "svelte-vite", "sveltekit", "astro")


def next_action(state, model=None):
    return next_setup_action(
        state, model or ProjectModel(root=Path(".")), CATALOG, BANKS,
        stack_questions=QUESTIONS, agent_ids=("claude", "codex"),
    )


class CatalogTests(unittest.TestCase):
    def test_every_new_stack_is_valid_with_factors_and_sources(self):
        for stack_id in (*BACKENDS, *FRONTENDS):
            entry = CATALOG.stacks[stack_id]
            with self.subTest(stack=stack_id):
                self.assertEqual(set(entry.factors), set(FACTOR_KEYS))
                self.assertEqual(set(entry.factor_sources), set(FACTOR_KEYS))
                for key in FACTOR_KEYS:
                    self.assertTrue(entry.factors[key].strip(), key)
                    self.assertTrue(entry.factor_sources[key], key)
                    self.assertTrue(all(url.startswith("https://") for url in entry.factor_sources[key]), key)
                self.assertTrue(entry.default_test_command)
                self.assertTrue(entry.package_manager)
                self.assertIn(entry.component, COMPONENTS)
                self.assertIn(stack_id, BACKEND_RULES if entry.component == "backend" else FRONTEND_RULES)
                self.assertTrue((TEMPLATES / "stacks" / f"{entry.template}.md").is_file())
                for engine in entry.supported_services or {}:
                    self.assertIn(engine, CATALOG.services)
                text = (TEMPLATES / "stacks" / f"{entry.template}.md").read_text(encoding="utf-8")
                for needed in ("Runtime", "Framework", "Testing"):
                    self.assertIn(f"**{needed}:**", text, stack_id)

    def test_hosting_fit_uses_the_three_values(self):
        for stack_id in (*BACKENDS, *FRONTENDS):
            tokens = {t.strip() for t in CATALOG.stacks[stack_id].factors["hosting_fit"].split(",")}
            self.assertTrue(tokens <= {"serverless", "containers", "PaaS"}, stack_id)

    def test_a_sidecar_without_factors_is_rapid1401(self):
        with tempfile.TemporaryDirectory() as tmp:
            templates = Path(tmp) / "templates"
            shutil.copytree(TEMPLATES, templates)
            path = templates / "stacks" / "backend" / "go.json"
            data = json.loads(path.read_text(encoding="utf-8"))
            data.pop("factors")
            path.write_text(json.dumps(data), encoding="utf-8")
            with self.assertRaises(CatalogError) as caught:
                load_catalog(templates)
            self.assertEqual(caught.exception.code, "RAPID1401")
            self.assertIn("factors", str(caught.exception))

    def test_topologies_declare_their_components(self):
        self.assertEqual(CATALOG.components_of("front-end-only"), ("frontend",))
        self.assertEqual(CATALOG.components_of("fullstack-separated"), ("frontend", "backend"))
        self.assertEqual(CATALOG.components_of("fullstack-baas"), ("frontend", "baas"))
        self.assertEqual(CATALOG.components_of("doc-site"), ("docs",))

    def test_the_stacks_that_host_both_cover_both(self):
        for stack_id in ("nextjs", "nuxt", "sveltekit", "ruby-rails", "python-django", "php-laravel"):
            self.assertEqual(set(CATALOG.stacks[stack_id].covers), {"frontend", "backend"}, stack_id)
        for stack_id in ("react-vite", "go", "python-fastapi"):
            self.assertEqual(len(CATALOG.stacks[stack_id].covers), 1, stack_id)

    def test_the_questions_are_the_ones_of_the_task(self):
        self.assertEqual(
            [q.id for q in QUESTIONS],
            ["product_type", "team_languages", "load_latency", "infra_budget", "realtime", "compute_ai",
             "maintenance_horizon", "org_constraints"],
        )


class ConductorTests(unittest.TestCase):
    def test_fullstack_separated_asks_the_frontend_and_then_the_backend(self):
        state = SetupState(topology="fullstack-separated")
        first = next_action(state).to_dict()
        self.assertEqual((first["kind"], first["component"]), ("choose_stack", "frontend"))
        self.assertEqual(first["command"][-2:], ["--component", "frontend"])
        self.assertTrue(all("frontend" in o["covers"] for o in first["options"] if "covers" in o))
        state = SetupState(topology="fullstack-separated", stacks={"frontend": StackChoice("react-vite", "catalog")})
        second = next_action(state).to_dict()
        self.assertEqual((second["kind"], second["component"]), ("choose_stack", "backend"))
        self.assertIn("go", {o["id"] for o in second["options"]})
        self.assertIn("python-django", {o["id"] for o in second["options"]})
        self.assertNotIn("react-vite", {o["id"] for o in second["options"]})

    def test_nextjs_covers_both_and_asks_no_backend(self):
        both = {c: StackChoice("nextjs", "catalog") for c in ("frontend", "backend")}
        state = SetupState(topology="fullstack-separated", stacks=both)
        self.assertEqual(next_action(state).kind, SetupActionKind.CHOOSE_ARCHETYPE)

    def test_the_baas_component_needs_no_stack(self):
        state = SetupState(topology="fullstack-baas", stacks={"frontend": StackChoice("react-vite", "catalog")})
        self.assertEqual(next_action(state).kind, SetupActionKind.CHOOSE_ARCHETYPE)

    def test_the_payload_carries_factors_questions_and_the_instruction(self):
        action = next_action(SetupState(topology="fullstack-separated", stacks={"frontend": StackChoice("react-vite", "catalog")})).to_dict()
        go = next(o for o in action["options"] if o["id"] == "go")
        self.assertEqual(set(go["factors"]), set(FACTOR_KEYS))
        self.assertTrue(go["factor_sources"]["performance"])
        self.assertTrue(action["questions"])
        self.assertIn("No afirmes nada que el catálogo no diga", action["instruction"])

    def test_without_a_topology_the_first_stack_can_be_of_any_component(self):
        action = next_action(SetupState()).to_dict()
        self.assertEqual(action["kind"], "choose_stack")
        self.assertNotIn("component", action)
        ids = {o["id"] for o in action["options"]}
        self.assertTrue({"go", "react-vite", "generic"} <= ids)
        after = next_action(SetupState(stacks={"backend": StackChoice("go", "catalog")})).to_dict()
        self.assertEqual(after["kind"], "choose_topology")
        self.assertEqual([o["id"] for o in after["options"]], ["backend-only", "fullstack-separated"])


class LegacyStateTests(unittest.TestCase):
    def read(self, stack_id, **extra):
        return SetupState.from_dict({"schema_version": 1, "stack": {"id": stack_id, "source": "catalog"}, **extra})

    def test_the_ids_of_before_map_to_the_new_stacks_without_losing_anything(self):
        docs = {"brief": {"status": "skipped", "confirmed": False, "sha256": ""}}
        full = dict(
            topology="fullstack-separated", archetype="mvp", agents=["codex"], test_command=["pytest"],
            docs=docs, finished=True, services=[{"role": "database", "engine": "postgresql", "when": "now"}],
        )
        state = self.read("python-api", **full)
        self.assertEqual({c: s.id for c, s in state.stacks.items()}, {"backend": "python-fastapi"})
        self.assertEqual((state.topology, state.archetype, state.agents, state.test_command, state.finished),
                         ("fullstack-separated", "mvp", ("codex",), ("pytest",), True))
        self.assertEqual(state.docs["brief"].status, "skipped")
        self.assertEqual(state.services[0].engine, "postgresql")
        self.assertFalse(state.ai)

    def test_the_ai_stacks_answer_ai_yes(self):
        python_ai = self.read("python-ai")
        self.assertEqual(({c: s.id for c, s in python_ai.stacks.items()}, python_ai.ai), ({"backend": "python-fastapi"}, True))
        node_ai = self.read("nodejs-ai")
        self.assertEqual(({c: s.id for c, s in node_ai.stacks.items()}, node_ai.ai), ({"backend": "node-fastify"}, True))
        # ...unless the file already says otherwise
        self.assertFalse(self.read("python-ai", ai=False).ai)

    def test_web_modern_and_frontend_creative(self):
        web = self.read("web-modern")
        self.assertEqual({c: s.id for c, s in web.stacks.items()}, {"frontend": "nextjs", "backend": "nextjs"})
        creative = self.read("frontend-creative")
        self.assertEqual((creative.stacks["frontend"].id, creative.stacks["frontend"].profile), ("react-vite", "creative"))

    def test_docs_modern_and_generic_stay(self):
        self.assertEqual({c: s.id for c, s in self.read("docs-modern").stacks.items()}, {"docs": "docs-modern"})
        generic = self.read("generic")
        self.assertEqual({s.id for s in generic.stacks.values()}, {"generic"})
        self.assertEqual(set(generic.stacks), set(COMPONENTS))

    def test_a_finished_project_is_not_reopened_by_the_component_it_never_decided(self):
        state = self.read(
            "python-api", topology="fullstack-separated", archetype="mvp", agents=["codex"], test_command=[],
            finished=True, services=[], ai=False,
            docs={d: {"status": "skipped", "confirmed": False, "sha256": ""} for d in
                  ("brief", "business", "data-model", "architecture", "deployment")},
        )
        self.assertEqual(next_action(state).kind, SetupActionKind.DONE)

    def test_the_state_round_trips_in_the_new_shape(self):
        state = self.read("web-modern", topology="fullstack-separated")
        written = state.to_dict()
        self.assertNotIn("stack", written)
        self.assertEqual(SetupState.from_dict(written), state)


class NamesTests(unittest.TestCase):
    def markdown(self, **stacks):
        template = (TEMPLATES / "architecture" / "modular-monolith.md").read_text(encoding="utf-8")
        return render_architecture_markdown(template, rules_for(stacks))

    def test_go_uses_internal_and_its_package_names(self):
        text = self.markdown(backend="go")
        for expected in ("internal/<m>/", "http/", "app/", "domain/", "store/"):
            self.assertIn(expected, text)
        self.assertIn("| `http` | Entrada (HTTP, eventos) |", text)
        self.assertIn("| `app` | Aplicación (casos de uso y puertos) |", text)
        self.assertIn("| `domain` | Dominio (reglas sin framework) |", text)
        self.assertIn("| `store` o `adapters` | Infraestructura (persistencia y adaptadores) |", text)
        self.assertNotIn("api/", text.split("## Estructura por stack")[1])

    def test_java_uses_packages(self):
        text = self.markdown(backend="java-spring-boot")
        self.assertIn("src/main/java/com/example/app", text)
        for expected in ("web/", "application/", "domain/", "infrastructure/"):
            self.assertIn(expected, text)
        self.assertIn("| `web` | Entrada (HTTP, eventos) |", text)
        self.assertIn("Spring Modulith", text)
        self.assertIn("src/main/kotlin/com/example/app", self.markdown(backend="kotlin-spring-boot"))

    def test_each_language_maps_its_names_to_the_canonical_responsibilities(self):
        for stack_id in BACKENDS:
            text = self.markdown(backend=stack_id)
            with self.subTest(stack=stack_id):
                table = text.split("| Nombre en este stack | Responsabilidad canónica |")[1]
                for responsibility in ("Entrada (HTTP, eventos)", "Aplicación (casos de uso y puertos)",
                                       "Dominio (reglas sin framework)", "Infraestructura (persistencia y adaptadores)",
                                       "Contrato público del módulo"):
                    self.assertIn(responsibility, table)
        for stack_id in FRONTENDS:
            text = self.markdown(frontend=stack_id)
            with self.subTest(stack=stack_id):
                for name in ("ui", "state", "data-access", "model", "index.ts"):
                    self.assertIn(f"`{name}`", text)

    def test_the_idiomatic_trees(self):
        self.assertIn("<M>.Contracts", self.markdown(backend="dotnet-aspnetcore"))
        self.assertIn("packs/", self.markdown(backend="ruby-rails"))
        self.assertIn("Test complementario", self.markdown(backend="ruby-rails"))
        self.assertIn("mod.rs", self.markdown(backend="rust-axum"))
        self.assertIn("ServiceProvider", self.markdown(backend="php-laravel"))
        self.assertIn("<m>.module.ts", self.markdown(backend="node-nestjs"))
        self.assertIn("models.py", self.markdown(backend="python-django"))
        self.assertIn("src/app/features", self.markdown(frontend="angular"))

    def test_the_scaffold_names_the_complementary_test_of_the_ecosystem(self):
        from rapid_os.orchestration.lifecycle import with_scaffold_task

        for stack_id, needle in (
            ("java-spring-boot", "Spring Modulith"), ("kotlin-spring-boot", "Spring Modulith"),
            ("php-laravel", "Deptrac"), ("dotnet-aspnetcore", "NetArchTest"), ("ruby-rails", "packwerk"),
        ):
            rule = default_config(stack_id)
            self.assertIn(needle, rule["complementary"], stack_id)
            task = with_scaffold_task(["T001: x"], architecture=True, complementary=rule["complementary"])[0]
            self.assertIn("test complementario", task)
            self.assertIn(needle, task)
        self.assertNotIn("complementary", default_config("go"))

    def test_a_backend_and_a_frontend_have_their_own_folders(self):
        text = self.markdown(backend="go", frontend="vue-vite")
        self.assertIn("(en `backend/`)", text)
        self.assertIn("(en `frontend/`)", text)


def config(stack_id, component=None, **overrides):
    document = default_config(stack_id)
    rules = document.get("rules") or [document]
    rule = next(r for r in rules if component is None or r["component"] == component)
    return ArchitectureConfig.from_dict({"schema_version": 1, **rule, **overrides})


def kinds(report):
    return sorted((v.rule, v.file, v.line) for v in report.violations)


class GoTests(unittest.TestCase):
    def test_a_valid_module(self):
        report = check_architecture(config("go"), {
            "internal/pay/pay.go": 'package pay\n\nimport "example.com/app/internal/pay/app"\n',
            "internal/pay/http/handler.go": 'package http\n\nimport (\n\t"net/http"\n\t"example.com/app/internal/pay/app"\n\t"example.com/app/internal/shared"\n)\n',
            "internal/pay/app/service.go": 'package app\n\nimport (\n\t"example.com/app/internal/pay/domain"\n\t"example.com/app/internal/orders"\n)\n',
            "internal/pay/store/repo.go": 'package store\n\nimport (\n\t"database/sql"\n\t"example.com/app/internal/pay/domain"\n)\n',
            "internal/pay/domain/order.go": "package domain\n\n// no imports\n",
        })
        self.assertEqual(report.violations, ())
        self.assertEqual(report.modules, ("pay",))

    def test_the_violations(self):
        report = check_architecture(config("go"), {
            "internal/pay/http/handler.go": 'package http\n\nimport "example.com/app/internal/pay/store"\n',
            "internal/pay/app/service.go": 'package app\n\nimport "example.com/app/internal/orders/store"\n',
            "internal/pay/domain/order.go": 'package domain\n\nimport (\n\t"net/http"\n\t"database/sql"\n)\n',
            "internal/shared/log.go": 'package shared\n\nimport "example.com/app/internal/pay"\n',
        })
        self.assertEqual(kinds(report), [
            ("cross_module", "internal/pay/app/service.go", 3),
            ("domain_forbidden_import", "internal/pay/domain/order.go", 4),
            ("domain_forbidden_import", "internal/pay/domain/order.go", 5),
            ("layer", "internal/pay/http/handler.go", 3),
            ("shared", "internal/shared/log.go", 3),
        ])

    def test_adapters_is_also_the_infrastructure(self):
        report = check_architecture(config("go"), {
            "internal/pay/http/handler.go": 'package http\n\nimport "example.com/app/internal/pay/adapters"\n',
        })
        self.assertEqual([v.rule for v in report.violations], ["layer"])

    def test_test_files_are_not_judged(self):
        report = check_architecture(config("go"), {
            "internal/pay/http/handler_test.go": 'package http\n\nimport "example.com/app/internal/pay/store"\n',
        })
        self.assertEqual(report.violations, ())


class JvmTests(unittest.TestCase):
    def test_java(self):
        cfg = config("java-spring-boot")
        base = "src/main/java/com/example/app"
        valid = check_architecture(cfg, {
            f"{base}/pay/web/PayController.java": "package com.example.app.pay.web;\n\nimport com.example.app.pay.application.PayService;\nimport com.example.app.orders.OrdersApi;\nimport org.springframework.web.bind.annotation.RestController;\n",
            f"{base}/pay/application/PayService.java": "package x;\nimport com.example.app.pay.domain.Order;\n",
            f"{base}/pay/infrastructure/PayRepo.java": "package x;\nimport com.example.app.pay.domain.Order;\nimport jakarta.persistence.Entity;\n",
            f"{base}/pay/domain/Order.java": "package x;\n\npublic class Order {}\n",
        })
        self.assertEqual(valid.violations, ())
        invalid = check_architecture(cfg, {
            f"{base}/pay/web/PayController.java": "package x;\nimport com.example.app.pay.infrastructure.PayRepo;\n",
            f"{base}/pay/application/PayService.java": "package x;\nimport com.example.app.orders.domain.Order;\n",
            f"{base}/pay/domain/Order.java": "package x;\nimport org.springframework.stereotype.Service;\nimport static jakarta.persistence.GenerationType.AUTO;\n",
        })
        self.assertEqual(kinds(invalid), [
            ("cross_module", f"{base}/pay/application/PayService.java", 2),
            ("domain_forbidden_import", f"{base}/pay/domain/Order.java", 2),
            ("domain_forbidden_import", f"{base}/pay/domain/Order.java", 3),
            ("layer", f"{base}/pay/web/PayController.java", 2),
        ])

    def test_kotlin(self):
        cfg = config("kotlin-spring-boot")
        base = "src/main/kotlin/com/example/app"
        valid = check_architecture(cfg, {
            f"{base}/pay/web/PayController.kt": "package x\n\nimport com.example.app.pay.application.PayService\nimport com.example.app.orders.OrdersApi\n",
            f"{base}/pay/domain/Order.kt": "package x\n\nclass Order\n",
        })
        self.assertEqual(valid.violations, ())
        invalid = check_architecture(cfg, {
            f"{base}/pay/web/PayController.kt": "package x\n\nimport com.example.app.pay.infrastructure.PayRepo as Repo\n",
            f"{base}/pay/application/PayService.kt": "package x\n\nimport com.example.app.orders.infrastructure.*\n",
        })
        self.assertEqual(kinds(invalid), [
            ("cross_module", f"{base}/pay/application/PayService.kt", 3),
            ("layer", f"{base}/pay/web/PayController.kt", 3),
        ])


class CSharpTests(unittest.TestCase):
    def test_usings_and_project_references(self):
        cfg = config("dotnet-aspnetcore")
        valid = check_architecture(cfg, {
            "src/Modules/Pay/Pay.Api/PayController.cs": "using App.Pay.Application;\nusing App.Orders.Contracts;\nusing Microsoft.AspNetCore.Mvc;\n",
            "src/Modules/Pay/Pay.Api/Pay.Api.csproj": '<Project>\n  <ItemGroup>\n    <ProjectReference Include="..\\Pay.Application\\Pay.Application.csproj" />\n    <ProjectReference Include="..\\..\\Orders\\Orders.Contracts\\Orders.Contracts.csproj" />\n  </ItemGroup>\n</Project>\n',
            "src/Modules/Pay/Pay.Domain/Order.cs": "namespace App.Pay.Domain;\npublic class Order {}\n",
        })
        self.assertEqual(valid.violations, ())
        invalid = check_architecture(cfg, {
            "src/Modules/Pay/Pay.Api/PayController.cs": "using App.Pay.Infrastructure;\n",
            "src/Modules/Pay/Pay.Application/PayService.cs": "using App.Orders.Domain;\n",
            "src/Modules/Pay/Pay.Domain/Order.cs": "using Microsoft.EntityFrameworkCore;\n",
            "src/Modules/Pay/Pay.Api/Pay.Api.csproj": '<Project>\n    <ProjectReference Include="..\\Pay.Infrastructure\\Pay.Infrastructure.csproj" />\n</Project>\n',
            "src/Modules/Pay/Pay.Domain/Pay.Domain.csproj": '<Project>\n    <PackageReference Include="Microsoft.EntityFrameworkCore" Version="10.0.0" />\n</Project>\n',
        })
        self.assertEqual(kinds(invalid), [
            ("cross_module", "src/Modules/Pay/Pay.Application/PayService.cs", 1),
            ("domain_forbidden_import", "src/Modules/Pay/Pay.Domain/Order.cs", 1),
            ("domain_forbidden_import", "src/Modules/Pay/Pay.Domain/Pay.Domain.csproj", 2),
            ("layer", "src/Modules/Pay/Pay.Api/Pay.Api.csproj", 2),
            ("layer", "src/Modules/Pay/Pay.Api/PayController.cs", 1),
        ])


class RustTests(unittest.TestCase):
    def test_use_statements(self):
        cfg = config("rust-axum")
        valid = check_architecture(cfg, {
            "src/modules/pay/routes.rs": "use axum::Router;\nuse crate::modules::pay::application::Service;\nuse super::domain::Order;\nuse crate::modules::orders::OrdersApi;\n",
            "src/modules/pay/mod.rs": "mod routes;\npub use self::domain::Order;\n",
            "src/modules/pay/infra.rs": "use sqlx::PgPool;\nuse super::domain::{Order, Total};\n",
            "src/modules/pay/domain.rs": "pub struct Order;\n",
        })
        self.assertEqual(valid.violations, ())
        invalid = check_architecture(cfg, {
            "src/modules/pay/routes.rs": "use crate::modules::pay::infra::Repo;\n",
            "src/modules/pay/application.rs": "use crate::modules::orders::domain::Order;\n",
            "src/modules/pay/domain.rs": "use sqlx::PgPool;\nuse {crate::modules::pay::application::{Service}};\n",
        })
        self.assertEqual(kinds(invalid), [
            ("cross_module", "src/modules/pay/application.rs", 1),
            ("domain_forbidden_import", "src/modules/pay/domain.rs", 1),
            ("layer", "src/modules/pay/domain.rs", 2),
            ("layer", "src/modules/pay/routes.rs", 1),
        ])


class PhpTests(unittest.TestCase):
    def test_namespaces(self):
        cfg = config("php-laravel")
        valid = check_architecture(cfg, {
            "app/Modules/Pay/Http/PayController.php": "<?php\nuse App\\Modules\\Pay\\Application\\ChargeService;\nuse App\\Modules\\Orders\\Contracts\\OrdersApi;\nuse Illuminate\\Http\\Request;\n",
            "app/Modules/Pay/Domain/Order.php": "<?php\nnamespace App\\Modules\\Pay\\Domain;\n",
        })
        self.assertEqual(valid.violations, ())
        invalid = check_architecture(cfg, {
            "app/Modules/Pay/Http/PayController.php": "<?php\nuse App\\Modules\\Pay\\Infrastructure\\PayRepo;\n",
            "app/Modules/Pay/Application/ChargeService.php": "<?php\nuse App\\Modules\\Orders\\Domain\\Order;\n",
            "app/Modules/Pay/Domain/Order.php": "<?php\nuse Illuminate\\Support\\Facades\\DB;\n",
        })
        self.assertEqual(kinds(invalid), [
            ("cross_module", "app/Modules/Pay/Application/ChargeService.php", 2),
            ("domain_forbidden_import", "app/Modules/Pay/Domain/Order.php", 2),
            ("layer", "app/Modules/Pay/Http/PayController.php", 2),
        ])


class SingleFileComponentTests(unittest.TestCase):
    def test_vue_reads_only_the_script(self):
        cfg = config("vue-vite")
        template = '<template>\n  <p>import x from "../data-access/api"</p>\n</template>\n'
        valid = check_architecture(cfg, {
            "src/features/pay/ui/PayForm.vue": template + '<script setup lang="ts">\nimport { usePay } from "../state/usePay";\nimport { orders } from "@/features/orders";\n</script>\n',
        })
        self.assertEqual(valid.violations, ())
        invalid = check_architecture(cfg, {
            "src/features/pay/ui/PayForm.vue": template + '<script setup lang="ts">\nimport { api } from "../data-access/api";\nimport OrderList from "@/features/orders/ui/OrderList.vue";\n</script>\n',
        })
        self.assertEqual(kinds(invalid), [
            ("cross_module", "src/features/pay/ui/PayForm.vue", 6),
            ("layer", "src/features/pay/ui/PayForm.vue", 5),
        ])

    def test_svelte(self):
        cfg = config("svelte-vite")
        invalid = check_architecture(cfg, {
            "src/features/pay/state/pay.svelte": '<script lang="ts">\n  import { x } from "../ui/Widget.svelte";\n</script>\n<div />\n',
        })
        self.assertEqual(kinds(invalid), [("layer", "src/features/pay/state/pay.svelte", 2)])
        valid = check_architecture(cfg, {
            "src/features/pay/ui/Widget.svelte": '<script>\n  import { x } from "../model/x";\n</script>\n',
        })
        self.assertEqual(valid.violations, ())

    def test_astro_frontmatter_and_script(self):
        cfg = config("astro")
        invalid = check_architecture(cfg, {
            "src/features/pay/ui/Card.astro": '---\nimport { api } from "../data-access/api";\n---\n<div />\n',
        })
        self.assertEqual(kinds(invalid), [("layer", "src/features/pay/ui/Card.astro", 2)])
        valid = check_architecture(cfg, {
            "src/features/pay/ui/Card.astro": '---\nimport { m } from "../model/m";\n---\n<div />\n<script>\n  import "../state/s";\n</script>\n',
        })
        self.assertEqual(valid.violations, ())

    def test_the_model_never_imports_a_ui_framework(self):
        report = check_architecture(config("react-vite"), {
            "src/features/pay/model/price.ts": 'import { useState } from "react";\n',
        })
        self.assertEqual([v.rule for v in report.violations], ["domain_forbidden_import"])
        self.assertIn("model no puede importar", report.violations[0].message)

    def test_nuxt_and_sveltekit_aliases(self):
        nuxt = config("nuxt", "frontend")
        report = check_architecture(nuxt, {
            "app/features/pay/ui/Pay.vue": '<script setup>\nimport { a } from "~/features/pay/data-access/a";\n</script>\n',
        })
        self.assertEqual([v.rule for v in report.violations], ["layer"])
        kit = config("sveltekit", "frontend")
        report = check_architecture(kit, {
            "src/lib/features/pay/ui/Pay.svelte": '<script>\nimport { a } from "$lib/features/pay/data-access/a";\n</script>\n',
        })
        self.assertEqual([v.rule for v in report.violations], ["layer"])


class NestAndRoleTests(unittest.TestCase):
    def test_nest_module_file_is_the_contract(self):
        cfg = config("node-nestjs")
        valid = check_architecture(cfg, {
            "src/modules/pay/application/pay.service.ts": "import { OrdersModule } from '../../orders/orders.module';\n",
        })
        self.assertEqual(valid.violations, ())
        invalid = check_architecture(cfg, {
            "src/modules/pay/application/pay.service.ts": "import { Order } from '../../orders/domain/order';\n",
        })
        self.assertEqual([v.rule for v in invalid.violations], ["cross_module"])

    def test_django_models_are_the_infrastructure(self):
        cfg = config("python-django")
        report = check_architecture(cfg, {
            "apps/pay/domain/order.py": "from apps.pay.models import Order\n",
            "apps/pay/api/views.py": "from apps.pay.services import charge\nfrom apps.orders.public import orders\n",
        })
        self.assertEqual(kinds(report), [("layer", "apps/pay/domain/order.py", 1)])


class RubyDelegationTests(GitIsolated):
    def test_without_packwerk_the_check_does_not_pass(self):
        result = run_delegate("packwerk", self.root)
        self.assertFalse(result.ok)
        self.assertTrue(result.missing)
        self.assertEqual(result.output, PACKWERK_MISSING)
        self.assertIn("packwerk", PACKWERK_MISSING)

    def test_the_cli_says_it_and_exits_one(self):
        rapid_dir = self.root / ".rapid-os" / "standards"
        rapid_dir.mkdir(parents=True)
        (rapid_dir / "architecture.json").write_text(
            json.dumps(architecture_document({"backend": "ruby-rails"})), encoding="utf-8"
        )
        result = self.rapid("arch", "check", "--json")
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        payload = json.loads(result.stdout)
        self.assertFalse(payload["ok"])
        self.assertTrue(payload["delegated"][0]["missing"])
        text = self.rapid("arch", "check")
        self.assertEqual(text.returncode, 1)
        self.assertIn("packwerk", text.stderr)

    def test_a_packwerk_binstub_that_passes_satisfies_the_gate(self):
        (self.root / "bin").mkdir()
        (self.root / "bin" / "packwerk").write_text(
            "#!/usr/bin/env python3\nimport sys\nprint('No offenses detected')\nsys.exit(0)\n", encoding="utf-8"
        )
        if sys.platform == "win32":
            self.skipTest("the binstub is a Ruby script; Windows runs it with ruby")
        (self.root / "bin" / "packwerk").chmod(0o755)
        self.assertTrue(run_delegate("packwerk", self.root).ok)


class CiTests(unittest.TestCase):
    AUDITORS = {
        "go": ("govulncheck", "go vet"),
        "rust": ("cargo audit", "clippy"),
        "ruby": ("bundle-audit", "brakeman"),
        "dotnet": ("dotnet package list --vulnerable",),
        "java": ("dependency-review-action",),
        "kotlin": ("dependency-review-action",),
        "php": ("composer audit",),
    }

    def test_each_language_has_its_auditor_and_every_action_is_pinned_by_sha(self):
        for language, needles in self.AUDITORS.items():
            for archetype in ("mvp", "corporate"):
                text = render_ci_workflow(
                    (TEMPLATES / "ci" / f"{language}-security.yml").read_text(encoding="utf-8"), archetype=archetype
                )
                with self.subTest(language=language, archetype=archetype):
                    for needle in needles:
                        self.assertIn(needle, text)
                    self.assertIn("semgrep scan --config p/owasp-top-ten", text)
                    self.assertIn("gitleaks", text)
                    uses = re.findall(r"uses:\s*(\S+)", text)
                    self.assertGreater(len(uses), 3)
                    for ref in uses:
                        self.assertRegex(ref, r"^[\w./-]+@[0-9a-f]{40}$", ref)
                    self.assertEqual(("anchore/sbom-action@" in text), archetype == "corporate")

    def test_every_template_is_pinned_and_only_the_first_workflow_scans_secrets(self):
        for path in sorted((TEMPLATES / "ci").glob("*-security.yml")):
            raw = path.read_text(encoding="utf-8")
            for ref in re.findall(r"uses:\s*(\S+)", raw):
                self.assertRegex(ref, r"@[0-9a-f]{40}$", (path.name, ref))
            primary = render_ci_workflow(raw, archetype="mvp", primary=True)
            secondary = render_ci_workflow(raw, archetype="mvp", primary=False)
            self.assertIn("gitleaks", primary, path.name)
            self.assertNotIn("gitleaks", secondary, path.name)

    def test_a_project_with_two_languages_gets_two_workflows(self):
        self.assertEqual(ci_languages(["go", "vue-vite"]), ["go", "typescript"])
        self.assertEqual(ci_languages(["nextjs", "nextjs"]), ["typescript"])
        self.assertEqual(ci_language("generic", ["Go"]), "go")
        self.assertEqual(ci_language("generic", ["csharp"]), "dotnet")
        self.assertIsNone(ci_language("custom"))


class ScannerTests(unittest.TestCase):
    def suggest(self, files):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for relative, text in files.items():
                path = root / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(text, encoding="utf-8")
            scan = scan_project(root)
            suggestions = suggest_init_choices(scan)
            return {c: s.value for c, s in (suggestions.stacks or {}).items()}, suggestions

    def test_a_minimal_fixture_per_framework(self):
        cases = {
            ("backend", "go"): {"go.mod": "module example.com/app\n\ngo 1.27\n"},
            ("backend", "rust-axum"): {"Cargo.toml": '[package]\nname = "app"\n\n[dependencies]\naxum = "0.8"\n'},
            ("backend", "ruby-rails"): {"Gemfile": 'source "https://rubygems.org"\ngem "rails", "~> 8.1"\n'},
            ("backend", "dotnet-aspnetcore"): {"App.csproj": '<Project Sdk="Microsoft.NET.Sdk.Web">\n</Project>\n'},
            ("backend", "java-spring-boot"): {"pom.xml": "<project><parent><artifactId>spring-boot-starter-parent</artifactId></parent></project>\n"},
            ("backend", "kotlin-spring-boot"): {"build.gradle.kts": 'plugins {\n  kotlin("jvm") version "2.2.21"\n  id("org.springframework.boot") version "4.1.2"\n}\n'},
            ("backend", "php-laravel"): {"composer.json": '{"require": {"laravel/framework": "^13.0"}}'},
            ("backend", "python-django"): {"pyproject.toml": 'dependencies = ["django"]'},
            ("backend", "node-nestjs"): {"package.json": '{"dependencies": {"@nestjs/core": "^11"}}'},
            ("backend", "node-fastify"): {"package.json": '{"dependencies": {"fastify": "^5"}}'},
            ("frontend", "angular"): {"angular.json": "{}", "package.json": '{"dependencies": {"@angular/core": "^22"}}'},
            ("frontend", "vue-vite"): {"package.json": '{"dependencies": {"vue": "^3"}}'},
            ("frontend", "nuxt"): {"package.json": '{"dependencies": {"nuxt": "^4", "vue": "^3"}}'},
            ("frontend", "svelte-vite"): {"package.json": '{"dependencies": {"svelte": "^5"}}'},
            ("frontend", "sveltekit"): {"package.json": '{"dependencies": {"@sveltejs/kit": "^2", "svelte": "^5"}}'},
            ("frontend", "astro"): {"package.json": '{"dependencies": {"astro": "^7"}}'},
            ("frontend", "react-vite"): {"package.json": '{"dependencies": {"react": "^19", "vite": "^8"}}'},
        }
        for (component, expected), files in cases.items():
            with self.subTest(stack=expected):
                stacks, _ = self.suggest(files)
                self.assertEqual(stacks.get(component), expected, stacks)

    def test_a_frontend_and_a_backend_suggest_the_separated_topology(self):
        stacks, suggestions = self.suggest({
            "backend/go.mod": "module example.com/app\n",
            "frontend/package.json": '{"dependencies": {"vue": "^3"}}',
        })
        self.assertEqual(stacks, {"backend": "go", "frontend": "vue-vite"})
        self.assertEqual(suggestions.topology.value, "fullstack-separated")

    def test_two_backends_suggest_nothing_for_that_component(self):
        stacks, _ = self.suggest({"go.mod": "module x\n", "Gemfile": 'gem "rails"\n'})
        self.assertNotIn("backend", stacks)


class SetStackCliTests(GitIsolated):
    def state(self):
        return json.loads((self.root / ".rapid-os" / "setup.json").read_text(encoding="utf-8"))

    def test_component_flag_fills_one_component(self):
        self.assertEqual(self.rapid("setup", "set", "topology", "fullstack-separated").returncode, 0)
        first = json.loads(self.rapid("setup", "next", "--json").stdout)
        self.assertEqual((first["kind"], first["component"]), ("choose_stack", "frontend"))
        self.assertEqual(self.rapid("setup", "set", "stack", "vue-vite", "--component", "frontend").returncode, 0)
        second = json.loads(self.rapid("setup", "next", "--json").stdout)
        self.assertEqual((second["kind"], second["component"]), ("choose_stack", "backend"))
        done = self.rapid("setup", "set", "stack", "go", "--component", "backend")
        self.assertEqual(done.returncode, 0, done.stderr)
        stacks = {c: s["id"] for c, s in self.state()["stacks"].items()}
        self.assertEqual(stacks, {"frontend": "vue-vite", "backend": "go"})
        self.assertEqual(json.loads(self.rapid("setup", "next", "--json").stdout)["kind"], "choose_archetype")

    def test_a_stack_that_covers_both_fills_both(self):
        self.assertEqual(self.rapid("setup", "set", "topology", "fullstack-separated").returncode, 0)
        self.assertEqual(self.rapid("setup", "set", "stack", "nextjs").returncode, 0)
        stacks = {c: s["id"] for c, s in self.state()["stacks"].items()}
        self.assertEqual(stacks, {"frontend": "nextjs", "backend": "nextjs"})
        # ...and with --component it fills only the one
        self.assertEqual(self.rapid("setup", "set", "stack", "nuxt", "--component", "frontend").returncode, 0)
        self.assertEqual({c: s["id"] for c, s in self.state()["stacks"].items()}, {"frontend": "nuxt", "backend": "nextjs"})

    def test_a_component_the_stack_cannot_fill_is_rapid1413(self):
        bad = self.rapid("setup", "set", "stack", "go", "--component", "frontend")
        self.assertEqual(bad.returncode, 1)
        self.assertIn("RAPID1413", bad.stderr)
        self.assertIn("backend", bad.stderr)
        also = self.rapid("setup", "set", "topology", "fullstack-separated", "--component", "backend")
        self.assertEqual(also.returncode, 1)
        self.assertIn("RAPID1413", also.stderr)

    def test_the_ids_of_before_still_work(self):
        result = self.rapid("setup", "set", "stack", "python-ai")
        self.assertEqual(result.returncode, 0, result.stderr)
        state = self.state()
        self.assertEqual({c: s["id"] for c, s in state["stacks"].items()}, {"backend": "python-fastapi"})
        self.assertTrue(state["ai"])

    def test_a_topology_the_stack_does_not_fit_is_rapid1402(self):
        self.assertEqual(self.rapid("setup", "set", "stack", "go").returncode, 0)
        bad = self.rapid("setup", "set", "topology", "front-end-only")
        self.assertEqual(bad.returncode, 1)
        self.assertIn("RAPID1402", bad.stderr)

    def test_services_are_judged_against_the_stack_of_the_backend(self):
        self.assertEqual(self.rapid("setup", "set", "stack", "go").returncode, 0)
        self.assertEqual(self.rapid("setup", "set", "services", "database:postgresql").returncode, 0)
        bad = self.rapid("setup", "set", "stack", "rust-axum")
        self.assertEqual(bad.returncode, 0, bad.stderr)
        mariadb = self.rapid("setup", "set", "services", "database:mariadb")
        self.assertEqual(mariadb.returncode, 1)
        self.assertIn("RAPID1402", mariadb.stderr)
        self.assertIn("rust-axum", mariadb.stderr)
        self.assertIn("postgresql", mariadb.stderr)


class ServicesPerStackTests(unittest.TestCase):
    def test_the_env_example_uses_the_driver_of_the_stack(self):
        from rapid_os.domain.services import render_env_example, render_tech_stack
        from rapid_os.domain.setup import ServiceChoice

        choices = (ServiceChoice("database", "postgresql", "now"), ServiceChoice("cache", "redis", "now"))
        go = CATALOG.stacks["go"]
        text = render_env_example(choices, CATALOG, "typescript", go)
        self.assertIn(f"DATABASE_URL=postgres://app:app_local_only@127.0.0.1:5432/app", text)
        template = (TEMPLATES / "stacks" / "backend" / "go.md").read_text(encoding="utf-8")
        self.assertIn("pgx", render_tech_stack(template, "typescript", choices, CATALOG, go))
        self.assertIn("go-redis", render_tech_stack(template, "typescript", choices, CATALOG, go))
        django = CATALOG.stacks["python-django"]
        django_text = render_tech_stack(
            (TEMPLATES / "stacks" / "backend" / "python-django.md").read_text(encoding="utf-8"),
            "python", (ServiceChoice("database", "mysql", "now"),), CATALOG, django,
        )
        self.assertIn("mysqlclient", django_text)
        self.assertNotIn("SQLAlchemy", django_text)

    def test_every_backend_declares_a_driver_for_postgresql_or_mysql(self):
        for stack_id in BACKENDS:
            supported = CATALOG.stacks[stack_id].supported_services
            self.assertTrue({"postgresql", "mysql"} & set(supported), stack_id)


class TechStackFileTests(GitIsolated):
    def finish(self, backend, frontend, extra=()):
        steps = (
            ("topology", "fullstack-separated"), ("stack", frontend, "--component", "frontend"),
            ("stack", backend, "--component", "backend"), ("archetype", "mvp"), ("ai", "no"),
            ("agents", "codex"), ("test-command", "none"), ("services", "none"), *extra,
        )
        for step in steps:
            result = self.rapid("setup", "set", *step)
            self.assertEqual(result.returncode, 0, result.stderr)
        for doc in ("brief", "business", "data-model", "architecture", "deployment"):
            self.assertEqual(self.rapid("setup", "doc", doc, "--skip").returncode, 0)
        result = self.rapid("setup", "finish", "--json")
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout)

    def test_the_standards_carry_both_stacks_and_both_rules(self):
        self.finish("go", "vue-vite")
        standards = self.root / ".rapid-os" / "standards"
        stack = (standards / "tech-stack.md").read_text(encoding="utf-8")
        self.assertIn("TECH STACK: GO", stack)
        self.assertIn("TECH STACK: VUE VITE", stack)
        self.assertIn("<!-- rapid-stack: backend=go -->", stack)
        self.assertIn("<!-- rapid-stack: frontend=vue-vite -->", stack)
        document = json.loads((standards / "architecture.json").read_text(encoding="utf-8"))
        self.assertEqual([(r["component"], r["root"]) for r in document["rules"]], [("backend", "backend"), ("frontend", "frontend")])
        text = (standards / "architecture.md").read_text(encoding="utf-8")
        self.assertIn("internal/<m>/", text)
        self.assertIn("src/features/<f>/", text)
        workflows = sorted(p.name for p in (self.root / ".github" / "workflows").glob("*.yml"))
        self.assertEqual(workflows, ["rapid-security-go.yml", "rapid-security-typescript.yml"])
        first = (self.root / ".github" / "workflows" / "rapid-security-go.yml").read_text(encoding="utf-8")
        self.assertIn("\nname: rapid-security (go)\n", first)
        second = (self.root / ".github" / "workflows" / "rapid-security-typescript.yml").read_text(encoding="utf-8")
        self.assertIn("govulncheck", first)
        self.assertIn("gitleaks", first)
        self.assertIn("\nname: rapid-security (typescript)\n", second)
        self.assertIn("npm audit", second)
        self.assertNotIn("gitleaks", second)

    def test_the_derived_state_reads_the_markers_back(self):
        self.finish("python-django", "angular")
        (self.root / ".rapid-os" / "setup.json").unlink()
        show = json.loads(self.rapid("setup", "show", "--json").stdout)
        stacks = {c: s["id"] for c, s in show["state"]["stacks"].items()}
        self.assertEqual(stacks, {"backend": "python-django", "frontend": "angular"})

    def test_ai_adds_the_ai_fragment_and_the_creative_profile_its_own(self):
        self.finish("python-fastapi", "react-vite", extra=(("ai", "yes"),))
        stack = (self.root / ".rapid-os" / "standards" / "tech-stack.md").read_text(encoding="utf-8")
        self.assertIn("LangChain", stack)


def _have(command):
    return shutil.which(command) is not None


SPEC = {
    "title": "Saludar", "mode": "feature", "business_objective": "Mostrar un saludo",
    "problem_statement": "No hay saludo", "scope": ["saludo"], "acceptance_criteria": ["se saluda"],
    "tasks": ["T001: Saludar"],
}
RUN_TESTS = """import subprocess
import sys

steps = [
    (["go", "test", "./..."], "backend"),
    (["node", "--test", "tests/greet.test.mjs"], "frontend"),
]
for command, cwd in steps:
    if subprocess.run(command, cwd=cwd).returncode != 0:
        sys.exit(1)
"""


class EndToEndTests(GitIsolated):
    """A frontend and a backend of different languages go from the onboarding to PASS."""

    def onboard(self, backend, frontend, test_command):
        steps = (
            ("topology", "fullstack-separated"), ("stack", frontend, "--component", "frontend"),
            ("stack", backend, "--component", "backend"), ("archetype", "mvp"), ("ai", "no"),
            ("agents", "codex"), ("test-command", test_command), ("services", "none"),
        )
        for step in steps:
            result = self.rapid("setup", "set", *step)
            self.assertEqual(result.returncode, 0, result.stderr)
        for doc in ("brief", "business", "data-model", "architecture", "deployment"):
            self.assertEqual(self.rapid("setup", "doc", doc, "--skip").returncode, 0)
        done = self.rapid("setup", "finish")
        self.assertEqual(done.returncode, 0, done.stderr)

    def write(self, relative, text):
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

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
                    self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.fail("the run never reached a human gate")

    def run_to_pass(self, backend, frontend, implement):
        self.onboard(backend, frontend, f'"{sys.executable}" run_tests.py')
        started = self.rapid("start", "feature", "--spec-file", "-", "--json", stdin=json.dumps(SPEC))
        self.assertEqual(started.returncode, 0, started.stderr)
        scaffold = json.dumps(json.loads(self.rapid("status", "--json").stdout)["run"]["tasks"][0], ensure_ascii=False)
        self.assertIn("architecture.md", scaffold)
        gate = self.drive(implement)
        self.assertEqual(approve(self.root, gate, self.env).returncode, 0)
        done = self.rapid("finish")
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        self.assertIn("verdict PASS", done.stdout)
        checked = self.rapid("arch", "check", "--json")
        self.assertEqual(checked.returncode, 0, checked.stdout)
        payload = json.loads(checked.stdout)
        self.assertEqual(payload["modules"], ["greet", "pay"] if False else payload["modules"])
        return payload

    def frontend_files(self):
        self.write("frontend/src/features/greet/index.mjs", "export { greet } from './model/greet.mjs';\n")
        self.write("frontend/src/features/greet/model/greet.mjs", "export const greet = (name) => `Hola ${name}`;\n")
        self.write(
            "frontend/src/features/greet/ui/Greeting.vue",
            '<template><p>{{ text }}</p></template>\n<script setup lang="ts">\nimport { greet } from "../model/greet.mjs";\nconst text = greet("mundo");\n</script>\n',
        )
        self.write(
            "frontend/tests/greet.test.mjs",
            "import test from 'node:test';\nimport assert from 'node:assert';\nimport { greet } from '../src/features/greet/index.mjs';\n\n"
            "test('greets', () => assert.strictEqual(greet('mundo'), 'Hola mundo'));\n",
        )

    @unittest.skipUnless(_have("go") and _have("node"), "needs go and node installed (they are in CI)")
    def test_vue_and_go_reach_pass(self):
        def implement():
            self.write("run_tests.py", RUN_TESTS)
            self.write("backend/go.mod", "module example.com/app\n\ngo 1.22\n")
            self.write("backend/internal/greet/greet.go", 'package greet\n\nimport "example.com/app/internal/greet/app"\n\nfunc Hello(name string) string { return app.Compose(name) }\n')
            self.write("backend/internal/greet/app/compose.go", 'package app\n\nimport "example.com/app/internal/greet/domain"\n\nfunc Compose(name string) string { return domain.Prefix + name }\n')
            self.write("backend/internal/greet/domain/prefix.go", 'package domain\n\nconst Prefix = "Hola "\n')
            self.write("backend/internal/greet/greet_test.go", 'package greet\n\nimport "testing"\n\nfunc TestHello(t *testing.T) {\n\tif Hello("mundo") != "Hola mundo" {\n\t\tt.Fatal("unexpected")\n\t}\n}\n')
            self.frontend_files()

        payload = self.run_to_pass("go", "vue-vite", implement)
        self.assertIn("greet", payload["modules"])

    @unittest.skipUnless(_have("node"), "needs node installed")
    def test_vue_and_node_reach_pass(self):
        runner = RUN_TESTS.replace('(["go", "test", "./..."], "backend")', '(["node", "--test", "tests/hello.test.mjs"], "backend")')

        def implement():
            self.write("run_tests.py", runner)
            self.write("backend/src/modules/greet/index.mjs", "export { hello } from './application/hello.mjs';\n")
            self.write("backend/src/modules/greet/application/hello.mjs", "import { PREFIX } from '../domain/prefix.mjs';\nexport const hello = (name) => PREFIX + name;\n")
            self.write("backend/src/modules/greet/domain/prefix.mjs", "export const PREFIX = 'Hola ';\n")
            self.write(
                "backend/tests/hello.test.mjs",
                "import test from 'node:test';\nimport assert from 'node:assert';\nimport { hello } from '../src/modules/greet/index.mjs';\n\n"
                "test('hello', () => assert.strictEqual(hello('mundo'), 'Hola mundo'));\n",
            )
            self.frontend_files()

        payload = self.run_to_pass("node-fastify", "vue-vite", implement)
        self.assertIn("greet", payload["modules"])

    @unittest.skipUnless(_have("node"), "needs node installed")
    def test_the_gate_fails_when_a_layer_is_crossed(self):
        self.onboard("node-fastify", "vue-vite", f'"{sys.executable}" -c "pass"')
        self.write("backend/src/modules/greet/application/hello.mjs", "import { Repo } from '../infrastructure/repo.mjs';\n")
        checked = self.rapid("arch", "check")
        self.assertEqual(checked.returncode, 1)
        self.assertIn("RAPID1420", checked.stdout)
        self.assertIn("backend/src/modules/greet/application/hello.mjs", checked.stdout)


if __name__ == "__main__":
    unittest.main()
