"""The architecture photo of a run: violations the project already had are debt, not this run's failure."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from rapid_os.domain.architecture import ArchitectureConfig, check_architecture, default_config
from rapid_os.orchestration.architecture_baseline import RunBaseline, classify, previous_debt_line, violation_key

ROOT = Path(__file__).resolve().parents[1]

TEST_COMMAND = f'"{sys.executable}" -m unittest discover -s tests -t .'
SMOKE = "import unittest\n\n\nclass T(unittest.TestCase):\n    def test_ok(self):\n        self.assertTrue(True)\n"
INFRA = "class Repo:\n    pass\n"
VIOLATING = "from app.modules.citas.infrastructure.repo import Repo\n"
FEATURE_SPEC = {
    "title": "Agendar citas", "mode": "feature", "business_objective": "Agendar", "problem_statement": "No hay agenda",
    "scope": ["citas"], "acceptance_criteria": ["se agenda"], "tasks": ["T001: Crear algo"],
}
REFACTOR_SPEC = {
    "title": "Limpiar capas", "business_objective": "Separar capas", "problem_statement": "api importa infrastructure",
    "acceptance_criteria": ["mismo comportamiento"], "tasks": ["T001: Limpiar", "T002: Verificar"],
}


class Project(unittest.TestCase):
    """A python-fastapi backend-only project with two violations that existed before any run."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        base = Path(self._tmp.name)
        self.root = base / "project"
        self.root.mkdir()
        gitconfig = base / "gitconfig"
        gitconfig.write_text("[user]\n\tname = T\n\temail = t@example.com\n[init]\n\tdefaultBranch = main\n", encoding="utf-8")
        self.env = {
            **{k: v for k, v in os.environ.items() if k not in ("CLAUDECODE", "CLAUDE_CODE_CHILD_SESSION")},
            "GIT_CONFIG_GLOBAL": str(gitconfig), "GIT_CONFIG_NOSYSTEM": "1",
            "PYTHONPATH": str(ROOT), "PYTHONIOENCODING": "utf-8", "PYTHONDONTWRITEBYTECODE": "1",
        }
        for step in (("stack", "python-fastapi"), ("topology", "backend-only"), ("archetype", "mvp"), ("ai", "no"),
                     ("agents", "claude"), ("test-command", TEST_COMMAND), ("services", "none")):
            self.ok("setup", "set", *step)
        for doc in ("brief", "business", "data-model", "architecture", "deployment"):
            self.ok("setup", "doc", doc, "--skip")
        self.ok("setup", "finish")
        self.write("tests/__init__.py", "")
        self.write("tests/test_ok.py", SMOKE)
        self.write("app/modules/citas/public.py", "x = 1\n")
        self.write("app/modules/citas/infrastructure/repo.py", INFRA)
        self.write("app/modules/citas/api/router.py", VIOLATING)
        self.write("app/modules/citas/api/dependencias.py", VIOLATING)
        subprocess.run(["git", "add", "-A"], cwd=self.root, env=self.env, check=True, capture_output=True)
        subprocess.run(["git", "commit", "-q", "-m", "base"], cwd=self.root, env=self.env, check=True, capture_output=True)

    def rapid(self, *argv, stdin=None):
        return subprocess.run(
            [sys.executable, "-m", "rapid_os.cli.main", *argv], cwd=self.root, capture_output=True, text=True,
            encoding="utf-8", env=self.env, input=stdin,
        )

    def ok(self, *argv, stdin=None):
        result = self.rapid(*argv, stdin=stdin)
        self.assertEqual(result.returncode, 0, f"{argv}: {result.stdout}{result.stderr}")
        return result

    def write(self, relative, text):
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    def start(self, mode="feature", spec=None):
        self.ok("start", mode, "--spec-file", "-", "--json", stdin=json.dumps(spec or FEATURE_SPEC))

    def session(self):
        return json.loads((self.root / ".rapid-os" / "session.json").read_text("utf-8"))

    def check(self, *flags):
        return self.rapid("arch", "check", *flags)


class PhotoAtStartTests(Project):
    def test_start_stores_file_rule_and_import_without_the_line(self):
        self.start()
        photo = self.session()["start_architecture"]
        self.assertEqual(
            sorted((item["file"], item["rule"], item["import"]) for item in photo),
            [("app/modules/citas/api/dependencias.py", "layer", "app.modules.citas.infrastructure.repo"),
             ("app/modules/citas/api/router.py", "layer", "app.modules.citas.infrastructure.repo")],
        )
        self.assertTrue(all(set(item) == {"file", "rule", "import"} for item in photo))

    def test_a_project_without_an_architecture_rule_has_no_photo(self):
        (self.root / ".rapid-os" / "standards" / "architecture.json").unlink()
        self.start()
        self.assertNotIn("start_architecture", self.session())

    def test_the_photo_does_not_depend_on_the_line_number(self):
        self.start()
        path = self.root / "app/modules/citas/api/router.py"
        path.write_text("# a comment\n\n\n" + VIOLATING, encoding="utf-8")
        result = self.check("--new-only", "--json")
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertEqual(json.loads(result.stdout)["counts"], {"new": 0, "previous": 2})


class NewOnlyTests(Project):
    def test_a_run_that_does_not_touch_the_previous_violations_passes(self):
        self.start()
        plain = self.check()
        self.assertEqual(plain.returncode, 1)  # plain still lists and fails on all of them
        self.assertEqual(plain.stdout.count("RAPID1420 app/modules/citas/api/"), 2)
        gate = self.check("--new-only")
        self.assertEqual(gate.returncode, 0, gate.stdout + gate.stderr)
        self.assertIn("2 violaciones previas; no bloquean este run", gate.stdout)
        self.assertIn("/rapid-refactor", gate.stdout)
        self.assertIn("Sin violaciones nuevas", gate.stdout)

    def test_a_run_that_adds_a_violation_does_not_pass(self):
        self.start()
        self.write("app/modules/citas/api/nuevo.py", VIOLATING)
        gate = self.check("--new-only")
        self.assertEqual(gate.returncode, 1)
        lines = [l for l in gate.stdout.splitlines() if l.startswith("RAPID1420")]
        self.assertEqual(len(lines), 1)
        self.assertIn("api/nuevo.py:1", lines[0])
        self.assertIn("2 violaciones previas", gate.stdout)

    def test_the_json_separates_new_and_previous(self):
        self.start()
        self.write("app/modules/citas/api/nuevo.py", VIOLATING)
        data = json.loads(self.check("--new-only", "--json").stdout)
        self.assertFalse(data["ok"])
        self.assertTrue(data["new_only"])
        self.assertEqual(data["counts"], {"new": 1, "previous": 2})
        self.assertTrue(data["baseline"])
        self.assertEqual(
            sorted((v["file"].rsplit("/", 1)[1], v["status"]) for v in data["violations"]),
            [("dependencias.py", "previous"), ("nuevo.py", "new"), ("router.py", "previous")],
        )
        plain = json.loads(self.check("--json").stdout)
        self.assertFalse(plain["ok"])  # a secas, all of them count
        self.assertFalse(plain["new_only"])

    def test_the_gate_command_rapid_next_proposes_is_new_only(self):
        self.start()
        for _ in range(30):
            action = json.loads(self.ok("next", "--json").stdout)["action"]
            if action["kind"] == "implement_task":
                self.write("app/modules/citas/domain/cita.py", "class Cita:\n    pass\n")
            if action["kind"] == "verify" and "arch" in (action.get("command") or ()):
                self.assertEqual(action["command"][-4:], ["rapid", "arch", "check", "--new-only"])
                return
            for key in ("command", "after"):
                if action.get(key):
                    self.ok(*action[key][1:])
        self.fail("rapid next never proposed the architecture gate")

    def test_the_gate_passes_with_previous_violations_and_fails_with_a_new_one(self):
        self.start()
        passed = self.rapid("check", "--gate", "gate.architecture", "--", "rapid", "arch", "check", "--new-only")
        self.assertEqual(passed.returncode, 0, passed.stdout + passed.stderr)
        self.write("app/modules/citas/api/nuevo.py", VIOLATING)
        failed = self.rapid("check", "--gate", "gate.architecture", "--", "rapid", "arch", "check", "--new-only")
        self.assertEqual(failed.returncode, 1)


class NoPhotoTests(Project):
    def test_without_an_active_run_every_violation_is_previous(self):
        result = self.check("--new-only")
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertIn("2 violaciones previas", result.stdout)
        data = json.loads(self.check("--new-only", "--json").stdout)
        self.assertEqual(data["counts"], {"new": 0, "previous": 2})
        self.assertIsNone(data["baseline"])

    def test_a_run_that_started_before_the_photo_existed_does_not_block(self):
        self.start()
        session_file = self.root / ".rapid-os" / "session.json"
        data = json.loads(session_file.read_text("utf-8"))
        del data["start_architecture"]
        session_file.write_text(json.dumps(data), encoding="utf-8")
        self.write("app/modules/citas/api/nuevo.py", VIOLATING)
        result = self.check("--new-only", "--json")
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertEqual(json.loads(result.stdout)["counts"], {"new": 0, "previous": 3})

    def test_a_closed_run_leaves_the_project_without_a_photo(self):
        self.start()
        self.ok("abort", "--reason", "test")
        self.write("app/modules/citas/api/nuevo.py", VIOLATING)
        result = self.check("--new-only", "--json")
        self.assertEqual(json.loads(result.stdout)["baseline"], None)

    def test_plain_check_without_the_flag_is_unchanged(self):
        result = self.check()
        self.assertEqual(result.returncode, 1)
        self.assertNotIn("previa", result.stdout)


class RefactorTests(Project):
    def test_a_refactor_that_touches_a_file_with_previous_violations_must_fix_it(self):
        self.start("refactor", REFACTOR_SPEC)
        self.write("app/modules/citas/api/router.py", VIOLATING + "# touched\n")
        result = self.check("--new-only", "--json")
        self.assertEqual(result.returncode, 1, result.stdout)
        data = json.loads(result.stdout)
        self.assertEqual(data["counts"], {"new": 1, "previous": 1})
        status = {v["file"].rsplit("/", 1)[1]: v["status"] for v in data["violations"]}
        self.assertEqual(status, {"router.py": "new", "dependencias.py": "previous"})

    def test_a_refactor_that_fixes_the_file_it_touched_passes(self):
        self.start("refactor", REFACTOR_SPEC)
        self.write("app/modules/citas/api/router.py", "x = 1\n")
        result = self.check("--new-only", "--json")
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertEqual(json.loads(result.stdout)["counts"], {"new": 0, "previous": 1})

    def test_a_feature_run_may_touch_a_file_with_previous_violations(self):
        self.start("feature")
        self.write("app/modules/citas/api/router.py", VIOLATING + "# touched\n")
        self.assertEqual(self.check("--new-only").returncode, 0)


class FinishTests(Project):
    def finish_ready(self):
        """Drive the run like an agent until `rapid finish` is the next step; returns the gate to approve."""
        for _ in range(30):
            action = json.loads(self.ok("next", "--json").stdout)["action"]
            if action["kind"] == "await_human_approval":
                return action["gate_ids"][0]
            if action["kind"] == "implement_task":
                self.write("app/modules/citas/domain/cita.py", "class Cita:\n    pass\n")
            for key in ("command", "after"):
                if action.get(key):
                    self.ok(*action[key][1:])
        self.fail("the run never reached a human gate")

    def approve(self, gate):
        code = (
            "import sys, unittest.mock as mock, rapid_os.cli.main as m; "
            f"sys.argv = ['rapid', 'approve', '{gate}']; "
            "mock.patch('sys.stdin.isatty', return_value=True).start(); "
            "mock.patch('rapid_os.orchestration.lifecycle.stdin_is_windows_nul', return_value=False).start(); "
            "mock.patch('rapid_os.orchestration.lifecycle.read_ancestry', "
            "return_value=__import__('rapid_os.core.ancestry', fromlist=['x']).AncestryResult(())).start(); "
            f"mock.patch('builtins.input', return_value='aprobar {gate}').start(); sys.exit(m.main())"
        )
        result = subprocess.run([sys.executable, "-c", code], cwd=self.root, capture_output=True, text=True, env=self.env)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_finish_passes_with_previous_violations_and_stops_at_a_new_one(self):
        self.start()
        self.approve(self.finish_ready())
        # The previous violations are still there and do not stop the run...
        self.write("app/modules/citas/api/nuevo.py", VIOLATING)
        refused = self.rapid("finish", "--json")
        self.assertEqual(refused.returncode, 1, refused.stdout)
        self.assertIn("RAPID1422", refused.stderr)
        self.assertIn("api/nuevo.py:1", refused.stderr)
        self.assertNotIn("api/router.py", refused.stderr)  # ...only the new one is reported
        # ...and without the new one, finish passes.
        (self.root / "app/modules/citas/api/nuevo.py").unlink()
        done = self.rapid("finish", "--json")
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertEqual(json.loads(done.stdout)["verdict"], "pass")


class ClassifyTests(unittest.TestCase):
    CONFIG = ArchitectureConfig.from_dict(default_config("python-api"))

    def violations(self):
        return list(check_architecture(self.CONFIG, {
            "app/modules/a/api/r.py": VIOLATING.replace("citas", "a"),
            "app/modules/a/api/s.py": VIOLATING.replace("citas", "a"),
        }).violations)

    def test_no_photo_means_nothing_is_new(self):
        new, previous = classify(self.violations(), None)
        self.assertEqual((new, len(previous)), ([], 2))

    def test_a_photo_with_the_key_makes_it_previous_and_touched_files_count(self):
        found = self.violations()
        keys = frozenset(violation_key(v) for v in found)
        baseline = RunBaseline("run", "refactor", keys, frozenset({"app/modules/a/api/r.py"}))
        new, previous = classify(found, baseline)
        self.assertEqual([v.file for v in new], ["app/modules/a/api/r.py"])
        self.assertEqual([v.file for v in previous], ["app/modules/a/api/s.py"])

    def test_the_debt_line_names_the_count_and_refactor(self):
        found = self.violations()
        self.assertIn("2 violaciones previas; no bloquean este run", previous_debt_line(found, None))
        self.assertIn("1 violación previa;", previous_debt_line(found[:1], None))
        refactor = RunBaseline("run", "refactor", frozenset())
        self.assertIn("no deja un archivo tocado violando", previous_debt_line(found, refactor))


class CompositionMessageTests(unittest.TestCase):
    def test_every_stack_says_where_the_composition_goes_when_the_entry_layer_reaches_infrastructure(self):
        cases = {
            "python-fastapi": ("app/modules/citas/api/router.py", "from app.modules.citas.infrastructure.repo import R\n",
                               "app/main.py o en el public.py del módulo"),
        }
        for stack, (path, source, expected) in cases.items():
            with self.subTest(stack=stack):
                config = ArchitectureConfig.from_dict(default_config(stack))
                (violation,) = check_architecture(config, {path: source}).violations
                self.assertIn("la capa 'api' no puede importar la capa 'infrastructure'", violation.message)
                self.assertIn(f"Dónde va la composición: ensambla las dependencias en {expected}", violation.message)

    def test_every_backend_and_frontend_stack_with_a_rule_carries_a_composition_note(self):
        from rapid_os.domain.architecture_profiles import BACKEND_RULES, FRONTEND_RULES

        for stack, spec in {**BACKEND_RULES, **{f"fe:{k}": v for k, v in FRONTEND_RULES.items()}}.items():
            with self.subTest(stack=stack):
                self.assertTrue(spec.composition, stack)
                self.assertEqual(spec.to_dict()["composition"], spec.composition)

    def test_a_frontend_ui_importing_data_access_is_told_to_go_through_state(self):
        config = ArchitectureConfig.from_dict(default_config("react-vite"))
        (violation,) = check_architecture(config, {
            "src/features/citas/ui/Lista.tsx": "import { api } from '../data-access/api';\n",
        }).violations
        self.assertIn("conecta el acceso a datos desde state/", violation.message)

    def test_a_rule_written_before_the_note_still_loads(self):
        data = default_config("python-fastapi")
        del data["composition"]
        config = ArchitectureConfig.from_dict(data)
        (violation,) = check_architecture(config, {
            "app/modules/citas/api/router.py": "from app.modules.citas.infrastructure.repo import R\n",
        }).violations
        self.assertNotIn("composición", violation.message)


if __name__ == "__main__":
    unittest.main()
