"""rc.4 · H-70: a run can end in PASS without the change it declares.

In phase 10 of the rc.3 e2e, with the refactored file back to its previous version, `rapid finish` gave PASS and
`git diff <baseline> -- backend` was empty. A feature, bugfix, refactor or hardening run whose tree outside `.rapid-os/` is back
to where the run started (start_head plus start_untracked) no longer ends in PASS on the file_change evidence an
earlier `rapid finish` left behind: RAPID1441. A run that never changed anything is UNVERIFIED, as before.
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

    def test_a_change_undone_after_an_earlier_finish_gets_no_pass(self):
        # Phase 10 of the rc.3 e2e: a `rapid finish` with the change recorded file_change and was refused; the
        # refactored file went back to its previous version and the next `rapid finish` gave PASS on that evidence.
        originals = {
            rel: (self.project / rel).read_bytes() if (self.project / rel).exists() else None for rel in SOLUTION
        }
        run_id, action = self._to_approval()
        self.assertFalse(any(n.startswith("RAPID1441") for n in action["notes"]), action)
        self.assertEqual(self._approve("gate.final-verification").returncode, 0)
        booking = self.project / "booking.py"
        booking.write_text(booking.read_text(encoding="utf-8") + "\n# edited after the approval\n", encoding="utf-8")
        refused = self._rapid("finish", "--json")
        self.assertEqual(refused.returncode, 1)
        self.assertNotIn("RAPID1441", refused.stderr)
        self.assertTrue([e for e in self._registry().list(run_id) if e.kind.value == "file_change"])

        # The change is undone: the tree is the one the run started from.
        for rel, content in originals.items():
            if content is None:
                (self.project / rel).unlink()
            else:
                (self.project / rel).write_bytes(content)
        self.assertEqual(self._rapid("check", "--gate", "gate.tests").returncode, 0)
        payload = json.loads(self._rapid("next", "--json").stdout)
        self.assertEqual(payload["action"]["kind"], "await_human_approval", payload)
        self.assertTrue(any(n.startswith("RAPID1441") for n in payload.get("notes", [])), payload)
        self.assertIn("Nota: RAPID1441", self._rapid("next").stdout)

        finish = self._approve_and_finish()
        self.assertEqual(finish.returncode, 1)
        self.assertIn("RAPID1441", finish.stderr)
        self.assertIn("no cambió nada fuera de .rapid-os/", finish.stderr)
        self.assertNotIn('"verdict": "pass"', finish.stdout)
        self.assertEqual(list(self._reports(run_id)), [])

        # Making the change again lets it end: check again, approve the new tree, finish.
        self._copy_solution(*SOLUTION)
        self.assertEqual(self._rapid("check", "--gate", "gate.tests").returncode, 0)
        self.assertEqual(self._approve("gate.final-verification").returncode, 0)
        done = self._rapid("finish", "--json")
        self.assertEqual(done.returncode, 0, done.stderr + done.stdout)
        self.assertEqual(json.loads(done.stdout)["verdict"], "pass")

    def test_a_run_that_never_changed_anything_is_unverified_as_before(self):
        self._copy_solution(*SOLUTION)
        self._git("add", ".")
        self._git("commit", "-qm", "solution already there")
        run_id, action = self._to_approval(implement=lambda _action: None)
        self.assertTrue(any(n.startswith("RAPID1441") for n in action["notes"]), action)
        finish = self._approve_and_finish()
        self.assertEqual(finish.returncode, 1)
        self.assertEqual(json.loads(finish.stdout)["verdict"], "unverified")
        self.assertNotIn("RAPID1441", finish.stderr)

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
