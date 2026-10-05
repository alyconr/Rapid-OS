import json
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Sequence


PLACEHOLDER_VALUES = (
    "YOUR_API_KEY_HERE",
    "[PASSWORD]",
    "[PROJECT-ID]",
    "postgresql://user:password@localhost:5432/dbname",
)

DEFAULT_MCP_PACKAGES = {
    "filesystem": "@modelcontextprotocol/server-filesystem",
    "context7": "@upstash/context7-mcp",
    "firecrawl": "firecrawl-mcp",
    "supabase": "@modelcontextprotocol/server-postgres",
}


def format_package_spec(package: str, version: str | None = None) -> str:
    """Format an npm package name and optional version into a package specifier."""
    cleaned_package = (package or "").strip()
    cleaned_version = (version or "").strip() if version is not None else ""
    if cleaned_package and cleaned_version:
        return f"{cleaned_package}@{cleaned_version}"
    return cleaned_package


def split_package_spec(spec: str) -> tuple[str, str | None]:
    """Split an npm package specifier into `(package, version)`."""
    cleaned = (spec or "").strip()
    if not cleaned:
        return "", None
    if "@" in cleaned[1:]:
        idx = cleaned.rfind("@")
        package = cleaned[:idx]
        version = cleaned[idx + 1 :] or None
        return package, version
    return cleaned, None


def _find_npx_package_arg_index(
    command: str,
    args: Sequence[str],
) -> int | None:
    """Return the index of the package argument in an `npx` invocation, or None."""
    if (command or "").lower() not in {"npx", "npx.cmd", "npx.exe"}:
        return None

    idx = 0
    while idx < len(args):
        token = str(args[idx]).strip()
        if token in {"-y", "--yes", "-q", "--quiet"}:
            idx += 1
            continue
        if token in {"-p", "--package"}:
            return idx + 1 if idx + 1 < len(args) else None
        if token.startswith("--package="):
            return idx
        if token.startswith("-"):
            idx += 1
            continue
        return idx
    return None


def extract_npx_package_spec(
    command: str,
    args: tuple[str, ...],
) -> tuple[str | None, str | None]:
    """Extract `(package, version)` from an `npx` command argument tuple."""
    arg_idx = _find_npx_package_arg_index(command, args)
    if arg_idx is None:
        return None, None

    token = str(args[arg_idx]).strip()
    if token.startswith("--package="):
        token = token.split("=", 1)[1]
    pkg, ver = split_package_spec(token)
    return (pkg or None), ver


def _normalize_npx_package_arg(
    command: str,
    args: Sequence[str],
    package: str,
    version: str | None,
) -> list[str] | None:
    """Rewrite the executable package argument in `args` to match `(package, version)` if it refers to `package`."""
    arg_idx = _find_npx_package_arg_index(command, args)
    if arg_idx is None:
        return None

    normalized = [str(item) for item in args]
    token = normalized[arg_idx].strip()
    target_spec = format_package_spec(package, version)

    if token.startswith("--package="):
        raw_spec = token.split("=", 1)[1]
        parsed_pkg, _ = split_package_spec(raw_spec)
        if parsed_pkg != package:
            return None
        normalized[arg_idx] = f"--package={target_spec}"
        return normalized

    parsed_pkg, _ = split_package_spec(token)
    if parsed_pkg != package:
        return None
    normalized[arg_idx] = target_spec
    return normalized


@dataclass(frozen=True)
class McpServer:
    id: str
    command: str
    args: tuple[str, ...] = ()
    env: Mapping[str, str] | None = None
    extra: Mapping[str, object] | None = None
    source: str = "generated"
    package: str | None = None
    version: str | None = None

    @property
    def package_spec(self) -> str | None:
        if not self.package:
            return None
        return format_package_spec(self.package, self.version)

    @property
    def runtime_package_spec(self) -> str | None:
        runtime_pkg, runtime_ver = extract_npx_package_spec(self.command, self.args)
        if not runtime_pkg:
            return None
        return format_package_spec(runtime_pkg, runtime_ver)

    @property
    def is_version_pinned(self) -> bool:
        runtime_pkg, runtime_ver = extract_npx_package_spec(self.command, self.args)
        if runtime_pkg is not None:
            if self.package and self.package != runtime_pkg:
                return False
            if self.version and self.version != runtime_ver:
                return False
            return bool(runtime_ver and runtime_ver.strip().lower() != "latest")
        if self.package:
            return False
        return bool(self.version and self.version.strip().lower() != "latest")


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

    seen_warning_keys = {(w.code, w.server_id) for w in warnings}
    for server in servers:
        for warning in detect_server_warnings(server):
            key = (warning.code, warning.server_id)
            if key not in seen_warning_keys:
                warnings.append(warning)
                seen_warning_keys.add(key)

    return McpConfig(tuple(servers), tuple(warnings))


def filesystem_server(current_dir: Path, version: str | None = None):
    package = DEFAULT_MCP_PACKAGES["filesystem"]
    spec = format_package_spec(package, version)
    return McpServer(
        id="filesystem",
        command="npx",
        args=("-y", spec, str(current_dir)),
        source="generated",
        package=package,
        version=version,
    )


def context7_server(version: str | None = None):
    package = DEFAULT_MCP_PACKAGES["context7"]
    spec = format_package_spec(package, version)
    return McpServer(
        id="context7",
        command="npx",
        args=("-y", spec),
        env={"CONTEXT7_API_KEY": "YOUR_API_KEY_HERE"},
        source="generated",
        package=package,
        version=version,
    )


def firecrawl_server(version: str | None = None):
    package = DEFAULT_MCP_PACKAGES["firecrawl"]
    spec = format_package_spec(package, version)
    return McpServer(
        id="firecrawl",
        command="npx",
        args=("-y", spec),
        env={"FIRECRAWL_API_KEY": "YOUR_API_KEY_HERE"},
        source="generated",
        package=package,
        version=version,
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

    normalized_args = [str(arg) for arg in args]
    raw_package = definition.get("package")
    raw_version = definition.get("version")
    package = str(raw_package).strip() if isinstance(raw_package, str) and raw_package.strip() else None
    version = str(raw_version).strip() if isinstance(raw_version, str) and raw_version.strip() else None

    inferred_pkg, inferred_ver = extract_npx_package_spec(
        str(command), tuple(normalized_args)
    )
    if package is None:
        package = inferred_pkg

    if package is not None:
        if inferred_pkg == package:
            if version is not None:
                rewritten = _normalize_npx_package_arg(
                    str(command),
                    normalized_args,
                    package,
                    version,
                )
                if rewritten is not None:
                    normalized_args = rewritten
            else:
                version = inferred_ver
        else:
            warnings.append(
                McpWarning(
                    "MCP014",
                    f"MCP server '{server_id}' declared package '{package}' does not match runtime package '{inferred_pkg or 'none'}'.",
                    server_id=str(server_id),
                    path=path,
                )
            )
    elif version is not None:
        warnings.append(
            McpWarning(
                "MCP014",
                f"MCP server '{server_id}' declared version '{version}' without a matching runtime package.",
                server_id=str(server_id),
                path=path,
            )
        )

    known_keys = {"command", "args", "env", "package", "version"}
    extra = {key: value for key, value in definition.items() if key not in known_keys}

    return (
        McpServer(
            id=str(server_id),
            command=str(command),
            args=tuple(normalized_args),
            env=env,
            extra=extra or None,
            source=source,
            package=package,
            version=version,
        ),
        tuple(warnings),
    )


def _extract_docker_image(args: tuple[str, ...]) -> str | None:
    if not args or args[0] != "run":
        return None
    idx = 1
    while idx < len(args):
        token = str(args[idx])
        if token in {"-e", "--env", "-v", "--volume", "-p", "--publish", "--name", "--network"}:
            idx += 2
            continue
        if token.startswith("-"):
            idx += 1
            continue
        return token
    return None


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

    runtime_pkg, runtime_ver = extract_npx_package_spec(server.command, server.args)
    if (server.package and server.package != runtime_pkg) or (
        server.version and server.version != runtime_ver
    ):
        declared = server.package_spec or server.package or server.version
        runtime_spec = (
            format_package_spec(runtime_pkg, runtime_ver) if runtime_pkg else "none"
        )
        warnings.append(
            McpWarning(
                "MCP014",
                f"MCP server '{server.id}' declared metadata '{declared}' does not match runtime package '{runtime_spec}'.",
                server_id=server.id,
            )
        )

    if runtime_pkg and (not runtime_ver or runtime_ver.strip().lower() == "latest"):
        warnings.append(
            McpWarning(
                "MCP012",
                f"MCP server '{server.id}' uses unpinned npx package '{runtime_pkg}'; pin a version for reproducible execution.",
                server_id=server.id,
            )
        )

    if server.command == "docker":
        image = _extract_docker_image(server.args)
        if image and (
            (":" not in image and "@" not in image)
            or image.endswith(":latest")
        ):
            warnings.append(
                McpWarning(
                    "MCP013",
                    f"MCP server '{server.id}' uses unpinned container image '{image}'; pin a tag or digest for reproducible execution.",
                    server_id=server.id,
                )
            )

    return tuple(warnings)
