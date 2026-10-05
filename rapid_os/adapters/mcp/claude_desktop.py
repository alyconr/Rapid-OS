def render_claude_desktop_config(mcp_config):
    servers = {}
    for server in mcp_config.servers:
        definition = dict(server.extra or {})
        definition.update({
            "command": server.command,
            "args": list(server.args),
        })
        if server.env:
            definition["env"] = dict(server.env)
        servers[server.id] = definition

    return {"mcpServers": servers}
