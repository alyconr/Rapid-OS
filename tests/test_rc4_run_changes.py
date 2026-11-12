"""rc.4 · H-70: a run can end in PASS without the change it declares.

In phase 10 of the rc.3 e2e, with the refactored file back to its previous version, `rapid finish` gave PASS and
`git diff <baseline> -- backend` was empty. A feature, bugfix, refactor or hardening run now ends in PASS only when
the tree outside `.rapid-os/` differs from where the run started (start_head plus start_untracked): RAPID1441.
A change that touches no affected_path of the spec is a warning (RAPID1442) in `rapid next` and `rapid finish`.
"""

from __future__ import annotations

import json
import unittest
from types import SimpleNamespace

from rapid_os.adapters.eval_registry import EvalRegistry
from rapid_os.orchestration.lifecycle import _in_affected_path, _run_diff
from tests.test_intent_loop import LabScenarioBase

SPEC = {
    "title": "Booking availability",
    "business_objective": "Reject double bookings",
    "problem_statement": "Bookings can overlap",
    "acceptance_criteria": ["overlapping bookings are rejected"],
    "tasks": ["T001: Implement availability control"],
}
SOLUTION = ("booking.py", "tests/test_booking.py")


class RunWithoutItsChangeTests(LabScenarioBase):
    LAB = "feature"

    def _implement(self, action):
        self._copy_solution(*SOLUTION)

    def _to_approval(self, spec=SPEC, implement=None):
        run_id = self._start("feature", spec)["run_id"]
        action, _ = self._drive(implement or self._implement)
        self.assertEqual(action["kind"], "await_human_approval", action)
        payload = json.loads(self._rapid("next", "--json").stdout)
        return run_id, {"notes": payload.get("notes", []), "action": payload["action"]}

    def _approve_and_finish(self):
        approved = self._approve("gate.final-verification")
        self.assertEqual(approved.returncode, 0, approved.stdout + approved.stderr)
        return self._rapid("finish", "--json")

    def _reports(self, run_id):
        return EvalRegistry(self.project, self.project / ".rapid-os").list_reports(run_id)

    def test_a_run_that_changes_nothing_gets_no_pass(self):
        # The change is already in the starting commit: the run's tree is the one it started from, as in
        # phase 10 with the refactored file back to its previous version.
        self._copy_solution(*SOLUTION)
        self._git("add", ".")
        self._git("commit", "-qm", "solution already there")
        run_id, action = self._to_approval(implement=lambda _action: None)
        self.assertTrue(any(n.startswith("RAPID1441") for n in action.get("notes", [])), action)
        text = self._rapid("next")
        self.assertIn("Nota: RAPID1441", text.stdout)

        finish = self._approve_and_finish()
        self.assertEqual(finish.returncode, 1)
        self.assertIn("RAPID1441", finish.stderr)
        self.assertIn("no cambió nada fuera de .rapid-os/", finish.stderr)
        self.assertNotIn('"verdict": "pass"', finish.stdout)
        self.assertEqual(list(self._reports(run_id)), [])

        # Making the change lets it end: check again, approve again the new tree, finish.
        (self.project / "booking.py").write_text(
            (self.project / "booking.py").read_text(encoding="utf-8") + "\n# availability control\n",
            encoding="utf-8",
        )
        self.assertEqual(self._rapid("check", "--gate", "gate.tests").returncode, 0)
        self.assertEqual(self._approve("gate.final-verification").returncode, 0)
        done = self._rapid("finish", "--json")
        self.assertEqual(done.returncode, 0, done.stderr + done.stdout)
        self.assertEqual(json.loads(done.stdout)["verdict"], "pass")

    def test_a_change_outside_the_affected_paths_is_a_warning(self):
        spec = dict(SPEC, affected_paths=["src/payments"])
        run_id, action = self._to_approval(spec)
        notes = action.get("notes", [])
        self.assertTrue(any(n.startswith("RAPID1442") and "src/payments" in n for n in notes), action)
        self.assertFalse(any(n.startswith("RAPID1441") for n in notes))

        finish = self._approve_and_finish()
        self.assertEqual(finish.returncode, 0, finish.stderr + finish.stdout)
        self.assertIn("WARNING RAPID1442", finish.stderr)
        self.assertEqual(json.loads(finish.stdout)["verdict"], "pass")

    def test_the_normal_case_is_as_before(self):
        spec = dict(SPEC, affected_paths=["booking.py"])
        run_id, action = self._to_approval(spec)
        self.assertFalse(any(n.startswith(("RAPID1441", "RAPID1442")) for n in action.get("notes", [])), action)
        finish = self._approve_and_finish()
        self.assertEqual(finish.returncode, 0, finish.stderr + finish.stdout)
        self.assertNotIn("RAPID1442", finish.stderr)
        self.assertEqual(json.loads(finish.stdout)["verdict"], "pass")


class RunDiffScopeTests(unittest.TestCase):
    def test_research_and_runs_without_a_git_start_are_not_judged(self):
        research = SimpleNamespace(mode="research", start_head="abc", start_untracked=(), workspace_path=None)
        no_git = SimpleNamespace(mode="feature", start_head=None, start_untracked=None, workspace_path=None)
        self.assertIsNone(_run_diff(".", research))
        self.assertIsNone(_run_diff(".", no_git))

    def test_affected_paths_match_files_directories_and_globs(self):
        self.assertTrue(_in_affected_path("backend/app/main.py", "backend"))
        self.assertTrue(_in_affected_path("backend/app/main.py", "./backend/"))
        self.assertTrue(_in_affected_path("backend/app/main.py", "backend\\app\\main.py"))
        self.assertTrue(_in_affected_path("src/a.ts", "src/*.ts"))
        self.assertFalse(_in_affected_path("frontend/a.ts", "backend"))
        self.assertFalse(_in_affected_path("backend2/a.py", "backend"))


if __name__ == "__main__":
    unittest.main()
