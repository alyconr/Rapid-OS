import json
import tempfile
import unittest
from pathlib import Path

from rapid_os.core.config import load_project_config, save_project_config


REPO_ROOT = Path(__file__).resolve().parents[1]


def workspace_tempdir():
    return tempfile.TemporaryDirectory(dir=REPO_ROOT)


class ProjectConfigTests(unittest.TestCase):
    def test_missing_config_returns_current_defaults(self):
        with workspace_tempdir() as tmp:
            config_file = Path(tmp) / ".rapid-os" / "config.json"

            self.assertEqual(
                load_project_config(config_file),
                {"tools": ["cursor", "claude", "antigravity", "vscode"]},
            )

    def test_valid_config_loads(self):
        with workspace_tempdir() as tmp:
            config_file = Path(tmp) / ".rapid-os" / "config.json"
            config_file.parent.mkdir()
            config_file.write_text('{"tools": ["cursor"]}', encoding="utf-8")

            self.assertEqual(load_project_config(config_file), {"tools": ["cursor"]})

    def test_invalid_config_falls_back_to_empty_tools(self):
        with workspace_tempdir() as tmp:
            config_file = Path(tmp) / ".rapid-os" / "config.json"
            config_file.parent.mkdir()
            config_file.write_text("{invalid", encoding="utf-8")

            self.assertEqual(load_project_config(config_file), {"tools": []})

    def test_save_creates_project_config_file(self):
        with workspace_tempdir() as tmp:
            project_dir = Path(tmp) / ".rapid-os"
            config_file = project_dir / "config.json"

            save_project_config({"tools": ["claude"]}, project_dir, config_file)

            self.assertTrue(config_file.exists())
            self.assertEqual(
                json.loads(config_file.read_text(encoding="utf-8")),
                {"tools": ["claude"]},
            )

    def test_save_creates_nested_project_config_directory(self):
        with workspace_tempdir() as tmp:
            project_dir = Path(tmp) / "nested" / "project" / ".rapid-os"
            config_file = project_dir / "config.json"

            save_project_config({"tools": ["cursor"]}, project_dir, config_file)

            self.assertTrue(config_file.exists())


if __name__ == "__main__":
    unittest.main()
