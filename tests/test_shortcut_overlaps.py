"""RAPID1321: warn when a harness selection leaves the same /rapid-* in two folders one tool reads."""

from __future__ import annotations

import itertools
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from rapid_os.adapters.agents import DEFAULT_AGENT_REGISTRY
from rapid_os.adapters.shortcut_installer import load_templates
from rapid_os.domain import shortcuts as shortcuts_domain
from rapid_os.domain.shortcuts import (
    HARNESS_FOLDERS,
    TOOL_READ_FOLDERS,
    detect_folder_overlaps,
)

ROOT = Path(__file__).resolve().parents[1]
ALL = ("claude", "codex", "antigravity", "cursor", "vscode")
READERS = ("cursor", "vscode")
WRITERS_READ_BY_BOTH = ("claude", "codex", "antigravity")


def summary(overlaps):
    return [(o.reader, o.harnesses, o.folders) for o in overlaps]


class DetectFolderOverlapsTests(unittest.TestCase):
    def test_every_harness_alone_has_no_overlap(self):
        for harness in ALL:
            with self.subTest(harness=harness):
                self.assertEqual(detect_folder_overlaps([harness]), [])

    def test_every_reader_with_every_writer_overlaps_once(self):
        for reader, writer in itertools.product(READERS, WRITERS_READ_BY_BOTH):
            with self.subTest(reader=reader, writer=writer):
                overlaps = detect_folder_overlaps([reader, writer])
                self.assertEqual(
                    summary(overlaps),
                    [(reader, (reader, writer), (HARNESS_FOLDERS[reader], HARNESS_FOLDERS[writer]))],
                )
                # Order of the selection does not matter.
                self.assertEqual(summary(detect_folder_overlaps([writer, reader])), summary(overlaps))

    def test_cursor_and_vscode_alone_do_not_overlap(self):
        # VS Code does not read .cursor/skills and Cursor does not read .github/prompts.
        self.assertEqual(detect_folder_overlaps(["cursor", "vscode"]), [])
        self.assertNotIn(".cursor/skills", TOOL_READ_FOLDERS["vscode"])
        self.assertNotIn(".github/prompts", TOOL_READ_FOLDERS["cursor"])

    def test_codex_and_antigravity_share_one_folder_and_do_not_overlap(self):
        self.assertEqual(HARNESS_FOLDERS["codex"], HARNESS_FOLDERS["antigravity"])
        self.assertEqual(detect_folder_overlaps(["codex", "antigravity"]), [])

    def test_a_reader_with_both_agents_folder_harnesses_is_one_overlap(self):
        overlaps = detect_folder_overlaps(["cursor", "codex", "antigravity"])
        self.assertEqual(
            summary(overlaps),
            [("cursor", ("cursor", "codex", "antigravity"), (".cursor/skills", ".agents/skills"))],
        )

    def test_both_readers_each_report_their_own_overlap(self):
        overlaps = detect_folder_overlaps(ALL)
        self.assertEqual([o.reader for o in overlaps], ["cursor", "vscode"])
        self.assertEqual(overlaps[0].harnesses, ("cursor", "claude", "codex", "antigravity"))
        self.assertEqual(overlaps[1].harnesses, ("vscode", "claude", "codex", "antigravity"))
        self.assertEqual(len(detect_folder_overlaps(["cursor", "vscode", "claude"])), 2)

    def test_unknown_ids_and_repeats_are_ignored(self):
        self.assertEqual(detect_folder_overlaps(["claude", "claude", "nope"]), [])
        self.assertEqual(len(detect_folder_overlaps(["cursor", "claude", "cursor", "claude"])), 1)

    def test_message_names_the_tool_the_folders_the_recommendation_and_the_guide(self):
        [overlap] = detect_folder_overlaps(["claude", "cursor"])
        message = overlap.message
        for needle in (
            "RAPID1321",
            "Cursor",
            ".cursor/skills",
            ".claude/skills",
            "--harness claude",
            "guides/shortcuts#si-combinas-harnesses",
        ):
            self.assertIn(needle, message)
        self.assertEqual(
            set(overlap.to_dict()),
            {"code", "message", "reader", "harnesses", "folders"},
        )
        self.assertEqual(overlap.to_dict()["code"], "RAPID1321")

    def test_recommendation_collapses_codex_and_antigravity_into_one_harness(self):
        [overlap] = detect_folder_overlaps(["vscode", "codex", "antigravity"])
        self.assertIn("--harness codex", overlap.message)
        self.assertNotIn("--harness antigravity", overlap.message)


class TablesStayInSyncTests(unittest.TestCase):
    def test_harness_folders_match_what_the_adapters_generate(self):
        templates = load_templates(ROOT / "templates")
        for adapter in DEFAULT_AGENT_REGISTRY.adapters():
            sample = next(iter(adapter.shortcut_outputs(templates))).as_posix()
            folder = sample[: sample.index("/rapid-")]
            with self.subTest(harness=adapter.id):
                self.assertEqual(HARNESS_FOLDERS[adapter.id], folder)
        self.assertEqual(set(HARNESS_FOLDERS), set(DEFAULT_AGENT_REGISTRY.ids()))

    def test_read_folders_are_the_ones_documented_in_the_shortcuts_guide(self):
        guide = (ROOT / "docs" / "guides" / "shortcuts.md").read_text(encoding="utf-8")
        for tool, folders in TOOL_READ_FOLDERS.items():
            for folder in folders:
                with self.subTest(tool=tool, folder=folder):
                    self.assertIn(folder + "/", guide)

    def test_the_two_official_urls_are_cited_next_to_the_table(self):
        source = Path(shortcuts_domain.__file__).read_text(encoding="utf-8")
        self.assertIn("https://cursor.com/docs/context/skills", source)
        self.assertIn("https://code.visualstudio.com/docs/copilot/customization/agent-skills", source)


class OverlapCliTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def rapid(self, *args, cwd=None):
        env = {k: v for k, v in os.environ.items() if k not in ("CLAUDECODE", "CLAUDE_CODE_CHILD_SESSION")}
        env["PYTHONPATH"] = str(ROOT)
        return subprocess.run(
            [sys.executable, "-m", "rapid_os.cli.main", *args],
            cwd=str(cwd or self.root), capture_output=True, text=True, encoding="utf-8", env=env,
        )

    def tree(self, root=None):
        base = Path(root or self.root)
        return sorted(p.relative_to(base).as_posix() for p in base.rglob("*") if p.is_file())

    def test_dry_run_json_with_claude_and_cursor_warns_and_writes_nothing(self):
        res = self.rapid("shortcuts", "install", "--harness", "claude", "--harness", "cursor", "--dry-run", "--json")
        self.assertEqual(res.returncode, 0, res.stderr)
        payload = json.loads(res.stdout)
        warnings = [w for w in payload["warnings"] if isinstance(w, dict)]
        self.assertEqual(len(warnings), 1)
        self.assertEqual(warnings[0]["code"], "RAPID1321")
        self.assertEqual(warnings[0]["reader"], "cursor")
        self.assertEqual(warnings[0]["harnesses"], ["cursor", "claude"])
        self.assertEqual(warnings[0]["folders"], [".cursor/skills", ".claude/skills"])
        self.assertIn("guides/shortcuts#si-combinas-harnesses", warnings[0]["message"])
        self.assertIn("WARNING RAPID1321", res.stderr)
        self.assertEqual(self.tree(), [])

    def test_the_warning_does_not_change_what_is_written_or_the_exit_code(self):
        combined = self.root / "combined"
        separate = self.root / "separate"
        combined.mkdir()
        separate.mkdir()
        both = self.rapid("shortcuts", "install", "--harness", "claude", "--harness", "cursor", cwd=combined)
        self.assertEqual(both.returncode, 0, both.stderr)
        self.assertIn("RAPID1321", both.stderr)
        self.assertEqual(self.rapid("shortcuts", "install", "--harness", "claude", cwd=separate).returncode, 0)
        self.assertEqual(self.rapid("shortcuts", "install", "--harness", "cursor", cwd=separate).returncode, 0)
        self.assertEqual(self.tree(combined), self.tree(separate))

    def test_install_with_a_single_harness_has_no_overlap_warning(self):
        res = self.rapid("shortcuts", "install", "--harness", "codex", "--dry-run", "--json")
        self.assertEqual(res.returncode, 0, res.stderr)
        payload = json.loads(res.stdout)
        # The text warnings list is part of today's output; it just holds no overlap entry.
        self.assertEqual([w for w in payload.get("warnings", []) if isinstance(w, dict)], [])
        self.assertNotIn("RAPID1321", res.stdout)
        self.assertNotIn("RAPID1321", res.stderr)

    def test_install_without_overlap_keeps_the_existing_json_shape(self):
        res = self.rapid("shortcuts", "install", "--harness", "claude", "--dry-run", "--json")
        payload = json.loads(res.stdout)
        self.assertEqual(
            sorted(payload), ["command", "dry_run", "files", "harnesses", "schema_version", "skipped", "warnings"]
        )
        self.assertEqual(payload["warnings"], [])

    def test_cursor_with_vscode_and_codex_with_antigravity_do_not_warn(self):
        for harnesses in (("cursor", "vscode"), ("codex", "antigravity")):
            with self.subTest(harnesses=harnesses):
                args = ["shortcuts", "install", "--dry-run", "--json"]
                for h in harnesses:
                    args += ["--harness", h]
                res = self.rapid(*args)
                self.assertEqual(res.returncode, 0, res.stderr)
                self.assertNotIn("RAPID1321", res.stderr)

    def test_list_with_claude_and_vscode_warns(self):
        text = self.rapid("shortcuts", "list", "--harness", "claude", "--harness", "vscode")
        self.assertEqual(text.returncode, 0, text.stderr)
        self.assertIn("WARNING RAPID1321", text.stderr)
        self.assertIn("VS Code", text.stderr)
        as_json = self.rapid("shortcuts", "list", "--harness", "claude", "--harness", "vscode", "--json")
        self.assertEqual(as_json.returncode, 0, as_json.stderr)
        payload = json.loads(as_json.stdout)
        self.assertEqual([w["code"] for w in payload["warnings"]], ["RAPID1321"])
        self.assertEqual(payload["warnings"][0]["reader"], "vscode")

    def test_list_without_overlap_omits_the_field(self):
        res = self.rapid("shortcuts", "list", "--harness", "claude", "--json")
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertNotIn("warnings", json.loads(res.stdout))
        self.assertNotIn("RAPID1321", res.stderr)

    def test_remove_does_not_warn(self):
        res = self.rapid("shortcuts", "remove", "--harness", "claude", "--harness", "cursor", "--dry-run")
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertNotIn("RAPID1321", res.stderr)

    def test_init_shortcuts_warns_for_the_selected_agents(self):
        res = self.rapid("init", "--yes", "--no-scan", "--agents", "claude,cursor", "--shortcuts")
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertIn("RAPID1321", res.stderr)
        self.assertTrue((self.root / ".claude" / "skills" / "rapid-feature" / "SKILL.md").exists())
        single = self.root / "single"
        single.mkdir()
        res = self.rapid("init", "--yes", "--no-scan", "--agents", "claude", "--shortcuts", cwd=single)
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertNotIn("RAPID1321", res.stderr)


if __name__ == "__main__":
    unittest.main()
