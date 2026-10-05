"""MCP renderers for Rapid OS outputs."""

from rapid_os.adapters.mcp.claude_desktop import render_claude_desktop_config
from rapid_os.adapters.mcp.install import (
    McpInstallTarget,
    render_antigravity_mcp_json,
    render_claude_mcp_json,
    render_codex_config_toml,
    render_cursor_mcp_json,
    render_mcp_install_content,
    render_vscode_mcp_json,
    resolve_mcp_install_target,
    resolve_supported_mcp_scopes,
    write_mcp_install_target,
)

__all__ = [
    "McpInstallTarget",
    "render_antigravity_mcp_json",
    "render_claude_desktop_config",
    "render_claude_mcp_json",
    "render_codex_config_toml",
    "render_cursor_mcp_json",
    "render_mcp_install_content",
    "render_vscode_mcp_json",
    "resolve_mcp_install_target",
    "resolve_supported_mcp_scopes",
    "write_mcp_install_target",
]
