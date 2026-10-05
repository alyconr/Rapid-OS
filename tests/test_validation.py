import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from rapid_os.adapters.agents import AgentRegistry
from rapid_os.adapters.agents.base import AgentAdapter, AgentOutput
from rapid_os.adapters.project_snapshot import write_project_snapshot
from rapid_os.cli.main import render_validation_report
from rapid_os.domain.scanner import build_project_model
from rapid_os.domain.validation import (
    Diagnostic,
    ERROR,
    INFO,
    WARNING,
    ValidationReport,
    detect_placeholders,
    inspect_project_context,
    validate_composed_context,
    validate_project_config,
    validate_project_intelligence,
    validate_stack_topology,
    validate_templates,
)


REPO_ROOT = Path(__file__).resolve().parents[1]


def workspace_tempdir():
    return tempfile.TemporaryDirectory(dir=REPO_ROOT)


def create_minimal_templates(root: Path):
    templates_dir = root / "templates"
    for dirname in ("stacks", "topologies", "archetypes", "mcp"):
        (templates_dir / dirname).mkdir(parents=True)
    (templates_dir / "stacks" / "web-modern.md").write_text("stack", encoding="utf-8")
    (templates_dir / "topologies" / "front-end-only.md").write_text(
        "topology", encoding="utf-8"
    )
    (templates_dir / "mcp" / "postgres.json").write_text("{}", encoding="utf-8")
    return templates_dir


class BrokenAdapter(AgentAdapter):
    id = "broken"
    name = "Broken"
    outputs = (AgentOutput(Path("BROKEN.md"), "broken"),)

    def render(self, context):
        return {}


class ValidationTests(unittest.TestCase):
    def test_missing_required_template_directory_is_error(self):
        with workspace_tempdir() as tmp:
            root = Path(tmp)
            templates_dir = create_minimal_templates(root)
            (templates_dir / "mcp" / "postgres.json").unlink()
            (templates_dir / "mcp").rmdir()

            report = validate_templates(templates_dir)

            self.assertTrue(report.has_errors)
            self.assertIn("RAPID103", [diagnostic.code for diagnostic in report.diagnostics])

    def test_invalid_mcp_json_template_is_error(self):
        with workspace_tempdir() as tmp:
            root = Path(tmp)
            templates_dir = create_minimal_templates(root)
            (templates_dir / "mcp" / "postgres.json").write_text(
                "{invalid", encoding="utf-8"
            )

            report = validate_templates(templates_dir)

            self.assertTrue(report.has_errors)
            self.assertIn("RAPID109", [diagnostic.code for diagnostic in report.diagnostics])

    def test_placeholder_detection_finds_common_unresolved_tokens(self):
        placeholders = detect_placeholders(
            "Use {{APP_NAME}}, YOUR_API_KEY_HERE, [PASSWORD], and TODO."
        )

        self.assertIn("{{APP_NAME}}", placeholders)
        self.assertIn("YOUR_API_KEY_HERE", placeholders)
        self.assertIn("[PASSWORD]", placeholders)
        self.assertIn("TODO", placeholders)

    def test_unknown_tool_id_is_error(self):
        with workspace_tempdir() as tmp:
            config_file = Path(tmp) / ".rapid-os" / "config.json"
            config_file.parent.mkdir()
            config_file.write_text('{"tools": ["cursor", "unknown-agent"]}', encoding="utf-8")

            report = validate_project_config(config_file)

            self.assertTrue(report.has_errors)
            self.assertIn("RAPID307", [diagnostic.code for diagnostic in report.diagnostics])

    def test_research_tools_are_known_non_agent_tools(self):
        with workspace_tempdir() as tmp:
            config_file = Path(tmp) / ".rapid-os" / "config.json"
            config_file.parent.mkdir()
            config_file.write_text('{"tools": ["context7", "firecrawl"]}', encoding="utf-8")

            report = validate_project_config(config_file)

            self.assertFalse(report.has_errors)
            self.assertEqual(
                [diagnostic.code for diagnostic in report.diagnostics],
                ["RAPID306", "RAPID306"],
            )

    def test_missing_adapter_render_contract_is_error_with_test_registry(self):
        with workspace_tempdir() as tmp:
            config_file = Path(tmp) / ".rapid-os" / "config.json"
            config_file.parent.mkdir()
            config_file.write_text('{"tools": ["broken"]}', encoding="utf-8")
            registry = AgentRegistry([BrokenAdapter()])

            report = validate_project_config(config_file, registry)

            self.assertTrue(report.has_errors)
            self.assertIn("RAPID310", [diagnostic.code for diagnostic in report.diagnostics])

    def test_empty_context_is_error(self):
        with workspace_tempdir() as tmp:
            current_dir = Path(tmp)
            project_dir = current_dir / ".rapid-os"
            (project_dir / "standards").mkdir(parents=True)

            report = validate_composed_context(project_dir, current_dir)

            self.assertTrue(report.has_errors)
            self.assertIn("RAPID500", [diagnostic.code for diagnostic in report.diagnostics])

    def test_stack_topology_mismatch_is_error(self):
        with workspace_tempdir() as tmp:
            current_dir = Path(tmp)
            standards_dir = current_dir / ".rapid-os" / "standards"
            standards_dir.mkdir(parents=True)
            (standards_dir / "tech-stack.md").write_text(
                "# TECH STACK: MODERN DOCS\nDocusaurus 3+", encoding="utf-8"
            )
            (standards_dir / "topology.md").write_text(
                "# TOPOLOGY: FRONTEND ONLY\nBackend: NONE", encoding="utf-8"
            )

            report = validate_stack_topology(current_dir / ".rapid-os")

            self.assertTrue(report.has_errors)
            self.assertIn("RAPID402", [diagnostic.code for diagnostic in report.diagnostics])

    def test_inspect_context_reports_sections_tools_and_preview(self):
        with workspace_tempdir() as tmp:
            current_dir = Path(tmp)
            project_dir = current_dir / ".rapid-os"
            standards_dir = project_dir / "standards"
            standards_dir.mkdir(parents=True)
            (standards_dir / "tech-stack.md").write_text("stack", encoding="utf-8")
            (standards_dir / "topology.md").write_text("topology", encoding="utf-8")
            config_file = project_dir / "config.json"
            config_file.write_text('{"tools": ["cursor"]}', encoding="utf-8")

            inspection = inspect_project_context(project_dir, current_dir, config_file)

            self.assertIn("tech-stack.md", inspection.included_sections)
            self.assertIn("topology.md", inspection.included_sections)
            self.assertEqual(inspection.selected_tools, ("cursor",))
            self.assertIn("stack", inspection.context)

    def test_report_exit_codes_support_errors_and_strict_warnings(self):
        success = ValidationReport((Diagnostic(INFO, "I", "ok"),))
        warning = ValidationReport((Diagnostic(WARNING, "W", "warn"),))
        error = ValidationReport((Diagnostic(ERROR, "E", "bad"),))

        self.assertEqual(success.exit_code(), 0)
        self.assertEqual(warning.exit_code(), 0)
        self.assertEqual(warning.exit_code(strict=True), 1)
        self.assertEqual(error.exit_code(), 1)

    def test_json_output_shape(self):
        report = ValidationReport((Diagnostic(INFO, "RAPID000", "ok"),))
        output = io.StringIO()

        with redirect_stdout(output):
            exit_code = render_validation_report(report, json_output=True)

        payload = json.loads(output.getvalue())
        self.assertEqual(exit_code, 0)
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["summary"], {"info": 1, "warning": 0, "error": 0})
        self.assertEqual(payload["diagnostics"][0]["code"], "RAPID000")

    def test_corrupt_config_json_and_schema_produce_explicit_diagnostics(self):
        with workspace_tempdir() as tmp:
            project_dir = Path(tmp) / ".rapid-os"
            standards_dir = project_dir / "standards"
            standards_dir.mkdir(parents=True)
            (standards_dir / "tech-stack.md").write_text("stack", encoding="utf-8")
            (standards_dir / "topology.md").write_text("topology", encoding="utf-8")
            config_file = project_dir / "config.json"

            config_file.write_text("{corrupt-json", encoding="utf-8")
            json_report = validate_project_config(config_file)
            self.assertTrue(json_report.has_errors)
            self.assertIn(
                "RAPID301",
                [diagnostic.code for diagnostic in json_report.diagnostics],
            )

            inspection = inspect_project_context(
                project_dir, Path(tmp), config_file
            )
            self.assertTrue(inspection.report.has_errors)
            self.assertIn(
                "RAPID301",
                [diagnostic.code for diagnostic in inspection.report.diagnostics],
            )

            config_file.write_text('{"tools": "not-a-list"}', encoding="utf-8")
            schema_report = validate_project_config(config_file)
            self.assertTrue(schema_report.has_errors)
            self.assertIn(
                "RAPID303",
                [diagnostic.code for diagnostic in schema_report.diagnostics],
            )

            config_file.write_text('{"tools": [123]}', encoding="utf-8")
            item_report = validate_project_config(config_file)
            self.assertTrue(item_report.has_errors)
            self.assertIn(
                "RAPID305",
                [diagnostic.code for diagnostic in item_report.diagnostics],
            )

    def test_unreadable_config_produces_rapid302_error(self):
        with workspace_tempdir() as tmp:
            config_dir = Path(tmp) / ".rapid-os" / "config.json"
            config_dir.mkdir(parents=True)

            report = validate_project_config(config_dir)
            self.assertTrue(report.has_errors)
            self.assertIn(
                "RAPID302",
                [diagnostic.code for diagnostic in report.diagnostics],
            )

    def test_valid_project_intelligence_snapshot_produces_rapid600(self):
        with workspace_tempdir() as tmp:
            project = Path(tmp) / "project"
            project.mkdir()
            (project / "pyproject.toml").write_text(
                'dependencies = ["fastapi"]', encoding="utf-8"
            )
            model = build_project_model(project)
            write_project_snapshot(model, project / ".rapid-os")

            report = validate_project_intelligence(project / ".rapid-os", project)

            self.assertFalse(report.has_errors)
            self.assertEqual(
                [d.code for d in report.diagnostics],
                ["RAPID600"],
            )

    def test_corrupt_project_intelligence_snapshot_produces_rapid601(self):
        with workspace_tempdir() as tmp:
            project = Path(tmp) / "project"
            snapshot = project / ".rapid-os" / "project.json"
            snapshot.parent.mkdir(parents=True)
            snapshot.write_text("{corrupt", encoding="utf-8")

            report = validate_project_intelligence(project / ".rapid-os", project)

            self.assertTrue(report.has_errors)
            self.assertEqual(
                [d.code for d in report.diagnostics],
                ["RAPID601"],
            )

    def test_unsupported_schema_version_in_project_snapshot_produces_rapid603(self):
        with workspace_tempdir() as tmp:
            project = Path(tmp) / "project"
            snapshot = project / ".rapid-os" / "project.json"
            snapshot.parent.mkdir(parents=True)
            snapshot.write_text(
                json.dumps({"schema_version": 999, "root": ".", "facts": []}),
                encoding="utf-8",
            )

            report = validate_project_intelligence(project / ".rapid-os", project)

            self.assertTrue(report.has_errors)
            self.assertEqual(
                [d.code for d in report.diagnostics],
                ["RAPID603"],
            )

    def test_invalid_fact_in_project_snapshot_produces_rapid604(self):
        with workspace_tempdir() as tmp:
            project = Path(tmp) / "project"
            snapshot = project / ".rapid-os" / "project.json"
            snapshot.parent.mkdir(parents=True)
            snapshot.write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "root": ".",
                        "facts": [
                            {
                                "category": "framework",
                                "value": "fastapi",
                                "confidence": "high",
                                "detector": "framework.fastapi",
                                "evidence": [],
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )

            report = validate_project_intelligence(project / ".rapid-os", project)

            self.assertTrue(report.has_errors)
            self.assertEqual(
                [d.code for d in report.diagnostics],
                ["RAPID604"],
            )


if __name__ == "__main__":
    unittest.main()

