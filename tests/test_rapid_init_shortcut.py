"""`/rapid-init`, the human-approval wording of the mode shortcuts and `shortcuts install --global`."""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from rapid_os.adapters import shortcut_installer as installer
from rapid_os.adapters.agents import DEFAULT_AGENT_REGISTRY
from rapid_os.core.ancestry import AncestryResult
from rapid_os.domain.shortcuts import MODE_SHORTCUTS, SHORTCUT_NAMES
from rapid_os.orchestration.lifecycle import execute_approve

ROOT = Path(__file__).resolve().parents[1]
TEMPLATES = ROOT / "templates"
HARNESSES = ("claude", "codex", "antigravity", "cursor", "vscode")
APPROVAL_SHORTCUTS = (*MODE_SHORTCUTS, "rapid-next", "rapid-approve")


def rapid(cwd, *argv, stdin=None, home=None):
    env = {**os.environ, "CLAUDECODE": "", "CLAUDE_CODE_CHILD_SESSION": "", "PYTHONPATH": str(ROOT), "PYTHONIOENCODING": "utf-8"}
    if home is not None:
        env.update(HOME=str(home), USERPROFILE=str(home))
    return subprocess.run(
        [sys.executable, "-m", "rapid_os.cli.main", *argv],
        cwd=cwd, input=stdin, capture_output=True, text=True, encoding="utf-8", env=env,
    )


def files_under(root: Path) -> list[str]:
    return sorted(p.relative_to(root).as_posix() for p in root.rglob("*") if p.is_file())


class RapidInitTemplateTests(unittest.TestCase):
    def setUp(self):
        self.templates = {t.name: t for t in installer.load_templates(TEMPLATES)}

    def test_rapid_init_is_a_utility_shortcut_listed_first(self):
        self.assertEqual(SHORTCUT_NAMES[0], "rapid-init")
        self.assertNotIn("rapid-init", MODE_SHORTCUTS)
        template = self.templates["rapid-init"]
        self.assertIsNone(template.mode)
        self.assertEqual(template.context_command, "rapid setup next --json")
        self.assertEqual(template.allowed_commands, ("setup",))

    def test_body_only_mentions_allowed_commands_plus_next_and_rapid_feature(self):
        template = self.templates["rapid-init"]
        allowed = set(template.allowed_commands) | {"next"}
        mentioned = set(re.findall(r"\brapid\s+([a-z][a-z-]*)", template.body))
        self.assertTrue(mentioned, "the body must name the rapid setup commands")
        self.assertLessEqual(mentioned, allowed, f"commands outside allowed-commands: {mentioned - allowed}")
        self.assertNotIn("rapid init", template.body)

    def test_body_covers_the_onboarding_loop(self):
        body = self.templates["rapid-init"].body
        for needle in (
            "rapid setup next --json", "action.kind", "action.command", "alt_command", "recommended",
            "questions", "notes", "legacy_source", "--source drafted", "--source provided",
            "SOLO si la persona dice explícitamente", "unconfirmed_docs", "/rapid-feature",
            "Nunca edites `.rapid-os/` ni `docs/`",
        ):
            with self.subTest(needle=needle):
                self.assertIn(needle, body)

    def test_rendered_for_every_harness_and_only_claude_runs_the_context_command(self):
        for harness in HARNESSES:
            outputs = DEFAULT_AGENT_REGISTRY.get(harness).shortcut_outputs(list(self.templates.values()))
            rendered = {p.as_posix(): c for p, c in outputs.items() if "rapid-init" in p.as_posix()}
            with self.subTest(harness=harness):
                self.assertEqual(len(rendered), 1)
                content = next(iter(rendered.values()))
                self.assertEqual("!`rapid setup next --json`" in content, harness == "claude")
                self.assertIn("rapid setup next --json", content)


class ApprovalWordingTests(unittest.TestCase):
    def setUp(self):
        self.templates = {t.name: t for t in installer.load_templates(TEMPLATES)}

    def test_mode_shortcuts_ask_for_approval_only_on_await_human_approval(self):
        for name in APPROVAL_SHORTCUTS:
            body = self.templates[name].body
            with self.subTest(shortcut=name):
                self.assertIn("otra terminal", body)
                self.assertNotIn("`!", body)
                self.assertNotIn("puede variar", body)
                if name != "rapid-approve":
                    self.assertIn("solo cuando action.kind sea await_human_approval", body)
                    self.assertIn("ignora awaiting_human", body)
                    self.assertIn("rapid approve gate.final-verification", body)

    def test_no_rendered_shortcut_suggests_the_bang_prefix(self):
        for harness in HARNESSES:
            outputs = DEFAULT_AGENT_REGISTRY.get(harness).shortcut_outputs(list(self.templates.values()))
            for path, content in outputs.items():
                if any(name in path.as_posix() for name in APPROVAL_SHORTCUTS):
                    with self.subTest(harness=harness, path=path.as_posix()):
                        self.assertNotIn("`!", content)
                        self.assertNotIn("puede variar", content)


class InstallInAnEmptyFolderTests(unittest.TestCase):
    def test_install_writes_only_shortcut_files_for_each_harness(self):
        templates = installer.load_templates(TEMPLATES)
        available, _skipped = installer.split_available(templates, TEMPLATES)
        for harness in HARNESSES:
            with self.subTest(harness=harness), tempfile.TemporaryDirectory() as tmp:
                result = rapid(tmp, "shortcuts", "install", "--harness", harness)
                self.assertEqual(result.returncode, 0, result.stderr)
                expected = sorted(p.as_posix() for p in DEFAULT_AGENT_REGISTRY.get(harness).shortcut_outputs(available))
                self.assertEqual(files_under(Path(tmp)), expected)
                self.assertTrue(any("rapid-init" in name for name in expected))
                self.assertFalse((Path(tmp) / ".rapid-os").exists())


class GlobalInstallTests(unittest.TestCase):
    def setUp(self):
        self._home = tempfile.TemporaryDirectory()
        self._cwd = tempfile.TemporaryDirectory()
        self.addCleanup(self._home.cleanup)
        self.addCleanup(self._cwd.cleanup)
        self.home = Path(self._home.name)
        self.cwd = Path(self._cwd.name)

    def install(self, *argv):
        return rapid(self.cwd, "shortcuts", "install", "--global", *argv, home=self.home)

    def test_harness_without_a_documented_user_folder_is_rejected_and_nothing_is_written(self):
        result = self.install("--harness", "vscode", "--only", "rapid-init")
        self.assertEqual(result.returncode, 1)
        self.assertIn("RAPID1413", result.stderr)
        self.assertIn("vscode", result.stderr)
        self.assertNotIn("Traceback", result.stderr)
        self.assertEqual(files_under(self.home), [])
        self.assertEqual(files_under(self.cwd), [])

    def test_one_unsupported_harness_blocks_the_whole_selection(self):
        result = self.install("--harness", "claude", "--harness", "vscode", "--only", "rapid-init")
        self.assertEqual(result.returncode, 1)
        self.assertEqual(files_under(self.home), [])

    def test_documented_harnesses_write_under_the_home_folder_only(self):
        expected = {
            "claude": ".claude/skills/rapid-init/SKILL.md",
            "codex": ".agents/skills/rapid-init/SKILL.md",
            "cursor": ".cursor/skills/rapid-init/SKILL.md",
            "antigravity": ".gemini/config/skills/rapid-init/SKILL.md",
        }
        for harness, relative in expected.items():
            with self.subTest(harness=harness):
                result = self.install("--harness", harness, "--only", "rapid-init", "--json")
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(json.loads(result.stdout)["scope"], "global")
                self.assertTrue((self.home / relative).is_file())
        self.assertEqual(files_under(self.cwd), [])
        self.assertEqual(len(files_under(self.home)), 4)

    def test_only_limits_the_files_and_an_unknown_name_is_rapid1413(self):
        self.assertEqual(self.install("--harness", "claude").returncode, 0)
        self.assertEqual(len(files_under(self.home)), len(SHORTCUT_NAMES))
        bad = self.install("--harness", "claude", "--only", "rapid-nope")
        self.assertEqual(bad.returncode, 1)
        self.assertIn("RAPID1413", bad.stderr)

    def test_global_needs_a_harness_and_refuses_hooks(self):
        for argv in ((), ("--harness", "claude", "--hooks")):
            with self.subTest(argv=argv):
                result = self.install(*argv)
                self.assertEqual(result.returncode, 1)
                self.assertIn("RAPID1413", result.stderr)
                self.assertEqual(files_under(self.home), [])

    def test_list_and_remove_work_on_the_global_folder(self):
        self.install("--harness", "claude", "--only", "rapid-init")
        listed = rapid(self.cwd, "shortcuts", "list", "--global", "--harness", "claude", "--only", "rapid-init", "--json", home=self.home)
        self.assertEqual([e["state"] for e in json.loads(listed.stdout)["shortcuts"]], ["installed"])
        removed = rapid(self.cwd, "shortcuts", "remove", "--global", "--harness", "claude", "--only", "rapid-init", home=self.home)
        self.assertEqual(removed.returncode, 0, removed.stderr)
        self.assertEqual(files_under(self.home), [])


class ApproveWithOpenTasksTests(unittest.TestCase):
    def test_in_progress_task_gets_rapid1014_and_a_human_sentence(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for argv in (("init",), ("config", "user.name", "Rapid"), ("config", "user.email", "r@example.com")):
                subprocess.run(["git", *argv], cwd=root, check=True, capture_output=True)
            (root / "a.py").write_text("x = 1\n", encoding="utf-8")
            subprocess.run(["git", "add", "."], cwd=root, check=True, capture_output=True)
            subprocess.run(["git", "commit", "-q", "-m", "base"], cwd=root, check=True, capture_output=True)
            self.assertEqual(rapid(root, "init", "--yes", "--test-command", f'"{sys.executable}" -c pass').returncode, 0)
            spec = {
                "title": "Open task", "mode": "feature", "business_objective": "o", "problem_statement": "p",
                "scope": ["s"], "acceptance_criteria": ["c"], "tasks": ["T001: do it"],
            }
            started = rapid(root, "start", "feature", "--spec-file", "-", "--json", stdin=json.dumps(spec))
            self.assertEqual(started.returncode, 0, started.stderr)
            output = json.loads(rapid(root, "next", "--json").stdout)
            nxt = output["action"]
            self.assertEqual(nxt["kind"], "implement_task")
            self.assertTrue(output["awaiting_human"], "the contract lists its human gates from the start")
            gate = output["awaiting_human"][0]
            if nxt.get("command"):  # `rapid task start T001`: the task is in progress now
                self.assertEqual(rapid(root, *nxt["command"][1:]).returncode, 0)

            code, message = execute_approve(
                root, root / ".rapid-os", gate, reviewer="Rapid",
                is_tty=True, environ={}, ancestry=AncestryResult(()),
                input_func=lambda _prompt: "aprobar " + gate,
            )
            self.assertEqual(code, 1)
            self.assertIn("RAPID1014", message)
            self.assertIn("T001 sigue en curso; espera a que el agente ejecute `rapid task done T001`.", message)


if __name__ == "__main__":
    unittest.main()
