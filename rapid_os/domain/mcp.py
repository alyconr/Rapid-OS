import json
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping


PLACEHOLDER_VALUES = (
    "YOUR_API_KEY_HERE",
    "[PASSWORD]",
    "[PROJECT-ID]",
    "postgresql://user:password@localhost:5432/dbname",
)


@dataclass(frozen=True)
class McpServer:
    id: str
    command: str
    args: tuple[str, ...] = ()
    env: Mapping[str, str] | None = None
    extra: Mapping[str, object] | None = None
    source: str = "generated"


@dataclass(frozen=True)
class McpWarning:
    code: str
    message: str
    server_id: str | None = None
    path: Path | None = None


@dataclass(frozen=True)
class McpConfig:
    servers: tuple[McpServer, ...] = ()
    warnings: tuple[McpWarning, ...] = ()

    def server_ids(self):
        return tuple(server.id for server in self.servers)


def build_mcp_config(
    topology_content: str,
    selected_tools,
    current_dir: Path,
    templates_dir: Path,
):
    normalized_topology = topology_content.lower()
    selected_tools = set(selected_tools or [])
    servers = [filesystem_server(current_dir)]
    warnings = []

    if "postgres" in normalized_topology and "supabase" not in normalized_topology:
        template_servers, template_warnings = load_template_servers(
            templates_dir / "mcp" / "postgres.json"
        )
        servers.extend(template_servers)
        warnings.extend(template_warnings)

    if "supabase" in normalized_topology:
        template_servers, template_warnings = load_template_servers(
            templates_dir / "mcp" / "supabase.json"
        )
        servers.extend(template_servers)
        warnings.extend(template_warnings)

    if "context7" in selected_tools:
        servers.append(context7_server())
    if "firecrawl" in selected_tools:
        servers.append(firecrawl_server())

    for server in servers:
        warnings.extend(detect_server_warnings(server))

    return McpConfig(tuple(servers), tuple(warnings))


def filesystem_server(current_dir: Path):
    return McpServer(
        id="filesystem",
        command="npx",
        args=("-y", "@modelcontextprotocol/server-filesystem", str(current_dir)),
        source="generated",
    )


def context7_server():
    return McpServer(
        id="context7",
        command="npx",
        args=("-y", "@upstash/context7-mcp"),
        env={"CONTEXT7_API_KEY": "YOUR_API_KEY_HERE"},
        source="generated",
    )


def firecrawl_server():
    return McpServer(
        id="firecrawl",
        command="npx",
        args=("-y", "firecrawl-mcp"),
        env={"FIRECRAWL_API_KEY": "YOUR_API_KEY_HERE"},
        source="generated",
    )


def load_template_servers(template_path: Path):
    if not template_path.exists():
        return (), (
            McpWarning(
                "MCP001",
                f"MCP template not found: {template_path.name}",
                path=template_path,
            ),
        )

    try:
        payload = json.loads(template_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return (), (
            McpWarning(
                "MCP002",
                f"MCP template JSON is invalid: {exc.msg}",
                path=template_path,
            ),
        )
    except OSError as exc:
        return (), (
            McpWarning(
                "MCP003",
                f"MCP template could not be read: {exc}",
                path=template_path,
            ),
        )

    if not isinstance(payload, dict):
        return (), (
            McpWarning(
                "MCP004",
                "MCP template must contain an object of server definitions.",
                path=template_path,
            ),
        )

    servers = []
    warnings = []
    for server_id, definition in payload.items():
        server, server_warnings = server_from_mapping(
            server_id,
            definition,
            source=str(template_path),
            path=template_path,
        )
        if server:
            servers.append(server)
        warnings.extend(server_warnings)

    return tuple(servers), tuple(warnings)


def server_from_mapping(server_id, definition, source="mapping", path=None):
    warnings = []
    if not isinstance(definition, dict):
        return None, (
            McpWarning(
                "MCP005",
                f"MCP server '{server_id}' definition must be an object.",
                server_id=server_id,
                path=path,
            ),
        )

    command = definition.get("command")
    if not command:
        warnings.append(
            McpWarning(
                "MCP006",
                f"MCP server '{server_id}' is missing command.",
                server_id=server_id,
                path=path,
            )
        )
        return None, tuple(warnings)

    args = definition.get("args", ())
    if args is None:
        args = ()
    if not isinstance(args, list):
        warnings.append(
            McpWarning(
                "MCP007",
                f"MCP server '{server_id}' args should be a list.",
                server_id=server_id,
                path=path,
            )
        )
        args = ()

    env = definition.get("env")
    if env is not None and not isinstance(env, dict):
        warnings.append(
            McpWarning(
                "MCP008",
                f"MCP server '{server_id}' env should be an object.",
                server_id=server_id,
                path=path,
            )
        )
        env = None

    known_keys = {"command", "args", "env"}
    extra = {key: value for key, value in definition.items() if key not in known_keys}

    return (
        McpServer(
            id=str(server_id),
            command=str(command),
            args=tuple(str(arg) for arg in args),
            env=env,
            extra=extra or None,
            source=source,
        ),
        tuple(warnings),
    )


def detect_server_warnings(server: McpServer):
    warnings = []
    values = [server.command, *server.args]
    if server.env:
        values.extend(server.env.values())

    for value in values:
        for placeholder in PLACEHOLDER_VALUES:
            if placeholder in str(value):
                warnings.append(
                    McpWarning(
                        "MCP009",
                        f"MCP server '{server.id}' contains unresolved placeholder: {placeholder}",
                        server_id=server.id,
                    )
                )

    if server.id == "context7" and (
        not server.env or not server.env.get("CONTEXT7_API_KEY")
    ):
        warnings.append(
            McpWarning(
                "MCP010",
                "Context7 MCP server is missing CONTEXT7_API_KEY.",
                server_id=server.id,
            )
        )

    if server.id == "firecrawl" and (
        not server.env or not server.env.get("FIRECRAWL_API_KEY")
    ):
        warnings.append(
            McpWarning(
                "MCP011",
                "Firecrawl MCP server is missing FIRECRAWL_API_KEY.",
                server_id=server.id,
            )
        )

    return tuple(warnings)
