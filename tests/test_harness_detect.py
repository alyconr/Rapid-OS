from __future__ import annotations

import unittest

from unittest import mock

from rapid_os.core.ancestry import Ancestor, AncestryResult
from rapid_os.core.harness_detect import HarnessDetection, detect_harness
from rapid_os.domain.capabilities import HarnessIdentityError

NO_AGENT = AncestryResult((Ancestor(10, "bash.exe"), Ancestor(11, "explorer.exe")))
CODEX_TREE = AncestryResult((
    Ancestor(10, "powershell.exe"),
    Ancestor(
        11,
        "codex.exe",
        ("C:\\Users\\u\\.codex\\packages\\app-server-daemon\\releases\\0.170.0-x86_64-pc-windows-msvc\\bin\\codex.exe",
         "app-server", "--managed-daemon"),
    ),
))
CLAUDE_TREE = AncestryResult((Ancestor(10, "bash.exe"), Ancestor(11, "claude.exe")))


class HarnessDetectTests(unittest.TestCase):
    def setUp(self):
        # The tests decide the process tree: the runner's own (an agent, `timeout`) must not leak in.
        patcher = mock.patch("rapid_os.core.harness_detect.read_ancestry", return_value=NO_AGENT)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_explicit_flag_takes_highest_precedence(self):
        detection = detect_harness(
            explicit="claude",
            env={"RAPID_HARNESS": "codex", "CLAUDE_CODE_CHILD_SESSION": "1"},
            config={"default_harness": "antigravity"},
        )
        self.assertEqual(detection.harness_id, "claude")
        self.assertEqual(detection.source, "flag")
        self.assertIsNone(detection.warning)

    def test_rapid_harness_env_takes_precedence_over_markers_and_config(self):
        detection = detect_harness(
            explicit=None,
            env={"RAPID_HARNESS": "codex", "CLAUDE_CODE_CHILD_SESSION": "1"},
            config={"default_harness": "vscode"},
        )
        self.assertEqual(detection.harness_id, "codex")
        self.assertEqual(detection.source, "env")
        self.assertIsNone(detection.warning)

    def test_marker_claude_code_child_session_detected(self):
        detection = detect_harness(
            explicit=None,
            env={"CLAUDE_CODE_CHILD_SESSION": "1"},
            config={"default_harness": "cursor"},
        )
        self.assertEqual(detection.harness_id, "claude")
        self.assertEqual(detection.source, "marker")
        self.assertIsNone(detection.warning)

    def test_marker_claude_code_child_session_not_one_ignored(self):
        detection = detect_harness(
            explicit=None,
            env={"CLAUDE_CODE_CHILD_SESSION": "0"},
            config={"default_harness": "cursor"},
        )
        self.assertEqual(detection.harness_id, "cursor")
        self.assertEqual(detection.source, "config")
        self.assertIsNone(detection.warning)

    def test_config_default_harness_used_when_no_env_or_marker(self):
        detection = detect_harness(
            explicit=None,
            env={},
            config={"default_harness": "antigravity"},
        )
        self.assertEqual(detection.harness_id, "antigravity")
        self.assertEqual(detection.source, "config")
        self.assertIsNone(detection.warning)

    def test_fallback_cursor_with_warning_when_nothing_configured(self):
        detection = detect_harness(
            explicit=None,
            env={},
            config={},
        )
        self.assertEqual(detection.harness_id, "cursor")
        self.assertEqual(detection.source, "fallback")
        self.assertIsNotNone(detection.warning)
        self.assertIn("RAPID1300", detection.warning)

    def test_single_supported_tool_in_config_is_the_harness(self):
        detection = detect_harness(explicit=None, env={}, config={"tools": ["codex"]})
        self.assertEqual(detection.harness_id, "codex")
        self.assertEqual(detection.source, "config_tools")
        self.assertIsNone(detection.warning)

    def test_default_harness_wins_over_tools(self):
        detection = detect_harness(
            explicit=None, env={}, config={"tools": ["codex"], "default_harness": "claude"}
        )
        self.assertEqual((detection.harness_id, detection.source), ("claude", "config"))

    def test_several_tools_fall_back_to_the_first_of_tools_with_rapid1300(self):
        # H-82: with tools = codex,claude a Codex run ended up as 'cursor', a harness the project did not choose.
        detection = detect_harness(explicit=None, env={}, config={"tools": ["codex", "claude"]})
        self.assertEqual(detection.harness_id, "codex")
        self.assertEqual(detection.source, "fallback")
        self.assertIn("RAPID1300", detection.warning)
        self.assertIn("codex, claude", detection.warning)
        self.assertIn("using 'codex', the first one", detection.warning)

    def test_the_codex_process_tree_decides_the_harness(self):
        for config in ({}, {"tools": ["codex", "claude"]}, {"default_harness": "cursor"}):
            with self.subTest(config=config):
                detection = detect_harness(explicit=None, env={}, config=config, ancestry=CODEX_TREE)
                self.assertEqual((detection.harness_id, detection.source), ("codex", "ancestry"))
                self.assertIsNone(detection.warning)

    def test_the_claude_code_tree_and_marker_work_as_before(self):
        detection = detect_harness(explicit=None, env={}, config={"tools": ["codex"]}, ancestry=CLAUDE_TREE)
        self.assertEqual((detection.harness_id, detection.source), ("claude", "ancestry"))
        detection = detect_harness(
            explicit=None, env={"CLAUDE_CODE_CHILD_SESSION": "1"}, config={}, ancestry=CODEX_TREE
        )
        self.assertEqual((detection.harness_id, detection.source), ("claude", "marker"))

    def test_flag_and_rapid_harness_still_win_over_the_tree(self):
        self.assertEqual(detect_harness("cursor", {}, {}, ancestry=CODEX_TREE).source, "flag")
        self.assertEqual(detect_harness(None, {"RAPID_HARNESS": "vscode"}, {}, ancestry=CODEX_TREE).source, "env")

    def test_the_variable_turns_off_only_the_real_tree(self):
        from unittest import mock as _mock

        off = {"RAPID_HARNESS_FROM_ANCESTRY": "0"}
        with _mock.patch("rapid_os.core.harness_detect.read_ancestry", return_value=CODEX_TREE) as real:
            self.assertEqual(detect_harness(None, off, {}).source, "fallback")
            real.assert_not_called()
            self.assertEqual(detect_harness(None, {}, {}).harness_id, "codex")  # without it, the real tree decides
        # A tree handed in is always looked at.
        self.assertEqual(detect_harness(None, off, {}, ancestry=CODEX_TREE).harness_id, "codex")

    def test_without_an_agent_or_with_unreadable_ancestry_nothing_changes(self):
        for tree in (NO_AGENT, AncestryResult((), "cannot read the parent of pid 1")):
            with self.subTest(tree=tree):
                detection = detect_harness(None, {}, {"default_harness": "antigravity"}, ancestry=tree)
                self.assertEqual((detection.harness_id, detection.source), ("antigravity", "config"))
                detection = detect_harness(None, {}, {}, ancestry=tree)
                self.assertEqual((detection.harness_id, detection.source), ("cursor", "fallback"))

    def test_unknown_or_malformed_tools_are_ignored(self):
        for tools in (["nope"], "codex", [1, None], []):
            detection = detect_harness(explicit=None, env={}, config={"tools": tools})
            self.assertEqual(detection.source, "fallback", tools)

    def test_invalid_harness_id_raises_identity_error(self):
        with self.assertRaises(HarnessIdentityError):
            detect_harness(
                explicit="INVALID_NAME",
                env={},
                config={},
            )

        with self.assertRaises(HarnessIdentityError):
            detect_harness(
                explicit=None,
                env={"RAPID_HARNESS": "../escape"},
                config={},
            )


if __name__ == "__main__":
    unittest.main()

