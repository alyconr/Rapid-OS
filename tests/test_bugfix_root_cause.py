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
        self.assertIn("--accept-reproduction --reason", text)
        self.assertIn("nunca lo ejecutes tú", text)


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
        self.assertIn("no hacen fallar ningún test más: 0 fallidos con ellos y 0 sin ellos", closed.stderr)
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

    # -- inconclusive: the person's way out ---------------------------------------------------------------------
    def _rapid_as(self, args, *answers, tty=True, agent=False):
        """`rapid <args>` with the given answers; a person's terminal unless `tty` is False or `agent` is True."""
        import sys

        ancestors = "(Ancestor(4242, 'claude.exe', ('claude.exe',)),)" if agent else "()"
        code = (
            "import sys, unittest.mock as mock, rapid_os.cli.main as m; "
            "from rapid_os.core.ancestry import Ancestor, AncestryResult; "
            f"sys.argv = ['rapid'] + {list(args)!r}; "
            f"mock.patch('sys.stdin.isatty', return_value={tty}).start(); "
            "mock.patch('rapid_os.orchestration.lifecycle.stdin_is_windows_nul', return_value=False).start(); "
            f"mock.patch('rapid_os.orchestration.lifecycle.read_ancestry', return_value=AncestryResult({ancestors})).start(); "
            f"mock.patch('builtins.input', side_effect={list(answers)!r}).start(); "
            "sys.exit(m.main())"
        )
        return subprocess.run([sys.executable, "-c", code], cwd=str(self.project), capture_output=True, text=True,
                              encoding="utf-8", env=self._env())

    def test_an_inconclusive_check_is_accepted_only_by_the_person(self):
        # On the baseline the new test kills the runner before its summary: nothing to count.
        crash = (
            "    def test_regression_expected_discount(self):\n"
            "        total = OrderPricer.calculate_total([{\"price\": 100.0, \"qty\": 1}], 10.0)\n"
            "        if total < 0:\n"
            "            import os\n"
            "            os._exit(3)\n"
            "        self.assertEqual(total, 90.0)\n\n"
        )
        run_id = self._to_fix_task(SPEC, lambda: self._add_test(crash))
        self._fix_pricer()
        closed = self._rapid("task", "done", "T003")
        self.assertEqual(closed.returncode, 1, closed.stdout)
        self.assertIn("RAPID1439", closed.stderr)
        self.assertIn("sin un resumen de tests que contar", closed.stderr)
        self.assertIn('rapid task done T003 --accept-reproduction --reason "<motivo>"', closed.stderr)

        accept = ["task", "done", "T003", "--accept-reproduction", "--reason", "el runner muere sin el arreglo"]
        from_agent = self._rapid_as(accept, "s", agent=True)
        self.assertEqual(from_agent.returncode, 1)
        self.assertIn("RAPID1310", from_agent.stderr)
        self.assertIn("claude.exe", from_agent.stderr)
        without_tty = self._rapid_as(accept, "s", tty=False)
        self.assertEqual(without_tty.returncode, 1)
        self.assertIn("RAPID1310", without_tty.stderr)
        self.assertIn("TTY", without_tty.stderr)
        declined = self._rapid_as(accept, "")
        self.assertEqual(declined.returncode, 1)
        self.assertIn("Sin cambios: T003 sigue en curso.", declined.stderr)
        accepted_reviews = lambda: [e for e in self._registry().list(run_id)
                                    if e.payload.get("accepts") == "reproduction_inconclusive"]
        self.assertEqual(accepted_reviews(), [])

        done = self._rapid_as(accept, "s")
        self.assertEqual(done.returncode, 0, done.stderr + done.stdout)
        reviews = accepted_reviews()
        self.assertEqual(len(reviews), 1)
        self.assertEqual(reviews[0].task_ids, ("T003",))
        self.assertEqual(reviews[0].payload["reason"], "el runner muere sin el arreglo")
        self.assertEqual(reviews[0].payload["via"], "rapid:task")
        self.assertEqual(self._holds(run_id), [])

        action, _ = self._drive(lambda action: None)
        self.assertEqual(action["kind"], "await_human_approval", action)
        bugfix = json.loads(self._rapid("next", "--json").stdout)["action"]["bugfix"]
        self.assertEqual(bugfix["reproduction_accepted"]["evidence_id"], reviews[0].id)
        self.assertIn(f"Reproducción: no comprobada en el baseline; la aceptó Lab Dev: «el runner muere sin el arreglo» "
                      f"(evidencia: {reviews[0].id})", self._rapid("next").stdout)
        self.assertEqual(self._approve("gate.final-verification").returncode, 0)
        self.assertEqual(self._finish()["verdict"], "pass")
        shown = self._rapid("eval", "show", "--run", run_id)
        self.assertIn("Aceptado por Lab Dev: reproducción sin comprobar en el baseline (T003), motivo "
                      f"«el runner muere sin el arreglo» ({reviews[0].id})", shown.stdout)


# --- H-67 corrections: the count decides, never the exit code ---------------------------------------------------

SECOND_STEP_FAILS = (
    "import subprocess, sys\n"
    "first = subprocess.run([sys.executable, '-m', 'unittest', 'discover', '-s', 'tests', '-t', '.'])\n"
    "print('      Tests  2 passed (2)')  # another part of the suite (a frontend without its dependencies)\n"
    "sys.exit(1)\n"
)


class ReproductionCountTests(unittest.TestCase):
    """`check_reproduction` on a minimal repository: the run's tests must make more tests fail on the baseline."""

    def setUp(self):
        import tempfile

        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name) / "repo"
        (self.root / "tests").mkdir(parents=True)
        (self.root / "tests" / "__init__.py").write_text("", encoding="utf-8")
        (self.root / "calc.py").write_text("def double(x):\n    return x * 3\n", encoding="utf-8")
        (self.root / "tests" / "test_ok.py").write_text(
            "import unittest\n\nclass Ok(unittest.TestCase):\n    def test_ok(self):\n        self.assertTrue(True)\n",
            encoding="utf-8",
        )
        self.git("init", "-q")
        self.git("config", "user.name", "Lab Dev")
        self.git("config", "user.email", "lab@example.com")
        self.git("add", ".")
        self.git("commit", "-qm", "baseline")
        self.head = self.git("rev-parse", "HEAD").strip()

    def tearDown(self):
        self._tmp.cleanup()

    def git(self, *args):
        return subprocess.run(["git", *args], cwd=self.root, check=True, capture_output=True, text=True).stdout

    def write_test(self, name, body):
        (self.root / "tests" / name).write_text(
            "import unittest\nfrom calc import double\n\nclass Case(unittest.TestCase):\n" + body, encoding="utf-8"
        )

    def check(self, command=None, baseline_failed=None):
        import sys

        from rapid_os.orchestration.reproduction import check_reproduction
        from rapid_os.orchestration.session import Session

        session = Session(active_run_id="r", mode="bugfix", harness="codex", start_head=self.head, start_untracked=())
        command = command or [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-t", "."]
        return check_reproduction(self.root / ".rapid-os", "r", session, command, cwd=self.root,
                                  baseline_failed=baseline_failed)

    def test_a_new_test_that_fails_on_the_baseline_holds_with_its_count(self):
        self.write_test("test_double.py", "    def test_double(self):\n        self.assertEqual(double(2), 4)\n")
        outcome = self.check()
        self.assertEqual(outcome.status, "holds", outcome.message)
        self.assertEqual((outcome.counts["failed"], outcome.baseline_failed), (1, 0))
        self.assertIn("1 fallidos con los tests del run", outcome.message)
        self.assertIn("frente a 0 sin ellos", outcome.message)
        self.assertEqual(outcome.failed_tests, ["tests/test_double"])
        listed = self.git("worktree", "list", "--porcelain")
        self.assertEqual(listed.count("worktree "), 1)  # the temporary worktree is gone

    def test_a_passing_reproduction_with_another_part_of_the_suite_failing_is_not_reproduced(self):
        # The case reproduced in Linux: exit 1 with a summary used to be `holds` with "0 fallidos".
        import sys

        (self.root / "run_all.py").write_text(SECOND_STEP_FAILS, encoding="utf-8")
        self.git("add", "run_all.py")
        self.git("commit", "-qm", "combined command")
        self.head = self.git("rev-parse", "HEAD").strip()
        self.write_test("test_double.py", "    def test_double(self):\n        self.assertEqual(double(1), 3)\n")
        outcome = self.check([sys.executable, "run_all.py"])
        self.assertEqual(outcome.status, "not_reproduced", outcome.message)
        self.assertEqual(outcome.exit_code, 1)
        self.assertIn("no hacen fallar ningún test más: 0 fallidos con ellos y 0 sin ellos", outcome.message)

    def test_a_test_that_already_failed_on_the_baseline_does_not_make_a_passing_test_a_reproduction(self):
        self.write_test("test_old_red.py", "    def test_red(self):\n        self.assertEqual(1, 2)\n")
        self.git("add", ".")
        self.git("commit", "-qm", "a test that already fails")
        self.head = self.git("rev-parse", "HEAD").strip()
        self.write_test("test_double.py", "    def test_double(self):\n        self.assertEqual(double(1), 3)\n")
        outcome = self.check()  # no counted baseline evidence: the baseline tree is run without the run's tests
        self.assertEqual(outcome.status, "not_reproduced", outcome.message)
        self.assertEqual((outcome.counts["failed"], outcome.baseline_failed), (1, 1))
        # With the run's own baseline count it is the same answer.
        self.assertEqual(self.check(baseline_failed=1).status, "not_reproduced")

    def test_when_only_other_tests_fail_it_is_not_the_reproduction(self):
        # The new test passes, but importing it breaks another test: more failures, none of them the run's.
        (self.root / "tests" / "test_ok.py").write_text(
            "import os, unittest\n\nclass Ok(unittest.TestCase):\n    def test_ok(self):\n"
            "        self.assertNotIn('BROKEN', os.environ)\n", encoding="utf-8",
        )
        self.git("commit", "-qam", "env-sensitive test")
        self.head = self.git("rev-parse", "HEAD").strip()
        (self.root / "tests" / "test_new.py").write_text(
            "import os, unittest\nos.environ['BROKEN'] = '1'\n\nclass New(unittest.TestCase):\n"
            "    def test_new(self):\n        self.assertTrue(True)\n", encoding="utf-8",
        )
        outcome = self.check(baseline_failed=0)
        self.assertEqual(outcome.status, "not_reproduced", outcome.message)
        self.assertIn("fallan otros tests en el baseline, no el de reproducción: tests/test_ok", outcome.message)

    def test_an_output_without_a_summary_is_inconclusive(self):
        import sys

        self.write_test("test_double.py", "    def test_double(self):\n        self.assertEqual(double(2), 4)\n")
        outcome = self.check([sys.executable, "-c", "import sys; sys.exit(1)"], baseline_failed=0)
        self.assertEqual(outcome.status, "inconclusive", outcome.message)


class SharedSummaryParserTests(unittest.TestCase):
    def test_pytest_and_vitest_summaries_are_added_up(self):
        from rapid_os.orchestration.check import parse_failed_test_files, parse_test_summary

        output = (
            "FAILED backend/tests/test_reader.py::test_bookable - assert\n"
            "==== 1 failed, 4 passed in 0.31s ====\n"
            " FAIL  src/booking.test.ts > booking > rejects zero\n"
            "      Tests  2 failed | 7 passed (9)\n"
        )
        self.assertEqual(parse_test_summary(output), {"passed": 11, "failed": 3, "skipped": 0})
        self.assertEqual(parse_failed_test_files(output), ["backend/tests/test_reader.py", "src/booking.test.ts"])


if __name__ == "__main__":
    unittest.main()
