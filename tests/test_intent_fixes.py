"""Approve refuses agent-harness ancestors; `rapid finish` text mode and terminal runs."""

from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

from rapid_os.core import ancestry
from rapid_os.core.ancestry import (
    Ancestor,
    AncestryResult,
    find_agent_ancestor,
    match_agent,
    read_ancestry,
)
from rapid_os.domain.execution import RunStatus
from rapid_os.orchestration.lifecycle import execute_approve
from tests.test_intent_loop import LabScenarioBase

ROOT = Path(__file__).resolve().parents[1]


class MatchAgentTests(unittest.TestCase):
    def test_claude_code_processes_are_recognised(self):
        cases = (
            Ancestor(1, "claude"),
            Ancestor(1, "claude.exe"),
            Ancestor(1, "CLAUDE.EXE"),
            # The VS Code extension binary seen on a real Windows install.
            Ancestor(1, "claude.exe", ()),
            # macOS/Linux native install: the process may be named after the version, argv[0] is claude.
            Ancestor(1, "2.1.89", ("claude", "--resume")),
            Ancestor(1, "2.1.89", ("/home/u/.local/bin/claude",)),
            Ancestor(1, "node", ("node", "/usr/lib/node_modules/@anthropic-ai/claude-code/cli.js")),
            Ancestor(1, "node", ("node", "C:\\Users\\u\\AppData\\Roaming\\npm\\node_modules\\@anthropic-ai\\claude-code\\cli.js")),
            Ancestor(1, "x", ("/home/u/.local/share/claude/versions/2.1.89", "--print")),
        )
        for ancestor in cases:
            with self.subTest(ancestor=ancestor):
                self.assertEqual(match_agent(ancestor), "claude")

    def test_ordinary_processes_are_not(self):
        cases = (
            Ancestor(1, "bash", ("bash", "-l")),
            Ancestor(1, "python", ("python", "-m", "rapid_os")),
            Ancestor(1, "Code.exe"),
            Ancestor(1, "vim", ("vim", "claude.md")),
            Ancestor(1, "less", ("less", "docs/claude-code.md")),
            Ancestor(1, "claude-notes"),
            Ancestor(1, "claudette.exe"),
            Ancestor(1, "node", ("node", "server.js")),
            Ancestor(1, "cursor"),
            Ancestor(1, "codex"),  # not confirmed: deliberately not matched
        )
        for ancestor in cases:
            with self.subTest(ancestor=ancestor):
                self.assertIsNone(match_agent(ancestor))

    def test_nearest_agent_ancestor_wins(self):
        chain = AncestryResult((Ancestor(10, "bash"), Ancestor(20, "claude"), Ancestor(30, "claude")))
        found = find_agent_ancestor(chain)
        self.assertEqual((found.harness, found.ancestor.pid), ("claude", 20))
        self.assertIsNone(find_agent_ancestor(AncestryResult((Ancestor(1, "bash"),))))


class ReadAncestryTests(unittest.TestCase):
    @staticmethod
    def reader(table):
        def read(pid):
            if pid not in table:
                raise OSError(f"no pid {pid}")
            return table[pid]

        return read

    def test_walks_the_chain_nearest_first(self):
        table = {
            100: (90, "python", ()),
            90: (80, "bash", ("bash",)),
            80: (1, "claude", ("claude",)),
            1: (0, "init", ()),
        }
        result = read_ancestry(100, reader=self.reader(table))
        self.assertIsNone(result.error)
        self.assertEqual([a.pid for a in result.ancestors], [90, 80, 1])

    def test_cycles_do_not_loop(self):
        table = {1: (2, "a", ()), 2: (3, "b", ()), 3: (2, "c", ())}
        result = read_ancestry(1, reader=self.reader(table))
        self.assertEqual([a.pid for a in result.ancestors], [2, 3])

    def test_unreadable_parent_is_reported_not_raised(self):
        result = read_ancestry(100, reader=self.reader({}))
        self.assertEqual(result.ancestors, ())
        self.assertIn("cannot read", result.error)

    def test_a_chain_cut_midway_keeps_what_was_read(self):
        table = {100: (90, "python", ()), 90: (80, "bash", ())}
        result = read_ancestry(100, reader=self.reader(table))
        self.assertEqual([a.pid for a in result.ancestors], [90])
        self.assertIsNone(result.error)

    def test_unavailable_platform_support_is_an_error_string(self):
        with mock.patch.object(ancestry, "default_reader", side_effect=ImportError("no ctypes")):
            result = read_ancestry()
        self.assertEqual(result.ancestors, ())
        self.assertIn("not available", result.error)

    def test_real_process_has_readable_ancestors_on_this_platform(self):
        result = read_ancestry()
        self.assertIsNone(result.error)
        self.assertTrue(result.ancestors)
        self.assertEqual(result.ancestors[0].pid, os.getppid())

    @unittest.skipIf(sys.platform.startswith("win"), "uses the Unix ps reader")
    def test_ps_reader_parses_ppid_name_and_args(self):
        outputs = {
            "ppid=,comm=": " 321 /Applications/Visual Studio Code.app/Contents/MacOS/Electron\n",
            "args=": "  /Applications/Visual Studio Code.app/Contents/MacOS/Electron --flag\n",
        }

        def fake_run(cmd, **kwargs):
            return subprocess.CompletedProcess(cmd, 0, stdout=outputs[cmd[2]], stderr="")

        with mock.patch.object(ancestry.subprocess, "run", side_effect=fake_run):
            ppid, name, args = ancestry._ps_reader(99)
        self.assertEqual(ppid, 321)
        self.assertTrue(name.endswith("Electron"))
        self.assertEqual(args[-1], "--flag")


class ApproveAncestryTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def approve(self, ancestry_result, **kwargs):
        return execute_approve(
            self.root, self.root / ".rapid-os", "gate.final-verification",
            is_tty=True, environ={}, ancestry=ancestry_result, **kwargs,
        )

    def test_agent_ancestor_is_refused_even_with_a_tty_and_no_session_variables(self):
        chain = AncestryResult((Ancestor(10, "bash"), Ancestor(20, "claude.exe")))
        code, msg = self.approve(chain)
        self.assertEqual(code, 1)
        self.assertIn("RAPID1310", msg)
        self.assertIn("agent harness", msg)
        self.assertIn("pid 20", msg)

    def test_unreadable_ancestry_does_not_reject(self):
        # Falls through to the next check (no active session) instead of RAPID1310.
        code, msg = self.approve(AncestryResult((), "cannot read the parent of pid 1: denied"))
        self.assertEqual(code, 1)
        self.assertIn("RAPID1307", msg)
        self.assertNotIn("RAPID1310", msg)

    def test_clean_ancestry_does_not_reject(self):
        code, msg = self.approve(AncestryResult((Ancestor(10, "bash"), Ancestor(11, "Code.exe"))))
        self.assertIn("RAPID1307", msg)

    def test_listing_gates_is_read_only_and_ignores_ancestry(self):
        chain = AncestryResult((Ancestor(20, "claude"),))
        code, msg = execute_approve(
            self.root, self.root / ".rapid-os", None, is_tty=False, environ={}, ancestry=chain
        )
        self.assertIn("RAPID1307", msg)  # no session; not refused for the ancestor


class FakeClaudeProcessTests(unittest.TestCase):
    """A real child process tree: approve launched under an executable named `claude`."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self.env = {k: v for k, v in os.environ.items() if k not in ("CLAUDECODE", "CLAUDE_CODE_CHILD_SESSION")}
        self.env["PYTHONPATH"] = str(ROOT)
        self.fake = self._make_fake("claude")

    def tearDown(self):
        self._tmp.cleanup()

    def _make_fake(self, name):
        """An executable called `name` that behaves like python."""
        # A virtualenv's python.exe needs its pyvenv.cfg: copy the base interpreter instead.
        interpreter = getattr(sys, "_base_executable", sys.executable)
        if sys.platform.startswith("win"):
            fake = self.tmp / (name + ".exe")
            shutil.copyfile(interpreter, fake)
            base = Path(sys.base_prefix)
            self.env["PYTHONHOME"] = str(base)
            self.env["PATH"] = str(base) + os.pathsep + self.env.get("PATH", "")
        else:
            fake = self.tmp / name
            fake.symlink_to(interpreter)
        probe = subprocess.run([str(fake), "-c", "print('ok')"], capture_output=True, text=True, env=self.env)
        if probe.returncode != 0 or probe.stdout.strip() != "ok":
            self.skipTest(f"cannot run a renamed python as a fake {name}: {probe.stderr.strip()[:120]}")
        return fake

    def _approve_under(self, fake):
        approve_code = (
            "import sys, unittest.mock as mock, rapid_os.cli.main as m; "
            "sys.argv = ['rapid', 'approve', 'gate.final-verification']; "
            "mock.patch('sys.stdin.isatty', return_value=True).start(); "
            "mock.patch('rapid_os.orchestration.lifecycle.stdin_is_windows_nul', return_value=False).start(); "
            "mock.patch('builtins.input', return_value='aprobar gate.final-verification').start(); "
            "sys.exit(m.main())"
        )
        parent_code = (
            "import os, subprocess, sys; "
            "print(os.getpid(), flush=True); "
            f"r = subprocess.run([{sys.executable!r}, '-c', {approve_code!r}], capture_output=True, text=True); "
            "sys.stderr.write(r.stderr); sys.exit(r.returncode)"
        )
        return subprocess.run(
            [str(fake), "-c", parent_code],
            cwd=str(self.tmp), capture_output=True, text=True, encoding="utf-8", env=self.env,
        )

    def test_approve_under_a_process_named_claude_is_rapid1310(self):
        result = self._approve_under(self.fake)
        fake_pid = result.stdout.split()[0]
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertIn("RAPID1310", result.stderr)
        self.assertIn("agent harness", result.stderr)
        # The nearest ancestor is the fake, not some real harness further up the tree.
        self.assertIn(f"pid {fake_pid}", result.stderr)
        self.assertNotIn("Traceback", result.stderr)

    def test_a_differently_named_parent_is_not_refused_for_its_name(self):
        other = self._make_fake("helper")
        result = self._approve_under(other)
        helper_pid = result.stdout.split()[0]
        # It may still be refused when this suite itself runs under a real agent harness, but never
        # because of the helper.
        self.assertNotIn(f"pid {helper_pid}", result.stderr)


class FinishScenarioTests(LabScenarioBase):
    LAB = "feature"

    SPEC = {
        "title": "Booking availability",
        "business_objective": "Reject double bookings",
        "problem_statement": "Bookings can overlap",
        "acceptance_criteria": ["overlapping bookings are rejected"],
        "tasks": ["T001: Implement availability control"],
    }

    def _run_to_approval(self):
        data = self._start("feature", self.SPEC)

        def implement(action):
            self._copy_solution("booking.py", "tests/test_booking.py")

        action, _ = self._drive(implement)
        self.assertEqual(action["kind"], "await_human_approval")
        self.assertEqual(self._approve("gate.final-verification").returncode, 0)
        return data["run_id"]

    def _evidence_count(self, run_id):
        return len(self._registry().list(run_id))

    def _report_files(self, run_id):
        return sorted((self.project / ".rapid-os" / "evals" / run_id / "reports").glob("*.json"))

    def test_finish_in_text_mode_prints_verdict_and_report_revision(self):
        run_id = self._run_to_approval()
        res = self._rapid("finish")
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertNotIn("Traceback", res.stderr)
        self.assertNotIn("AttributeError", res.stderr)
        self.assertIn(f"Evaluation report 0001 for run '{run_id}': verdict PASS", res.stdout)
        closed_check = self._rapid("check", "--", sys.executable, "-c", "pass")
        self.assertEqual(closed_check.returncode, 1)
        self.assertIn(
            f"RAPID1342 El run {run_id} ya terminó (finished); empieza uno nuevo con rapid start.",
            closed_check.stderr,
        )
        business_doc = self.project / "business-rules.md"
        business_doc.write_text(
            "# Reglas de negocio\n\n## Objetivo\nObjetivo.\n\n## Reglas no negociables\nReglas.\n\n## Restricciones\nNinguna.\n\n## Supuestos\nSupuestos.\n\n## Glosario\nTérminos.\n",
            encoding="utf-8",
        )
        onboarded = self._rapid("setup", "doc", "business", "--source", "provided", "--file", str(business_doc))
        self.assertEqual(onboarded.returncode, 0, onboarded.stdout + onboarded.stderr)
        strict = self._rapid("validate", "--strict")
        self.assertEqual(strict.returncode, 0, strict.stdout + strict.stderr)

    def test_finish_on_a_finished_run_is_idempotent(self):
        run_id = self._run_to_approval()
        first = self._rapid("finish", "--json")
        self.assertEqual(first.returncode, 0, first.stderr)
        evidence_before = self._evidence_count(run_id)
        reports_before = [p.name for p in self._report_files(run_id)]
        self.assertEqual(reports_before, ["0001.json"])

        again_json = self._rapid("finish", "--json")
        self.assertEqual(again_json.returncode, 0, again_json.stderr)
        self.assertEqual(json.loads(again_json.stdout), json.loads(first.stdout))

        again_text = self._rapid("finish")
        self.assertEqual(again_text.returncode, 0, again_text.stderr)
        self.assertIn(f"Evaluation report 0001 for run '{run_id}': verdict PASS", again_text.stdout)

        self.assertEqual(self._evidence_count(run_id), evidence_before)
        self.assertEqual([p.name for p in self._report_files(run_id)], reports_before)

    def _registry_state(self, run_id, status):
        from rapid_os.adapters.run_registry import RunRegistry

        RunRegistry(self.project, self.project / ".rapid-os").transition_status(run_id, status, reason="test")

    def test_finish_on_a_run_without_a_report_exits_1_with_already_ended(self):
        for status, outcome in ((RunStatus.CANCELLED, "cancelled"), (RunStatus.FAILED, "failed")):
            with self.subTest(status=outcome):
                self.tearDown()
                self.setUp()
                run_id = self._start("feature", self.SPEC)["run_id"]
                self._registry_state(run_id, status)
                evidence_before = self._evidence_count(run_id)

                res = self._rapid("finish")
                self.assertEqual(res.returncode, 1, res.stdout + res.stderr)
                self.assertIn(f"already ended ({outcome})", res.stderr)
                self.assertNotIn("Traceback", res.stderr)

                as_json = self._rapid("finish", "--json")
                self.assertEqual(as_json.returncode, 1, as_json.stderr)
                payload = json.loads(as_json.stdout)
                self.assertEqual(payload["action"]["kind"], "done")
                self.assertEqual(payload["outcome"], outcome)

                self.assertEqual(self._evidence_count(run_id), evidence_before)
                self.assertEqual(self._report_files(run_id), [])

    def test_finish_on_a_run_with_a_non_passing_stored_verdict_exits_1(self):
        from types import SimpleNamespace

        from rapid_os.adapters.eval_registry import EvalRegistry
        from rapid_os.domain.evals import EvaluationVerdict
        from rapid_os.orchestration import lifecycle

        run_id = self._run_to_approval()
        self.assertEqual(self._rapid("finish").returncode, 0)  # ends the run with a pass
        evidence_before = self._evidence_count(run_id)
        reports_before = [p.name for p in self._report_files(run_id)]

        # A stored report that is not a pass (a finished run cannot be forged into one through the
        # CLI, so the stored report is stubbed): exit 1 and the report is still returned.
        for verdict in (EvaluationVerdict.FAIL, EvaluationVerdict.UNVERIFIED):
            with self.subTest(verdict=verdict.value):
                stub = SimpleNamespace(verdict=verdict, run_id=run_id)
                with mock.patch.object(EvalRegistry, "list_reports", return_value=(stub,)):
                    code, result = lifecycle.execute_finish(
                        self.project, self.project / ".rapid-os", templates_dir=ROOT / "templates"
                    )
                self.assertEqual(code, 1)
                self.assertIs(result, stub)

        for verdict in (EvaluationVerdict.PASS, EvaluationVerdict.PASS_WITH_WAIVERS):
            with self.subTest(verdict=verdict.value):
                stub = SimpleNamespace(verdict=verdict, run_id=run_id)
                with mock.patch.object(EvalRegistry, "list_reports", return_value=(stub,)):
                    code, _ = lifecycle.execute_finish(
                        self.project, self.project / ".rapid-os", templates_dir=ROOT / "templates"
                    )
                self.assertEqual(code, 0)

        self.assertEqual(self._evidence_count(run_id), evidence_before)
        self.assertEqual([p.name for p in self._report_files(run_id)], reports_before)


class FinishWithWaiversTests(LabScenarioBase):
    LAB = "hardening"
    ARCHETYPE = "corporate"

    SPEC = {
        "title": "Validate profile inputs",
        "business_objective": "Reject hostile input",
        "problem_statement": "register_user accepts anything",
        "acceptance_criteria": ["invalid usernames are rejected"],
        "tasks": ["T001: Add defensive validation"],
    }

    def test_pass_with_waivers_exits_0_and_a_second_finish_stays_0(self):
        self._start("hardening", self.SPEC, "--worktree")
        session = json.loads((self.project / ".rapid-os" / "session.json").read_text(encoding="utf-8"))
        workspace = Path(session["workspace_path"])
        run_id = session["active_run_id"]

        def implement(action):
            self._copy_solution("profile_mgr.py", "tests/test_profile_mgr.py", dest_root=workspace)

        action, _ = self._drive(implement)
        self.assertEqual(action["kind"], "await_human_approval")
        waived = self._rapid_tty(
            ["approve", "gate.review", "--waive", "--reason", "covered by the audit"],
            "dispensar gate.review",
        )
        self.assertEqual(waived.returncode, 0, waived.stderr)
        self.assertEqual(self._approve("gate.final-verification").returncode, 0)

        first = self._rapid("finish", "--json")
        self.assertEqual(first.returncode, 0, first.stderr)
        self.assertEqual(json.loads(first.stdout)["verdict"], "pass_with_waivers")
        evidence_before = len(self._registry().list(run_id))

        again = self._rapid("finish")
        self.assertEqual(again.returncode, 0, again.stdout + again.stderr)
        self.assertIn("verdict PASS_WITH_WAIVERS", again.stdout)
        self.assertEqual(len(self._registry().list(run_id)), evidence_before)


if __name__ == "__main__":
    unittest.main()
