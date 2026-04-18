import tempfile
import unittest
from pathlib import Path

from rapid_os.core.context import compose_project_context


REPO_ROOT = Path(__file__).resolve().parents[1]


def workspace_tempdir():
    return tempfile.TemporaryDirectory(dir=REPO_ROOT)


class ContextCompositionTests(unittest.TestCase):
    def test_standards_are_composed_in_existing_priority_order(self):
        with workspace_tempdir() as tmp:
            current_dir = Path(tmp)
            project_dir = current_dir / ".rapid-os"
            standards_dir = project_dir / "standards"
            standards_dir.mkdir(parents=True)
            (standards_dir / "business.md").write_text("business", encoding="utf-8")
            (standards_dir / "tech-stack.md").write_text("stack", encoding="utf-8")
            (standards_dir / "topology.md").write_text("topology", encoding="utf-8")

            context = compose_project_context(project_dir, current_dir)

            self.assertLess(context.index("stack"), context.index("topology"))
            self.assertLess(context.index("topology"), context.index("business"))

    def test_missing_standards_are_ignored(self):
        with workspace_tempdir() as tmp:
            current_dir = Path(tmp)
            project_dir = current_dir / ".rapid-os"
            (project_dir / "standards").mkdir(parents=True)

            self.assertEqual(compose_project_context(project_dir, current_dir), "")

    def test_visual_context_is_appended_when_present(self):
        with workspace_tempdir() as tmp:
            current_dir = Path(tmp)
            project_dir = current_dir / ".rapid-os"
            standards_dir = project_dir / "standards"
            references_dir = current_dir / "references"
            standards_dir.mkdir(parents=True)
            references_dir.mkdir()
            (standards_dir / "tech-stack.md").write_text("stack", encoding="utf-8")
            (references_dir / "VISION_CONTEXT.md").write_text("visual", encoding="utf-8")

            context = compose_project_context(project_dir, current_dir)

            self.assertLess(context.index("stack"), context.index("VISUAL STANDARDS"))
            self.assertIn("visual", context)


if __name__ == "__main__":
    unittest.main()
