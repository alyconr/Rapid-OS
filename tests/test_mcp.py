import argparse
import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from rapid_os.adapters.mcp import (
    render_antigravity_mcp_json,
    render_claude_desktop_config,
    render_claude_mcp_json,
    render_codex_config_toml,
    render_cursor_mcp_json,
    render_vscode_mcp_json,
    resolve_mcp_install_target,
    write_mcp_install_target,
)
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
    server_from_mapping,
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

    def test_missing_template_file_returns_warning_without_crashing(self):
        with workspace_tempdir() as tmp:
            path = Path(tmp) / "templates" / "mcp" / "postgres.json"

            servers, warnings = load_template_servers(path)

            self.assertEqual(servers, ())
            self.assertEqual(warnings[0].code, "MCP001")

    def test_malformed_server_without_command_is_skipped_with_warning(self):
        server, warnings = server_from_mapping("broken", {"args": ["mcp-broken"]})

        self.assertIsNone(server)
        self.assertEqual(warnings[0].code, "MCP006")

    def test_invalid_args_shape_is_warned_and_safely_handled(self):
        server, warnings = server_from_mapping(
            "custom",
            {"command": "npx", "args": "not-a-list"},
        )

        self.assertIsNotNone(server)
        self.assertEqual(server.args, ())
        self.assertTrue(any(warning.code == "MCP007" for warning in warnings))

    def test_invalid_env_shape_is_warned_and_safely_handled(self):
        server, warnings = server_from_mapping(
            "custom",
            {"command": "npx", "env": "not-an-object"},
        )

        self.assertIsNotNone(server)
        self.assertIsNone(server.env)
        self.assertTrue(any(warning.code == "MCP008" for warning in warnings))

    def test_placeholder_warnings_are_non_blocking(self):
        server = context7_server()

        warnings = detect_server_warnings(server)

        self.assertTrue(any(warning.code == "MCP009" for warning in warnings))

    def test_missing_research_tool_keys_are_warnings(self):
        warnings = detect_server_warnings(
            McpServer(id="context7", command="npx", args=("-y", "@upstash/context7-mcp"))
        )

        self.assertTrue(any(warning.code == "MCP010" for warning in warnings))

    def test_renderer_outputs_all_supported_server_ids(self):
        with workspace_tempdir() as tmp:
            templates_dir = create_mcp_templates(Path(tmp))
            postgres_servers, postgres_warnings = load_template_servers(
                templates_dir / "mcp" / "postgres.json"
            )
            supabase_servers, supabase_warnings = load_template_servers(
                templates_dir / "mcp" / "supabase.json"
            )
            config = McpConfig(
                (
                    filesystem_server(Path("project")),
                    *postgres_servers,
                    *supabase_servers,
                    context7_server(),
                    firecrawl_server(),
                ),
                (*postgres_warnings, *supabase_warnings),
            )

            rendered = render_claude_desktop_config(config)

            self.assertEqual(
                set(rendered["mcpServers"]),
                {"filesystem", "postgres", "supabase", "context7", "firecrawl"},
            )
            for server in rendered["mcpServers"].values():
                self.assertIn("command", server)
                self.assertIn("args", server)

    def test_render_claude_and_cursor_json_use_mcp_servers(self):
        config = McpConfig((context7_server(),))

        self.assertEqual(set(render_claude_mcp_json(config)), {"mcpServers"})
        self.assertEqual(set(render_cursor_mcp_json(config)), {"mcpServers"})

    def test_render_vscode_json_uses_servers_key(self):
        config = McpConfig((context7_server(),))

        rendered = render_vscode_mcp_json(config)

        self.assertEqual(set(rendered), {"servers"})
        self.assertIn("context7", rendered["servers"])

    def test_render_antigravity_json_uses_current_json_compatible_shape(self):
        config = McpConfig((context7_server(),))

        rendered = render_antigravity_mcp_json(config)

        self.assertEqual(set(rendered), {"mcpServers"})
        self.assertIn("context7", rendered["mcpServers"])

    def test_render_codex_config_toml_uses_mcp_servers_sections(self):
        config = McpConfig((context7_server(),))

        rendered = render_codex_config_toml(config)

        self.assertIn("[mcp_servers.context7]", rendered)
        self.assertIn('command = "npx"', rendered)
        self.assertIn('env = { CONTEXT7_API_KEY = "YOUR_API_KEY_HERE" }', rendered)

    def test_resolve_mcp_install_target_supports_documented_paths(self):
        current_dir = Path("/workspace/project")
        home_dir = Path("/users/dev")

        self.assertEqual(
            resolve_mcp_install_target("codex", "project", current_dir, home_dir).path,
            current_dir / ".codex" / "config.toml",
        )
        self.assertEqual(
            resolve_mcp_install_target("codex", "global", current_dir, home_dir).path,
            home_dir / ".codex" / "config.toml",
        )
        self.assertEqual(
            resolve_mcp_install_target("claude", "project", current_dir, home_dir).path,
            current_dir / ".mcp.json",
        )
        self.assertEqual(
            resolve_mcp_install_target("claude", "global", current_dir, home_dir).path,
            home_dir / ".claude.json",
        )
        self.assertEqual(
            resolve_mcp_install_target("cursor", "project", current_dir, home_dir).path,
            current_dir / ".cursor" / "mcp.json",
        )
        self.assertEqual(
            resolve_mcp_install_target("cursor", "global", current_dir, home_dir).path,
            home_dir / ".cursor" / "mcp.json",
        )
        self.assertEqual(
            resolve_mcp_install_target("vscode", "project", current_dir, home_dir).path,
            current_dir / ".vscode" / "mcp.json",
        )
        self.assertEqual(
            resolve_mcp_install_target("antigravity", "global", current_dir, home_dir).path,
            home_dir / ".gemini" / "antigravity" / "mcp_config.json",
        )

    def test_resolve_mcp_install_target_rejects_unsupported_scope(self):
        with self.assertRaises(ValueError):
            resolve_mcp_install_target("antigravity", "project", Path("."), Path("/tmp"))

    def test_write_mcp_install_target_backs_up_and_merges_global_claude_json(self):
        with workspace_tempdir() as tmp:
            root = Path(tmp)
            target = resolve_mcp_install_target(
                "claude",
                "global",
                root,
                root / "home",
            )
            target.path.parent.mkdir(parents=True, exist_ok=True)
            target.path.write_text(
                json.dumps(
                    {
                        "theme": "dark",
                        "mcpServers": {"old": {"command": "old", "args": []}},
                    }
                ),
                encoding="utf-8",
            )

            write_mcp_install_target(
                target,
                render_claude_mcp_json(McpConfig((context7_server(),))),
            )

            payload = json.loads(target.path.read_text(encoding="utf-8"))
            self.assertEqual(payload["theme"], "dark")
            self.assertIn("context7", payload["mcpServers"])
            self.assertTrue(list(target.path.parent.glob(".claude.json.*.bak")))

    def test_write_mcp_install_target_preserves_existing_codex_settings(self):
        with workspace_tempdir() as tmp:
            root = Path(tmp)
            target = resolve_mcp_install_target(
                "codex",
                "project",
                root / "project",
                root / "home",
            )
            target.path.parent.mkdir(parents=True, exist_ok=True)
            target.path.write_text(
                '[core]\nmodel = "gpt-5"\n',
                encoding="utf-8",
            )

            write_mcp_install_target(
                target,
                render_codex_config_toml(McpConfig((context7_server(),))),
            )

            content = target.path.read_text(encoding="utf-8")
            self.assertIn('[core]\nmodel = "gpt-5"', content)
            self.assertIn("[mcp_servers.context7]", content)
            self.assertEqual(content.count("[mcp_servers.context7]"), 1)
            self.assertTrue(list(target.path.parent.glob("config.toml.*.bak")))


class McpCliTests(unittest.TestCase):
    def test_generate_mcp_config_writes_claude_project_json_when_flags_are_provided(self):
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
                cli_main.generate_mcp_config(
                    argparse.Namespace(ide="claude", scope="project")
                )

            payload = json.loads(
                (current_dir / ".mcp.json").read_text(encoding="utf-8")
            )

            self.assertIn("mcpServers", payload)
            self.assertIn("filesystem", payload["mcpServers"])
            self.assertIn("supabase", payload["mcpServers"])
            self.assertIn("context7", payload["mcpServers"])
            self.assertNotIn("postgres", payload["mcpServers"])

    def test_generate_mcp_config_cancel_before_init_writes_nothing(self):
        with workspace_tempdir() as tmp:
            root = Path(tmp)
            current_dir = root / "project"
            current_dir.mkdir()
            project_dir = current_dir / ".rapid-os"
            templates_dir = create_mcp_templates(root)

            with patch.object(cli_main, "CURRENT_DIR", current_dir), patch.object(
                cli_main, "PROJECT_RAPID_DIR", project_dir
            ), patch.object(cli_main, "CONFIG_FILE", project_dir / "config.json"), patch.object(
                cli_main, "TEMPLATES_DIR", templates_dir
            ), patch(
                "builtins.input", return_value="2"
            ), redirect_stdout(
                io.StringIO()
            ):
                cli_main.generate_mcp_config(
                    argparse.Namespace(ide="claude", scope="project")
                )

            self.assertFalse((current_dir / ".mcp.json").exists())
            self.assertFalse(project_dir.exists())

    def test_generate_mcp_config_minimal_setup_before_init(self):
        with workspace_tempdir() as tmp:
            root = Path(tmp)
            current_dir = root / "project"
            current_dir.mkdir()
            project_dir = current_dir / ".rapid-os"
            templates_dir = create_mcp_templates(root)

            with patch.object(cli_main, "CURRENT_DIR", current_dir), patch.object(
                cli_main, "PROJECT_RAPID_DIR", project_dir
            ), patch.object(cli_main, "CONFIG_FILE", project_dir / "config.json"), patch.object(
                cli_main, "TEMPLATES_DIR", templates_dir
            ), patch(
                "builtins.input", return_value="1"
            ), redirect_stdout(
                io.StringIO()
            ):
                cli_main.generate_mcp_config(
                    argparse.Namespace(ide="claude", scope="project")
                )

            self.assertTrue((project_dir / "standards" / "topology.md").exists())
            self.assertTrue((project_dir / "config.json").exists())
            payload = json.loads(
                (current_dir / ".mcp.json").read_text(encoding="utf-8")
            )

            self.assertEqual(set(payload["mcpServers"]), {"filesystem"})

    def test_generate_mcp_config_supports_interactive_ide_and_scope_selection(self):
        with workspace_tempdir() as tmp:
            root = Path(tmp)
            current_dir = root / "project"
            project_dir = current_dir / ".rapid-os"
            standards_dir = project_dir / "standards"
            standards_dir.mkdir(parents=True)
            templates_dir = create_mcp_templates(root)

            (standards_dir / "topology.md").write_text(
                "Database: PostgreSQL", encoding="utf-8"
            )
            (project_dir / "config.json").write_text(
                json.dumps({"tools": []}), encoding="utf-8"
            )

            with patch.object(cli_main, "CURRENT_DIR", current_dir), patch.object(
                cli_main, "PROJECT_RAPID_DIR", project_dir
            ), patch.object(cli_main, "CONFIG_FILE", project_dir / "config.json"), patch.object(
                cli_main, "TEMPLATES_DIR", templates_dir
            ), patch(
                "builtins.input", side_effect=["3", "1"]
            ), redirect_stdout(
                io.StringIO()
            ):
                cli_main.generate_mcp_config(argparse.Namespace())

            payload = json.loads(
                (current_dir / ".cursor" / "mcp.json").read_text(encoding="utf-8")
            )

            self.assertIn("mcpServers", payload)
            self.assertIn("postgres", payload["mcpServers"])


if __name__ == "__main__":
    unittest.main()
