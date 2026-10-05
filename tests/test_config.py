import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from rapid_os.core.config import (
    CONFIG_STATUS_INVALID_JSON,
    CONFIG_STATUS_INVALID_SCHEMA,
    CONFIG_STATUS_IO_ERROR,
    CONFIG_STATUS_MISSING,
    CONFIG_STATUS_VALID,
    ProjectConfigError,
    inspect_project_config_file,
    load_project_config,
    save_project_config,
)


REPO_ROOT = Path(__file__).resolve().parents[1]


def workspace_tempdir():
    return tempfile.TemporaryDirectory(dir=REPO_ROOT)


class ProjectConfigTests(unittest.TestCase):
    def test_missing_config_returns_current_defaults(self):
        with workspace_tempdir() as tmp:
            config_file = Path(tmp) / ".rapid-os" / "config.json"
            result = inspect_project_config_file(config_file)
            config = load_project_config(config_file)

            self.assertEqual(result.status, CONFIG_STATUS_MISSING)
            self.assertTrue(result.is_valid)
            self.assertEqual(
                config,
                {"tools": ["cursor", "claude", "antigravity", "vscode"]},
            )
            self.assertNotIn("codex", config["tools"])

    def test_valid_config_loads(self):
        with workspace_tempdir() as tmp:
            config_file = Path(tmp) / ".rapid-os" / "config.json"
            config_file.parent.mkdir()
            config_file.write_text('{"tools": ["cursor"]}', encoding="utf-8")

            result = inspect_project_config_file(config_file)
            self.assertEqual(result.status, CONFIG_STATUS_VALID)
            self.assertTrue(result.is_valid)
            self.assertEqual(load_project_config(config_file), {"tools": ["cursor"]})

    def test_invalid_config_falls_back_to_empty_tools(self):
        with workspace_tempdir() as tmp:
            config_file = Path(tmp) / ".rapid-os" / "config.json"
            config_file.parent.mkdir()
            config_file.write_text("{invalid", encoding="utf-8")

            result = inspect_project_config_file(config_file)
            self.assertEqual(result.status, CONFIG_STATUS_INVALID_JSON)
            self.assertFalse(result.is_valid)
            self.assertEqual(load_project_config(config_file), {"tools": []})
            with self.assertRaises(ProjectConfigError) as ctx:
                load_project_config(config_file, strict=True)
            self.assertEqual(ctx.exception.status, CONFIG_STATUS_INVALID_JSON)

    def test_invalid_schema_is_distinguished_from_invalid_json_and_missing(self):
        with workspace_tempdir() as tmp:
            config_file = Path(tmp) / ".rapid-os" / "config.json"
            config_file.parent.mkdir()

            config_file.write_text('["not-an-object"]', encoding="utf-8")
            root_result = inspect_project_config_file(config_file)
            self.assertEqual(root_result.status, CONFIG_STATUS_INVALID_SCHEMA)

            config_file.write_text('{"tools": "cursor"}', encoding="utf-8")
            tools_result = inspect_project_config_file(config_file)
            self.assertEqual(tools_result.status, CONFIG_STATUS_INVALID_SCHEMA)

            config_file.write_text('{"tools": ["cursor", 123]}', encoding="utf-8")
            item_result = inspect_project_config_file(config_file)
            self.assertEqual(item_result.status, CONFIG_STATUS_INVALID_SCHEMA)

            with self.assertRaises(ProjectConfigError) as ctx:
                load_project_config(config_file, strict=True)
            self.assertEqual(ctx.exception.status, CONFIG_STATUS_INVALID_SCHEMA)

    def test_io_error_is_distinguished(self):
        with workspace_tempdir() as tmp:
            config_dir = Path(tmp) / ".rapid-os" / "config.json"
            config_dir.mkdir(parents=True)

            dir_result = inspect_project_config_file(config_dir)
            self.assertEqual(dir_result.status, CONFIG_STATUS_IO_ERROR)
            self.assertFalse(dir_result.is_valid)

            config_file = Path(tmp) / ".rapid-os" / "unreadable.json"
            config_file.write_text('{"tools": ["cursor"]}', encoding="utf-8")
            with patch.object(
                Path, "read_text", side_effect=OSError("permission denied")
            ):
                io_result = inspect_project_config_file(config_file)
            self.assertEqual(io_result.status, CONFIG_STATUS_IO_ERROR)

    def test_save_creates_project_config_file_and_backups_existing(self):
        with workspace_tempdir() as tmp:
            project_dir = Path(tmp) / ".rapid-os"
            config_file = project_dir / "config.json"

            save_project_config({"tools": ["claude"]}, project_dir, config_file)
            self.assertTrue(config_file.exists())
            self.assertEqual(
                json.loads(config_file.read_text(encoding="utf-8")),
                {"tools": ["claude"]},
            )

            save_project_config({"tools": ["cursor"]}, project_dir, config_file)
            self.assertEqual(
                json.loads(config_file.read_text(encoding="utf-8")),
                {"tools": ["cursor"]},
            )
            self.assertTrue(list(project_dir.glob("config.json.*.bak")))

    def test_save_creates_nested_project_config_directory(self):
        with workspace_tempdir() as tmp:
            project_dir = Path(tmp) / "nested" / "project" / ".rapid-os"
            config_file = project_dir / "config.json"

            save_project_config({"tools": ["cursor"]}, project_dir, config_file)

            self.assertTrue(config_file.exists())


if __name__ == "__main__":
    unittest.main()
