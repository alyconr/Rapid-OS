"""Tests for generated `/rapid-<modo>` harness shortcuts.

Golden files live in tests/golden/shortcuts/<harness>/<relative path>. Regenerate them after
an intentional template change with:  RAPID_UPDATE_GOLDEN=1 python -m unittest tests.test_shortcuts
"""

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

from rapid_os.adapters import shortcut_installer as installer
from rapid_os.adapters.agents import DEFAULT_AGENT_REGISTRY
from rapid_os.domain.shortcuts import GENERATED_MARKER, SHORTCUT_NAMES

ROOT = Path(__file__).resolve().parents[1]
TEMPLATES = ROOT / "templates"
GOLDEN = ROOT / "tests" / "golden" / "shortcuts"
HARNESSES = ("claude", "codex", "antigravity", "cursor", "vscode")
MODE_SHORTCUTS = ("rapid-feature", "rapid-bugfix", "rapid-refactor", "rapid-hardening", "rapid-research")


def tree(root: Path) -> dict[str, str]:
    return {
        p.relative_to(root).as_posix(): p.read_text(encoding="utf-8")
        for p in sorted(root.rglob("*"))
        if p.is_file()
    }


class ShortcutRenderingTests(unittest.TestCase):
    def setUp(self):
        self.templates = installer.load_templates(TEMPLATES)

    def test_one_template_per_shortcut(self):
        self.assertEqual(tuple(t.name for t in self.templates), SHORTCUT_NAMES)
        self.assertEqual(len(SHORTCUT_NAMES), 8)

    def test_golden_files_per_harness_and_shortcut(self):
        update = os.environ.get("RAPID_UPDATE_GOLDEN") == "1"
        for harness in HARNESSES:
            outputs = DEFAULT_AGENT_REGISTRY.get(harness).shortcut_outputs(self.templates)
            self.assertEqual(len(outputs), 8, harness)
            for relative, content in outputs.items():
                golden = GOLDEN / harness / relative
                with self.subTest(harness=harness, path=relative.as_posix()):
                    if update:
                        golden.parent.mkdir(parents=True, exist_ok=True)
                        golden.write_text(content, encoding="utf-8", newline="\n")
                    self.assertTrue(golden.is_file(), f"missing golden {golden}")
                    self.assertEqual(content, golden.read_text(encoding="utf-8").replace("\r\n", "\n"))

    def test_marker_follows_frontmatter(self):
        for harness in HARNESSES:
            for relative, content in DEFAULT_AGENT_REGISTRY.get(harness).shortcut_outputs(self.templates).items():
                with self.subTest(harness=harness, path=relative.as_posix()):
                    _, frontmatter, rest = content.split("---\n", 2)
                    self.assertTrue(frontmatter.strip())
                    self.assertTrue(rest.startswith(GENERATED_MARKER + "\n"))

    def test_only_claude_injects_the_command_line(self):
        for harness in HARNESSES:
            outputs = DEFAULT_AGENT_REGISTRY.get(harness).shortcut_outputs(self.templates)
            feature = next(c for p, c in outputs.items() if "rapid-feature" in p.as_posix())
            with self.subTest(harness=harness):
                if harness == "claude":
                    self.assertIn("!`rapid next --json`", feature)
                else:
                    self.assertNotIn("!`", feature)
                    self.assertIn("ejecuta `rapid next --json`", feature)

    def test_mode_bodies_teach_only_the_loop(self):
        for template in self.templates:
            if template.mode is None:
                continue
            with self.subTest(shortcut=template.name):
                for plumbing in ("rapid run ", "rapid spec ", "rapid policy", "rapid evidence add`", "rapid harness"):
                    self.assertNotIn(
                        plumbing,
                        template.body.replace("`rapid run gate`", "").replace("`rapid evidence add`", ""),
                    )
                self.assertIn(f"rapid start {template.mode} --spec-file -", template.body)
                self.assertIn("rapid check -- <comando>", template.body)

    def test_agents_never_pre_approve_human_gate_commands(self):
        outputs = DEFAULT_AGENT_REGISTRY.get("claude").shortcut_outputs(self.templates)
        for relative, content in outputs.items():
            allowed = [l for l in content.splitlines() if l.startswith("allowed-tools:")]
            with self.subTest(path=relative.as_posix()):
                for line in allowed:
                    for forbidden in ("approve", "evidence", "run"):
                        self.assertNotIn(f"rapid {forbidden}", line)

    def test_approve_disables_model_invocation_where_supported(self):
        for harness, expected in (("claude", True), ("cursor", True), ("codex", False), ("vscode", False)):
            outputs = DEFAULT_AGENT_REGISTRY.get(harness).shortcut_outputs(self.templates)
            for relative, content in outputs.items():
                is_approve = "rapid-approve" in relative.as_posix()
                with self.subTest(harness=harness, path=relative.as_posix()):
                    self.assertEqual("disable-model-invocation: true" in content, is_approve and expected)

    def test_default_adapter_has_no_shortcuts(self):
        from rapid_os.adapters.agents.base import AgentAdapter

        class Bare(AgentAdapter):
            id = "bare"
            name = "Bare"

            def render(self, context):
                return {}

        self.assertEqual(dict(Bare().shortcut_outputs(self.templates)), {})


class ShortcutInstallerTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def plan(self, harnesses=("claude", "codex"), templates_dir=TEMPLATES):
        return installer.build_plan(self.root, harnesses, templates_dir)

    def test_every_mode_shortcut_is_generated_when_all_playbooks_exist(self):
        plan = self.plan(("claude",))
        self.assertEqual({f.shortcut for f in plan.files}, set(SHORTCUT_NAMES))
        self.assertEqual(plan.skipped, ())

    def test_only_modes_with_a_playbook_are_generated(self):
        templates = self.root / "tpl"
        shutil.copytree(TEMPLATES / "shortcuts", templates / "shortcuts")
        (templates / "modes").mkdir()
        shutil.copy(TEMPLATES / "modes" / "feature.json", templates / "modes" / "feature.json")

        plan = installer.build_plan(self.root, ("claude",), templates)
        names = {f.shortcut for f in plan.files}
        self.assertEqual(names, {"rapid-feature", "rapid-next", "rapid-status", "rapid-approve"})
        self.assertEqual(
            sorted(s.shortcut for s in plan.skipped),
            ["rapid-bugfix", "rapid-hardening", "rapid-refactor", "rapid-research"],
        )
        self.assertTrue(all(s.code == "RAPID1315" for s in plan.skipped))

    def test_install_after_new_playbook_adds_the_missing_shortcut(self):
        templates = self.root / "tpl"
        shutil.copytree(TEMPLATES / "shortcuts", templates / "shortcuts")
        (templates / "modes").mkdir()
        shutil.copy(TEMPLATES / "modes" / "feature.json", templates / "modes" / "feature.json")
        project = self.root / "project"
        project.mkdir()

        first = installer.build_plan(project, ("claude",), templates)
        installer.apply_plan(project, first)
        self.assertFalse((project / ".claude/skills/rapid-bugfix").exists())

        playbook = json_playbook("bugfix")
        (templates / "modes" / "bugfix.json").write_text(playbook, encoding="utf-8")
        second = installer.build_plan(project, ("claude",), templates)
        actions = {f.shortcut: f.action for f in second.files}
        self.assertEqual(actions["rapid-bugfix"], "create")
        self.assertEqual(actions["rapid-feature"], "unchanged")
        self.assertEqual(sum(1 for s in second.skipped if s.shortcut == "rapid-bugfix"), 0)

    def test_install_twice_writes_nothing_the_second_time(self):
        installer.apply_plan(self.root, self.plan())
        before = tree(self.root)

        with mock.patch.object(installer, "safe_write_text") as writer:
            second = self.plan()
            written = installer.apply_plan(self.root, second)

        writer.assert_not_called()
        self.assertEqual(written, ())
        self.assertTrue(all(f.action == "unchanged" for f in second.files))
        self.assertEqual(tree(self.root), before)
        self.assertFalse(any(p.suffix == ".bak" for p in self.root.rglob("*")))

    def test_dry_run_plan_writes_nothing(self):
        plan = self.plan(("claude", "codex", "cursor", "vscode"))
        self.assertTrue(plan.files)
        self.assertEqual(tree(self.root), {})

    def test_different_content_is_backed_up(self):
        installer.apply_plan(self.root, self.plan(("claude",)))
        target = self.root / ".claude/skills/rapid-feature/SKILL.md"
        edited = target.read_text(encoding="utf-8") + "\nedited by hand\n"
        target.write_text(edited, encoding="utf-8")

        plan = self.plan(("claude",))
        self.assertEqual({f.shortcut: f.action for f in plan.files}["rapid-feature"], "update")
        installer.apply_plan(self.root, plan)

        backups = list(target.parent.glob("SKILL.md.*.bak"))
        self.assertEqual(len(backups), 1)
        self.assertEqual(backups[0].read_text(encoding="utf-8"), edited)
        self.assertNotIn("edited by hand", target.read_text(encoding="utf-8"))

    def test_existing_file_without_marker_warns_before_replacing(self):
        target = self.root / ".claude/skills/rapid-feature/SKILL.md"
        target.parent.mkdir(parents=True)
        target.write_text("my own skill\n", encoding="utf-8")

        plan = self.plan(("claude",))
        self.assertTrue(any(w.startswith("RAPID1316") for w in plan.warnings))
        installer.apply_plan(self.root, plan)
        self.assertEqual(len(list(target.parent.glob("SKILL.md.*.bak"))), 1)

    def test_codex_and_antigravity_share_agents_skills_once(self):
        plan = self.plan(("codex", "antigravity"))
        self.assertEqual(len(plan.files), 8)
        for planned in plan.files:
            self.assertTrue(planned.path.as_posix().startswith(".agents/skills/"))
            self.assertEqual(planned.harnesses, ("antigravity", "codex"))  # registry order

        with mock.patch.object(installer, "safe_write_text", wraps=installer.safe_write_text) as writer:
            installer.apply_plan(self.root, plan)
        self.assertEqual(writer.call_count, 8)

    def test_remove_only_deletes_marked_files(self):
        installer.apply_plan(self.root, self.plan(("claude", "codex")))
        own = self.root / ".claude/skills/rapid-next/SKILL.md"
        own.write_text("mine, no marker\n", encoding="utf-8")

        entries = installer.plan_removal(self.root, ("claude", "codex", "cursor"), TEMPLATES)
        actions = {e.path.as_posix(): e.action for e in entries}
        self.assertEqual(actions[".claude/skills/rapid-next/SKILL.md"], "skip_unmarked")
        self.assertEqual(actions[".claude/skills/rapid-feature/SKILL.md"], "remove")
        self.assertEqual(actions[".cursor/skills/rapid-feature/SKILL.md"], "absent")

        installer.apply_removal(self.root, entries)
        self.assertEqual(own.read_text(encoding="utf-8"), "mine, no marker\n")
        self.assertFalse((self.root / ".claude/skills/rapid-feature").exists())
        self.assertFalse((self.root / ".agents/skills/rapid-feature").exists())
        self.assertTrue((self.root / ".claude/skills").is_dir())

    def test_remove_dry_run_changes_nothing(self):
        installer.apply_plan(self.root, self.plan(("vscode",)))
        before = tree(self.root)
        entries = installer.plan_removal(self.root, ("vscode",), TEMPLATES)
        self.assertTrue(any(e.action == "remove" for e in entries))
        self.assertEqual(tree(self.root), before)

    def test_harness_resolution(self):
        registry_ids = DEFAULT_AGENT_REGISTRY.ids()
        self.assertEqual(
            installer.resolve_harness_ids(None, ["context7", "codex", "claude", "firecrawl"]),
            tuple(h for h in registry_ids if h in {"codex", "claude"}),
        )
        with self.assertRaises(installer.ShortcutError) as ctx:
            installer.resolve_harness_ids(["nope"], None)
        self.assertEqual(ctx.exception.code, "RAPID1311")
        with self.assertRaises(installer.ShortcutError) as ctx:
            installer.resolve_harness_ids(None, ["context7"])
        self.assertEqual(ctx.exception.code, "RAPID1312")

    def test_corrupt_template_is_reported_with_code(self):
        templates = self.root / "tpl"
        shutil.copytree(TEMPLATES / "shortcuts", templates / "shortcuts")
        (templates / "shortcuts" / "rapid-next.md").write_text("no frontmatter", encoding="utf-8")
        with self.assertRaises(installer.ShortcutError) as ctx:
            installer.load_templates(templates)
        self.assertEqual(ctx.exception.code, "RAPID1313")


def json_playbook(mode: str) -> str:
    data = json.loads((TEMPLATES / "modes" / "feature.json").read_text(encoding="utf-8"))
    data["mode"] = mode
    return json.dumps(data)


class ShortcutCliTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def rapid(self, *args, input_str=None, extra_env=None):
        env = {k: v for k, v in os.environ.items() if k not in ("CLAUDECODE", "CLAUDE_CODE_CHILD_SESSION")}
        env["PYTHONPATH"] = str(ROOT)
        env.update(extra_env or {})
        return subprocess.run(
            [sys.executable, "-m", "rapid_os.cli.main", *args],
            cwd=str(self.root),
            input=input_str,
            capture_output=True,
            text=True,
            encoding="utf-8",
            env=env,
        )

    def test_dry_run_json_lists_files_and_writes_nothing(self):
        result = self.rapid("shortcuts", "install", "--harness", "claude", "--harness", "codex", "--dry-run", "--json")
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertTrue(payload["dry_run"])
        self.assertEqual(payload["harnesses"], ["claude", "codex"])
        paths = {f["path"] for f in payload["files"]}
        self.assertIn(".claude/skills/rapid-feature/SKILL.md", paths)
        self.assertIn(".agents/skills/rapid-feature/SKILL.md", paths)
        self.assertIn(".claude/skills/rapid-bugfix/SKILL.md", paths)
        self.assertEqual(payload["skipped"], [])
        self.assertEqual(tree(self.root), {})

    def test_install_list_remove_roundtrip(self):
        first = self.rapid("shortcuts", "install", "--harness", "claude", "--json")
        self.assertEqual(first.returncode, 0, first.stderr)
        self.assertTrue((self.root / ".claude/skills/rapid-feature/SKILL.md").is_file())

        second = self.rapid("shortcuts", "install", "--harness", "claude", "--json")
        self.assertTrue(all(f["action"] == "unchanged" for f in json.loads(second.stdout)["files"]))

        listed = json.loads(self.rapid("shortcuts", "list", "--harness", "claude", "--json").stdout)
        self.assertTrue(all(e["state"] == "installed" for e in listed["shortcuts"]))
        self.assertEqual(listed["skipped"], [])
        self.assertEqual(len(listed["shortcuts"]), 8)

        removed = self.rapid("shortcuts", "remove", "--harness", "claude", "--json")
        self.assertEqual(removed.returncode, 0, removed.stderr)
        self.assertEqual(tree(self.root), {})

    def test_defaults_to_tools_in_config(self):
        (self.root / ".rapid-os").mkdir()
        (self.root / ".rapid-os" / "config.json").write_text(
            json.dumps({"tools": ["cursor", "context7"]}), encoding="utf-8"
        )
        result = self.rapid("shortcuts", "install", "--dry-run", "--json")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["harnesses"], ["cursor"])

    def test_expected_errors_use_codes_and_exit_1(self):
        for args, code in (
            (("shortcuts", "install", "--harness", "nope"), "RAPID1311"),
            (("shortcuts", "install"), "RAPID1312"),
            (("shortcuts",), "RAPID1318"),
        ):
            with self.subTest(code=code):
                result = self.rapid(*args)
                self.assertEqual(result.returncode, 1)
                self.assertIn(code, result.stderr)
                self.assertNotIn("Traceback", result.stderr)

    def test_init_does_not_install_unattended_without_flag(self):
        result = self.rapid("init", "--yes", "--agents", "claude", "--no-scan")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse((self.root / ".claude" / "skills").exists())

    def test_init_shortcuts_flag_installs_for_selected_agents(self):
        result = self.rapid("init", "--yes", "--agents", "claude", "--no-scan", "--shortcuts")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue((self.root / ".claude/skills/rapid-feature/SKILL.md").is_file())


if __name__ == "__main__":
    unittest.main()
