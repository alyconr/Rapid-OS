from __future__ import annotations

import unittest
from typing import Mapping

from rapid_os.core.harness_detect import HarnessDetection, detect_harness
from rapid_os.domain.capabilities import HarnessIdentityError


class HarnessDetectTests(unittest.TestCase):
    def test_explicit_flag_takes_highest_precedence(self):
        detection = detect_harness(
            explicit="claude",
            env={"RAPID_HARNESS": "codex", "CURSOR_AGENT": "1"},
            config={"default_harness": "antigravity"},
        )
        self.assertEqual(detection.harness_id, "claude")
        self.assertEqual(detection.source, "flag")
        self.assertIsNone(detection.warning)

    def test_rapid_harness_env_takes_precedence_over_markers_and_config(self):
        detection = detect_harness(
            explicit=None,
            env={"RAPID_HARNESS": "codex", "CURSOR_AGENT": "1"},
            config={"default_harness": "vscode"},
        )
        self.assertEqual(detection.harness_id, "codex")
        self.assertEqual(detection.source, "env")
        self.assertIsNone(detection.warning)

    def test_marker_claude_project_dir_detected(self):
        detection = detect_harness(
            explicit=None,
            env={"CLAUDE_PROJECT_DIR": "/workspace/project"},
            config={"default_harness": "cursor"},
        )
        self.assertEqual(detection.harness_id, "claude")
        self.assertEqual(detection.source, "marker")
        self.assertIsNone(detection.warning)

    def test_marker_cursor_agent_detected(self):
        detection = detect_harness(
            explicit=None,
            env={"CURSOR_AGENT": "1"},
            config={"default_harness": "vscode"},
        )
        self.assertEqual(detection.harness_id, "cursor")
        self.assertEqual(detection.source, "marker")
        self.assertIsNone(detection.warning)

    def test_marker_vscode_term_program_detected(self):
        detection = detect_harness(
            explicit=None,
            env={"TERM_PROGRAM": "vscode"},
            config={"default_harness": "antigravity"},
        )
        self.assertEqual(detection.harness_id, "vscode")
        self.assertEqual(detection.source, "marker")
        self.assertIsNone(detection.warning)

    def test_marker_codex_thread_id_detected(self):
        detection = detect_harness(
            explicit=None,
            env={"CODEX_THREAD_ID": "thread_abc123"},
            config={"default_harness": "cursor"},
        )
        self.assertEqual(detection.harness_id, "codex")
        self.assertEqual(detection.source, "marker")
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
