"""rc.5 fixes from the rc.4 e2e on Windows (talleres-rc2, Codex and Claude Code).

H-83: removing a run's worktree on Windows (`git worktree remove` refused, `--force` failed with "Filename too
long"). The messages give the command that works once everything is merged, and warn that --force deletes the
work that is not integrated after an abort or a finish without merge.
"""

from __future__ import annotations

import json
import unittest

from rapid_os.orchestration.workspace import (
    FORCE_BEFORE_MERGE_WARNING,
    UNINTEGRATED_FORCE_WARNING,
    integrated_worktree_removal,
)
from tests.test_rc4_specs_utf8 import Project, rapid, spec


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


if __name__ == "__main__":
    unittest.main()
