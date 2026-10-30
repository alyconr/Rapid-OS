"""Tests for the Claude Code hooks: pure decisions, project resolution, settings merge and CLI."""

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

from rapid_os.adapters import claude_hooks
from rapid_os.adapters.shortcut_installer import ShortcutError
from rapid_os.orchestration.actions import ActionKind, NextAction
from rapid_os.orchestration.hook_runtime import HookProject, find_project, run_hook
from rapid_os.orchestration.hooks import (
    HookPayload,
    StopGuard,
    decide_pre_tool,
    decide_stop,
    find_env_tamper,
    find_protected_write,
    find_reserved_use,
    parse_payload,
    pre_tool_output,
)
from rapid_os.orchestration.session import Session, save_session
from tests.test_intent_loop import LabScenarioBase

ROOT = Path(__file__).resolve().parents[1]
PROTECTED = ("/proj/.rapid-os",)
CWD = "/proj"


def action(kind, *, task_id=None, gate_ids=(), command=None, after=None, instructions="Do the thing"):
    return NextAction(
        run_id="r1",
        mode="feature",
        kind=kind,
        instructions=instructions,
        task_id=task_id,
        gate_ids=gate_ids,
        command=command,
        after=after,
    )


def stop_payload(active=False, session="s1"):
    return HookPayload(event="Stop", session_id=session, cwd=CWD, stop_hook_active=active)


def bash(command, cwd=CWD, tool="Bash"):
    return HookPayload(event="PreToolUse", session_id="s1", cwd=cwd, tool_name=tool, tool_input={"command": command})


class StopDecisionTests(unittest.TestCase):
    BLOCKING = {
        ActionKind.RUN_BASELINE: dict(command=("rapid", "check", "--gate", "gate.baseline", "--", "pytest")),
        ActionKind.ACTIVATE: dict(command=("rapid", "start", "--resume")),
        ActionKind.IMPLEMENT_TASK: dict(task_id="T001", command=("rapid", "task", "start", "T001"),
                                        after=("rapid", "task", "done", "T001")),
        ActionKind.VERIFY: dict(task_id="T001", command=("rapid", "check", "--task", "T001", "--", "pytest")),
        ActionKind.FINISH: dict(command=("rapid", "finish")),
    }

    def test_blocks_only_when_the_agent_still_has_work(self):
        for kind in ActionKind:
            with self.subTest(kind=kind.value):
                output, guard = decide_stop(stop_payload(), action(kind, **self.BLOCKING.get(kind, {})), None)
                if kind in self.BLOCKING:
                    self.assertEqual(output["decision"], "block")
                    self.assertEqual(guard.count, 1)
                else:
                    self.assertIsNone(output)
                    self.assertIsNone(guard)

    def test_reason_carries_instructions_and_the_exact_command(self):
        spec = self.BLOCKING[ActionKind.VERIFY]
        output, _ = decide_stop(stop_payload(), action(ActionKind.VERIFY, **spec), None)
        self.assertIn("Do the thing", output["reason"])
        self.assertIn("`rapid check --task T001 -- pytest`", output["reason"])

    def test_reason_falls_back_to_after_when_there_is_no_command(self):
        output, _ = decide_stop(
            stop_payload(),
            action(ActionKind.IMPLEMENT_TASK, task_id="T002", after=("rapid", "task", "done", "T002")),
            None,
        )
        self.assertIn("`rapid task done T002`", output["reason"])

    def test_implement_task_reason_lists_command_then_after(self):
        output, _ = decide_stop(stop_payload(), action(ActionKind.IMPLEMENT_TASK, **self.BLOCKING[ActionKind.IMPLEMENT_TASK]), None)
        self.assertIn("`rapid task start T001`", output["reason"])
        self.assertIn("`rapid task done T001`", output["reason"])

    def test_no_session_and_rejected_review_abort_do_not_block(self):
        self.assertEqual(decide_stop(stop_payload(), None, None), (None, None))
        proposed_abort = action(ActionKind.BLOCKED, command=("rapid", "abort"), gate_ids=("gate.review",))
        self.assertEqual(decide_stop(stop_payload(), proposed_abort, None), (None, None))

    def test_guard_allows_the_stop_after_max_consecutive_blocks(self):
        act = action(ActionKind.FINISH, command=("rapid", "finish"))
        guard = None
        outputs = []
        for attempt in range(5):
            output, guard = decide_stop(stop_payload(active=attempt > 0), act, guard, max_blocks=3)
            outputs.append(output is not None)
        self.assertEqual(outputs, [True, True, True, False, False])

    def test_guard_restarts_when_the_action_changes(self):
        first = action(ActionKind.IMPLEMENT_TASK, task_id="T001", command=("rapid", "task", "start", "T001"))
        second = action(ActionKind.IMPLEMENT_TASK, task_id="T002", command=("rapid", "task", "start", "T002"))
        guard = StopGuard("implement_task|T001|", 3)
        output, guard = decide_stop(stop_payload(active=True), first, guard, max_blocks=3)
        self.assertIsNone(output)  # T001 already blocked three times
        output, guard = decide_stop(stop_payload(active=True), second, guard, max_blocks=3)
        self.assertIsNotNone(output)  # a different task: the counter restarts
        self.assertEqual(guard, StopGuard("implement_task|T002|", 1))

    def test_a_stop_that_is_not_a_continuation_restarts_the_count(self):
        act = action(ActionKind.FINISH, command=("rapid", "finish"))
        output, guard = decide_stop(stop_payload(active=False), act, StopGuard("finish||", 3), max_blocks=3)
        self.assertIsNotNone(output)
        self.assertEqual(guard.count, 1)

    def test_zero_disables_blocking(self):
        act = action(ActionKind.FINISH, command=("rapid", "finish"))
        self.assertIsNone(decide_stop(stop_payload(), act, None, max_blocks=0)[0])


class PreToolDecisionTests(unittest.TestCase):
    DENIED = (
        "rapid approve gate.final-verification",
        "rapid run gate RUN gate.baseline acknowledged",
        "rapid run status RUN completed",
        "rapid evidence add --run RUN --input e.json",
        "rapid spec status my-spec ready",
        "rapid abort",
        "python -m rapid_os approve x",
        "python3 -m rapid_os.cli.main approve x",
        "py -m rapid_os abort",
        "python rapid.py approve x",
        "python -u ./rapid.py approve x",
        "/usr/local/bin/rapid approve x",
        "C:\\Python312\\Scripts\\rapid.exe approve x",
        ".venv/bin/rapid approve x",
        "./rapid.py approve x",
        "VAR=1 rapid approve x",
        "A=1 B=2 rapid abort",
        "env FOO=1 rapid approve x",
        "sudo -u bob rapid approve x",
        "timeout 5 rapid approve x",
        "nohup rapid abort &",
        "uv run rapid approve x",
        "cd x && rapid approve x",
        "ls; rapid approve x",
        "true || rapid approve x",
        "echo hi | rapid approve x",
        "echo a\nrapid approve x",
        "echo $(rapid evidence add --run r --input f.json)",
        "echo `rapid approve x`",
        'echo "$(rapid approve x)"',
        "bash -c 'rapid approve x'",
        'sh -c "cd y; rapid abort"',
        "eval 'rapid approve x'",
        "(cd x && rapid approve x)",
        "{ rapid approve x; }",
        "rapid --json approve x",
        "RAPID approve x".lower(),
    )
    ALLOWED = (
        "rapid status --json",
        "rapid next",
        "rapid next --json",
        "rapid check -- python -m unittest",
        "rapid task done T001",
        "rapid attach notes.md --label findings",
        "rapid finish",
        "rapid start feature --spec-file -",
        "rapid run create --spec s",
        "rapid run list",
        "rapid evidence list --run r",
        "rapid spec create --title x",
        "rapid shortcuts install --harness claude",
        "python -m rapid_os status",
        "python rapid.py next --json",
        "python -m unittest discover",
        "git commit -m 'docs: rapid approve flow'",
        "grep 'rapid approve' README.md",
        "echo rapid approve",
        "rapid status --json | head",
        "cat <<'EOF' > notes.md\nrapid approve gate.x\nEOF",
        "ls .rapid-os",
        "cat .rapid-os/session.json",
        "cp .rapid-os/config.json /tmp/c.json",
        "cat .rapid-os/x > out.txt",
        "echo x > notes.txt",
        "rm tmp.txt",
    )

    def test_reserved_commands_table(self):
        for command in self.DENIED:
            with self.subTest(denied=command):
                self.assertIsNotNone(decide_pre_tool(bash(command), PROTECTED), command)
        for command in self.ALLOWED:
            with self.subTest(allowed=command):
                self.assertIsNone(decide_pre_tool(bash(command), PROTECTED), command)

    def test_powershell_tool_is_covered_too(self):
        for command in ("& rapid approve x", ".\\rapid.exe approve x", "rapid abort; Write-Host done"):
            with self.subTest(command=command):
                self.assertIsNotNone(decide_pre_tool(bash(command, tool="PowerShell"), PROTECTED))
        self.assertIsNone(decide_pre_tool(bash("rapid status --json", tool="PowerShell"), PROTECTED))

    def test_approve_reason_gives_the_exact_command_for_the_person(self):
        decision = decide_pre_tool(bash("rapid approve gate.final-verification"), PROTECTED)
        self.assertIn("`rapid approve gate.final-verification`", decision.reason)
        self.assertIn("own terminal", decision.reason)
        self.assertIn("rapid next --json", decision.reason)
        output = pre_tool_output(decision)["hookSpecificOutput"]
        self.assertEqual(output["hookEventName"], "PreToolUse")
        self.assertEqual(output["permissionDecision"], "deny")

    def test_other_reserved_reasons_point_to_rapid_next(self):
        decision = decide_pre_tool(bash("rapid evidence add --run r --input e.json"), PROTECTED)
        self.assertIn("rapid next --json", decision.reason)

    def test_file_tools_inside_rapid_os_are_denied(self):
        cases = (
            ("Write", {"file_path": "/proj/.rapid-os/config.json"}),
            ("Edit", {"file_path": "/proj/.rapid-os/runs/r1/contract.json"}),
            ("Edit", {"file_path": ".rapid-os/specs/x.json"}),
            ("Edit", {"file_path": "src/../.rapid-os/x"}),
            ("MultiEdit", {"file_path": "/proj/.rapid-os/x"}),
            ("NotebookEdit", {"notebook_path": "/proj/.rapid-os/n.ipynb"}),
            ("Write", {"file_path": "C:\\proj\\.rapid-os\\x.json"}),
        )
        for tool, tool_input in cases:
            with self.subTest(tool=tool, tool_input=tool_input):
                cwd = "C:\\proj" if "C:" in json.dumps(tool_input) else CWD
                protected = ("C:/proj/.rapid-os",) if cwd.startswith("C:") else PROTECTED
                payload = HookPayload("PreToolUse", "s1", cwd, tool, tool_input)
                self.assertIsNotNone(decide_pre_tool(payload, protected))

    def test_file_tools_elsewhere_are_allowed(self):
        cases = (
            ("Write", {"file_path": "/proj/src/app.py"}),
            ("Edit", {"file_path": "/proj/.rapid-os-notes/x.md"}),
            ("Edit", {"file_path": "/elsewhere/.rapid-os/x"}),
            ("Write", {"file_path": "docs/rapid-os.md"}),
            ("Read", {"file_path": "/proj/.rapid-os/session.json"}),
        )
        for tool, tool_input in cases:
            with self.subTest(tool=tool, tool_input=tool_input):
                payload = HookPayload("PreToolUse", "s1", CWD, tool, tool_input)
                self.assertIsNone(decide_pre_tool(payload, PROTECTED))

    def test_bash_writes_into_rapid_os_are_denied(self):
        denied = (
            "echo x > .rapid-os/session.json",
            "echo x >> .rapid-os/runs/r/x",
            "echo x >.rapid-os/x",
            "cat f | tee .rapid-os/a",
            "cp a .rapid-os/b",
            "mv .rapid-os/a b",
            "rm -rf .rapid-os/scratch",
            "sed -i 's/a/b/' .rapid-os/config.json",
            "sed --in-place s/a/b/ .rapid-os/config.json",
            "touch .rapid-os/x",
            "dd if=a of=.rapid-os/b",
            "echo x > $CLAUDE_PROJECT_DIR/.rapid-os/x",
            "cd /tmp && echo x > /proj/.rapid-os/x",
            "bash -c 'echo x > .rapid-os/y'",
        )
        for command in denied:
            with self.subTest(command=command):
                self.assertIsNotNone(find_protected_write(command, CWD, PROTECTED), command)
        for command in ("Set-Content -Path .rapid-os\\config.json -Value x", "Remove-Item -Recurse .rapid-os"):
            with self.subTest(command=command):
                self.assertIsNotNone(decide_pre_tool(bash(command, tool="PowerShell"), PROTECTED))

    def test_find_reserved_use_names_the_gate(self):
        use = find_reserved_use("cd x && VAR=1 rapid approve gate.review --reviewer me")
        self.assertEqual((use.command, use.gate), ("approve", "gate.review"))


class PreToolBypassTests(unittest.TestCase):
    """Bypasses found in the review of PR #57: pty wrappers, session-variable tampering, find -exec."""

    SCRIPT_DENIED = (
        # The command from the review: strips the agent-session variables, then gets a TTY via script.
        "env -u CLAUDE_CODE_CHILD_SESSION -u CLAUDECODE script -qec 'rapid approve gate.final-verification' /dev/null",
        "script -qec 'rapid approve gate.final-verification' /dev/null",
        "script -qc 'rapid approve gate.x' /dev/null",
        "script -c 'rapid abort' /dev/null",
        "script -q -e -c 'rapid approve x' /dev/null",
        "script --command 'rapid approve x' /dev/null",
        "script --command='rapid approve x' /dev/null",
        "script -qec 'cd x && VAR=1 python -m rapid_os approve x' /dev/null",
        "su -c 'rapid approve x' someone",
        "runuser -c 'rapid abort' someone",
        "bash -xc 'rapid approve x'",
        "sh -ec \"rapid abort\"",
    )
    SCRIPT_ALLOWED = (
        "script -qec 'rapid status --json' /dev/null",
        "script -q session.log",
        "script -qec 'python -m unittest' /dev/null",
        "bash -c 'rapid next --json'",
        "su -c 'ls' someone",
    )
    TAMPER_DENIED = (
        "env -u CLAUDE_CODE_CHILD_SESSION ls",
        "env -u CLAUDECODE ls",
        "env --unset CLAUDECODE ls",
        "env --unset=CLAUDE_CODE_CHILD_SESSION ls",
        "env -uCLAUDECODE ls",
        "env -i rapid next",
        "env CLAUDECODE=0 ls",
        "unset CLAUDE_CODE_CHILD_SESSION",
        "unset -v CLAUDECODE",
        "unset FOO CLAUDECODE",
        "CLAUDECODE= rapid next",
        "CLAUDECODE=0 rapid next",
        "CLAUDE_CODE_CHILD_SESSION= python x.py",
        "CLAUDE_CODE_CHILD_SESSION=0 CLAUDECODE=0 ls",
        "export CLAUDECODE=0",
        "export CLAUDE_CODE_CHILD_SESSION=",
        "export -n CLAUDECODE",
        "declare -x CLAUDECODE=0",
        "sudo CLAUDECODE=0 ls",
        "cd x && CLAUDECODE=0 ls",
        "bash -c 'unset CLAUDECODE; ls'",
        "echo $(env -u CLAUDECODE ls)",
        "find . -exec env -u CLAUDECODE ls {} \\;",
    )
    TAMPER_ALLOWED = (
        "echo $CLAUDECODE",
        "printenv CLAUDECODE",
        "CLAUDECODE=1 rapid next",
        "export CLAUDECODE=1",
        "env -u HOME ls",
        "env FOO=1 ls",
        "unset FOO",
        "echo CLAUDECODE=0",
        "grep -r CLAUDE_CODE_CHILD_SESSION docs",
    )
    POWERSHELL_TAMPER_DENIED = (
        "Remove-Item Env:CLAUDE_CODE_CHILD_SESSION",
        "ri env:CLAUDECODE",
        "Remove-Item -Path Env:\\CLAUDECODE -ErrorAction SilentlyContinue",
        "$env:CLAUDECODE = ''",
        '$env:CLAUDE_CODE_CHILD_SESSION="0"',
        "$env:CLAUDECODE=$null",
        "[Environment]::SetEnvironmentVariable('CLAUDECODE', $null)",
        "Set-Item Env:CLAUDECODE 0",
        "Get-Date; $env:CLAUDECODE = 0; rapid next",
    )
    POWERSHELL_TAMPER_ALLOWED = (
        "$env:CLAUDECODE",
        "Get-ChildItem Env:",
        "$env:CLAUDECODE = '1'",
        "Remove-Item Env:FOO",
    )
    FIND_DENIED = (
        "find . -name x -exec rapid approve gate.x {} \\;",
        "find . -execdir rapid abort {} +",
        "find . -ok rapid evidence add x \\;",
        "find . -exec python -m rapid_os approve x \\;",
    )
    FIND_ALLOWED = (
        "find . -name '*.py' -exec grep rapid {} \\;",
        "find . -exec rapid status --json {} \\;",
        "find src -delete",
        "find . -type f -name '*.pyc' -delete",
    )
    HELP_ALLOWED = (
        "rapid approve --help",
        "rapid approve -h",
        "rapid approve gate.final-verification --help",
        "rapid abort --help",
        "rapid run gate --help",
        "python -m rapid_os approve --help",
        "cd x && rapid approve -h",
    )

    def assertTable(self, commands, *, denied, tool="Bash"):
        for command in commands:
            with self.subTest(command=command, denied=denied):
                decision = decide_pre_tool(bash(command, tool=tool), PROTECTED)
                if denied:
                    self.assertIsNotNone(decision, command)
                else:
                    self.assertIsNone(decision, command)

    def test_script_and_other_command_string_programs_are_shell_payloads(self):
        self.assertTable(self.SCRIPT_DENIED, denied=True)
        self.assertTable(self.SCRIPT_ALLOWED, denied=False)

    def test_review_bypass_command_is_denied_with_the_gate_command_for_the_person(self):
        command = self.SCRIPT_DENIED[0]
        self.assertIsNotNone(find_reserved_use(command))
        decision = decide_pre_tool(bash(command), PROTECTED)
        self.assertIsNotNone(decision)
        self.assertIn("`rapid approve gate.final-verification`", decision.reason)
        self.assertEqual(
            pre_tool_output(decision)["hookSpecificOutput"]["permissionDecision"], "deny"
        )

    def test_script_payload_is_analysed_inside_short_flag_clusters(self):
        for flags in ("-c", "-qc", "-qec", "-eqc", "-lc"):
            with self.subTest(flags=flags):
                use = find_reserved_use(f"script {flags} 'rapid approve gate.review' /dev/null")
                self.assertEqual(use.gate, "gate.review")

    def test_powershell_flags_are_not_mistaken_for_clusters(self):
        # -ExecutionPolicy contains a 'c' but is not a short cluster: the real -Command must still be read.
        command = 'powershell -NoProfile -ExecutionPolicy Bypass -Command "rapid approve gate.x"'
        self.assertIsNotNone(decide_pre_tool(bash(command, tool="PowerShell"), PROTECTED))

    def test_removing_or_redefining_the_agent_session_variables_is_denied(self):
        self.assertTable(self.TAMPER_DENIED, denied=True)
        self.assertTable(self.TAMPER_ALLOWED, denied=False)

    def test_powershell_environment_tampering_is_denied(self):
        self.assertTable(self.POWERSHELL_TAMPER_DENIED, denied=True, tool="PowerShell")
        self.assertTable(self.POWERSHELL_TAMPER_ALLOWED, denied=False, tool="PowerShell")

    def test_tamper_reason_points_to_rapid_next_and_names_the_variable(self):
        decision = decide_pre_tool(bash("env -u CLAUDE_CODE_CHILD_SESSION ls"), PROTECTED)
        self.assertIn("CLAUDE_CODE_CHILD_SESSION", decision.reason)
        self.assertIn("rapid next --json", decision.reason)
        self.assertEqual(find_env_tamper("CLAUDECODE=0 rapid next"), "CLAUDECODE")
        self.assertIsNone(find_env_tamper("CLAUDECODE=1 rapid next"))

    def test_find_exec_is_a_wrapper(self):
        self.assertTable(self.FIND_DENIED, denied=True)
        self.assertTable(self.FIND_ALLOWED, denied=False)

    def test_find_can_not_delete_or_exec_writes_inside_rapid_os(self):
        for command in ("find .rapid-os -delete", "find /proj/.rapid-os -name '*.json' -delete",
                        "find . -exec rm .rapid-os/x {} \\;"):
            with self.subTest(command=command):
                self.assertIsNotNone(find_protected_write(command, CWD, PROTECTED), command)
        self.assertIsNone(find_protected_write("find src -delete", CWD, PROTECTED))

    def test_help_for_reserved_commands_is_allowed(self):
        self.assertTable(self.HELP_ALLOWED, denied=False)

    def test_help_does_not_open_a_loophole_for_real_approvals(self):
        for command in (
            "rapid approve gate.x --reviewer me",
            "rapid approve gate.x && rapid approve --help",
            "rapid approve --help; rapid approve gate.x",
            "rapid approve --help | rapid approve gate.x",
        ):
            with self.subTest(command=command):
                self.assertIsNotNone(decide_pre_tool(bash(command), PROTECTED), command)


class ProjectResolutionTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.base = Path(self._tmp.name).resolve()
        self.repo = self.base / "repo"
        self.repo.mkdir()

    def tearDown(self):
        subprocess.run(["git", "worktree", "prune"], cwd=str(self.repo), capture_output=True)
        self._tmp.cleanup()

    def git(self, *args, cwd=None):
        return subprocess.run(["git", *args], cwd=str(cwd or self.repo), check=True, capture_output=True, text=True)

    def test_walks_up_from_a_nested_directory(self):
        (self.repo / ".rapid-os").mkdir()
        nested = self.repo / "src" / "pkg"
        nested.mkdir(parents=True)
        project = find_project(nested)
        self.assertEqual(project.root, self.repo)
        self.assertIsNone(project.workspace)

    def test_no_project_means_none(self):
        self.assertIsNone(find_project(self.base))
        self.assertIsNone(find_project(None))
        self.assertIsNone(find_project(""))

    def test_run_worktree_resolves_to_the_main_ledger(self):
        self.git("init", "-q")
        self.git("config", "user.name", "T")
        self.git("config", "user.email", "t@example.com")
        (self.repo / "a.txt").write_text("x", encoding="utf-8")
        self.git("add", ".")
        self.git("commit", "-qm", "init")
        worktree = self.base / "repo-run-001"
        self.git("worktree", "add", "-q", "-b", "rapid/run-001", str(worktree))
        rapid_dir = self.repo / ".rapid-os"
        rapid_dir.mkdir()
        save_session(
            rapid_dir,
            Session(active_run_id="run-001", mode="hardening", harness="claude", workspace_path=str(worktree)),
        )
        # The worktree carries its own (tracked) copy of .rapid-os: it must not win.
        (worktree / ".rapid-os").mkdir()
        inside = worktree / "src"
        inside.mkdir()

        project = find_project(inside)
        self.assertEqual(project.root, self.repo)
        self.assertEqual(project.workspace, worktree.resolve())
        protected = project.protected_dirs
        self.assertIn((self.repo / ".rapid-os").as_posix(), protected)
        self.assertIn((worktree / ".rapid-os").as_posix(), protected)

    def test_a_foreign_worktree_does_not_borrow_the_ledger(self):
        self.git("init", "-q")
        self.git("config", "user.name", "T")
        self.git("config", "user.email", "t@example.com")
        (self.repo / "a.txt").write_text("x", encoding="utf-8")
        self.git("add", ".")
        self.git("commit", "-qm", "init")
        other = self.base / "other-worktree"
        self.git("worktree", "add", "-q", "-b", "feature/x", str(other))
        rapid_dir = self.repo / ".rapid-os"
        rapid_dir.mkdir()
        save_session(rapid_dir, Session(active_run_id="r", mode="feature", harness="claude"))
        self.assertIsNone(find_project(other))


class SettingsMergeTests(unittest.TestCase):
    USER = {
        "theme": "dark",
        "permissions": {"allow": ["Bash(ls)"], "deny": []},
        "hooks": {
            "Stop": [{"hooks": [{"type": "command", "command": "echo user-stop"}]}],
            "PreToolUse": [{"matcher": "Bash", "hooks": [{"type": "command", "command": "user-check.sh"}]}],
            "PostToolUse": [{"matcher": "Edit", "hooks": [{"type": "command", "command": "fmt.sh"}]}],
        },
    }

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def write(self, data):
        path = self.root / ".claude" / "settings.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, indent=2), encoding="utf-8")
        return path

    def read(self):
        return json.loads((self.root / ".claude" / "settings.json").read_text(encoding="utf-8"))

    def test_fresh_install_creates_both_hooks(self):
        plan = claude_hooks.plan_install(self.root)
        self.assertEqual(plan.action, "create")
        claude_hooks.apply_plan(self.root, plan)
        hooks = self.read()["hooks"]
        stop = hooks["Stop"][0]["hooks"][0]
        self.assertEqual((stop["command"], stop["args"]), ("rapid", ["hook", "stop"]))
        pre = hooks["PreToolUse"][0]
        self.assertEqual(pre["hooks"][0]["args"], ["hook", "pre-tool"])
        for tool in ("Bash", "PowerShell", "Write", "Edit", "MultiEdit", "NotebookEdit"):
            self.assertIn(tool, pre["matcher"].split("|"))

    def test_merge_keeps_foreign_keys_and_hooks(self):
        self.write(self.USER)
        claude_hooks.apply_plan(self.root, claude_hooks.plan_install(self.root))
        merged = self.read()
        self.assertEqual(merged["theme"], "dark")
        self.assertEqual(merged["permissions"], self.USER["permissions"])
        self.assertEqual(merged["hooks"]["PostToolUse"], self.USER["hooks"]["PostToolUse"])
        self.assertEqual(merged["hooks"]["Stop"][0], self.USER["hooks"]["Stop"][0])
        self.assertEqual(merged["hooks"]["PreToolUse"][0], self.USER["hooks"]["PreToolUse"][0])
        self.assertEqual(len(merged["hooks"]["Stop"]), 2)
        self.assertEqual(len(merged["hooks"]["PreToolUse"]), 2)

    def test_install_twice_writes_nothing_the_second_time(self):
        self.write(self.USER)
        claude_hooks.apply_plan(self.root, claude_hooks.plan_install(self.root))
        before = (self.root / ".claude" / "settings.json").read_text(encoding="utf-8")
        baks = list((self.root / ".claude").glob("*.bak"))

        with mock.patch.object(claude_hooks, "safe_write_text") as writer:
            plan = claude_hooks.plan_install(self.root)
            changed = claude_hooks.apply_plan(self.root, plan)
        self.assertEqual(plan.action, "unchanged")
        self.assertFalse(changed)
        writer.assert_not_called()
        self.assertEqual((self.root / ".claude" / "settings.json").read_text(encoding="utf-8"), before)
        self.assertEqual(list((self.root / ".claude").glob("*.bak")), baks)

    def test_first_write_over_an_existing_file_keeps_a_backup(self):
        path = self.write(self.USER)
        claude_hooks.apply_plan(self.root, claude_hooks.plan_install(self.root))
        backups = list(path.parent.glob("settings.json.*.bak"))
        self.assertEqual(len(backups), 1)
        self.assertEqual(json.loads(backups[0].read_text(encoding="utf-8")), self.USER)

    def test_stale_own_handler_is_updated_in_place(self):
        stale = json.loads(json.dumps(self.USER))
        stale["hooks"]["Stop"].append(
            {"hooks": [{"type": "command", "command": "rapid", "args": ["hook", "stop"], "timeout": 999}]}
        )
        self.write(stale)
        plan = claude_hooks.plan_install(self.root)
        self.assertEqual(plan.action, "update")
        claude_hooks.apply_plan(self.root, plan)
        stops = self.read()["hooks"]["Stop"]
        self.assertEqual(len(stops), 2)
        self.assertEqual(stops[1]["hooks"][0]["timeout"], claude_hooks.HOOK_TIMEOUT_S)

    def test_remove_restores_the_users_settings(self):
        self.write(self.USER)
        claude_hooks.apply_plan(self.root, claude_hooks.plan_install(self.root))
        plan = claude_hooks.plan_remove(self.root)
        self.assertEqual(plan.action, "remove")
        claude_hooks.apply_plan(self.root, plan)
        self.assertEqual(self.read(), self.USER)

    def test_remove_only_touches_its_own_handlers(self):
        shared = json.loads(json.dumps(self.USER))
        shared["hooks"]["Stop"][0]["hooks"].append(
            {"type": "command", "command": "rapid", "args": ["hook", "stop"]}
        )
        shared["hooks"]["PreToolUse"].append(
            {"matcher": "Bash", "hooks": [{"type": "command", "command": "rapid", "args": ["status"]}]}
        )
        self.write(shared)
        claude_hooks.apply_plan(self.root, claude_hooks.plan_remove(self.root))
        result = self.read()
        self.assertEqual(result["hooks"]["Stop"][0]["hooks"], [{"type": "command", "command": "echo user-stop"}])
        self.assertEqual(result["hooks"]["PreToolUse"][1]["hooks"][0]["args"], ["status"])

    def test_remove_deletes_a_file_that_only_held_our_hooks(self):
        claude_hooks.apply_plan(self.root, claude_hooks.plan_install(self.root))
        claude_hooks.apply_plan(self.root, claude_hooks.plan_remove(self.root))
        self.assertFalse((self.root / ".claude" / "settings.json").exists())

    def test_remove_without_hooks_does_nothing(self):
        self.write(self.USER)
        plan = claude_hooks.plan_remove(self.root)
        self.assertEqual(plan.action, "absent")
        self.assertFalse(claude_hooks.apply_plan(self.root, plan))
        self.assertEqual(self.read(), self.USER)

    def test_unreadable_settings_are_reported_not_overwritten(self):
        path = self.root / ".claude" / "settings.json"
        for content in ("{not json", "[1, 2]", json.dumps({"hooks": []}), json.dumps({"hooks": {"Stop": {}}})):
            with self.subTest(content=content):
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(content, encoding="utf-8")
                with self.assertRaises(ShortcutError) as ctx:
                    claude_hooks.plan_install(self.root)
                self.assertEqual(ctx.exception.code, "RAPID1338")
                self.assertEqual(path.read_text(encoding="utf-8"), content)

    def test_hooks_installed_detection(self):
        self.assertFalse(claude_hooks.hooks_installed(self.root))
        self.write(self.USER)
        self.assertFalse(claude_hooks.hooks_installed(self.root))
        claude_hooks.apply_plan(self.root, claude_hooks.plan_install(self.root))
        self.assertTrue(claude_hooks.hooks_installed(self.root))


class HookCliTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def rapid(self, *args, input_str=None, env_extra=None):
        env = {k: v for k, v in os.environ.items() if k not in ("CLAUDECODE", "CLAUDE_CODE_CHILD_SESSION")}
        env["PYTHONPATH"] = str(ROOT)
        env.update(env_extra or {})
        return subprocess.run(
            [sys.executable, "-m", "rapid_os.cli.main", *args],
            cwd=str(self.root), input=input_str, capture_output=True, text=True, encoding="utf-8", env=env,
        )

    def tree(self):
        return sorted(p.relative_to(self.root).as_posix() for p in self.root.rglob("*") if p.is_file())

    def test_shortcuts_hooks_dry_run_json(self):
        res = self.rapid("shortcuts", "install", "--harness", "claude", "--hooks", "--dry-run", "--json")
        self.assertEqual(res.returncode, 0, res.stderr)
        payload = json.loads(res.stdout)
        self.assertEqual(payload["hooks"]["action"], "create")
        self.assertEqual(payload["hooks"]["path"], ".claude/settings.json")
        self.assertEqual(payload["hooks"]["events"], ["Stop", "PreToolUse"])
        self.assertEqual(self.tree(), [])

    def test_hooks_flag_is_optional_in_the_json_contract(self):
        res = self.rapid("shortcuts", "install", "--harness", "claude", "--dry-run", "--json")
        self.assertNotIn("hooks", json.loads(res.stdout))

    def test_install_and_remove_roundtrip(self):
        res = self.rapid("shortcuts", "install", "--harness", "claude", "--hooks")
        self.assertEqual(res.returncode, 0, res.stderr)
        settings = json.loads((self.root / ".claude" / "settings.json").read_text(encoding="utf-8"))
        self.assertIn("Stop", settings["hooks"])
        again = self.rapid("shortcuts", "install", "--harness", "claude", "--hooks", "--json")
        self.assertEqual(json.loads(again.stdout)["hooks"]["action"], "unchanged")
        res = self.rapid("shortcuts", "remove", "--harness", "claude", "--hooks")
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertFalse((self.root / ".claude" / "settings.json").exists())
        # Only the safety copy of the deleted settings file remains.
        self.assertEqual(len(self.tree()), 1)
        self.assertTrue(self.tree()[0].startswith(".claude/settings.json."))
        self.assertTrue(self.tree()[0].endswith(".bak"))

    def test_hooks_require_the_claude_harness(self):
        for verb in ("install", "remove"):
            with self.subTest(verb=verb):
                res = self.rapid("shortcuts", verb, "--harness", "codex", "--hooks")
                self.assertEqual(res.returncode, 1)
                self.assertIn("RAPID1337", res.stderr)
                self.assertNotIn("Traceback", res.stderr)
                self.assertEqual(self.tree(), [])

    def test_invalid_settings_json_is_rapid1338(self):
        (self.root / ".claude").mkdir()
        (self.root / ".claude" / "settings.json").write_text("{oops", encoding="utf-8")
        res = self.rapid("shortcuts", "install", "--harness", "claude", "--hooks")
        self.assertEqual(res.returncode, 1)
        self.assertIn("RAPID1338", res.stderr)
        self.assertEqual((self.root / ".claude" / "settings.json").read_text(encoding="utf-8"), "{oops")
        self.assertFalse((self.root / ".claude" / "skills").exists())

    def test_init_installs_hooks_only_with_the_explicit_flag(self):
        res = self.rapid("init", "--yes", "--no-scan", "--agents", "claude", "--shortcuts")
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertTrue((self.root / ".claude" / "skills" / "rapid-feature" / "SKILL.md").exists())
        self.assertFalse((self.root / ".claude" / "settings.json").exists())
        res = self.rapid("init", "--yes", "--no-scan", "--agents", "claude", "--hooks")
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertTrue((self.root / ".claude" / "settings.json").exists())

    def test_init_hooks_without_claude_warns_and_continues(self):
        res = self.rapid("init", "--yes", "--no-scan", "--agents", "codex", "--hooks")
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertIn("RAPID1337", res.stdout + res.stderr)
        self.assertFalse((self.root / ".claude" / "settings.json").exists())

    def test_doctor_warns_when_rapid_is_not_on_path(self):
        self.rapid("shortcuts", "install", "--harness", "claude", "--hooks")
        no_path = self.rapid("doctor", env_extra={"PATH": ""})
        self.assertIn("RAPID1339", no_path.stdout + no_path.stderr)
        self.rapid("shortcuts", "remove", "--harness", "claude", "--hooks")
        clean = self.rapid("doctor", env_extra={"PATH": ""})
        self.assertNotIn("RAPID1339", clean.stdout + clean.stderr)

    def test_non_json_stdin_and_no_project_are_silent(self):
        for stdin in ("not json at all", "", "[1,2,3]", '"text"'):
            for event in ("stop", "pre-tool"):
                with self.subTest(event=event, stdin=stdin):
                    res = self.rapid("hook", event, input_str=stdin)
                    self.assertEqual(res.returncode, 0)
                    self.assertEqual(res.stdout, "")

    def test_non_json_stdin_inside_a_project_is_logged(self):
        (self.root / ".rapid-os").mkdir()
        res = self.rapid("hook", "stop", input_str="garbage")
        self.assertEqual((res.returncode, res.stdout), (0, ""))
        log = (self.root / ".rapid-os" / "scratch" / "hooks.log").read_text(encoding="utf-8")
        self.assertIn("not valid JSON", log)

    def test_corrupt_rapid_os_is_silent_and_logged(self):
        rapid_dir = self.root / ".rapid-os"
        (rapid_dir / "runs" / "r1").mkdir(parents=True)
        (rapid_dir / "session.json").write_text("{corrupt", encoding="utf-8")
        (rapid_dir / "config.json").write_text("{corrupt", encoding="utf-8")
        (rapid_dir / "runs" / "r1" / "run.json").write_text("{corrupt", encoding="utf-8")
        payload = json.dumps({"session_id": "s", "cwd": str(self.root), "hook_event_name": "Stop"})
        for event, extra in (("stop", {}), ("pre-tool", {"tool_name": "Bash", "tool_input": {"command": "ls"}})):
            with self.subTest(event=event):
                body = json.dumps({**json.loads(payload), **extra})
                res = self.rapid("hook", event, input_str=body)
                self.assertEqual((res.returncode, res.stdout), (0, ""))
                self.assertNotIn("Traceback", res.stderr)

    def test_hook_without_a_subcommand_does_not_fail(self):
        res = self.rapid("hook")
        self.assertEqual(res.returncode, 0)
        self.assertIn("rapid hook", res.stderr)


class FeatureHookScenarioTests(LabScenarioBase):
    LAB = "feature"

    SPEC = {
        "title": "Booking availability",
        "business_objective": "Reject double bookings",
        "problem_statement": "Bookings can overlap",
        "acceptance_criteria": ["overlapping bookings are rejected"],
        "tasks": ["T001: Implement availability control"],
    }

    def hook(self, event, **payload):
        body = {"session_id": "sess-1", "cwd": str(self.project), **payload}
        res = self._rapid("hook", event, input_str=json.dumps(body))
        self.assertEqual(res.returncode, 0, res.stderr)
        return json.loads(res.stdout) if res.stdout.strip() else None

    def test_stop_follows_the_run_until_a_person_is_needed(self):
        self._start("feature", self.SPEC)

        blocked = self.hook("stop", hook_event_name="Stop", stop_hook_active=False)
        self.assertEqual(blocked["decision"], "block")
        self.assertIn("rapid task start T001", blocked["reason"])

        def implement(action):
            self._copy_solution("booking.py", "tests/test_booking.py")

        action, _ = self._drive(implement)
        self.assertEqual(action["kind"], "await_human_approval")
        self.assertIsNone(self.hook("stop", hook_event_name="Stop", stop_hook_active=False))

    def test_stop_guard_lets_the_agent_go_after_three_consecutive_blocks(self):
        self._start("feature", self.SPEC)
        results = [
            self.hook("stop", hook_event_name="Stop", stop_hook_active=attempt > 0) is not None
            for attempt in range(5)
        ]
        self.assertEqual(results, [True, True, True, False, False])
        state = json.loads((self.project / ".rapid-os" / "scratch" / "hooks.json").read_text(encoding="utf-8"))
        self.assertEqual(state["sessions"]["sess-1"]["count"], 3)

    def test_configured_cap_is_respected(self):
        config_path = self.project / ".rapid-os" / "config.json"
        config = json.loads(config_path.read_text(encoding="utf-8"))
        config["hooks"] = {"max_stop_blocks": 1}
        config_path.write_text(json.dumps(config), encoding="utf-8")
        self._start("feature", self.SPEC)
        first = self.hook("stop", hook_event_name="Stop", stop_hook_active=False)
        second = self.hook("stop", hook_event_name="Stop", stop_hook_active=True)
        self.assertIsNotNone(first)
        self.assertIsNone(second)

    def test_no_session_means_no_block(self):
        self.assertIsNone(self.hook("stop", hook_event_name="Stop"))

    def test_rapid_approve_is_denied_and_status_is_allowed_for_real(self):
        self._start("feature", self.SPEC)
        denied = self.hook(
            "pre-tool", hook_event_name="PreToolUse", tool_name="Bash",
            tool_input={"command": "rapid approve gate.final-verification"},
        )
        self.assertEqual(denied["hookSpecificOutput"]["permissionDecision"], "deny")
        evasion = self.hook(
            "pre-tool", hook_event_name="PreToolUse", tool_name="Bash",
            tool_input={"command": "cd x && VAR=1 python -m rapid_os approve gate.final-verification"},
        )
        self.assertEqual(evasion["hookSpecificOutput"]["permissionDecision"], "deny")
        pty_bypass = self.hook(
            "pre-tool", hook_event_name="PreToolUse", tool_name="Bash",
            tool_input={"command": "env -u CLAUDE_CODE_CHILD_SESSION -u CLAUDECODE script -qec "
                                   "'rapid approve gate.final-verification' /dev/null"},
        )
        self.assertEqual(pty_bypass["hookSpecificOutput"]["permissionDecision"], "deny")
        self.assertIsNone(self.hook(
            "pre-tool", hook_event_name="PreToolUse", tool_name="Bash",
            tool_input={"command": "rapid approve --help"},
        ))
        self.assertIsNone(self.hook(
            "pre-tool", hook_event_name="PreToolUse", tool_name="Bash",
            tool_input={"command": "rapid status --json"},
        ))
        edit = self.hook(
            "pre-tool", hook_event_name="PreToolUse", tool_name="Edit",
            tool_input={"file_path": str(self.project / ".rapid-os" / "config.json")},
        )
        self.assertEqual(edit["hookSpecificOutput"]["permissionDecision"], "deny")
        relative = self.hook(
            "pre-tool", hook_event_name="PreToolUse", tool_name="Write",
            tool_input={"file_path": ".rapid-os/specs/x.json"},
        )
        self.assertEqual(relative["hookSpecificOutput"]["permissionDecision"], "deny")
        self.assertIsNone(self.hook(
            "pre-tool", hook_event_name="PreToolUse", tool_name="Write",
            tool_input={"file_path": str(self.project / "booking.py")},
        ))

    def test_a_rejected_review_does_not_make_the_agent_abort(self):
        self._start("feature", self.SPEC)

        def implement(action):
            self._copy_solution("booking.py", "tests/test_booking.py")

        self._drive(implement)
        res = self._rapid_tty(
            ["approve", "gate.final-verification", "--reject", "--reason", "needs work"],
            "rechazar gate.final-verification",
        )
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertEqual(self._next()["command"], ["rapid", "abort"])
        self.assertIsNone(self.hook("stop", hook_event_name="Stop", stop_hook_active=False))


class HardeningWorktreeHookTests(LabScenarioBase):
    LAB = "hardening"
    ARCHETYPE = "corporate"

    SPEC = {
        "title": "Validate profile inputs",
        "business_objective": "Reject hostile input",
        "problem_statement": "register_user accepts anything",
        "acceptance_criteria": ["H001: invalid usernames are rejected (CWE-20)"],
        "findings": [{
            "id": "H001", "title": "Reject hostile usernames", "cwe": "CWE-20",
            "cvss_v4_vector": "CVSS:4.0/AV:N/AC:L/AT:N/PR:N/UI:P/VC:L/VI:L/VA:N/SC:N/SI:N/SA:N",
            "severity": "medium", "standard_ref": "CVSS v4.0",
        }],
        "tasks": ["T001: Add defensive validation"],
    }

    def hook(self, event, cwd, **payload):
        body = {"session_id": "sess-w", "cwd": str(cwd), **payload}
        res = self._rapid("hook", event, input_str=json.dumps(body))
        self.assertEqual(res.returncode, 0, res.stderr)
        return json.loads(res.stdout) if res.stdout.strip() else None

    def test_hooks_invoked_from_inside_the_worktree_use_the_main_ledger(self):
        self._start("hardening", self.SPEC, "--worktree")
        session = json.loads((self.project / ".rapid-os" / "session.json").read_text(encoding="utf-8"))
        workspace = Path(session["workspace_path"])
        nested = workspace / "tests"
        self.assertTrue(nested.is_dir())

        blocked = self.hook("stop", nested, hook_event_name="Stop")
        self.assertEqual(blocked["decision"], "block")
        self.assertIn("rapid task start T001", blocked["reason"])
        # The guard state lives in the main ledger, not in the worktree.
        self.assertTrue((self.project / ".rapid-os" / "scratch" / "hooks.json").exists())

        denied = self.hook(
            "pre-tool", nested, hook_event_name="PreToolUse", tool_name="Bash",
            tool_input={"command": "rapid approve gate.review"},
        )
        self.assertEqual(denied["hookSpecificOutput"]["permissionDecision"], "deny")
        for target in (self.project / ".rapid-os" / "runs" / "x.json", workspace / ".rapid-os" / "x.json"):
            with self.subTest(target=target):
                out = self.hook(
                    "pre-tool", nested, hook_event_name="PreToolUse", tool_name="Write",
                    tool_input={"file_path": str(target)},
                )
                self.assertEqual(out["hookSpecificOutput"]["permissionDecision"], "deny")
        self.assertIsNone(self.hook(
            "pre-tool", nested, hook_event_name="PreToolUse", tool_name="Write",
            tool_input={"file_path": str(workspace / "profile_mgr.py")},
        ))


if __name__ == "__main__":
    unittest.main()
