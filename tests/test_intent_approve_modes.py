"""Unit contracts for the approval flow, session fields and the mode playbooks."""

from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from rapid_os.domain.evidence import validate_evidence_producer
from rapid_os.orchestration.lifecycle import execute_approve
from rapid_os.orchestration.playbooks import load_playbook
from rapid_os.orchestration.session import Session, resolve_git_untracked

ROOT = Path(__file__).resolve().parents[1]
MODES = ("feature", "bugfix", "refactor", "hardening", "research")


class ApproveContractTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.rapid_dir = self.root / ".rapid-os"

    def tearDown(self):
        self._tmp.cleanup()

    def approve(self, gate_id=None, **kwargs):
        kwargs.setdefault("is_tty", False)
        kwargs.setdefault("environ", {})
        return execute_approve(self.root, self.rapid_dir, gate_id, **kwargs)

    def test_reject_and_waive_are_mutually_exclusive(self):
        code, msg = self.approve("gate.review", reject=True, waive=True, reason="x")
        self.assertEqual(code, 1)
        self.assertIn("RAPID1330", msg)

    def test_reject_and_waive_need_a_gate(self):
        for flag in ("reject", "waive"):
            with self.subTest(flag=flag):
                code, msg = self.approve(None, reason="x", **{flag: True})
                self.assertEqual(code, 1)
                self.assertIn("RAPID1330", msg)

    def test_reason_is_mandatory_for_reject_and_waive(self):
        for flag in ("reject", "waive"):
            with self.subTest(flag=flag):
                code, msg = self.approve("gate.review", **{flag: True})
                self.assertEqual(code, 1)
                self.assertIn("RAPID1333", msg)
                self.assertIn("Reason is required" if flag == "reject" else "'--reason' is required", msg)

    def test_no_tty_fails_with_rapid1310_before_touching_the_ledger(self):
        # No session exists at all: the TTY check still comes first.
        for kwargs in ({}, {"reject": True, "reason": "x"}, {"waive": True, "reason": "x"}):
            with self.subTest(kwargs=kwargs):
                code, msg = self.approve("gate.final-verification", **kwargs)
                self.assertEqual(code, 1)
                self.assertIn("RAPID1310", msg)

    def test_agent_session_is_rejected_even_with_a_tty(self):
        code, msg = self.approve(
            "gate.final-verification", is_tty=True, environ={"CLAUDE_CODE_CHILD_SESSION": "1"}
        )
        self.assertEqual(code, 1)
        self.assertIn("RAPID1310", msg)

    def test_listing_is_read_only_and_needs_a_session(self):
        code, msg = self.approve(None)
        self.assertEqual(code, 1)
        self.assertIn("RAPID1307", msg)


class SessionFieldTests(unittest.TestCase):
    def test_new_fields_are_omitted_when_unused(self):
        payload = Session(active_run_id="r", mode="feature", harness="cursor").to_dict()
        self.assertNotIn("start_untracked", payload)
        self.assertNotIn("workspace_path", payload)

    def test_round_trip_keeps_new_fields(self):
        session = Session(
            active_run_id="r",
            mode="hardening",
            harness="cursor",
            start_untracked=("a.txt", "b/c.py"),
            workspace_path="/tmp/x-r",
        )
        again = Session.from_dict(json.loads(json.dumps(session.to_dict())))
        self.assertEqual(again, session)

    def test_empty_untracked_list_is_kept_distinct_from_unknown(self):
        session = Session(active_run_id="r", mode="feature", harness="cursor", start_untracked=())
        self.assertEqual(session.to_dict()["start_untracked"], [])
        self.assertEqual(Session.from_dict(session.to_dict()).start_untracked, ())

    def test_invalid_field_types_are_rejected(self):
        base = {"active_run_id": "r", "mode": "feature", "harness": "cursor"}
        for extra in ({"start_untracked": "a.txt"}, {"start_untracked": [1]}, {"workspace_path": 5}):
            with self.subTest(extra=extra):
                with self.assertRaises(ValueError):
                    Session.from_dict({**base, **extra})

    def test_untracked_outside_a_repo_is_unknown(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertIsNone(resolve_git_untracked(tmp))


class PlaybookTests(unittest.TestCase):
    def test_all_five_modes_have_a_valid_playbook(self):
        for mode in MODES:
            with self.subTest(mode=mode):
                playbook = load_playbook(mode, templates_dir=ROOT / "templates")
                self.assertEqual(playbook.mode, mode)
                self.assertTrue(playbook.spec_template["implementation_tasks"])
                for kind in ("author_spec", "implement_task", "verify", "blocked", "done"):
                    self.assertTrue(playbook.get_instruction(kind), (mode, kind))

    def test_bugfix_starts_with_the_reproduction_task(self):
        tasks = load_playbook("bugfix", templates_dir=ROOT / "templates").spec_template["implementation_tasks"]
        self.assertEqual(tasks[0], "T001: Reproducir con un test en rojo")

    def test_attach_is_a_valid_evidence_producer(self):
        self.assertEqual(validate_evidence_producer("rapid:attach"), "rapid:attach")


if __name__ == "__main__":
    unittest.main()
