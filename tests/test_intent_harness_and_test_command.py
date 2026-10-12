from __future__ import annotations

import contextlib
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from rapid_os.cli import main as cli_main
from rapid_os.domain.validation import validate_project

REPO_ROOT = Path(__file__).resolve().parent.parent


def _run_cli(args: list[str], cwd: Path | None = None, env: dict[str, str] | None = None) -> tuple[int, str, str]:
    stdout = io.StringIO()
    stderr = io.StringIO()
    project_root = cwd if cwd is not None else REPO_ROOT
    rapid_dir = project_root / ".rapid-os"
    config_file = rapid_dir / "config.json"
    exit_code = 0
    with (
        patch.object(cli_main, "CURRENT_DIR", project_root),
        patch.object(cli_main, "PROJECT_RAPID_DIR", rapid_dir),
        patch.object(cli_main, "CONFIG_FILE", config_file),
        patch.dict(os.environ, env or {}, clear=False),
        contextlib.redirect_stdout(stdout),
        contextlib.redirect_stderr(stderr),
    ):
        try:
            res = cli_main.main(args)
            if isinstance(res, int):
                exit_code = res
        except SystemExit as exc:
            exit_code = int(exc.code) if exc.code is not None else 0
    return exit_code, stdout.getvalue(), stderr.getvalue()


def _create_ready_spec(root: Path) -> None:
    code, out, err = _run_cli(
        [
            "spec",
            "create",
            "--id",
            "feature-spec",
            "--title",
            "Sample Feature",
            "--mode",
            "feature",
            "--scope",
            "core logic",
            "--acceptance",
            "returns true",
            "--task",
            "implement feature",
            "--status",
            "ready",
        ],
        cwd=root,
    )
    assert code == 0, f"spec create failed: {err}"


class IntentHarnessAndTestCommandTests(unittest.TestCase):
    def test_run_create_fallback_prints_rapid1300_warning(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            # init with --yes and no test command
            code, out, err = _run_cli(
                ["init", "--stack", "web-modern", "--topology", "front-end-only", "--archetype", "mvp", "--yes", "--no-scan"],
                cwd=root,
                env={},
            )
            self.assertEqual(code, 0, err)
            _create_ready_spec(root)

            # Ensure clean env without markers or RAPID_HARNESS
            clean_env = {k: v for k, v in os.environ.items() if k not in ("RAPID_HARNESS", "CURSOR_AGENT", "CLAUDE_PROJECT_DIR", "TERM_PROGRAM", "CODEX_THREAD_ID")}
            code, out, err = _run_cli(
                ["run", "create", "--spec", "feature-spec"],
                cwd=root,
                env=clean_env,
            )
            self.assertEqual(code, 0, err)
            self.assertIn("RAPID1300", err)
            # Verify the contract in disk has harness "cursor"
            run_dirs = list((root / ".rapid-os" / "runs").iterdir())
            contract_data = json.loads((run_dirs[0] / "contract.json").read_text(encoding="utf-8"))
            self.assertEqual(contract_data["harness"], "cursor")

    def test_run_create_with_rapid_harness_env(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            code, out, err = _run_cli(
                ["init", "--stack", "web-modern", "--topology", "front-end-only", "--archetype", "mvp", "--yes", "--no-scan"],
                cwd=root,
            )
            self.assertEqual(code, 0)
            _create_ready_spec(root)

            code, out, err = _run_cli(
                ["run", "create", "--spec", "feature-spec", "--json"],
                cwd=root,
                env={"RAPID_HARNESS": "claude"},
            )
            self.assertEqual(code, 0, err)
            data = json.loads(out)
            self.assertEqual(data["harness"], "claude")
            self.assertEqual(data["harness_source"], "env")
            self.assertNotIn("RAPID1300", err)

    def test_run_create_with_explicit_flag_and_config_default(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            code, out, err = _run_cli(
                ["init", "--stack", "web-modern", "--topology", "front-end-only", "--archetype", "mvp", "--yes", "--no-scan"],
                cwd=root,
            )
            self.assertEqual(code, 0)
            _create_ready_spec(root)

            # set default_harness in config
            cfg_path = root / ".rapid-os" / "config.json"
            cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
            cfg["default_harness"] = "antigravity"
            cfg_path.write_text(json.dumps(cfg), encoding="utf-8")

            # without flag -> config used
            clean_env = {k: v for k, v in os.environ.items() if k not in ("RAPID_HARNESS", "CURSOR_AGENT", "CLAUDE_PROJECT_DIR", "TERM_PROGRAM", "CODEX_THREAD_ID")}
            code, out, err = _run_cli(
                ["run", "create", "--spec", "feature-spec", "--json"],
                cwd=root,
                env=clean_env,
            )
            self.assertEqual(code, 0)
            data = json.loads(out)
            self.assertEqual(data["harness"], "antigravity")
            self.assertEqual(data["harness_source"], "config")
            self.assertNotIn("RAPID1300", err)

            # with explicit flag -> flag takes precedence over config
            code, out, err = _run_cli(
                ["run", "create", "--spec", "feature-spec", "--harness", "vscode", "--json"],
                cwd=root,
                env=clean_env,
            )
            self.assertEqual(code, 0)
            data = json.loads(out)
            self.assertEqual(data["harness"], "vscode")
            self.assertEqual(data["harness_source"], "flag")

    def test_init_non_interactive_with_test_command_and_validate(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            # init with explicit --test-command
            code, out, err = _run_cli(
                [
                    "init",
                    "--stack",
                    "python-ai",
                    "--topology",
                    "fullstack-separated",
                    "--archetype",
                    "mvp",
                    "--agents",
                    "cursor,claude",
                    "--test-command",
                    "python -m pytest",
                    "--yes",
                    "--no-scan",
                ],
                cwd=root,
            )
            self.assertEqual(code, 0, err)

            cfg = json.loads((root / ".rapid-os" / "config.json").read_text(encoding="utf-8"))
            self.assertEqual(cfg["test_command"], ["python", "-m", "pytest"])
            self.assertIn("cursor", cfg["tools"])
            self.assertIn("claude", cfg["tools"])

            # validate should not produce RAPID1301 when test_command is set
            code, val_out, err = _run_cli(["validate", "--json"], cwd=root)
            self.assertEqual(code, 0)
            val_doc = json.loads(val_out)
            val_codes = [d["code"] for d in val_doc["diagnostics"]]
            self.assertNotIn("RAPID1301", val_codes)

            # doctor should show test_command
            code, doc_out, err = _run_cli(["doctor"], cwd=root)
            self.assertEqual(code, 0)
            self.assertIn("RAPID909", doc_out)
            self.assertIn("pytest", doc_out)

    def test_validate_emits_rapid1301_when_test_command_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            code, out, err = _run_cli(
                [
                    "init",
                    "--stack",
                    "web-modern",
                    "--topology",
                    "front-end-only",
                    "--archetype",
                    "mvp",
                    "--yes",
                    "--no-scan",
                ],
                cwd=root,
            )
            self.assertEqual(code, 0, err)

            # config does not have test_command
            code, val_out, err = _run_cli(["validate", "--json"], cwd=root)
            self.assertEqual(code, 0)
            val_doc = json.loads(val_out)
            val_codes = [d["code"] for d in val_doc["diagnostics"]]
            self.assertIn("RAPID1301", val_codes)


if __name__ == "__main__":
    unittest.main()
