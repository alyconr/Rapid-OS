import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from rapid_os.adapters.agents import DEFAULT_AGENT_REGISTRY
from rapid_os.core.config import (
    CONFIG_STATUS_INVALID_JSON,
    CONFIG_STATUS_INVALID_SCHEMA,
    CONFIG_STATUS_IO_ERROR,
    CONFIG_STATUS_MISSING,
    DEFAULT_PROJECT_CONFIG,
    inspect_project_config_file,
)
from rapid_os.core.context import STANDARDS_PRIORITY, compose_project_context
from rapid_os.domain.context import (
    DEFAULT_CONTEXT_POLICY,
    CompiledContext,
    ContextBudgetExceededError,
    ContextCompiler,
    ContextPolicy,
    ContextRequest,
    ContextSource,
)
from rapid_os.domain.project import PROJECT_MODEL_SCHEMA_VERSION, ProjectModel


INFO = "info"
WARNING = "warning"
ERROR = "error"

KNOWN_RESEARCH_TOOLS = ("context7", "firecrawl")
REQUIRED_TEMPLATE_DIRS = ("stacks", "topologies", "archetypes", "mcp")
REQUIRED_STANDARD_FILES = ("tech-stack.md", "topology.md")
OPTIONAL_STANDARD_FILES = ("security.md", "business.md", "coding-rules.md")

PLACEHOLDER_PATTERNS = (
    re.compile(r"\{\{[^}\n]+\}\}"),
    re.compile(r"<TODO>", re.IGNORECASE),
    re.compile(r"\bTODO\b"),
    re.compile(r"YOUR_API_KEY_HERE"),
    re.compile(r"REPLACE_ME"),
    re.compile(r"\[(PASSWORD|PROJECT-ID|PROJECT_ID)\]", re.IGNORECASE),
)


@dataclass(frozen=True)
class Diagnostic:
    level: str
    code: str
    message: str
    path: Path | None = None
    hint: str | None = None

    def to_dict(self):
        return {
            "level": self.level,
            "code": self.code,
            "message": self.message,
            "path": str(self.path) if self.path else None,
            "hint": self.hint,
        }


@dataclass(frozen=True)
class ValidationReport:
    diagnostics: tuple[Diagnostic, ...] = ()

    @property
    def has_errors(self):
        return any(diagnostic.level == ERROR for diagnostic in self.diagnostics)

    @property
    def has_warnings(self):
        return any(diagnostic.level == WARNING for diagnostic in self.diagnostics)

    def counts(self):
        return {
            INFO: sum(1 for diagnostic in self.diagnostics if diagnostic.level == INFO),
            WARNING: sum(
                1 for diagnostic in self.diagnostics if diagnostic.level == WARNING
            ),
            ERROR: sum(1 for diagnostic in self.diagnostics if diagnostic.level == ERROR),
        }

    def extend(self, diagnostics: Iterable[Diagnostic]):
        return ValidationReport(self.diagnostics + tuple(diagnostics))

    def merge(self, *reports):
        diagnostics = list(self.diagnostics)
        for report in reports:
            diagnostics.extend(report.diagnostics)
        return ValidationReport(tuple(diagnostics))

    def exit_code(self, strict=False):
        if self.has_errors or (strict and self.has_warnings):
            return 1
        return 0

    def to_dict(self, strict=False):
        return {
            "ok": self.exit_code(strict=strict) == 0,
            "summary": self.counts(),
            "diagnostics": [
                diagnostic.to_dict() for diagnostic in self.diagnostics
            ],
        }


@dataclass(frozen=True)
class ContextInspection:
    report: ValidationReport
    context: str
    included_sections: tuple[str, ...]
    selected_tools: tuple[str, ...]

    def to_dict(self, strict=False, include_context=True):
        data = self.report.to_dict(strict=strict)
        data["context"] = {
            "included_sections": list(self.included_sections),
            "selected_tools": list(self.selected_tools),
            "length": len(self.context),
            "preview": self.context if include_context else None,
        }
        return data


def detect_placeholders(content: str):
    matches = []
    for pattern in PLACEHOLDER_PATTERNS:
        matches.extend(match.group(0) for match in pattern.finditer(content))
    return tuple(sorted(set(matches)))


def validate_templates(templates_dir: Path):
    diagnostics = [
        Diagnostic(
            INFO,
            "RAPID100",
            f"Using templates directory: {templates_dir}",
            templates_dir,
        )
    ]

    if not templates_dir.exists():
        diagnostics.append(
            Diagnostic(
                ERROR,
                "RAPID101",
                "Templates directory does not exist.",
                templates_dir,
            )
        )
        return ValidationReport(tuple(diagnostics))

    if not templates_dir.is_dir():
        diagnostics.append(
            Diagnostic(
                ERROR,
                "RAPID102",
                "Templates path is not a directory.",
                templates_dir,
            )
        )
        return ValidationReport(tuple(diagnostics))

    for dirname in REQUIRED_TEMPLATE_DIRS:
        directory = templates_dir / dirname
        if not directory.exists():
            diagnostics.append(
                Diagnostic(
                    ERROR,
                    "RAPID103",
                    f"Required template directory missing: {dirname}",
                    directory,
                )
            )
            continue
        if not directory.is_dir():
            diagnostics.append(
                Diagnostic(
                    ERROR,
                    "RAPID104",
                    f"Required template path is not a directory: {dirname}",
                    directory,
                )
            )
            continue
        if dirname in ("stacks", "topologies") and not list(directory.glob("*.md")):
            diagnostics.append(
                Diagnostic(
                    ERROR,
                    "RAPID105",
                    f"Required template directory has no Markdown templates: {dirname}",
                    directory,
                )
            )

    for template_file in _iter_template_files(templates_dir):
        diagnostics.extend(_validate_template_file(template_file))

    return ValidationReport(tuple(diagnostics))


def validate_project(
    project_rapid_dir: Path,
    current_dir: Path,
    config_file: Path,
    templates_dir: Path,
    registry=DEFAULT_AGENT_REGISTRY,
):
    template_report = validate_templates(templates_dir)
    standards_report = validate_project_standards(project_rapid_dir)
    config_report = validate_project_config(config_file, registry)
    compatibility_report = validate_stack_topology(project_rapid_dir)
    context_report = validate_composed_context(project_rapid_dir, current_dir)
    intelligence_report = validate_project_intelligence(project_rapid_dir, current_dir)
    return template_report.merge(
        standards_report,
        config_report,
        compatibility_report,
        context_report,
        intelligence_report,
    )


def validate_project_intelligence(
    project_rapid_dir: Path,
    current_dir: Path | None = None,
) -> ValidationReport:
    """Validate optional `.rapid-os/project.json` snapshot when present using RAPID6xx codes."""
    snapshot_file = Path(project_rapid_dir) / "project.json"
    if not snapshot_file.exists():
        return ValidationReport(())

    try:
        raw_content = snapshot_file.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        return ValidationReport(
            (
                Diagnostic(
                    ERROR,
                    "RAPID602",
                    f"Project intelligence snapshot could not be read: {exc}",
                    snapshot_file,
                ),
            )
        )

    try:
        payload = json.loads(raw_content)
    except json.JSONDecodeError as exc:
        return ValidationReport(
            (
                Diagnostic(
                    ERROR,
                    "RAPID601",
                    f"Project intelligence snapshot is invalid JSON: {exc.msg}",
                    snapshot_file,
                ),
            )
        )

    if not isinstance(payload, dict):
        return ValidationReport(
            (
                Diagnostic(
                    ERROR,
                    "RAPID604",
                    "Project intelligence snapshot must be a JSON object.",
                    snapshot_file,
                ),
            )
        )

    schema_version = payload.get("schema_version")
    if (
        isinstance(schema_version, bool)
        or not isinstance(schema_version, int)
        or schema_version != PROJECT_MODEL_SCHEMA_VERSION
    ):
        return ValidationReport(
            (
                Diagnostic(
                    ERROR,
                    "RAPID603",
                    f"Unsupported project intelligence schema_version '{schema_version}': expected {PROJECT_MODEL_SCHEMA_VERSION}.",
                    snapshot_file,
                ),
            )
        )

    try:
        root = Path(current_dir) if current_dir is not None else Path(project_rapid_dir).parent
        model = ProjectModel.from_dict(payload, root=root)
    except ValueError as exc:
        return ValidationReport(
            (
                Diagnostic(
                    ERROR,
                    "RAPID604",
                    f"Project intelligence snapshot schema is invalid: {exc}",
                    snapshot_file,
                ),
            )
        )

    return ValidationReport(
        (
            Diagnostic(
                INFO,
                "RAPID600",
                f"Project intelligence snapshot valid ({len(model.facts)} fact(s)).",
                snapshot_file,
            ),
        )
    )


def validate_project_standards(project_rapid_dir: Path):
    diagnostics = []
    standards_dir = project_rapid_dir / "standards"

    if not project_rapid_dir.exists():
        return ValidationReport(
            (
                Diagnostic(
                    ERROR,
                    "RAPID200",
                    "Rapid OS project directory is missing. Run 'rapid init' first.",
                    project_rapid_dir,
                ),
            )
        )

    if not standards_dir.exists():
        return ValidationReport(
            (
                Diagnostic(
                    ERROR,
                    "RAPID201",
                    "Project standards directory is missing.",
                    standards_dir,
                ),
            )
        )

    for filename in REQUIRED_STANDARD_FILES:
        path = standards_dir / filename
        if not path.exists():
            diagnostics.append(
                Diagnostic(
                    ERROR,
                    "RAPID202",
                    f"Required standard missing: {filename}",
                    path,
                )
            )
            continue
        diagnostics.extend(_validate_markdown_context_file(path, required=True))

    for filename in OPTIONAL_STANDARD_FILES:
        path = standards_dir / filename
        if not path.exists():
            diagnostics.append(
                Diagnostic(
                    WARNING,
                    "RAPID203",
                    f"Optional standard missing: {filename}",
                    path,
                )
            )
            continue
        diagnostics.extend(_validate_markdown_context_file(path, required=False))

    return ValidationReport(tuple(diagnostics))


def validate_project_config(config_file: Path, registry=DEFAULT_AGENT_REGISTRY):
    diagnostics = []
    config_result = inspect_project_config_file(config_file)

    if config_result.status == CONFIG_STATUS_MISSING:
        diagnostics.append(
            Diagnostic(
                WARNING,
                "RAPID300",
                "Project config missing; Rapid OS will use default tools.",
                config_file,
            )
        )
        config = config_result.config
    elif config_result.status == CONFIG_STATUS_INVALID_JSON:
        return ValidationReport(
            (
                Diagnostic(
                    ERROR,
                    "RAPID301",
                    f"Project config is invalid JSON: {config_result.error}",
                    config_file,
                ),
            )
        )
    elif config_result.status == CONFIG_STATUS_IO_ERROR:
        return ValidationReport(
            (
                Diagnostic(
                    ERROR,
                    "RAPID302",
                    f"Project config could not be read: {config_result.error}",
                    config_file,
                ),
            )
        )
    elif config_result.status == CONFIG_STATUS_INVALID_SCHEMA:
        if config_result.error and "Tool ids" in config_result.error:
            return ValidationReport(
                (
                    Diagnostic(
                        ERROR,
                        "RAPID305",
                        config_result.error,
                        config_file,
                    ),
                )
            )
        return ValidationReport(
            (
                Diagnostic(
                    ERROR,
                    "RAPID303",
                    config_result.error or "Project config field 'tools' must be a list.",
                    config_file,
                ),
            )
        )
    else:
        config = config_result.config

    tools = config.get("tools", [])

    if not tools:
        diagnostics.append(
            Diagnostic(
                WARNING,
                "RAPID304",
                "No tools are selected in project config.",
                config_file,
            )
        )

    adapter_ids = set(registry.ids())
    known_tools = adapter_ids | set(KNOWN_RESEARCH_TOOLS)

    for tool in tools:
        if not isinstance(tool, str):
            diagnostics.append(
                Diagnostic(
                    ERROR,
                    "RAPID305",
                    "Tool ids in project config must be strings.",
                    config_file,
                )
            )
            continue
        if tool in KNOWN_RESEARCH_TOOLS:
            diagnostics.append(
                Diagnostic(
                    INFO,
                    "RAPID306",
                    f"Known research tool selected: {tool}",
                    config_file,
                )
            )
            continue
        if tool not in known_tools:
            diagnostics.append(
                Diagnostic(
                    ERROR,
                    "RAPID307",
                    f"Unknown tool reference: {tool}",
                    config_file,
                    hint=(
                        "Use registered agents or known research tools: "
                        + ", ".join(sorted(known_tools))
                    ),
                )
            )
            continue
        diagnostics.extend(_validate_adapter_render_contract(tool, registry, config_file))

    return ValidationReport(tuple(diagnostics))


def validate_stack_topology(project_rapid_dir: Path):
    standards_dir = project_rapid_dir / "standards"
    stack_file = standards_dir / "tech-stack.md"
    topology_file = standards_dir / "topology.md"

    if not stack_file.exists() or not topology_file.exists():
        return ValidationReport(())

    try:
        stack_content = stack_file.read_text(encoding="utf-8")
        topology_content = topology_file.read_text(encoding="utf-8")
    except OSError:
        return ValidationReport(())

    stack = infer_stack(stack_content)
    topology = infer_topology(topology_content)
    diagnostics = []

    if stack:
        diagnostics.append(
            Diagnostic(INFO, "RAPID400", f"Detected stack: {stack}", stack_file)
        )
    if topology:
        diagnostics.append(
            Diagnostic(
                INFO,
                "RAPID401",
                f"Detected topology: {topology}",
                topology_file,
            )
        )

    if stack == "docs-modern" and topology and topology != "doc-site":
        diagnostics.append(
            Diagnostic(
                ERROR,
                "RAPID402",
                "docs-modern stack should use doc-site topology.",
                topology_file,
            )
        )
    if topology == "doc-site" and stack and stack != "docs-modern":
        diagnostics.append(
            Diagnostic(
                ERROR,
                "RAPID403",
                "doc-site topology should use docs-modern stack.",
                stack_file,
            )
        )
    if topology == "front-end-only" and stack in ("python-ai", "nodejs-ai"):
        diagnostics.append(
            Diagnostic(
                ERROR,
                "RAPID404",
                f"{stack} stack requires backend/database capabilities and conflicts with front-end-only topology.",
                stack_file,
            )
        )
    if topology == "fullstack-baas" and stack == "python-ai":
        diagnostics.append(
            Diagnostic(
                WARNING,
                "RAPID405",
                "fullstack-baas is tuned for integrated web apps; verify this Python AI pairing is intentional.",
                stack_file,
            )
        )

    return ValidationReport(tuple(diagnostics))


def validate_composed_context(project_rapid_dir: Path, current_dir: Path):
    diagnostics = []
    context = compose_project_context(project_rapid_dir, current_dir)

    if not context.strip():
        diagnostics.append(
            Diagnostic(
                ERROR,
                "RAPID500",
                "Assembled project context is empty.",
                project_rapid_dir / "standards",
            )
        )
        return ValidationReport(tuple(diagnostics))

    diagnostics.append(
        Diagnostic(
            INFO,
            "RAPID501",
            f"Assembled project context length: {len(context)} characters.",
            project_rapid_dir,
        )
    )

    placeholders = detect_placeholders(context)
    if placeholders:
        diagnostics.append(
            Diagnostic(
                WARNING,
                "RAPID502",
                "Assembled project context contains unresolved placeholders: "
                + ", ".join(placeholders),
                project_rapid_dir,
            )
        )

    return ValidationReport(tuple(diagnostics))


def inspect_project_context(
    project_rapid_dir: Path,
    current_dir: Path,
    config_file: Path,
):
    context = compose_project_context(project_rapid_dir, current_dir)
    diagnostics = list(validate_project_standards(project_rapid_dir).diagnostics)
    config_report = validate_project_config(config_file)
    diagnostics.extend(
        diagnostic for diagnostic in config_report.diagnostics if diagnostic.level == ERROR
    )
    diagnostics.extend(validate_composed_context(project_rapid_dir, current_dir).diagnostics)
    selected_tools = _read_selected_tools(config_file)

    return ContextInspection(
        report=ValidationReport(tuple(diagnostics)),
        context=context,
        included_sections=_included_context_sections(project_rapid_dir, current_dir),
        selected_tools=tuple(selected_tools),
    )


def validate_compiled_context(
    compiled: CompiledContext,
    load_errors=(),
) -> ValidationReport:
    """Validate a CompiledContext and any source load errors using RAPID7xx codes."""
    diagnostics: list[Diagnostic] = []

    for load_error in load_errors or ():
        err_path = getattr(load_error, "path", None)
        path_obj = Path(err_path) if err_path else None
        source_id = getattr(load_error, "source_id", "unknown")
        err_msg = getattr(load_error, "message", str(load_error))
        diagnostics.append(
            Diagnostic(
                ERROR,
                "RAPID704",
                f"Context source '{source_id}' could not be read: {err_msg}",
                path_obj,
            )
        )

    for skipped in compiled.manifest.skipped:
        if skipped.required:
            path_obj = Path(skipped.path) if skipped.path else None
            diagnostics.append(
                Diagnostic(
                    ERROR,
                    "RAPID701",
                    f"Required context source missing or empty: {skipped.source_id} ({skipped.reason})",
                    path_obj,
                )
            )

    for conflict in compiled.manifest.conflicts:
        diagnostics.append(
            Diagnostic(
                WARNING,
                "RAPID703",
                (
                    f"Context conflict detected in '{conflict.category}' between "
                    f"{', '.join(conflict.sources)} (winner: {conflict.winner}): {conflict.reason}"
                ),
            )
        )

    diagnostics.append(
        Diagnostic(
            INFO,
            "RAPID700",
            (
                f"Context compiled ({compiled.manifest.compiled_chars}/"
                f"{compiled.manifest.budget_max_chars} chars, "
                f"{len(compiled.manifest.selected)} fragment(s))."
            ),
        )
    )

    return ValidationReport(tuple(diagnostics))


def validate_context_compilation(
    request: ContextRequest | dict | None,
    sources: Iterable[ContextSource] = (),
    project_model: ProjectModel | None = None,
    policy: ContextPolicy = DEFAULT_CONTEXT_POLICY,
    load_errors=(),
) -> ValidationReport:
    """Compile and validate context, emitting RAPID700-RAPID705 diagnostics."""
    diagnostics: list[Diagnostic] = []

    for load_error in load_errors or ():
        err_path = getattr(load_error, "path", None)
        path_obj = Path(err_path) if err_path else None
        source_id = getattr(load_error, "source_id", "unknown")
        err_msg = getattr(load_error, "message", str(load_error))
        diagnostics.append(
            Diagnostic(
                ERROR,
                "RAPID704",
                f"Context source '{source_id}' could not be read: {err_msg}",
                path_obj,
            )
        )

    resolved_request: ContextRequest | None = None
    if isinstance(request, ContextRequest):
        resolved_request = request
    elif isinstance(request, dict):
        try:
            resolved_request = ContextRequest(**request)
        except (TypeError, ValueError) as exc:
            diagnostics.append(
                Diagnostic(
                    ERROR,
                    "RAPID705",
                    f"Invalid ContextRequest: {exc}",
                )
            )
            return ValidationReport(tuple(diagnostics))
    else:
        diagnostics.append(
            Diagnostic(
                ERROR,
                "RAPID705",
                "Invalid ContextRequest: request must be a ContextRequest instance.",
            )
        )
        return ValidationReport(tuple(diagnostics))

    compiler = ContextCompiler()
    try:
        compiled = compiler.compile(
            request=resolved_request,
            sources=tuple(sources),
            project_model=project_model,
            policy=policy,
        )
    except ContextBudgetExceededError as exc:
        diagnostics.append(
            Diagnostic(
                ERROR,
                "RAPID702",
                f"Context budget exceeded by required sources: {exc}",
            )
        )
        return ValidationReport(tuple(diagnostics))
    except ValueError as exc:
        diagnostics.append(
            Diagnostic(
                ERROR,
                "RAPID705",
                f"Invalid ContextRequest or context sources: {exc}",
            )
        )
        return ValidationReport(tuple(diagnostics))

    compiled_report = validate_compiled_context(compiled, load_errors=())
    return ValidationReport(tuple(diagnostics)).merge(compiled_report)


def infer_stack(content: str):
    normalized = content.lower()
    if "modern docs" in normalized or "docusaurus" in normalized:
        return "docs-modern"
    if "python ai agent" in normalized or "fastapi" in normalized:
        return "python-ai"
    if "nodejs ai agent" in normalized or "bun.js" in normalized:
        return "nodejs-ai"
    if "creative & motion" in normalized:
        return "frontend-creative"
    if "modern web" in normalized or "next.js" in normalized:
        return "web-modern"
    return None


def infer_topology(content: str):
    normalized = content.lower()
    if "documentation site" in normalized or "docusaurus.config" in normalized:
        return "doc-site"
    if "frontend only" in normalized or "backend:** none" in normalized:
        return "front-end-only"
    if "serverless" in normalized or "baas" in normalized:
        return "fullstack-baas"
    if "separated frontend" in normalized or "decoupled" in normalized:
        return "fullstack-separated"
    return None


def _iter_template_files(templates_dir: Path):
    for directory_name in REQUIRED_TEMPLATE_DIRS:
        directory = templates_dir / directory_name
        if directory.exists() and directory.is_dir():
            yield from sorted(path for path in directory.rglob("*") if path.is_file())


def _validate_template_file(path: Path):
    diagnostics = []
    try:
        content = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return (
            Diagnostic(
                ERROR,
                "RAPID106",
                "Template file is not valid UTF-8.",
                path,
            ),
        )
    except OSError as exc:
        return (
            Diagnostic(
                ERROR,
                "RAPID107",
                f"Template file could not be read: {exc}",
                path,
            ),
        )

    if not content.strip():
        diagnostics.append(
            Diagnostic(WARNING, "RAPID108", "Template file is empty.", path)
        )

    if path.suffix.lower() == ".json":
        try:
            json.loads(content)
        except json.JSONDecodeError as exc:
            diagnostics.append(
                Diagnostic(
                    ERROR,
                    "RAPID109",
                    f"Template JSON is invalid: {exc.msg}",
                    path,
                )
            )

    placeholders = detect_placeholders(content)
    if placeholders:
        diagnostics.append(
            Diagnostic(
                WARNING,
                "RAPID110",
                "Template contains unresolved placeholders: "
                + ", ".join(placeholders),
                path,
            )
        )

    return tuple(diagnostics)


def _validate_markdown_context_file(path: Path, required: bool):
    diagnostics = []
    try:
        content = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return (
            Diagnostic(
                ERROR,
                "RAPID204",
                "Standard file is not valid UTF-8.",
                path,
            ),
        )
    except OSError as exc:
        return (
            Diagnostic(
                ERROR,
                "RAPID205",
                f"Standard file could not be read: {exc}",
                path,
            ),
        )

    if required and not content.strip():
        diagnostics.append(
            Diagnostic(ERROR, "RAPID206", "Required standard file is empty.", path)
        )
    elif not content.strip():
        diagnostics.append(
            Diagnostic(WARNING, "RAPID207", "Optional standard file is empty.", path)
        )

    placeholders = detect_placeholders(content)
    if placeholders:
        diagnostics.append(
            Diagnostic(
                WARNING,
                "RAPID208",
                "Standard file contains unresolved placeholders: "
                + ", ".join(placeholders),
                path,
            )
        )

    return tuple(diagnostics)


def _validate_adapter_render_contract(tool: str, registry, path: Path):
    diagnostics = []
    try:
        adapter = registry.get(tool)
    except KeyError:
        return (
            Diagnostic(
                ERROR,
                "RAPID308",
                f"Selected agent has no registered adapter: {tool}",
                path,
            ),
        )

    try:
        rendered = adapter.render("Rapid OS validation context")
    except Exception as exc:
        return (
            Diagnostic(
                ERROR,
                "RAPID309",
                f"Adapter '{tool}' failed to render validation context: {exc}",
                path,
            ),
        )

    for output in adapter.outputs:
        relative_path = output.relative_path
        if relative_path not in rendered:
            diagnostics.append(
                Diagnostic(
                    ERROR,
                    "RAPID310",
                    f"Adapter '{tool}' did not render declared output: {relative_path.as_posix()}",
                    path,
                )
            )
        if relative_path.is_absolute() or ".." in relative_path.parts:
            diagnostics.append(
                Diagnostic(
                    ERROR,
                    "RAPID311",
                    f"Adapter '{tool}' declares unsafe output path: {relative_path.as_posix()}",
                    path,
                )
            )

    return tuple(diagnostics)


def _read_selected_tools(config_file: Path):
    result = inspect_project_config_file(config_file)
    if not result.is_valid:
        return ()
    tools = result.config.get("tools", [])
    return tuple(tool for tool in tools if isinstance(tool, str))


def _included_context_sections(project_rapid_dir: Path, current_dir: Path):
    sections = []
    standards_dir = project_rapid_dir / "standards"
    for filename in STANDARDS_PRIORITY:
        if (standards_dir / filename).exists():
            sections.append(filename)
    if (current_dir / "references" / "VISION_CONTEXT.md").exists():
        sections.append("references/VISION_CONTEXT.md")
    return tuple(sections)
