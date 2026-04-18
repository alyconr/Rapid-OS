import argparse
import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from rapid_os.adapters.mcp import render_claude_desktop_config
from rapid_os.cli import main as cli_main
from rapid_os.domain.mcp import (
    McpConfig,
    McpServer,
    build_mcp_config,
    context7_server,
    detect_server_warnings,
    filesystem_server,
    firecrawl_server,
    load_template_servers,
)


REPO_ROOT = Path(__file__).resolve().parents[1]


def workspace_tempdir():
    return tempfile.TemporaryDirectory(dir=REPO_ROOT)


def create_mcp_templates(root: Path):
    templates_dir = root / "templates"
    mcp_dir = templates_dir / "mcp"
    mcp_dir.mkdir(parents=True)
    (mcp_dir / "postgres.json").write_text(
        json.dumps(
            {
                "postgres": {
                    "command": "docker",
                    "args": [
                        "run",
                        "-i",
                        "--rm",
                        "-e",
                        "POSTGRES_CONNECTION_STRING=postgresql://user:password@localhost:5432/dbname",
                        "mcp/postgres",
                    ],
                }
            }
        ),
        encoding="utf-8",
    )
    (mcp_dir / "supabase.json").write_text(
        json.dumps(
            {
                "supabase": {
                    "command": "npx",
                    "args": [
                        "-y",
                        "@modelcontextprotocol/server-postgres",
                        "postgresql://postgres:[PASSWORD]@db.[PROJECT-ID].supabase.co:6543/postgres?pgbouncer=true",
                    ],
                }
            }
        ),
        encoding="utf-8",
    )
    return templates_dir


class McpDomainTests(unittest.TestCase):
    def test_filesystem_server_model(self):
        server = filesystem_server(Path("project"))

        self.assertEqual(server.id, "filesystem")
        self.assertEqual(server.command, "npx")
        self.assertEqual(
            server.args,
            ("-y", "@modelcontextprotocol/server-filesystem", "project"),
        )

    def test_research_server_models(self):
        context7 = context7_server()
        firecrawl = firecrawl_server()

        self.assertEqual(context7.id, "context7")
        self.assertEqual(context7.env["CONTEXT7_API_KEY"], "YOUR_API_KEY_HERE")
        self.assertEqual(firecrawl.id, "firecrawl")
        self.assertEqual(firecrawl.env["FIRECRAWL_API_KEY"], "YOUR_API_KEY_HERE")

    def test_build_config_includes_filesystem_by_default(self):
        with workspace_tempdir() as tmp:
            templates_dir = create_mcp_templates(Path(tmp))

            config = build_mcp_config("", [], Path(tmp), templates_dir)

            self.assertEqual(config.server_ids(), ("filesystem",))

    def test_postgres_topology_loads_postgres_template(self):
        with workspace_tempdir() as tmp:
            templates_dir = create_mcp_templates(Path(tmp))

            config = build_mcp_config(
                "Database: PostgreSQL", [], Path(tmp), templates_dir
            )

            self.assertIn("filesystem", config.server_ids())
            self.assertIn("postgres", config.server_ids())
            self.assertNotIn("supabase", config.server_ids())

    def test_supabase_topology_loads_supabase_template_not_postgres(self):
        with workspace_tempdir() as tmp:
            templates_dir = create_mcp_templates(Path(tmp))

            config = build_mcp_config(
                "Database: Supabase Postgres", [], Path(tmp), templates_dir
            )

            self.assertIn("supabase", config.server_ids())
            self.assertNotIn("postgres", config.server_ids())

    def test_selected_research_tools_add_servers(self):
        with workspace_tempdir() as tmp:
            templates_dir = create_mcp_templates(Path(tmp))

            config = build_mcp_config(
                "", ["context7", "firecrawl"], Path(tmp), templates_dir
            )

            self.assertIn("context7", config.server_ids())
            self.assertIn("firecrawl", config.server_ids())

    def test_renderer_outputs_current_claude_desktop_shape(self):
        with workspace_tempdir() as tmp:
            templates_dir = create_mcp_templates(Path(tmp))
            config = build_mcp_config(
                "", ["context7"], Path("project"), templates_dir
            )

            rendered = render_claude_desktop_config(config)

            self.assertEqual(set(rendered), {"mcpServers"})
            self.assertIn("filesystem", rendered["mcpServers"])
            self.assertEqual(
                rendered["mcpServers"]["context7"]["env"],
                {"CONTEXT7_API_KEY": "YOUR_API_KEY_HERE"},
            )

    def test_renderer_preserves_extra_template_fields(self):
        config = McpConfig(
            (
                McpServer(
                    id="custom",
                    command="npx",
                    args=("-y", "custom-mcp"),
                    extra={"transport": "stdio"},
                ),
            )
        )

        rendered = render_claude_desktop_config(config)

        self.assertEqual(
            rendered["mcpServers"]["custom"],
            {
                "transport": "stdio",
                "command": "npx",
                "args": ["-y", "custom-mcp"],
            },
        )

    def test_invalid_template_json_returns_warning_without_crashing(self):
        with workspace_tempdir() as tmp:
            path = Path(tmp) / "templates" / "mcp" / "postgres.json"
            path.parent.mkdir(parents=True)
            path.write_text("{invalid", encoding="utf-8")

            servers, warnings = load_template_servers(path)

            self.assertEqual(servers, ())
            self.assertEqual(warnings[0].code, "MCP002")

    def test_placeholder_warnings_are_non_blocking(self):
        server = context7_server()

        warnings = detect_server_warnings(server)

        self.assertTrue(any(warning.code == "MCP009" for warning in warnings))

    def test_missing_research_tool_keys_are_warnings(self):
        warnings = detect_server_warnings(
            McpServer(id="context7", command="npx", args=("-y", "@upstash/context7-mcp"))
        )

        self.assertTrue(any(warning.code == "MCP010" for warning in warnings))


class McpCliTests(unittest.TestCase):
    def test_generate_mcp_config_writes_compatible_claude_desktop_json(self):
        with workspace_tempdir() as tmp:
            root = Path(tmp)
            current_dir = root / "project"
            project_dir = current_dir / ".rapid-os"
            standards_dir = project_dir / "standards"
            standards_dir.mkdir(parents=True)
            templates_dir = create_mcp_templates(root)

            (standards_dir / "topology.md").write_text(
                "Database: Supabase", encoding="utf-8"
            )
            (project_dir / "config.json").write_text(
                json.dumps({"tools": ["context7"]}), encoding="utf-8"
            )

            with patch.object(cli_main, "CURRENT_DIR", current_dir), patch.object(
                cli_main, "PROJECT_RAPID_DIR", project_dir
            ), patch.object(cli_main, "CONFIG_FILE", project_dir / "config.json"), patch.object(
                cli_main, "TEMPLATES_DIR", templates_dir
            ), redirect_stdout(
                io.StringIO()
            ):
                cli_main.generate_mcp_config(argparse.Namespace())

            payload = json.loads(
                (current_dir / "claude_desktop_config.json").read_text(
                    encoding="utf-8"
                )
            )

            self.assertIn("mcpServers", payload)
            self.assertIn("filesystem", payload["mcpServers"])
            self.assertIn("supabase", payload["mcpServers"])
            self.assertIn("context7", payload["mcpServers"])
            self.assertNotIn("postgres", payload["mcpServers"])


if __name__ == "__main__":
    unittest.main()
