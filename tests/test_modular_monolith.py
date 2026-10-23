"""F5: every backend project starts as a modular monolith; the rule reaches the agent as a
standard and Rapid OS verifies it in every run (gate.architecture)."""

from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path

from rapid_os.adapters.evidence_registry import EvidenceRegistry
from rapid_os.adapters.run_registry import RunRegistry
from tests.test_no_git import SMOKE_TEST, GitIsolated

ROOT = Path(__file__).resolve().parents[1]
TEST_COMMAND = f'"{sys.executable}" -m unittest discover -s tests -t .'

SPEC = {
    "title": "Agendar citas", "mode": "feature", "business_objective": "Agendar citas",
    "problem_statement": "No hay agenda", "scope": ["citas"], "acceptance_criteria": ["se agenda"],
    "tasks": ["T001: Crear el módulo citas"],
}

ARCHITECTURE_BODY = (
    "## Decisión\nMonolito modular.\n\n## Por qué\nUn solo despliegue.\n\n"
    "## Alternativas descartadas\nMicroservicios.\n\n## Consecuencias\nLímites por módulo.\n\n"
    "## Módulos\n- citas: agenda; tablas citas; no hexagonal.\n\n"
    "## Reglas de dependencia\napi -> application -> domain.\n\n"
    "## Servicios de infraestructura\nSolo PostgreSQL.\n"
)


class Project(GitIsolated):
    def decide(self, stack, topology, test_command="none"):
        for key, value in (
            ("stack", stack), ("topology", topology), ("archetype", "mvp"), ("ai", "no"),
            ("agents", "claude"), ("test-command", test_command), ("services", "none"),
        ):
            result = self.rapid("setup", "set", key, value)
            self.assertEqual(result.returncode, 0, result.stderr)

    def finish_onboarding(self, stack, topology, test_command="none"):
        self.decide(stack, topology, test_command)
        for doc in ("brief", "business", "data-model", "architecture", "deployment"):
            self.assertEqual(self.rapid("setup", "doc", doc, "--skip").returncode, 0)
        finished = self.rapid("setup", "finish")
        self.assertEqual(finished.returncode, 0, finished.stderr)

    @property
    def standards(self) -> Path:
        return self.root / ".rapid-os" / "standards"

    def write(self, relative, text):
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    def contract(self):
        run_id = json.loads((self.root / ".rapid-os" / "session.json").read_text("utf-8"))["active_run_id"]
        return RunRegistry(self.root, self.root / ".rapid-os").get_contract(run_id)


class StandardIsWrittenTests(Project):
    def test_python_api_gets_the_text_and_the_machine_rule(self):
        self.finish_onboarding("python-api", "fullstack-separated")
        md = (self.standards / "architecture.md").read_text("utf-8")
        rule = json.loads((self.standards / "architecture.json").read_text("utf-8"))
        self.assertEqual(rule["language"], "python")
        self.assertEqual((rule["modules_root"], rule["shared_root"], rule["public_entry"]), ("app/modules", "app/shared", "public.py"))
        self.assertEqual(rule["layers"]["domain"], [])
        self.assertEqual(rule["domain_forbidden_imports"], ["fastapi", "sqlalchemy", "starlette", "httpx"])
        # The text of the rule, with only the Python tree.
        for expected in (
            "módulos por capacidad de negocio", "nunca en capas globales", "`api/`", "`application/`",
            "`domain/`", "`infrastructure/`", "único punto público", "Entre módulos",
            "dueño de sus tablas", "`shared/` no importa ningún módulo", "Cuándo un módulo es hexagonal",
            "Nunca desactives ni edites `.rapid-os/standards/architecture.json` para que un check pase",
            "app/modules/", "public.py",
        ):
            with self.subTest(expected=expected):
                self.assertIn(expected, md)
        self.assertNotIn("src/modules", md)  # the tree of the other family is left out

    def test_the_other_stacks_of_the_family_get_their_own_tree(self):
        self.finish_onboarding("web-modern", "fullstack-baas")
        md = (self.standards / "architecture.md").read_text("utf-8")
        rule = json.loads((self.standards / "architecture.json").read_text("utf-8"))
        self.assertEqual(rule["language"], "typescript")
        self.assertEqual((rule["modules_root"], rule["public_entry"]), ("src/modules", "index.ts"))
        self.assertEqual(rule["domain_forbidden_imports"], ["next", "react", "express", "@prisma/client"])
        self.assertIn("src/app/", md)
        self.assertIn("solo importa el `index.ts`", md)
        self.assertNotIn("app/main.py", md)  # the Python tree is left out

    def test_it_reaches_the_agent_as_a_standard_without_the_assumption_banner(self):
        self.finish_onboarding("python-api", "fullstack-separated")
        claude = (self.root / "CLAUDE.md").read_text("utf-8")
        self.assertIn("ARQUITECTURA: MONOLITO MODULAR", claude)
        self.assertNotIn("Supuestos redactados por el agente", claude)
        context = self.rapid("context")
        self.assertEqual(context.returncode, 0, context.stderr)

    def test_stacks_without_a_backend_do_not_get_the_rule(self):
        self.finish_onboarding("docs-modern", "doc-site")
        self.assertFalse((self.standards / "architecture.md").exists())
        self.assertFalse((self.standards / "architecture.json").exists())

    def test_a_person_edit_survives_a_later_finish(self):
        self.finish_onboarding("python-api", "fullstack-separated")
        mine = self.standards / "architecture.md"
        mine.write_text(mine.read_text("utf-8") + "\nNota de la persona.\n", encoding="utf-8")
        self.assertEqual(self.rapid("setup", "set", "test-command", "none").returncode, 0)
        self.assertIn("Nota de la persona.", mine.read_text("utf-8"))


class GateInTheContractTests(Project):
    started_runs = 0

    def start(self, mode):
        # A spec is identified by its title: every start needs its own.
        self.started_runs += 1
        spec = {**SPEC, "mode": mode, "title": f"Agendar citas {mode} {self.started_runs}"}
        return self.rapid("start", mode, "--spec-file", "-", "--json", stdin=json.dumps(spec))

    def gates(self, mode):
        started = self.start(mode)
        self.assertEqual(started.returncode, 0, started.stderr + started.stdout)
        gate_ids = [g.id for g in self.contract().gates]
        self.assertEqual(self.rapid("abort").returncode, 0)
        return gate_ids

    def test_feature_bugfix_and_refactor_get_gate_architecture_and_the_others_do_not(self):
        self.finish_onboarding("python-api", "fullstack-separated", TEST_COMMAND)
        self.write("app/main.py", "print('hi')\n")  # bugfix and refactor need code to work on
        self.write("tests/__init__.py", "")
        self.write("tests/test_smoke.py", SMOKE_TEST)
        for mode in ("feature", "bugfix", "refactor"):
            with self.subTest(mode=mode):
                self.assertIn("gate.architecture", self.gates(mode))
        for mode in ("hardening", "research"):
            with self.subTest(mode=mode):
                self.assertNotIn("gate.architecture", self.gates(mode))

    def test_the_gate_sits_after_the_tests_and_is_not_waivable(self):
        self.finish_onboarding("python-api", "fullstack-separated", TEST_COMMAND)
        self.assertEqual(self.start("feature").returncode, 0)
        gates = self.contract().gates
        ids = [g.id for g in gates]
        self.assertLess(ids.index("gate.tests"), ids.index("gate.architecture"))
        self.assertLess(ids.index("gate.architecture"), ids.index("gate.final-verification"))
        gate = next(g for g in gates if g.id == "gate.architecture")
        self.assertEqual(gate.kind.value, "architecture_check")
        self.assertTrue(gate.required)
        self.assertFalse(gate.waivable)

    def test_without_the_rule_there_is_no_gate(self):
        self.finish_onboarding("generic", "fullstack-separated", TEST_COMMAND)
        self.assertFalse((self.standards / "architecture.json").exists())
        self.assertNotIn("gate.architecture", self.gates("feature"))

    def test_removing_the_rule_removes_the_gate_from_new_runs(self):
        self.finish_onboarding("python-api", "fullstack-separated", TEST_COMMAND)
        self.assertIn("gate.architecture", self.gates("feature"))
        (self.standards / "architecture.json").unlink()
        self.assertNotIn("gate.architecture", self.gates("feature"))


class ArchitectureBankTests(Project):
    def draft(self, body):
        return self.rapid("setup", "doc", "architecture", "--source", "drafted", "--file", "-", stdin=body)

    def test_a_draft_without_modules_is_rejected(self):
        body = ARCHITECTURE_BODY.replace("## Módulos\n- citas: agenda; tablas citas; no hexagonal.\n\n", "")
        result = self.draft(body)
        self.assertEqual(result.returncode, 1)
        self.assertIn("RAPID1403", result.stderr)
        self.assertIn("'modules'", result.stderr)
        self.assertIn("Módulos", result.stderr)
        self.assertFalse((self.root / "docs" / "ARCHITECTURE.md").exists())

    def test_a_draft_without_dependency_rules_is_rejected(self):
        result = self.draft(ARCHITECTURE_BODY.replace("## Reglas de dependencia\napi -> application -> domain.\n", ""))
        self.assertEqual(result.returncode, 1)
        self.assertIn("RAPID1403", result.stderr)
        self.assertIn("'dependency_rules'", result.stderr)

    def test_a_complete_draft_is_accepted_also_in_english(self):
        self.assertEqual(self.draft(ARCHITECTURE_BODY).returncode, 0)
        english = (
            "## Decision\nx\n\n## Rationale\nx\n\n## Rejected alternatives\nx\n\n## Consequences\nx\n\n"
            "## Modules\nx\n\n## Dependency rules\nx\n\n## Infrastructure services\nx\n"
        )
        replaced = self.rapid(
            "setup", "doc", "architecture", "--source", "drafted", "--replace", "--file", "-", stdin=english
        )
        self.assertEqual(replaced.returncode, 0, replaced.stderr)

    def test_the_limit_is_now_6000_characters(self):
        long_body = ARCHITECTURE_BODY + "x" * 5000
        self.assertEqual(self.draft(long_body).returncode, 0)
        too_long = self.rapid(
            "setup", "doc", "architecture", "--source", "drafted", "--replace", "--file", "-",
            stdin=ARCHITECTURE_BODY + "x" * 6100,
        )
        self.assertEqual(too_long.returncode, 1)
        self.assertIn("RAPID1404", too_long.stderr)

    def test_the_questions_ask_for_modules_and_hexagonal_modules(self):
        self.decide("python-api", "fullstack-separated")
        for doc in ("brief", "business", "data-model"):
            self.rapid("setup", "doc", doc, "--skip")
        action = json.loads(self.rapid("setup", "next", "--json").stdout)
        self.assertEqual(action["doc"], "architecture")
        texts = [q["text"] for q in action["questions"]]
        self.assertIn("¿Qué capacidades de negocio tiene el producto? Cada una será un módulo", texts)
        self.assertIn("¿Qué módulos integran sistemas externos o tienen reglas complejas (serán hexagonales)?", texts)
        self.assertEqual(action["max_chars"], 6000)


class WorktreeTests(Project):
    """A run in a worktree: the rule lives in the main project, the code to judge is the worktree's."""

    def setUp(self):
        super().setUp()
        self.finish_onboarding("python-api", "fullstack-separated", TEST_COMMAND)
        committed = self.git("-c", "user.name=t", "-c", "user.email=t@example.com", "commit", "--allow-empty", "-m", "base")
        self.assertEqual(committed.returncode, 0, committed.stderr)
        started = self.rapid("start", "feature", "--spec-file", "-", "--json", stdin=json.dumps(SPEC))
        self.assertEqual(started.returncode, 0, started.stderr + started.stdout)
        self.assertIn("gate.architecture", [g.id for g in self.contract().gates])
        self.worktree = self.root.parent / "run-worktree"
        added = self.git("worktree", "add", str(self.worktree), "-b", "run-branch")
        self.assertEqual(added.returncode, 0, added.stderr)
        self.assertFalse((self.worktree / ".rapid-os").exists())  # the ledger stays in the main project

    def arch(self, *argv, cwd=None):
        return subprocess.run(
            [sys.executable, "-m", "rapid_os.cli.main", "arch", "check", *argv],
            cwd=cwd or self.worktree, capture_output=True, text=True, encoding="utf-8", env=self.env,
        )

    def write_in_worktree(self, relative, text):
        path = self.worktree / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    def test_it_uses_the_rule_of_the_main_project_and_judges_the_worktrees_code(self):
        self.write_in_worktree("app/modules/citas/public.py", "x = 1\n")
        clean = self.arch()
        self.assertEqual(clean.returncode, 0, clean.stdout + clean.stderr)
        self.assertIn("Arquitectura OK", clean.stdout)
        self.write_in_worktree("app/modules/citas/domain/cita.py", "import sqlalchemy\n")
        dirty = self.arch()
        self.assertEqual(dirty.returncode, 1)
        self.assertIn("RAPID1420 app/modules/citas/domain/cita.py:1 importa 'sqlalchemy'", dirty.stdout)
        # The code of the main project was never looked at: it has no violation.
        self.assertEqual(self.arch(cwd=self.root).returncode, 0)

    def test_a_rule_in_the_worktree_itself_wins(self):
        own = json.loads((self.standards / "architecture.json").read_text("utf-8"))
        own["domain_forbidden_imports"] = []
        self.write_in_worktree(".rapid-os/standards/architecture.json", json.dumps(own))
        self.write_in_worktree("app/modules/citas/domain/cita.py", "import sqlalchemy\n")
        self.assertEqual(self.arch().returncode, 0)

    def test_a_run_that_demands_the_gate_does_not_pass_without_any_rule(self):
        (self.standards / "architecture.json").unlink()
        for cwd in (self.worktree, self.root):
            with self.subTest(cwd=cwd.name):
                result = self.arch(cwd=cwd)
                self.assertEqual(result.returncode, 1)
                self.assertIn("RAPID1420 el run exige gate.architecture y no hay architecture.json", result.stderr)
                self.assertNotIn("Traceback", result.stderr)
        as_json = self.arch("--json")
        self.assertEqual(as_json.returncode, 1)
        report = json.loads(as_json.stdout)
        self.assertFalse(report["ok"])
        self.assertIn("el run exige gate.architecture", report["error"])

    def test_outside_a_run_a_missing_rule_is_still_only_a_warning(self):
        self.assertEqual(self.rapid("abort").returncode, 0)
        (self.standards / "architecture.json").unlink()
        for cwd in (self.worktree, self.root):
            with self.subTest(cwd=cwd.name):
                result = self.arch(cwd=cwd)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertIn("WARNING", result.stdout)


class ShortcutTemplateTests(unittest.TestCase):
    def test_init_shortcut_starts_from_the_modular_monolith(self):
        text = (ROOT / "templates" / "shortcuts" / "rapid-init.md").read_text("utf-8")
        for expected in (
            "monolito modular", ".rapid-os/standards/architecture.md", "responsabilidad", "tablas",
            "hexagonal", "## Módulos", "## Reglas de dependencia",
        ):
            with self.subTest(expected=expected):
                self.assertIn(expected, text)


def approve(root, gate, env):
    code = (
        "import sys, unittest.mock as mock, rapid_os.cli.main as m; "
        f"sys.argv = ['rapid', 'approve', '{gate}']; "
        "mock.patch('sys.stdin.isatty', return_value=True).start(); "
        "mock.patch('rapid_os.orchestration.lifecycle.stdin_is_windows_nul', return_value=False).start(); "
        "mock.patch('rapid_os.orchestration.lifecycle.read_ancestry', "
        "return_value=__import__('rapid_os.core.ancestry', fromlist=['x']).AncestryResult(())).start(); "
        f"mock.patch('builtins.input', return_value='aprobar {gate}').start(); sys.exit(m.main())"
    )
    return subprocess.run([sys.executable, "-c", code], cwd=root, capture_output=True, text=True, env=env)


MODULE_FILES = {
    "app/main.py": "from app.modules.citas.public import agendar\n",
    "app/shared/__init__.py": "",
    "app/modules/__init__.py": "",
    "app/modules/citas/__init__.py": "",
    "app/modules/citas/public.py": "from app.modules.citas.application.agendar import agendar\n",
    "app/modules/citas/api/__init__.py": "",
    "app/modules/citas/application/__init__.py": "",
    "app/modules/citas/application/agendar.py": "from app.modules.citas.domain.cita import Cita\n\n\ndef agendar():\n    return Cita()\n",
    "app/modules/citas/domain/__init__.py": "",
    "app/modules/citas/domain/cita.py": "class Cita:\n    pass\n",
    "app/modules/citas/infrastructure/__init__.py": "",
    "tests/__init__.py": "",
    "tests/test_smoke.py": SMOKE_TEST,
}


class EndToEndTests(Project):
    def begin(self):
        """An empty python-api project, onboarded, with the run started."""
        self.finish_onboarding("python-api", "fullstack-separated", TEST_COMMAND)
        started = self.rapid("start", "feature", "--spec-file", "-", "--json", stdin=json.dumps(SPEC))
        self.assertEqual(started.returncode, 0, started.stderr + started.stdout)

    def drive(self, before_gate=None):
        """Follow `rapid next` like an agent. Returns the human gate, or the failed command."""
        for _ in range(30):
            action = json.loads(self.rapid("next", "--json").stdout)["action"]
            if action["kind"] == "await_human_approval":
                return action["gate_ids"][0], None
            if action["kind"] == "implement_task":
                for relative, text in MODULE_FILES.items():
                    self.write(relative, text)
            if action["kind"] == "verify" and "gate.architecture" in action.get("gate_ids", ()) and before_gate:
                before_gate()
            for key in ("command", "after"):
                if action.get(key):
                    result = self.rapid(*action[key][1:])
                    if result.returncode != 0:
                        return None, (action[key], result)
        self.fail("the run never reached a human gate")

    def test_the_scaffold_task_asks_for_the_modular_structure(self):
        self.begin()
        scaffold = self.contract().tasks[0].description
        self.assertIn("con la estructura de .rapid-os/standards/architecture.md", scaffold)
        self.assertIn("un módulo de ejemplo con sus cuatro capas y su punto público", scaffold)

    def test_without_the_rule_the_scaffold_task_is_the_old_one(self):
        self.finish_onboarding("generic", "fullstack-separated", TEST_COMMAND)
        started = self.rapid("start", "feature", "--spec-file", "-", "--json", stdin=json.dumps(SPEC))
        self.assertEqual(started.returncode, 0, started.stderr)
        self.assertNotIn("architecture.md", self.contract().tasks[0].description)

    def test_empty_project_to_pass_through_the_architecture_gate(self):
        self.begin()
        gate, failed = self.drive()
        self.assertIsNone(failed, failed)
        self.assertEqual(approve(self.root, gate, self.env).returncode, 0)
        evidence = [
            e
            for e in EvidenceRegistry(self.root, self.root / ".rapid-os").list(self.contract().run_id)
            if "gate.architecture" in e.gate_ids
        ]
        self.assertTrue(evidence, "gate.architecture has no evidence")
        finished = self.rapid("finish", "--json")
        self.assertEqual(finished.returncode, 0, finished.stderr)
        report = json.loads(finished.stdout)
        self.assertEqual(report["verdict"], "pass")
        gate_assertions = [a for a in report["assertions"] if a["subject_id"] == "gate.architecture"]
        self.assertEqual([a["status"] for a in gate_assertions], ["pass"])

    def test_a_violation_keeps_the_run_from_passing(self):
        self.begin()

        def introduce_a_violation():
            self.write("app/modules/citas/domain/cita.py", "import sqlalchemy\n\n\nclass Cita:\n    pass\n")

        gate, failed = self.drive(before_gate=introduce_a_violation)
        self.assertIsNone(gate)
        command, result = failed
        self.assertIn("gate.architecture", command)
        self.assertEqual(result.returncode, 1)
        # The failure is on the screen of the person (and in the check log): file, line, import, rule.
        self.assertIn("RAPID1420", result.stdout + result.stderr)
        self.assertIn("app/modules/citas/domain/cita.py:1", result.stdout + result.stderr)
        finished = self.rapid("finish", "--json")
        self.assertNotIn('"verdict": "pass"', finished.stdout)
        # Fixing the code lets the same gate pass.
        self.write("app/modules/citas/domain/cita.py", "class Cita:\n    pass\n")
        gate, failed = self.drive()
        self.assertIsNone(failed, failed)
        self.assertEqual(approve(self.root, gate, self.env).returncode, 0)
        done = self.rapid("finish", "--json")
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertEqual(json.loads(done.stdout)["verdict"], "pass")


if __name__ == "__main__":
    unittest.main()
