"""H-67: a bugfix names its root cause, reproduces it on the baseline and fixes it there.

In talleres-rc2 the agent tested BookingService with a fake catalog (the defective reader never ran), added a
barrier there and the test passed: symptom covered, cause intact. A bugfix spec now declares `root_cause`, closing
the fix task requires the reproduction test to fail on the run's baseline tree, and the hand-over separates the
change at the cause from additional defenses, warning when the fix does not touch the declared cause."""

from __future__ import annotations

import json
from pathlib import Path
import subprocess
import unittest

from rapid_os.domain.evidence import EvidenceKind
from rapid_os.domain.root_cause import RootCause, root_cause_error
from rapid_os.domain.execution import TaskContract
from rapid_os.orchestration.reproduction import fix_task_id, is_test_path, reproduction_task_id
from tests.test_intent_loop import EXAMPLES, LabScenarioBase

CAUSE = {
    "file": "pricer.py",
    "symbol": "OrderPricer.calculate_total",
    "how_found": "lectura del código y traza del test",
    "explanation": "discount_amount multiplica por el porcentaje sin dividir entre 100",
}
TASKS = [
    "T001: Localizar y confirmar la causa raíz (root_cause) antes de escribir el test",
    "T002: Reproducir con un test en rojo que ejecute el código de root_cause",
    "T003: Corregir la causa raíz",
    "T004: Verificar la regresión con la suite completa",
]
SPEC = {
    "title": "Discount is applied as a multiplier",
    "business_objective": "Charge the right discounted total",
    "problem_statement": "A 10% discount on 100 yields -900",
    "acceptance_criteria": ["10% of 100 is 90"],
    "root_cause": CAUSE,
    "tasks": TASKS,
}
REPRO_TEST = (
    "    def test_regression_expected_discount(self):\n"
    "        items = [{\"price\": 100.0, \"qty\": 1}]\n"
    "        self.assertEqual(OrderPricer.calculate_total(items, 10.0), 90.0)\n\n"
)


class RootCauseUnitTests(unittest.TestCase):
    def test_missing_root_cause_names_the_field_and_its_shape(self):
        message = root_cause_error(None, Path("."))
        self.assertTrue(message.startswith("RAPID1438"))
        self.assertIn("root_cause", message)
        self.assertIn("how_found", message)

    def test_each_missing_part_is_named(self):
        message = root_cause_error({"file": "x.py"}, Path("."))
        self.assertIn("how_found", message)
        self.assertIn("explanation", message)
        self.assertIn("symbol o line", message)

    def test_a_path_outside_the_project_is_refused(self):
        for raw in ("../x.py", "/etc/passwd", "C:/x.py"):
            with self.subTest(raw=raw), self.assertRaises(ValueError):
                RootCause(file=raw, symbol="f", how_found="git blame", explanation="e")

    def test_test_paths(self):
        for path in ("tests/test_x.py", "src/x.test.ts", "pkg/x_test.go", "app/__tests__/a.js", "conftest.py",
                     "src/test/java/FooTest.java", "spec/models/user_spec.rb"):
            self.assertTrue(is_test_path(path), path)
        for path in ("pricer.py", "src/contest.py", "catalog/infrastructure/sqlalchemy_catalog_reader.py", "latest.py"):
            self.assertFalse(is_test_path(path), path)

    def test_task_roles(self):
        new = [TaskContract(id=f"T00{i}", description=d) for i, d in enumerate(TASKS, 1)]
        self.assertEqual((reproduction_task_id(new), fix_task_id(new)), ("T002", "T003"))
        old = [TaskContract(id="T001", description="Reproducir con un test en rojo"),
               TaskContract(id="T002", description="Corregir la causa raíz")]
        self.assertEqual((reproduction_task_id(old), fix_task_id(old)), ("T001", "T002"))


class BugfixShortcutNamesTheCauseTests(unittest.TestCase):
    def test_the_shortcut_asks_for_the_cause_first_and_names_it_when_handing_over(self):
        text = (Path(__file__).resolve().parents[1] / "templates" / "shortcuts" / "rapid-bugfix.md").read_text("utf-8")
        self.assertIn("localiza la causa raíz sin editar archivos", text)
        self.assertIn("`RAPID1438`", text)
        self.assertIn("El test de reproducción ejecuta el código de `root_cause`", text)
        self.assertIn("no uno con dobles del componente defectuoso", text)
        self.assertIn("Al entregar, nombra la causa raíz (`action.bugfix.root_cause`", text)
        self.assertIn("las defensas adicionales", text)
        self.assertIn("no toca la causa declarada, no entregues", text)


class BugfixRootCauseScenarioTests(LabScenarioBase):
    LAB = "bugfix"

    def prepare_starter(self):
        # A green baseline before the reproduction test exists (as in BugfixLabScenarioTests), plus a module
        # where a different cause can be declared.
        test_file = self.project / "tests" / "test_pricer.py"
        text = test_file.read_text(encoding="utf-8")
        start = text.index("    def test_regression_expected_discount")
        end = text.index("if __name__")
        test_file.write_text(text[:start] + "\n" + text[end:], encoding="utf-8")
        (self.project / "discounts.py").write_text("def normalize(percent):\n    return percent\n", encoding="utf-8")

    # -- helpers ---------------------------------------------------------------------------------------------
    def _no_run(self):
        runs = self.project / ".rapid-os" / "runs"
        self.assertFalse(runs.exists() and any(runs.iterdir()))

    def _work(self):
        """Where the run's files live: its worktree when it has one."""
        session = self._session() if (self.project / ".rapid-os" / "session.json").exists() else {}
        return Path(session.get("workspace_path") or self.project)

    def _session(self):
        return json.loads((self.project / ".rapid-os" / "session.json").read_text(encoding="utf-8"))

    def _add_test(self, body):
        test_file = self._work() / "tests" / "test_pricer.py"
        text = test_file.read_text(encoding="utf-8")
        test_file.write_text(text.replace("if __name__", body + "if __name__", 1), encoding="utf-8")

    def _to_fix_task(self, spec, write_reproduction, *flags):
        """Start, close T001 (locate), record T002's expected failure, start T003 (fix)."""
        run_id = self._start("bugfix", spec, *flags)["run_id"]
        action = self._next()
        self.assertEqual((action["task_id"], action["command"]), ("T001", ["rapid", "task", "start", "T001"]))
        self.assertEqual(self._run_command(action["command"]).returncode, 0)
        closed = self._run_command(self._next()["after"])
        self.assertEqual(closed.returncode, 0, closed.stderr)

        action = self._next()
        self.assertEqual(action["task_id"], "T002")
        self.assertEqual(self._run_command(action["command"]).returncode, 0)
        action = self._next()
        self.assertEqual(action["command"][:6], ["rapid", "check", "--expect", "fail", "--task", "T002"])
        write_reproduction()
        recorded = self._run_command(action["command"])
        self.assertEqual(recorded.returncode, 0, recorded.stderr + recorded.stdout)
        closed = self._run_command(self._next()["after"])
        self.assertEqual(closed.returncode, 0, closed.stderr)

        action = self._next()
        self.assertEqual(action["task_id"], "T003")
        self.assertEqual(self._run_command(action["command"]).returncode, 0)
        return run_id

    def _fix_pricer(self):
        self._copy_solution("pricer.py", dest_root=self._work())
        # The characterization test documents the defect (-900) and goes away with it.
        test_path = self._work() / "tests" / "test_pricer.py"
        source = test_path.read_text(encoding="utf-8")
        begin = source.index("    def test_defect_characterization")
        following = [i for i in (source.find("    def test_", begin + 10), source.find("if __name__", begin)) if i != -1]
        test_path.write_text(source[:begin] + source[min(following):], encoding="utf-8")

    def _holds(self, run_id):
        return [e for e in self._registry().list(run_id) if e.payload.get("label") == "reproduction_holds"]

    def _worktrees(self):
        listed = subprocess.run(["git", "worktree", "list", "--porcelain"], cwd=self.project, capture_output=True,
                                text=True, check=True).stdout
        return [line for line in listed.splitlines() if line.startswith("worktree ")]

    # -- the spec ------------------------------------------------------------------------------------------------
    def test_a_bugfix_spec_without_root_cause_is_refused(self):
        spec = {key: value for key, value in SPEC.items() if key != "root_cause"}
        res = self._rapid("start", "bugfix", "--spec-file", "-", "--json", input_str=json.dumps(spec))
        self.assertEqual(res.returncode, 1)
        self.assertIn("RAPID1438", res.stderr)
        self.assertIn("root_cause", res.stderr)
        self._no_run()
        self.assertFalse((self.project / ".rapid-os" / "specs").exists() and
                         any((self.project / ".rapid-os" / "specs").iterdir()))

    def test_a_root_cause_whose_file_does_not_exist_is_refused(self):
        spec = {**SPEC, "root_cause": {**CAUSE, "file": "catalog/reader.py"}}
        res = self._rapid("start", "bugfix", "--spec-file", "-", "--json", input_str=json.dumps(spec))
        self.assertEqual(res.returncode, 1)
        self.assertIn("RAPID1438", res.stderr)
        self.assertIn("catalog/reader.py", res.stderr)
        self.assertIn("no existe", res.stderr)
        self._no_run()

    def test_the_template_asks_for_the_cause_first(self):
        template = json.loads(self._rapid("start", "bugfix", "--json").stdout)["action"]["spec_template"]
        self.assertEqual(set(template["root_cause"]), {"file", "symbol", "how_found", "explanation"})
        self.assertTrue(template["implementation_tasks"][0].startswith("T001: Localizar"))
        self.assertIn("Reproducir", template["implementation_tasks"][1])

    # -- closing the fix task -----------------------------------------------------------------------------------
    def test_a_reproduction_that_passes_on_the_baseline_does_not_close_the_fix(self):
        pricer = self.project / "pricer.py"
        original = pricer.read_text(encoding="utf-8")

        def write_reproduction():
            # The new test holds on the baseline; it fails now only because the run broke the code itself.
            self._add_test("    def test_without_discount(self):\n"
                           "        self.assertEqual(OrderPricer.calculate_total([{\"price\": 100.0}], 0), 100.0)\n\n")
            pricer.write_text(original.replace("return round(total, 2)", "return round(total, 2) + 1"), encoding="utf-8")

        run_id = self._to_fix_task(SPEC, write_reproduction)
        pricer.write_text(original, encoding="utf-8")  # the "fix"
        closed = self._rapid("task", "done", "T003")
        self.assertEqual(closed.returncode, 1, closed.stdout)
        self.assertIn("RAPID1439", closed.stderr)
        self.assertIn("pasa en el árbol del baseline", closed.stderr)
        self.assertIn("tests/test_pricer.py", closed.stderr)
        status = {t["id"]: t["status"] for t in json.loads(self._rapid("status", "--json").stdout)["run"]["tasks"]}
        self.assertEqual(status["T003"], "in_progress")
        self.assertEqual(self._holds(run_id), [])
        self.assertEqual(len(self._worktrees()), 1)  # the temporary worktree was removed
        # --no-check does not skip it.
        self.assertEqual(self._rapid("task", "done", "T003", "--no-check").returncode, 1)

    def test_the_good_case_records_reproduction_holds_and_hands_over_the_cause(self):
        run_id = self._to_fix_task(SPEC, lambda: self._add_test(REPRO_TEST))
        self._fix_pricer()
        (self.project / "validation.py").write_text("def positive(value):\n    return value >= 0\n", encoding="utf-8")
        closed = self._rapid("task", "done", "T003")
        self.assertEqual(closed.returncode, 0, closed.stderr + closed.stdout)
        self.assertIn("falla en el árbol del baseline", closed.stdout)
        holds = self._holds(run_id)
        self.assertEqual(len(holds), 1)
        self.assertEqual(holds[0].task_ids, ("T003",))
        self.assertEqual(holds[0].kind, EvidenceKind.COMMAND_RESULT)
        self.assertEqual(len(self._worktrees()), 1)

        action, _ = self._drive(lambda action: None)
        self.assertEqual(action["kind"], "await_human_approval", action)
        bugfix = json.loads(self._rapid("next", "--json").stdout)["action"]["bugfix"]
        self.assertEqual(bugfix["root_cause"]["file"], "pricer.py")
        self.assertEqual(bugfix["root_cause"]["location"], "pricer.py · OrderPricer.calculate_total")
        self.assertTrue(bugfix["touches_root_cause"])
        self.assertIn("+        discount_amount = subtotal * (discount_percent / 100.0)", bugfix["fix_at_cause"])
        self.assertEqual([d["file"] for d in bugfix["additional_defenses"]], ["validation.py"])
        self.assertEqual(bugfix["reproduction_holds"], holds[0].id)
        self.assertNotIn("warning", bugfix)

        text = self._rapid("next").stdout
        self.assertIn("Causa raíz: pricer.py · OrderPricer.calculate_total", text)
        self.assertIn("Corrección en la causa (pricer.py):", text)
        self.assertIn("Defensas adicionales (fuera de la causa):\n  - validation.py (+", text)
        self.assertIn(f"evidencia: {holds[0].id}", text)
        self.assertNotIn("AVISO", text)

        self.assertEqual(self._approve("gate.final-verification").returncode, 0)
        self.assertEqual(self._finish()["verdict"], "pass")

    def test_a_fix_that_does_not_touch_the_declared_cause_is_flagged(self):
        spec = {**SPEC, "root_cause": {**CAUSE, "file": "discounts.py", "symbol": "normalize"}}
        self._to_fix_task(spec, lambda: self._add_test(REPRO_TEST))
        self._fix_pricer()
        self.assertEqual(self._rapid("task", "done", "T003").returncode, 0)
        action, _ = self._drive(lambda action: None)
        self.assertEqual(action["kind"], "await_human_approval", action)
        bugfix = json.loads(self._rapid("next", "--json").stdout)["action"]["bugfix"]
        self.assertFalse(bugfix["touches_root_cause"])
        self.assertEqual(bugfix["fix_at_cause"], [])
        self.assertEqual([d["file"] for d in bugfix["additional_defenses"]], ["pricer.py"])
        self.assertIn("el arreglo no toca la causa declarada", bugfix["warning"])
        self.assertIn("AVISO: el arreglo no toca la causa declarada (discounts.py · normalize).", self._rapid("next").stdout)


if __name__ == "__main__":
    unittest.main()
