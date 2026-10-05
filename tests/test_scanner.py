import argparse
import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from rapid_os.cli import main as cli_main
from rapid_os.domain.project import Confidence
from rapid_os.domain.scanner import (
    build_project_model,
    read_env_keys,
    scan_project,
    suggest_init_choices,
)


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

    def test_read_env_keys_extracts_only_names_and_ignores_comments_and_invalid_lines(self):
        with workspace_tempdir() as tmp:
            env_file = Path(tmp) / ".env.local"
            env_file.write_text(
                "# SUPABASE_URL=https://commented.supabase.co\n"
                "INVALID LINE WITHOUT EQUALS\n"
                "123_INVALID_KEY=secret\n"
                "DATABASE_URL=postgresql://admin:UltraSecretPass123!@db.internal:5432/prod\n"
                "export SUPABASE_ANON_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.SUPER_SECRET_TOKEN\n"
                "MONGO_URI=mongodb+srv://user:TopSecretMongo99@cluster.mongodb.net/app\n",
                encoding="utf-8",
            )

            keys = read_env_keys(env_file)

            self.assertEqual(
                keys,
                ("DATABASE_URL", "SUPABASE_ANON_KEY", "MONGO_URI"),
            )
            serialized = " ".join(keys)
            self.assertNotIn("UltraSecretPass123!", serialized)
            self.assertNotIn("SUPER_SECRET_TOKEN", serialized)
            self.assertNotIn("TopSecretMongo99", serialized)

    def test_scanner_env_detection_never_exposes_or_matches_secret_values(self):
        with workspace_tempdir() as tmp:
            project = Path(tmp) / "project"
            project.mkdir()
            secret_postgres = "UltraSecretPostgresPassword_987654"
            secret_supabase = "eyJhbGciOi_SuperSecretSupabaseJwt_123456"
            secret_decoy = "value_mentioning_MONGO_and_SUPABASE_and_DATABASE_URL_in_secret"
            (project / ".env").write_text(
                f"# Comment with MONGO and SUPABASE\n"
                f"DATABASE_URL=postgresql://admin:{secret_postgres}@localhost:5432/db\n"
                f"NEXT_PUBLIC_SUPABASE_URL=https://{secret_supabase}.supabase.co\n"
                f"APP_SECRET_TOKEN={secret_decoy}\n",
                encoding="utf-8",
            )

            scan = scan_project(project)
            suggestions = suggest_init_choices(scan)
            output_buffer = io.StringIO()
            with redirect_stdout(output_buffer):
                cli_main.print_scan_summary(scan, suggestions)

            self.assertIn("postgres", scan.values("database"))
            self.assertIn("supabase", scan.values("database"))
            self.assertNotIn("mongo", scan.values("database"))

            combined_dump = json.dumps(
                {
                    "scan": scan.to_dict(),
                    "suggestions": suggestions.to_dict(),
                    "reasons": [
                        evidence.reason
                        for detection in scan.detections
                        for evidence in detection.evidence
                    ],
                    "stdout": output_buffer.getvalue(),
                }
            )
            self.assertNotIn(secret_postgres, combined_dump)
            self.assertNotIn(secret_supabase, combined_dump)
            self.assertNotIn(secret_decoy, combined_dump)

    def test_consecutive_scans_produce_identical_project_model_and_json(self):
        with workspace_tempdir() as tmp:
            project = Path(tmp) / "project"
            project.mkdir()
            (project / "Dockerfile").write_text("FROM python:3.12", encoding="utf-8")
            (project / "pytest.ini").write_text("[pytest]", encoding="utf-8")
            write_json(
                project / "package.json",
                {"dependencies": {"next": "^14.0.0", "pg": "^8.0.0"}},
            )
            (project / "requirements.txt").write_text(
                "fastapi>=0.110.0\npsycopg[binary]\n", encoding="utf-8"
            )

            first = build_project_model(project)
            second = build_project_model(project)

            self.assertEqual(first, second)
            self.assertEqual(first.to_dict(), second.to_dict())
            self.assertEqual(first.to_json(), second.to_json())

    def test_consolidates_same_fact_across_package_json_env_and_requirements(self):
        with workspace_tempdir() as tmp:
            project = Path(tmp) / "project"
            project.mkdir()
            write_json(
                project / "package.json",
                {"dependencies": {"pg": "^8.11.0"}},
            )
            (project / "requirements.txt").write_text(
                "psycopg2-binary==2.9.9\n", encoding="utf-8"
            )
            (project / ".env").write_text(
                "DATABASE_URL=postgresql://localhost:5432/app\n", encoding="utf-8"
            )

            model = build_project_model(project)
            db_facts = model.facts_for("database")

            self.assertEqual(len(db_facts), 1)
            postgres_fact = db_facts[0]
            self.assertEqual(postgres_fact.value, "postgres")
            self.assertEqual(postgres_fact.confidence, Confidence.MEDIUM)
            self.assertEqual(postgres_fact.detector, "database.postgres")
            self.assertEqual(
                [ev.portable_path() for ev in postgres_fact.evidence],
                [".env", "package.json", "requirements.txt"],
            )
            self.assertEqual(
                [ev.detector for ev in postgres_fact.evidence],
                ["database.postgres", "database.postgres", "database.postgres"],
            )

    def test_secret_decoy_value_never_appears_in_serialized_project_model(self):
        with workspace_tempdir() as tmp:
            project = Path(tmp) / "project"
            project.mkdir()
            (project / ".env").write_text(
                "DATABASE_URL=postgresql://admin:SUPER_SECRET_VALUE_12345@localhost/db\n",
                encoding="utf-8",
            )

            model = build_project_model(project)

            self.assertTrue(model.has("database"))
            self.assertTrue(model.has("database", "postgres"))
            self.assertNotIn("SUPER_SECRET_VALUE_12345", json.dumps(model.to_dict()))
            self.assertNotIn("SUPER_SECRET_VALUE_12345", model.to_json())

    def test_project_scan_facade_wraps_project_model_without_duplicate_state(self):
        with workspace_tempdir() as tmp:
            project = Path(tmp) / "project"
            project.mkdir()
            (project / "pyproject.toml").write_text(
                'dependencies = ["fastapi"]', encoding="utf-8"
            )

            scan = scan_project(project)
            model = scan.to_model()

            self.assertIs(model, scan.model)
            self.assertEqual(scan.facts, model.facts)
            self.assertEqual(scan.detections, model.facts)
            self.assertEqual(scan.values("framework"), model.values("framework"))
            self.assertTrue(scan.has("framework"))
            self.assertTrue(scan.has("framework", "fastapi"))
            self.assertFalse(scan.has("framework", "nextjs"))
            self.assertFalse(scan.has("database"))
            for fact in model.facts:
                for ev in fact.evidence:
                    self.assertEqual(ev.detector, fact.detector)
            self.assertEqual(
                suggest_init_choices(scan).to_dict(),
                suggest_init_choices(model).to_dict(),
            )


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
