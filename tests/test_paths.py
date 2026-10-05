import tempfile
import unittest
from pathlib import Path

from rapid_os.core.paths import resolve_paths


REPO_ROOT = Path(__file__).resolve().parents[1]


def workspace_tempdir():
    return tempfile.TemporaryDirectory(dir=REPO_ROOT)


class PathResolutionTests(unittest.TestCase):
    def test_source_templates_take_precedence_when_present(self):
        with workspace_tempdir() as tmp:
            root = Path(tmp)
            script_dir = root / "source"
            templates_dir = script_dir / "templates"
            templates_dir.mkdir(parents=True)
            rapid_home = root / "home"

            paths = resolve_paths(
                current_dir=root / "project",
                script_dir=script_dir,
                rapid_home=rapid_home,
            )

            self.assertEqual(paths.templates_dir, templates_dir)

    def test_installed_templates_are_used_without_source_templates(self):
        with workspace_tempdir() as tmp:
            root = Path(tmp)
            script_dir = root / "source"
            script_dir.mkdir()
            rapid_home = root / "home"

            paths = resolve_paths(
                current_dir=root / "project",
                script_dir=script_dir,
                rapid_home=rapid_home,
            )

            self.assertEqual(paths.templates_dir, rapid_home / "templates")
            self.assertEqual(paths.config_file, root / "project" / ".rapid-os" / "config.json")


if __name__ == "__main__":
    unittest.main()

