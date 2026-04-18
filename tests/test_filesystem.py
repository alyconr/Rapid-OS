import tempfile
import unittest
from pathlib import Path

from rapid_os.core.filesystem import create_backup


REPO_ROOT = Path(__file__).resolve().parents[1]


def workspace_tempdir():
    return tempfile.TemporaryDirectory(dir=REPO_ROOT)


class FilesystemTests(unittest.TestCase):
    def test_create_backup_skips_missing_file(self):
        with workspace_tempdir() as tmp:
            missing_file = Path(tmp) / "missing.md"

            self.assertIsNone(create_backup(missing_file, timestamp=123))

    def test_create_backup_copies_existing_file(self):
        with workspace_tempdir() as tmp:
            source = Path(tmp) / "rules.md"
            source.write_text("original", encoding="utf-8")

            backup = create_backup(source, timestamp=123)

            self.assertEqual(backup, Path(tmp) / "rules.md.123.bak")
            self.assertEqual(backup.read_text(encoding="utf-8"), "original")


if __name__ == "__main__":
    unittest.main()
