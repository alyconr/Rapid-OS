"""`rapid arch check`: the modular-monolith rule, verified on imports without running code."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from rapid_os.domain.architecture import (
    ArchitectureConfig,
    ArchitectureConfigError,
    architecture_document,
    check_architecture,
    default_config,
    load_rules,
)

ROOT = Path(__file__).resolve().parents[1]
PY = ArchitectureConfig.from_dict(default_config("python-api"))
TS = ArchitectureConfig.from_dict(default_config("web-modern"))


def rules(report):
    return sorted((v.rule, v.file, v.line) for v in report.violations)


class ConfigTests(unittest.TestCase):
    def test_defaults_per_stack(self):
        for stack in ("python-api", "python-ai", "python-fastapi"):
            self.assertEqual(default_config(stack)["modules_root"], "app/modules")
            self.assertEqual(default_config(stack)["public_entry"], "public.py")
            self.assertIn("sqlalchemy", default_config(stack)["domain_forbidden_imports"])
        for stack in ("nodejs-ai", "web-modern", "node-fastify", "nextjs"):
            self.assertEqual(default_config(stack)["modules_root"], "src/modules")
            self.assertEqual(default_config(stack)["public_entry"], "index.ts")
        self.assertIn("@prisma/client", default_config("web-modern")["domain_forbidden_imports"])
        for stack in ("docs-modern", "generic", "custom"):
            self.assertEqual(default_config(stack), {})

    def test_a_frontend_gets_the_feature_rule(self):
        for stack in ("react-vite", "vue-vite", "svelte-vite", "astro", "angular", "nuxt", "sveltekit"):
            config = default_config(stack)
            self.assertEqual(config["component"] if stack in ("react-vite", "vue-vite", "svelte-vite", "astro", "angular") else config["rules"][-1]["component"], "frontend")
        self.assertEqual(default_config("react-vite")["modules_root"], "src/features")
        self.assertEqual(default_config("react-vite")["pure_layer"], "model")
        self.assertEqual(default_config("angular")["modules_root"], "src/app/features")
        self.assertEqual(default_config("frontend-creative")["modules_root"], "src/features")

    def test_a_framework_that_covers_both_gets_two_rules_at_the_root(self):
        document = default_config("nextjs")
        self.assertEqual([r["modules_root"] for r in document["rules"]], ["src/modules", "src/features"])
        self.assertTrue(all("root" not in r for r in document["rules"]))

    def test_a_separate_backend_and_frontend_live_in_their_own_folders(self):
        document = architecture_document({"backend": "go", "frontend": "vue-vite"})
        self.assertEqual([(r["component"], r["root"]) for r in document["rules"]], [("backend", "backend"), ("frontend", "frontend")])
        rules = load_rules(document)
        self.assertEqual([c.modules_root for c in rules], ["backend/internal", "frontend/src/features"])

    def test_layers_are_the_ones_of_the_task(self):
        self.assertEqual(
            default_config("python-api")["layers"],
            {"api": ["application", "domain"], "application": ["domain"], "domain": [],
             "infrastructure": ["application", "domain"]},
        )

    def test_an_invalid_config_is_rapid1420(self):
        for bad in (
            [], {"schema_version": 2}, {**default_config("python-api"), "language": "cobol"},
            {**default_config("python-api"), "modules_root": "../x"},
            {**default_config("python-api"), "layers": {"api": ["ghost"]}},
            {**default_config("python-api"), "domain_forbidden_imports": "sqlalchemy"},
        ):
            with self.subTest(bad=bad), self.assertRaises(ArchitectureConfigError) as caught:
                ArchitectureConfig.from_dict(bad)
            self.assertIn("RAPID1420", str(caught.exception))


class PythonTests(unittest.TestCase):
    def check(self, sources):
        return check_architecture(PY, sources)

    def test_domain_importing_an_orm_or_web_framework(self):
        report = self.check({
            "app/modules/citas/domain/cita.py": "import sqlalchemy\nfrom fastapi import APIRouter\nimport httpx.client\n",
        })
        self.assertEqual(
            rules(report),
            [("domain_forbidden_import", "app/modules/citas/domain/cita.py", n) for n in (1, 2, 3)],
        )

    def test_a_module_importing_another_modules_layer_is_a_violation(self):
        report = self.check({
            "app/modules/citas/application/svc.py": "from app.modules.pagos.infrastructure.repo import Repo\n",
        })
        (violation,) = report.violations
        self.assertEqual(violation.rule, "cross_module")
        self.assertIn("punto público (public.py)", violation.message)
        self.assertEqual(violation.line, 1)

    def test_importing_the_other_modules_public_entry_is_fine(self):
        report = self.check({
            "app/modules/citas/application/svc.py": (
                "from app.modules.pagos.public import charge\n"
                "import app.modules.pagos.public\n"
                "from app.modules.pagos import public\n"
                "from app.modules.pagos import charge\n"  # may be a re-export of the package: not judged
            ),
        })
        self.assertEqual(report.violations, ())

    def test_from_import_of_a_layer_and_plain_import_of_a_layer(self):
        report = self.check({
            "app/modules/citas/api/routes.py": (
                "from app.modules.pagos import infrastructure\n"
                "import app.modules.pagos.domain.model\n"
            ),
        })
        self.assertEqual([v.rule for v in report.violations], ["cross_module", "cross_module"])
        self.assertEqual([v.line for v in report.violations], [1, 2])

    def test_relative_imports_are_resolved(self):
        report = self.check({
            # api -> infrastructure: not allowed
            "app/modules/citas/api/routes.py": "from ..infrastructure import repo\nfrom ..application import svc\nfrom . import helpers\n",
            # domain -> application: not allowed
            "app/modules/citas/domain/cita.py": "from ..application.svc import X\n",
            # three dots from application reaches app.modules: another module's layer
            "app/modules/citas/application/svc.py": "from ...pagos.domain import Y\nfrom ...pagos.public import ok\n",
        })
        self.assertEqual(
            rules(report),
            [
                ("cross_module", "app/modules/citas/application/svc.py", 1),
                ("layer", "app/modules/citas/api/routes.py", 1),
                ("layer", "app/modules/citas/domain/cita.py", 1),
            ],
        )

    def test_layer_directions(self):
        ok = self.check({
            "app/modules/citas/api/r.py": "from app.modules.citas.application import s\nfrom app.modules.citas.domain import d\n",
            "app/modules/citas/application/s.py": "from app.modules.citas.domain import d\n",
            "app/modules/citas/infrastructure/repo.py": "from app.modules.citas.application import s\nfrom app.modules.citas.domain import d\n",
            "app/modules/citas/public.py": "from app.modules.citas.application import s\nfrom app.modules.citas.api import r\n",
        })
        self.assertEqual(ok.violations, ())
        bad = self.check({
            "app/modules/citas/application/s.py": "from app.modules.citas.infrastructure import repo\nfrom app.modules.citas.api import r\n",
            "app/modules/citas/domain/d.py": "from app.modules.citas.infrastructure import repo\n",
        })
        self.assertEqual([v.rule for v in bad.violations], ["layer", "layer", "layer"])

    def test_shared_never_imports_a_module(self):
        report = self.check({
            "app/shared/db.py": "from app.modules.citas.public import x\nfrom app.shared.errors import E\nimport os\n",
        })
        (violation,) = report.violations
        self.assertEqual((violation.rule, violation.line), ("shared", 1))

    def test_modules_may_use_shared_and_files_outside_the_roots_are_not_judged(self):
        report = self.check({
            "app/modules/citas/domain/cita.py": "from app.shared.errors import DomainError\n",
            "app/main.py": "from app.modules.citas.infrastructure.repo import Repo\nimport sqlalchemy\n",
            "tests/test_x.py": "from app.modules.citas.domain import cita\n",
        })
        self.assertEqual(report.violations, ())
        self.assertEqual(report.checked_files, 1)

    def test_a_file_that_cannot_be_parsed_is_skipped_not_a_violation(self):
        report = self.check({"app/modules/citas/domain/broken.py": "def (:\n"})
        self.assertEqual(report.violations, ())
        self.assertIn("broken.py", report.skipped[0])

    def test_a_module_init_that_reexports_an_internal_layer_is_a_back_door(self):
        report = self.check({
            "app/modules/pagos/__init__.py": "from app.modules.pagos.infrastructure.repo import PaymentRepo\n",
            "app/modules/pagos/infrastructure/repo.py": "class PaymentRepo:\n    pass\n",
            "app/modules/citas/application/svc.py": "from app.modules.pagos import PaymentRepo\n",
        })
        (violation,) = report.violations
        self.assertEqual((violation.rule, violation.file, violation.line), ("init_reexport", "app/modules/pagos/__init__.py", 1))
        self.assertEqual(
            violation.message,
            "el __init__.py del módulo 'pagos' solo puede reexportar su public.py",
        )
        self.assertIn("RAPID1420 app/modules/pagos/__init__.py:1", violation.to_line())

    def test_a_module_init_may_be_empty_or_only_reexport_its_own_public(self):
        for body in (
            "",
            "from app.modules.pagos.public import cobrar\n",
            "from .public import cobrar\n",
            "from . import public\n",
            "from app.modules.pagos import public\n",
            "import app.modules.pagos.public\n",
            "from __future__ import annotations\n\nfrom .public import cobrar\n",
        ):
            with self.subTest(body=body):
                report = self.check({
                    "app/modules/pagos/__init__.py": body,
                    # importing the root of the module is allowed, and no longer a back door
                    "app/modules/citas/application/svc.py": "from app.modules.pagos import cobrar\n",
                })
                self.assertEqual(report.violations, ())

    def test_every_other_import_in_a_module_init_is_a_violation(self):
        for body in (
            "import os\n",
            "from . import infrastructure\n",
            "from . import public, infrastructure\n",
            "from .application.cobrar import cobrar\n",
            "from ..citas.public import agendar\n",
            "from app.modules.pagos.domain import Pago\n",
            "from app.shared.errors import E\n",
        ):
            with self.subTest(body=body):
                report = self.check({"app/modules/pagos/__init__.py": body})
                self.assertIn("init_reexport", [v.rule for v in report.violations])

    def test_the_init_rule_only_covers_the_module_root_and_python(self):
        report = self.check({
            "app/modules/pagos/infrastructure/__init__.py": "from .repo import PaymentRepo\n",
            "app/modules/pagos/application/__init__.py": "import os\n",
            "app/shared/__init__.py": "from .errors import E\n",
        })
        self.assertEqual(report.violations, ())
        typescript = check_architecture(TS, {
            "src/modules/pagos/index.ts": "export { Repo } from './infrastructure/repo';\n",
        })
        self.assertEqual(typescript.violations, ())  # index.ts is already the contract

    def test_a_file_directly_in_modules_root_is_not_a_module(self):
        report = self.check({
            "app/modules/__init__.py": "",
            "app/modules/helpers.py": "import sqlalchemy\n",
            "app/modules/citas/public.py": "x = 1\n",
            "app/modules/pagos/public.py": "x = 1\n",
        })
        self.assertEqual(report.modules, ("citas", "pagos"))
        self.assertEqual(report.checked_files, 2)
        self.assertEqual(report.violations, ())

    def test_no_modules_yet(self):
        report = self.check({})
        self.assertEqual((report.ok, report.modules, report.checked_files), (True, (), 0))

    def test_modules_are_listed(self):
        report = self.check({
            "app/modules/citas/public.py": "x = 1\n",
            "app/modules/pagos/public.py": "x = 1\n",
        })
        self.assertEqual(report.modules, ("citas", "pagos"))


class TypeScriptTests(unittest.TestCase):
    def check(self, sources):
        return check_architecture(TS, sources)

    def test_domain_forbidden_libraries(self):
        report = self.check({
            "src/modules/citas/domain/cita.ts": (
                "import { PrismaClient } from '@prisma/client';\n"
                "import React from \"react\";\n"
                "import { NextResponse } from 'next/server';\n"
                "import { z } from 'zod';\n"
            ),
        })
        self.assertEqual([(v.rule, v.line) for v in report.violations], [("domain_forbidden_import", n) for n in (1, 2, 3)])

    def test_cross_module_only_through_index(self):
        report = self.check({
            "src/modules/citas/application/svc.ts": (
                "import { charge } from '../../pagos';\n"
                "import { charge2 } from '../../pagos/index';\n"
                "import { charge3 } from '@/modules/pagos';\n"
                "import { Repo } from '../../pagos/infrastructure/repo';\n"
                "import { Model } from '@/modules/pagos/domain/model';\n"
            ),
        })
        self.assertEqual([(v.rule, v.line) for v in report.violations], [("cross_module", 4), ("cross_module", 5)])

    def test_layer_directions(self):
        report = self.check({
            "src/modules/citas/api/route.ts": "import { r } from '../infrastructure/repo';\nimport { s } from '../application/svc';\n",
            "src/modules/citas/domain/cita.ts": "import { s } from '../application/svc';\n",
            "src/modules/citas/infrastructure/repo.ts": "import { s } from '../application/svc';\nimport { d } from '../domain/cita';\n",
            "src/modules/citas/index.ts": "export { s } from './application/svc';\n",
        })
        self.assertEqual(rules(report), [("layer", "src/modules/citas/api/route.ts", 1), ("layer", "src/modules/citas/domain/cita.ts", 1)])

    def test_shared_never_imports_a_module(self):
        report = self.check({
            "src/shared/db.ts": "import { x } from '../modules/citas';\nimport { y } from './errors';\n",
        })
        self.assertEqual([(v.rule, v.line) for v in report.violations], [("shared", 1)])

    def test_every_import_form_and_comments(self):
        report = self.check({
            "src/modules/citas/application/svc.ts": (
                "// import { a } from '../../pagos/domain/a';\n"
                "/* import { b } from '../../pagos/domain/b'; */\n"
                "import {\n  c,\n  d,\n} from '../../pagos/domain/c';\n"
                "export * from '../../pagos/infrastructure/e';\n"
                "const f = await import('../../pagos/domain/f');\n"
                "const g = require('../../pagos/domain/g');\n"
                "import '../../pagos/domain/side-effect';\n"
            ),
        })
        self.assertEqual(
            sorted(v.line for v in report.violations), [6, 7, 8, 9, 10]
        )

    def test_the_ui_outside_the_roots_is_not_judged(self):
        report = self.check({"src/app/page.tsx": "import { x } from '../modules/citas/domain/x';\n"})
        self.assertEqual(report.violations, ())


class CliCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)
        self.env = {
            **{k: v for k, v in os.environ.items() if k not in ("CLAUDECODE", "CLAUDE_CODE_CHILD_SESSION")},
            "PYTHONPATH": str(ROOT),
            "PYTHONIOENCODING": "utf-8",
            "PYTHONDONTWRITEBYTECODE": "1",
        }

    def write(self, relative, text):
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    def rule(self, stack="python-api"):
        self.write(".rapid-os/standards/architecture.json", json.dumps(default_config(stack)))

    def arch(self, *argv):
        return subprocess.run(
            [sys.executable, "-m", "rapid_os.cli.main", "arch", "check", *argv],
            cwd=self.root, capture_output=True, text=True, encoding="utf-8", env=self.env,
        )


class ArchCheckCliTests(CliCase):
    def test_without_architecture_json_it_warns_and_exits_zero(self):
        result = self.arch()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("WARNING", result.stdout)
        self.assertIn("architecture.json", result.stdout)
        as_json = json.loads(self.arch("--json").stdout)
        self.assertTrue(as_json["ok"])
        self.assertIn("warning", as_json)

    def test_without_modules_yet_it_exits_zero(self):
        self.rule()
        result = self.arch()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Sin módulos todavía", result.stdout)

    def test_two_modules_and_the_modules_init_count_as_two_modules(self):
        self.rule()
        self.write("app/modules/__init__.py", "")
        self.write("app/modules/citas/public.py", "x = 1\n")
        self.write("app/modules/pagos/public.py", "x = 1\n")
        result = self.arch()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("en 2 módulo(s)", result.stdout)
        self.assertEqual(json.loads(self.arch("--json").stdout)["modules"], ["citas", "pagos"])

    def test_the_reexport_back_door_fails_the_cli(self):
        self.rule()
        self.write("app/modules/pagos/__init__.py", "from app.modules.pagos.infrastructure.repo import PaymentRepo\n")
        self.write("app/modules/pagos/infrastructure/repo.py", "class PaymentRepo:\n    pass\n")
        self.write("app/modules/citas/application/svc.py", "from app.modules.pagos import PaymentRepo\n")
        result = self.arch()
        self.assertEqual(result.returncode, 1)
        self.assertIn(
            "RAPID1420 app/modules/pagos/__init__.py:1 importa 'app.modules.pagos.infrastructure.repo': "
            "el __init__.py del módulo 'pagos' solo puede reexportar su public.py",
            result.stdout,
        )

    def test_a_clean_modular_project(self):
        self.rule()
        self.write("app/modules/citas/public.py", "from app.modules.citas.application.svc import crear\n")
        self.write("app/modules/citas/application/svc.py", "from app.modules.citas.domain.cita import Cita\n")
        self.write("app/modules/citas/domain/cita.py", "class Cita:\n    pass\n")
        result = self.arch()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("Arquitectura OK", result.stdout)

    def test_violations_exit_one_with_rapid1420_per_violation(self):
        self.rule()
        self.write("app/modules/citas/domain/cita.py", "import sqlalchemy\nfrom app.modules.pagos.infrastructure import repo\n")
        result = self.arch()
        self.assertEqual(result.returncode, 1)
        lines = [l for l in result.stdout.splitlines() if l.startswith("RAPID1420")]
        self.assertEqual(len(lines), 2)
        self.assertIn("app/modules/citas/domain/cita.py:1 importa 'sqlalchemy'", lines[0])
        self.assertNotIn("Traceback", result.stderr)
        report = json.loads(self.arch("--json").stdout)
        self.assertFalse(report["ok"])
        self.assertEqual(
            [(v["code"], v["rule"], v["line"], v["import"]) for v in report["violations"]],
            [("RAPID1420", "domain_forbidden_import", 1, "sqlalchemy"),
             ("RAPID1420", "cross_module", 2, "app.modules.pagos.infrastructure")],
        )

    def test_an_existing_project_with_global_layers_is_only_judged_inside_the_modules_root(self):
        self.rule()
        self.write("controllers/user.py", "import sqlalchemy\nfrom services.user import x\n")
        self.write("services/user.py", "from models.user import User\n")
        self.write("models/user.py", "import sqlalchemy\n")
        result = self.arch()
        self.assertEqual(result.returncode, 0, result.stdout)

    def test_typescript_project(self):
        self.rule("web-modern")
        self.write("src/modules/citas/domain/cita.ts", "import { PrismaClient } from '@prisma/client';\n")
        result = self.arch("--json")
        self.assertEqual(result.returncode, 1)
        self.assertEqual(json.loads(result.stdout)["violations"][0]["import"], "@prisma/client")

    def test_an_invalid_architecture_json_is_reported_without_traceback(self):
        self.write(".rapid-os/standards/architecture.json", "{not json")
        result = self.arch()
        self.assertEqual(result.returncode, 1)
        self.assertIn("RAPID1420", result.stderr)
        self.assertNotIn("Traceback", result.stderr)


if __name__ == "__main__":
    unittest.main()
