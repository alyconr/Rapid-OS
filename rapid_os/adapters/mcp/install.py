import json
from dataclasses import dataclass
from pathlib import Path

from rapid_os.adapters.mcp.claude_desktop import render_claude_desktop_config
from rapid_os.core.filesystem import create_backup
from rapid_os.core.paths import RAPID_HOME


MANAGED_TOML_BEGIN = "# BEGIN RAPID OS MCP"
MANAGED_TOML_END = "# END RAPID OS MCP"

SUPPORTED_MCP_IDES = ("codex", "claude", "cursor", "vscode", "antigravity")

SUPPORTED_MCP_SCOPES = {
    "codex": ("project", "global"),
    "claude": ("project", "global"),
    "cursor": ("project", "global"),
    "vscode": ("project",),
    "antigravity": ("global",),
}


@dataclass(frozen=True)
class McpInstallTarget:
    ide: str
    scope: str
    path: Path
    format: str
    json_key: str | None = None
    preserve_other_keys: bool = False


def resolve_supported_mcp_scopes(ide: str):
    if ide not in SUPPORTED_MCP_SCOPES:
        raise ValueError(f"Unsupported MCP IDE: {ide}")
    return SUPPORTED_MCP_SCOPES[ide]


def resolve_mcp_install_target(ide: str, scope: str, current_dir: Path, home_dir=None):
    if ide not in SUPPORTED_MCP_IDES:
        raise ValueError(f"Unsupported MCP IDE: {ide}")

    supported_scopes = resolve_supported_mcp_scopes(ide)
    if scope not in supported_scopes:
        supported = ", ".join(supported_scopes)
        raise ValueError(f"Unsupported scope '{scope}' for {ide}. Supported: {supported}")

    home_dir = Path(home_dir) if home_dir else RAPID_HOME.parent
    current_dir = Path(current_dir)

    if ide == "codex":
        path = (
            current_dir / ".codex" / "config.toml"
            if scope == "project"
            else home_dir / ".codex" / "config.toml"
        )
        return McpInstallTarget(ide=ide, scope=scope, path=path, format="toml")

    if ide == "claude":
        path = (
            current_dir / ".mcp.json"
            if scope == "project"
            else home_dir / ".claude.json"
        )
        return McpInstallTarget(
            ide=ide,
            scope=scope,
            path=path,
            format="json",
            json_key="mcpServers",
            preserve_other_keys=scope == "global",
        )

    if ide == "cursor":
        path = (
            current_dir / ".cursor" / "mcp.json"
            if scope == "project"
            else home_dir / ".cursor" / "mcp.json"
        )
        return McpInstallTarget(
            ide=ide,
            scope=scope,
            path=path,
            format="json",
            json_key="mcpServers",
        )

    if ide == "vscode":
        return McpInstallTarget(
            ide=ide,
            scope=scope,
            path=current_dir / ".vscode" / "mcp.json",
            format="json",
            json_key="servers",
        )

    return McpInstallTarget(
        ide=ide,
        scope=scope,
        path=home_dir / ".gemini" / "antigravity" / "mcp_config.json",
        format="json",
        json_key="mcpServers",
    )


def _render_server_definition(server):
    definition = dict(server.extra or {})
    definition.update(
        {
            "command": server.command,
            "args": list(server.args),
        }
    )
    if server.env:
        definition["env"] = dict(server.env)
    return definition


def render_claude_mcp_json(mcp_config):
    return render_claude_desktop_config(mcp_config)


def render_cursor_mcp_json(mcp_config):
    return render_claude_desktop_config(mcp_config)


def render_vscode_mcp_json(mcp_config):
    servers = {}
    for server in mcp_config.servers:
        servers[server.id] = _render_server_definition(server)
    return {"servers": servers}


def render_antigravity_mcp_json(mcp_config):
    # Antigravity MCP docs are not modeled in this repository yet.
    # Use the current JSON-compatible `mcpServers` structure conservatively.
    return render_claude_desktop_config(mcp_config)


def _escape_toml_string(value: str):
    return value.replace("\\", "\\\\").replace('"', '\\"')


def _to_toml_value(value):
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, str):
        return f'"{_escape_toml_string(value)}"'
    if isinstance(value, list):
        return "[" + ", ".join(_to_toml_value(item) for item in value) + "]"
    if isinstance(value, tuple):
        return "[" + ", ".join(_to_toml_value(item) for item in value) + "]"
    if isinstance(value, dict):
        items = ", ".join(
            f"{key} = {_to_toml_value(item)}" for key, item in value.items()
        )
        return "{ " + items + " }"
    raise TypeError(f"Unsupported TOML value: {value!r}")


def render_codex_config_toml(mcp_config):
    lines = []
    for server in mcp_config.servers:
        lines.append(f"[mcp_servers.{server.id}]")
        definition = _render_server_definition(server)
        for key, value in definition.items():
            lines.append(f"{key} = {_to_toml_value(value)}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def render_mcp_install_content(target: McpInstallTarget, mcp_config):
    if target.ide == "codex":
        return render_codex_config_toml(mcp_config)
    if target.ide == "claude":
        return render_claude_mcp_json(mcp_config)
    if target.ide == "cursor":
        return render_cursor_mcp_json(mcp_config)
    if target.ide == "vscode":
        return render_vscode_mcp_json(mcp_config)
    if target.ide == "antigravity":
        return render_antigravity_mcp_json(mcp_config)
    raise ValueError(f"Unsupported MCP IDE: {target.ide}")


def _replace_managed_toml_block(existing_text: str, rendered_block: str):
    managed_block = (
        MANAGED_TOML_BEGIN + "\n" + rendered_block.rstrip() + "\n" + MANAGED_TOML_END
    )
    if MANAGED_TOML_BEGIN in existing_text and MANAGED_TOML_END in existing_text:
        start = existing_text.index(MANAGED_TOML_BEGIN)
        end = existing_text.index(MANAGED_TOML_END, start) + len(MANAGED_TOML_END)
        prefix = existing_text[:start].rstrip()
        suffix = existing_text[end:].lstrip("\n")
        parts = [part for part in (prefix, managed_block, suffix) if part]
        return "\n\n".join(parts).rstrip() + "\n"

    existing_text = existing_text.rstrip()
    if not existing_text:
        return managed_block + "\n"
    return existing_text + "\n\n" + managed_block + "\n"


def write_mcp_install_target(target: McpInstallTarget, rendered_content):
    target.path.parent.mkdir(parents=True, exist_ok=True)

    if target.format == "toml":
        existing_text = ""
        if target.path.exists():
            create_backup(target.path)
            existing_text = target.path.read_text(encoding="utf-8")
        updated_text = _replace_managed_toml_block(existing_text, rendered_content)
        target.path.write_text(updated_text, encoding="utf-8")
        return target.path

    if target.format != "json":
        raise ValueError(f"Unsupported MCP target format: {target.format}")

    payload = rendered_content
    if target.path.exists():
        create_backup(target.path)
        if target.preserve_other_keys:
            try:
                existing_payload = json.loads(target.path.read_text(encoding="utf-8"))
            except json.JSONDecodeError as exc:
                raise ValueError(
                    f"Cannot safely merge existing JSON at {target.path}: {exc.msg}"
                ) from exc
            if not isinstance(existing_payload, dict):
                raise ValueError(
                    f"Cannot safely merge existing JSON at {target.path}: root must be an object"
                )
            existing_payload[target.json_key] = payload[target.json_key]
            payload = existing_payload

    target.path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return target.path
