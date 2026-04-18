import argparse
import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from rapid_os.cli import main as cli_main
from rapid_os.domain.scanner import scan_project, suggest_init_choices


REPO_ROOT = Path(__file__).resolve().parents[1]


def workspace_tempdir():
    return tempfile.TemporaryDirectory(dir=REPO_ROOT)


def write_json(path: Path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data), encoding="utf-8")


def create_init_templates(root: Path):
    templates = root / "templates"
    for dirname in ("stacks", "topologies", "archetypes", "business"):
        (templates / dirname).mkdir(parents=True)

    for stack in ("web-modern", "docs-modern", "python-ai", "nodejs-ai"):
        (templates / "stacks" / f"{stack}.md").write_text(
            f"# {stack}\n", encoding="utf-8"
        )

    for topology in ("front-end-only", "doc-site", "fullstack-separated", "fullstack-baas"):
        (templates / "topologies" / f"{topology}.md").write_text(
            f"# {topology}\n", encoding="utf-8"
        )

    (templates / "archetypes" / "mvp").mkdir()
    (templates / "archetypes" / "mvp" / "coding-rules.md").write_text(
        "rules", encoding="utf-8"
    )
    return templates


class ScannerTests(unittest.TestCase):
    def test_detects_docusaurus_project_and_suggests_docs(self):
        with workspace_tempdir() as tmp:
            project = Path(tmp) / "project"
            project.mkdir()
            (project / "docusaurus.config.ts").write_text("config", encoding="utf-8")
            (project / "tsconfig.json").write_text("{}", encoding="utf-8")
            (project / "package-lock.json").write_text("{}", encoding="utf-8")
            write_json(
                project / "package.json",
                {"dependencies": {"@docusaurus/core": "^3.0.0"}},
            )

            scan = scan_project(project)
            suggestions = suggest_init_choices(scan)

            self.assertIn("typescript", scan.values("language"))
            self.assertIn("docusaurus", scan.values("framework"))
            self.assertIn("npm", scan.values("package_manager"))
            self.assertEqual(suggestions.stack.value, "docs-modern")
            self.assertEqual(suggestions.topology.value, "doc-site")

    def test_detects_next_supabase_and_suggests_baas_topology(self):
        with workspace_tempdir() as tmp:
            project = Path(tmp) / "project"
            project.mkdir()
            (project / "next.config.js").write_text("module.exports = {}", encoding="utf-8")
            (project / "supabase" / "config.toml").parent.mkdir()
            (project / "supabase" / "config.toml").write_text("", encoding="utf-8")
            write_json(
                project / "package.json",
                {
                    "dependencies": {
                        "next": "^14.0.0",
                        "@supabase/supabase-js": "^2.0.0",
                    }
                },
            )

            scan = scan_project(project)
            suggestions = suggest_init_choices(scan)

            self.assertIn("nextjs", scan.values("framework"))
            self.assertIn("supabase", scan.values("database"))
            self.assertEqual(suggestions.stack.value, "web-modern")
            self.assertEqual(suggestions.topology.value, "fullstack-baas")

    def test_detects_python_fastapi_and_suggests_separated_backend(self):
        with workspace_tempdir() as tmp:
            project = Path(tmp) / "project"
            project.mkdir()
            (project / "pyproject.toml").write_text(
                'dependencies = ["fastapi"]', encoding="utf-8"
            )

            scan = scan_project(project)
            suggestions = suggest_init_choices(scan)

            self.assertIn("python", scan.values("language"))
            self.assertIn("fastapi", scan.values("framework"))
            self.assertEqual(suggestions.stack.value, "python-ai")
            self.assertEqual(suggestions.topology.value, "fullstack-separated")

    def test_detects_node_ai_hints(self):
        with workspace_tempdir() as tmp:
            project = Path(tmp) / "project"
            project.mkdir()
            write_json(
                project / "package.json",
                {"dependencies": {"langchain": "^0.1.0"}},
            )

            scan = scan_project(project)
            suggestions = suggest_init_choices(scan)

            self.assertIn("langchain", scan.values("framework"))
            self.assertEqual(suggestions.stack.value, "nodejs-ai")

    def test_detects_frontend_without_backend_as_frontend_only(self):
        with workspace_tempdir() as tmp:
            project = Path(tmp) / "project"
            project.mkdir()
            (project / "vite.config.ts").write_text("export default {}", encoding="utf-8")
            write_json(
                project / "package.json",
                {"dependencies": {"react": "^18.0.0", "vite": "^5.0.0"}},
            )

            scan = scan_project(project)
            suggestions = suggest_init_choices(scan)

            self.assertIn("vite", scan.values("framework"))
            self.assertEqual(suggestions.topology.value, "front-end-only")

    def test_detects_testing_docker_monorepo_and_deploy_hints(self):
        with workspace_tempdir() as tmp:
            project = Path(tmp) / "project"
            project.mkdir()
            (project / "Dockerfile").write_text("FROM python", encoding="utf-8")
            (project / "pytest.ini").write_text("[pytest]", encoding="utf-8")
            (project / "pnpm-workspace.yaml").write_text("packages: []", encoding="utf-8")
            (project / "vercel.json").write_text("{}", encoding="utf-8")

            scan = scan_project(project)

            self.assertIn("present", scan.values("docker"))
            self.assertIn("pytest", scan.values("testing"))
            self.assertIn("pnpm-workspace", scan.values("monorepo"))
            self.assertIn("vercel", scan.values("deploy_provider"))

    def test_mixed_framework_evidence_avoids_strong_suggestions(self):
        with workspace_tempdir() as tmp:
            project = Path(tmp) / "project"
            project.mkdir()
            (project / "docusaurus.config.ts").write_text("config", encoding="utf-8")
            (project / "next.config.js").write_text("config", encoding="utf-8")

            suggestions = suggest_init_choices(scan_project(project))

            self.assertIsNone(suggestions.stack)
            self.assertIsNone(suggestions.topology)

    def test_scanner_ignores_generated_and_dependency_directories(self):
        with workspace_tempdir() as tmp:
            project = Path(tmp) / "project"
            ignored = project / "node_modules" / "next"
            ignored.mkdir(parents=True)
            (ignored / "package.json").write_text("{}", encoding="utf-8")

            scan = scan_project(project)

            self.assertNotIn("nextjs", scan.values("framework"))

    def test_scanner_does_not_mutate_project_config(self):
        with workspace_tempdir() as tmp:
            project = Path(tmp) / "project"
            project.mkdir()
            write_json(project / "package.json", {"dependencies": {"next": "^14.0.0"}})

            scan_project(project)

            self.assertFalse((project / ".rapid-os" / "config.json").exists())


class ScannerInitIntegrationTests(unittest.TestCase):
    def test_parser_supports_no_scan_for_init(self):
        parser = cli_main.create_parser()
        args = parser.parse_args(["init", "--no-scan"])

        self.assertTrue(args.no_scan)

    def test_stack_override_remains_authoritative_when_accepting_suggestions(self):
        with workspace_tempdir() as tmp:
            root = Path(tmp)
            project = root / "project"
            project.mkdir()
            templates = create_init_templates(root)
            (project / "docusaurus.config.ts").write_text("config", encoding="utf-8")

            inputs = iter(["y", "", "", "", "n", ""])
            args = argparse.Namespace(stack="web-modern", archetype=None, no_scan=False)

            with patch.object(cli_main, "CURRENT_DIR", project), patch.object(
                cli_main, "PROJECT_RAPID_DIR", project / ".rapid-os"
            ), patch.object(cli_main, "CONFIG_FILE", project / ".rapid-os" / "config.json"), patch.object(
                cli_main, "TEMPLATES_DIR", templates
            ), patch(
                "builtins.input", lambda prompt="": next(inputs)
            ), redirect_stdout(
                io.StringIO()
            ):
                cli_main.init_project(args)

            stack_content = (
                project / ".rapid-os" / "standards" / "tech-stack.md"
            ).read_text(encoding="utf-8")
            topology_content = (
                project / ".rapid-os" / "standards" / "topology.md"
            ).read_text(encoding="utf-8")

            self.assertIn("web-modern", stack_content)
            self.assertIn("doc-site", topology_content)

    def test_no_scan_preserves_manual_stack_and_topology_flow(self):
        with workspace_tempdir() as tmp:
            root = Path(tmp)
            project = root / "project"
            project.mkdir()
            templates = create_init_templates(root)
            (project / "docusaurus.config.ts").write_text("config", encoding="utf-8")

            inputs = iter(["1", "1", "", "", "", "n", ""])
            args = argparse.Namespace(stack=None, archetype=None, no_scan=True)

            with patch.object(cli_main, "CURRENT_DIR", project), patch.object(
                cli_main, "PROJECT_RAPID_DIR", project / ".rapid-os"
            ), patch.object(cli_main, "CONFIG_FILE", project / ".rapid-os" / "config.json"), patch.object(
                cli_main, "TEMPLATES_DIR", templates
            ), patch(
                "builtins.input", lambda prompt="": next(inputs)
            ), redirect_stdout(
                io.StringIO()
            ):
                cli_main.init_project(args)

            stack_content = (
                project / ".rapid-os" / "standards" / "tech-stack.md"
            ).read_text(encoding="utf-8")
            topology_content = (
                project / ".rapid-os" / "standards" / "topology.md"
            ).read_text(encoding="utf-8")

            self.assertIn("docs-modern", stack_content)
            self.assertIn("doc-site", topology_content)


if __name__ == "__main__":
    unittest.main()
