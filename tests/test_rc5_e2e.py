"""rc.5 fixes from the rc.4 e2e on Windows (talleres-rc2, Codex and Claude Code).

H-83: removing a run's worktree on Windows (`git worktree remove` refused, `--force` failed with "Filename too
long"). The messages give the command that works once everything is merged, and warn that --force deletes the
work that is not integrated after an abort or a finish without merge.

H-84: the shortcuts said that integrating needs a commit in the worktree first, and the agent repeated it to the
person, when `rapid finish --merge` commits on rapid/<run> and merges after the [s/N].

H-85: `rapid abort` on a run that had already ended said "cancelado y sesión limpiada" without cancelling anything.

H-88: after the last approval Rapid said "Siguiente: `rapid finish`" even when the run had a worktree; with one, the
next step is `rapid finish --merge`. The worktree case is in test_intent_loop (hardening lab with --worktree).
"""

from __future__ import annotations

import json
import unittest

from rapid_os.orchestration.workspace import (
    FORCE_BEFORE_MERGE_WARNING,
    UNINTEGRATED_FORCE_WARNING,
    integrated_worktree_removal,
)
from tests.test_rc4_specs_utf8 import Project, drive_to_approval, rapid, spec


class WorktreeRemovalMessagesTests(Project):
    def test_after_a_merge_the_long_path_command_and_a_safe_branch_delete(self):
        self.assertEqual(
            integrated_worktree_removal(r"C:\work\talleres-rc2-run-1", "run-1"),
            [
                r'git -c core.longpaths=true worktree remove --force "C:\work\talleres-rc2-run-1"',
                "git branch -d rapid/run-1",
            ],
        )
        self.assertIn("borra el trabajo sin integrar", FORCE_BEFORE_MERGE_WARNING)

    def test_abort_keeps_the_worktree_and_warns_that_force_deletes_the_work(self):
        started = rapid(self.root, "start", "feature", "--spec-file", "-", "--json", stdin=json.dumps(spec(), ensure_ascii=False))
        self.assertEqual(started.returncode, 0, started.stderr)
        session_file = self.root / ".rapid-os" / "session.json"
        session = json.loads(session_file.read_text("utf-8"))
        workspace = self.root.parent / "project-run"
        workspace.mkdir()
        session["workspace_path"] = str(workspace)
        session_file.write_text(json.dumps(session), encoding="utf-8")

        aborted = rapid(self.root, "abort")
        self.assertEqual(aborted.returncode, 0, aborted.stderr)
        out = aborted.stdout + aborted.stderr
        self.assertIn(f'git worktree remove "{workspace}"', out)
        self.assertIn(UNINTEGRATED_FORCE_WARNING, out)
        self.assertNotIn("core.longpaths", out)  # nothing is integrated: no --force command is offered


class IntegrationIsFinishMergeTests(unittest.TestCase):
    def test_the_shortcuts_name_finish_merge_and_no_longer_ask_for_a_commit_first(self):
        from pathlib import Path

        shortcuts = Path(__file__).resolve().parents[1] / "templates" / "shortcuts"
        for name in ("rapid-feature", "rapid-hardening", "rapid-refactor", "rapid-research"):
            with self.subTest(shortcut=name):
                text = (shortcuts / f"{name}.md").read_text(encoding="utf-8")
                self.assertNotIn("primero un commit", text)
                self.assertIn("la integración es `rapid finish --merge`", text)
                self.assertIn("El commit manual en el worktree solo es el camino de un `rapid finish` sin `--merge`", text)


class AbortAFinishedRunTests(Project):
    def test_abort_after_finish_says_the_run_already_ended_and_how_to_undo_it(self):
        from rapid_os.core.ancestry import AncestryResult
        from rapid_os.orchestration.lifecycle import execute_approve

        started = rapid(self.root, "start", "feature", "--spec-file", "-", "--json", stdin=json.dumps(spec(), ensure_ascii=False))
        self.assertEqual(started.returncode, 0, started.stderr)
        (self.root / "app.py").write_text("x = 2\n", encoding="utf-8")  # the run changes a file
        for gate in drive_to_approval(self, self.root)["gate_ids"]:
            code, message = execute_approve(
                self.root, self.root / ".rapid-os", gate, reviewer="Ada", is_tty=True,
                input_func=lambda _prompt: "s", environ={}, ancestry=AncestryResult(()),
            )
            self.assertEqual(code, 0, message)
        session_file = self.root / ".rapid-os" / "session.json"
        session = session_file.read_text("utf-8")
        finished = rapid(self.root, "finish")
        self.assertEqual(finished.returncode, 0, finished.stdout + finished.stderr)
        session_file.write_text(session, encoding="utf-8")  # the session the e2e still had

        aborted = rapid(self.root, "abort")
        self.assertEqual(aborted.returncode, 0, aborted.stderr)
        out = aborted.stdout + aborted.stderr
        self.assertNotIn("cancelado", out)
        self.assertIn("ya terminó con PASS; solo se limpió la sesión (no se canceló nada)", out)
        self.assertIn("git revert", out)
        self.assertIn("docs/guides/undo-approval.md", out)
        self.assertFalse(session_file.exists())
        status = json.loads(rapid(self.root, "status", "--json").stdout)
        self.assertNotEqual((status.get("run") or {}).get("status"), "cancelled")


class AfterTheLastApprovalTests(Project):
    def test_without_a_worktree_the_next_step_is_still_rapid_finish(self):
        from rapid_os.core.ancestry import AncestryResult
        from rapid_os.orchestration.lifecycle import AFTER_LAST_APPROVAL, execute_approve

        started = rapid(self.root, "start", "feature", "--spec-file", "-", "--json", stdin=json.dumps(spec(), ensure_ascii=False))
        self.assertEqual(started.returncode, 0, started.stderr)
        (self.root / "app.py").write_text("x = 2\n", encoding="utf-8")
        messages = []
        for gate in drive_to_approval(self, self.root)["gate_ids"]:
            code, message = execute_approve(
                self.root, self.root / ".rapid-os", gate, reviewer="Ada", is_tty=True,
                input_func=lambda _prompt: "s", environ={}, ancestry=AncestryResult(()),
            )
            self.assertEqual(code, 0, message)
            messages.append(message)
        self.assertIn(AFTER_LAST_APPROVAL, messages[-1])
        self.assertNotIn("--merge", messages[-1])

    def test_the_shortcuts_say_finish_merge_with_a_worktree(self):
        from pathlib import Path

        shortcuts = Path(__file__).resolve().parents[1] / "templates" / "shortcuts"
        next_text = (shortcuts / "rapid-next.md").read_text(encoding="utf-8")
        self.assertIn("Si el run tiene worktree (`action.workspace_path`), después de la última aprobación el "
                      "siguiente paso es `rapid finish --merge`", next_text)
        self.assertIn("Tras la última aprobación, si el run tiene worktree el siguiente paso es `rapid finish --merge`",
                      (shortcuts / "rapid-approve.md").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
