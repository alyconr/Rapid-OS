"""Automated test verifying that docs/tutorials/first-governed-project.md is strictly executable.

Parses code blocks in order from docs/tutorials/first-governed-project.md:
1. ```bash: executes commands sequentially in a clean temporary directory.
2. ```json: writes JSON content to the last mentioned `*.json` file before the block.
3. ```python: writes code to the path specified in its first line (e.g. "# <path>").

Verifies that `rapid eval run --run <id> --require-pass` exits with 0 and verdict "pass".
"""

from pathlib import Path
import json
import os
import re
import shlex
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
TUTORIAL_PATH = ROOT / "docs" / "tutorials" / "first-governed-project.md"


class TestTutorialExecutable(unittest.TestCase):
    def test_first_governed_project_tutorial_is_executable(self):
        self.assertTrue(TUTORIAL_PATH.is_file(), f"Tutorial not found: {TUTORIAL_PATH}")
        content = TUTORIAL_PATH.read_text(encoding="utf-8")

        # Find code blocks in order with preceding context:
        # Regex accepts optional language identifier and empty blocks
        pattern = re.compile(r"```([\w-]*)\n(.*?)```", re.DOTALL)
        matches = list(pattern.finditer(content))

        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            env = dict(os.environ)
            env["PYTHONPATH"] = str(ROOT)

            def run_rapid_cmd(cli_line: str) -> subprocess.CompletedProcess:
                # Handle pipeline redirection in bash commands if present
                if ">" in cli_line:
                    cmd_part, out_file = cli_line.split(">", 1)
                    cmd_part = cmd_part.strip()
                    out_file = out_file.strip()
                    # e.g., "> base.log 2>&1"
                    if "2>&1" in out_file:
                        out_file = out_file.replace("2>&1", "").strip()
                    tokens = shlex.split(cmd_part)
                    if tokens[0] == "python":
                        cmd = [sys.executable] + tokens[1:]
                    elif tokens[0] == "rapid":
                        cmd = [sys.executable, str(ROOT / "rapid.py")] + tokens[1:]
                    else:
                        cmd = tokens
                    res = subprocess.run(
                        cmd,
                        cwd=str(tmp_path),
                        capture_output=True,
                        text=True,
                        encoding="utf-8",
                        errors="replace",
                        env=env,
                        timeout=30,
                    )
                    combined_output = (res.stdout or "") + (res.stderr or "")
                    (tmp_path / out_file).write_text(combined_output, encoding="utf-8")
                    return res

                tokens = shlex.split(cli_line)
                if not tokens:
                    return subprocess.CompletedProcess(args=[], returncode=0, stdout="", stderr="")

                if tokens[0] == "rapid":
                    cmd = [sys.executable, str(ROOT / "rapid.py")] + tokens[1:]
                    return subprocess.run(
                        cmd,
                        cwd=str(tmp_path),
                        capture_output=True,
                        text=True,
                        encoding="utf-8",
                        errors="replace",
                        env=env,
                        timeout=30,
                    )
                elif tokens[0] == "python":
                    cmd = [sys.executable] + tokens[1:]
                    return subprocess.run(
                        cmd,
                        cwd=str(tmp_path),
                        capture_output=True,
                        text=True,
                        encoding="utf-8",
                        errors="replace",
                        env=env,
                        timeout=30,
                    )
                else:
                    return subprocess.run(
                        tokens,
                        cwd=str(tmp_path),
                        capture_output=True,
                        text=True,
                        encoding="utf-8",
                        errors="replace",
                        env=env,
                        timeout=30,
                    )

            last_json_filename = None

            for i, match in enumerate(matches):
                lang = (match.group(1) or "").strip().lower()
                body = match.group(2)
                preceding_text = content[: match.start()]
                if i > 0:
                    prev_end = matches[i - 1].end()
                    preceding_text = content[prev_end : match.start()]

                # Look for filename in backticks in preceding_text (e.g. `evidence_baseline.json`)
                json_file_match = re.findall(r"`([a-zA-Z0-9_\-./]+\.json)`", preceding_text)
                if json_file_match:
                    last_json_filename = json_file_match[-1]

                if lang == "python":
                    first_line = body.strip().split("\n")[0].strip()
                    if first_line.startswith("#"):
                        target_rel = first_line.lstrip("#").strip()
                        target_file = tmp_path / target_rel
                        target_file.parent.mkdir(parents=True, exist_ok=True)
                        target_file.write_text(body, encoding="utf-8")

                elif lang == "json":
                    # Only write JSON files that correspond to instructions/evidence
                    # Skip expected output blocks (e.g. {"verdict": "pass", ...})
                    if last_json_filename and not body.strip().startswith('{\n  "verdict"'):
                        target_json = tmp_path / last_json_filename
                        target_json.parent.mkdir(parents=True, exist_ok=True)
                        target_json.write_text(body, encoding="utf-8")
                        # Reset so we don't accidentally overwrite with later blocks
                        last_json_filename = None

                elif lang == "bash":
                    # Split lines handling multi-line commands with backslashes
                    normalized_body = body.replace("\\\n", " ")
                    for raw_line in normalized_body.split("\n"):
                        line = raw_line.strip()
                        if not line or line.startswith("#"):
                            continue
                        # Execute command
                        res = run_rapid_cmd(line)
                        self.assertEqual(
                            res.returncode,
                            0,
                            f"Command '{line}' failed with exit code {res.returncode}:\nSTDOUT:\n{res.stdout}\nSTDERR:\n{res.stderr}",
                        )

            # Verify tutorial contains a rapid eval run with --require-pass
            require_pass_match = re.search(
                r"rapid\s+eval\s+run\s+.*--require-pass",
                content,
            )
            self.assertIsNotNone(
                require_pass_match,
                "Tutorial must contain a 'rapid eval run' command with '--require-pass'",
            )

            # Assert that the evaluation report was written and verdict is pass
            runs_dir = tmp_path / ".rapid-os" / "runs"
            self.assertTrue(runs_dir.is_dir(), ".rapid-os/runs directory was not created")
            evals_dir = tmp_path / ".rapid-os" / "evals"
            self.assertTrue(evals_dir.is_dir(), ".rapid-os/evals directory was not created")
            report_files = sorted(evals_dir.rglob("*.json"))
            self.assertTrue(len(report_files) >= 1, "No evaluation reports found in .rapid-os/evals")
            latest_report = json.loads(report_files[-1].read_text(encoding="utf-8"))
            self.assertEqual(latest_report["verdict"], "pass")


if __name__ == "__main__":
    unittest.main()
