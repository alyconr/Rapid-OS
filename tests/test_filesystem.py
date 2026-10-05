import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from rapid_os.core.filesystem import (
    create_backup,
    safe_append_text,
    safe_copy_file,
    safe_write_text,
)


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

    def test_safe_write_text_creates_parents_and_writes_utf8(self):
        with workspace_tempdir() as tmp:
            target = Path(tmp) / "nested" / "dir" / "STANDARDS.md"

            written = safe_write_text(
                target,
                "Contenido UTF-8: áéíóú 🚀",
                backup=True,
                create_parents=True,
            )

            self.assertEqual(written, target)
            self.assertEqual(
                target.read_text(encoding="utf-8"),
                "Contenido UTF-8: áéíóú 🚀",
            )
            self.assertEqual(list(target.parent.glob("*.tmp")), [])

    def test_safe_write_text_preserves_backup_when_overwriting(self):
        with workspace_tempdir() as tmp:
            target = Path(tmp) / "CLAUDE.md"
            target.write_text("initial content", encoding="utf-8")

            safe_write_text(
                target,
                "updated content",
                backup=True,
                timestamp=456,
            )

            self.assertEqual(target.read_text(encoding="utf-8"), "updated content")
            backup = Path(tmp) / "CLAUDE.md.456.bak"
            self.assertTrue(backup.exists())
            self.assertEqual(backup.read_text(encoding="utf-8"), "initial content")

    def test_safe_write_text_failed_replace_preserves_original_and_cleans_temp(self):
        with workspace_tempdir() as tmp:
            target = Path(tmp) / "AGENTS.md"
            target.write_text("stable content", encoding="utf-8")

            with patch(
                "rapid_os.core.filesystem.os.replace",
                side_effect=OSError("simulated atomic replace failure"),
            ):
                with self.assertRaises(OSError):
                    safe_write_text(target, "partial replacement", backup=False)

            self.assertEqual(target.read_text(encoding="utf-8"), "stable content")
            self.assertEqual(list(Path(tmp).glob("*.tmp")), [])
            self.assertEqual(list(Path(tmp).glob(".*.tmp")), [])

    def test_safe_copy_file_copies_atomically_and_backs_up_existing(self):
        with workspace_tempdir() as tmp:
            root = Path(tmp)
            src = root / "template.md"
            dest = root / "standards" / "tech-stack.md"
            src.write_text("new stack", encoding="utf-8")
            dest.parent.mkdir(parents=True)
            dest.write_text("old stack", encoding="utf-8")

            safe_copy_file(src, dest, backup=True, timestamp=789)

            self.assertEqual(dest.read_text(encoding="utf-8"), "new stack")
            backup = dest.parent / "tech-stack.md.789.bak"
            self.assertTrue(backup.exists())
            self.assertEqual(backup.read_text(encoding="utf-8"), "old stack")

    def test_safe_append_text_appends_atomically(self):
        with workspace_tempdir() as tmp:
            target = Path(tmp) / "references" / "VISION_CONTEXT.md"

            safe_append_text(target, "- **first.png**: login")
            safe_append_text(target, "\n- **second.png**: dashboard")

            self.assertEqual(
                target.read_text(encoding="utf-8"),
                "- **first.png**: login\n- **second.png**: dashboard",
            )


if __name__ == "__main__":
    unittest.main()
