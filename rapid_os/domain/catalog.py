"""Stack and topology catalog read from JSON sidecars (RAPID1401 on invalid data)."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

from rapid_os.domain.project import ProjectModel
from rapid_os.domain.stack_aliases import LEGACY_STACKS

CATALOG_SCHEMA_VERSION = 1
GENERIC_STACK_ID = "generic"
GENERIC_STACK_HEADER = "# TECH STACK: GENERIC"
GENERIC_STACK_RULE = "Follow the existing conventions of the repository."


class CatalogError(ValueError):
    """Invalid catalog sidecar (RAPID1401)."""

    code = "RAPID1401"


COMPONENTS = ("frontend", "backend", "baas", "docs")
# The qualitative factors every catalog stack of a component describes, each with its sources.
FACTOR_KEYS = (
    "performance",
    "memory_footprint",
    "cold_start",
    "concurrency_model",
    "typing",
    "productivity",
    "learning_curve",
    "maintainability",
    "ecosystem_maturity",
    "hiring_pool",
    "hosting_fit",
)
HOSTING_FITS = ("serverless", "containers", "PaaS")


@dataclass(frozen=True)
class StackEntry:
    id: str
    summary: str
    language: str
    fits: tuple[str, ...]
    avoid_if: tuple[str, ...]
    compatible_topologies: tuple[str, ...]
    default_topology: str
    # `<role>:<engine>` the stack proposes as a minimum (a suggestion, never a decision).
    suggested_services: tuple[str, ...] = ()
    # Roles of infrastructure services the stack can use; None means all of them.
    service_roles: tuple[str, ...] | None = None
    # The component the stack is listed under (None: a flat sidecar such as `generic`) and the
    # components it fills when it is chosen without `--component`.
    component: str | None = None
    covers: tuple[str, ...] = ()
    factors: dict[str, str] = field(default_factory=dict)
    factor_sources: dict[str, tuple[str, ...]] = field(default_factory=dict)
    default_test_command: tuple[str, ...] = ()
    package_manager: str = ""
    # engine -> {"driver": ..., "url": ...}; None means every engine of the catalog.
    supported_services: dict[str, dict[str, str]] | None = None
    # Id of the idiomatic architecture profile (`rapid_os.domain.architecture.PROFILES`).
    architecture: str = ""
    # Directory of the Markdown template below `templates/stacks`.
    template: str = ""

    @property
    def monolith(self) -> bool:
        """A backend framework that also covers the frontend (Rails, Django, Laravel...)."""
        return self.component is not None and len(set(self.covers)) > 1 and self.component != "frontend"


SERVICE_ROLES = ("database", "cache", "queue", "stream", "search", "object-storage")
SERVICE_LANGUAGES = ("python", "typescript")


@dataclass(frozen=True)
class ServiceEntry:
    """An infrastructure engine Rapid OS can run locally in a container (`templates/services`)."""

    id: str
    role: str
    image: str
    ports: tuple[int, ...]
    env: dict[str, str]
    fixed_env: dict[str, str]
    healthcheck: dict
    volume: dict[str, str] | None
    connection_env: str
    drivers: dict[str, dict[str, str]]
    sources: tuple[str, ...]
    hostname: str | None = None
    migrations: dict[str, str] | None = None

    @property
    def version(self) -> str:
        return self.image.rsplit(":", 1)[-1]


@dataclass(frozen=True)
class TopologyEntry:
    id: str
    summary: str
    fits: tuple[str, ...]
    avoid_if: tuple[str, ...]
    # The components the topology needs a stack for, in the order they are asked.
    components: tuple[str, ...] = ()


DOC_SITE_TOPOLOGY = "doc-site"


@dataclass(frozen=True)
class Catalog:
    stacks: dict[str, StackEntry]
    topologies: dict[str, TopologyEntry]
    # Markdown templates without a sidecar (RAPID1412): still usable, compatible with every
    # topology except doc-site.
    sidecarless_stacks: tuple[str, ...] = ()
    sidecarless_topologies: tuple[str, ...] = ()
    services: dict[str, ServiceEntry] = field(default_factory=dict)

    def engines_for_role(self, role: str) -> tuple[str, ...]:
        return tuple(sorted(s.id for s in self.services.values() if s.role == role))

    @property
    def topology_ids(self) -> tuple[str, ...]:
        return tuple(sorted(set(self.topologies) | set(self.sidecarless_topologies)))

    def entry(self, stack_id: str) -> StackEntry | None:
        """The catalog entry of a stack id; a legacy id (`python-api`...) resolves to the stack it maps to."""
        entry = self.stacks.get(stack_id)
        if entry is not None:
            return entry
        legacy = LEGACY_STACKS.get(stack_id)
        if legacy is not None:
            return self.stacks.get(legacy.primary_id())
        return None

    def components_of(self, topology_id: str | None) -> tuple[str, ...]:
        """The components a topology needs a stack for (empty when the topology is unknown)."""
        entry = self.topologies.get(topology_id or "")
        if entry is not None:
            return entry.components
        return DEFAULT_TOPOLOGY_COMPONENTS.get(topology_id or "", ())

    def options_for(self, component: str) -> tuple[StackEntry, ...]:
        """Stacks that can fill a component: the ones listed under it and the monolithic ones that cover it."""
        return tuple(
            entry
            for entry in self.stacks.values()
            if entry.component == component or component in entry.covers
        )

    def compatible_topologies(self, stack_id: str) -> tuple[str, ...] | None:
        """Compatible topologies for a known stack, None when the stack is not in the catalog."""
        legacy = LEGACY_STACKS.get(stack_id)
        if legacy is not None and legacy.topologies:
            return tuple(t for t in legacy.topologies if t in self.topology_ids)
        entry = self.entry(stack_id)
        if entry is not None:
            return entry.compatible_topologies
        if stack_id in self.sidecarless_stacks:
            return tuple(t for t in self.topology_ids if t != DOC_SITE_TOPOLOGY)
        return None

    def is_compatible(self, stack_id: str, topology_id: str) -> bool | None:
        """True/False for known stacks, None when the stack is not in the catalog."""
        compatible = self.compatible_topologies(stack_id)
        if compatible is None:
            return None
        return topology_id in compatible

    def default_topology_for_stack(
        self, stack_name: str, suggested_topology: str | None, topologies
    ) -> str | None:
        """Topology for `rapid init --yes` when nothing was asked: coherent with the stack.

        A stack that only fits doc-site gets it; any other stack never defaults to doc-site.
        A scanner suggestion is kept only when it does not contradict the chosen stack.
        """
        compatible = self.compatible_topologies(stack_name)
        if compatible == (DOC_SITE_TOPOLOGY,):
            return DOC_SITE_TOPOLOGY if DOC_SITE_TOPOLOGY in topologies else None
        if (
            suggested_topology in topologies
            and suggested_topology != DOC_SITE_TOPOLOGY
            and self.is_compatible(stack_name, suggested_topology) is not False
        ):
            return suggested_topology
        entry = self.entry(stack_name)
        if entry is not None and entry.default_topology in topologies:
            return entry.default_topology
        for name in topologies:
            if name != DOC_SITE_TOPOLOGY:
                return name
        return None


def _fail(path: Path, message: str) -> CatalogError:
    return CatalogError(f"RAPID1401 Invalid catalog sidecar '{path.name}': {message}")


def _read_sidecar(path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise _fail(path, f"cannot be read as JSON ({exc}).") from exc
    if not isinstance(data, dict):
        raise _fail(path, "must contain a JSON object.")
    version = data.get("schema_version")
    if isinstance(version, bool) or version != CATALOG_SCHEMA_VERSION:
        raise _fail(path, f"schema_version must be {CATALOG_SCHEMA_VERSION}.")
    if data.get("id") != path.stem:
        raise _fail(path, f"id '{data.get('id')}' does not match the file name '{path.stem}'.")
    return data


def _text(path: Path, data: dict, field: str) -> str:
    value = data.get(field)
    if not isinstance(value, str) or not value.strip():
        raise _fail(path, f"missing or empty field '{field}'.")
    return value


def _text_list(path: Path, data: dict, field: str, *, non_empty: bool = False) -> tuple[str, ...]:
    value = data.get(field)
    if not isinstance(value, list) or not all(
        isinstance(item, str) and item.strip() for item in value
    ):
        raise _fail(path, f"field '{field}' must be a list of non-empty strings.")
    if non_empty and not value:
        raise _fail(path, f"field '{field}' must not be empty.")
    return tuple(value)


DEFAULT_TOPOLOGY_COMPONENTS = {
    "front-end-only": ("frontend",),
    "fullstack-separated": ("frontend", "backend"),
    "fullstack-baas": ("frontend", "baas"),
    "doc-site": ("docs",),
}


def _load_topology(path: Path) -> TopologyEntry:
    data = _read_sidecar(path)
    if "components" in data:
        components = _text_list(path, data, "components", non_empty=True)
    else:
        components = DEFAULT_TOPOLOGY_COMPONENTS.get(data["id"])
        if components is None:
            raise _fail(path, "missing field 'components'.")
    unknown = [item for item in components if item not in COMPONENTS]
    if unknown:
        raise _fail(path, f"components references unknown component: {', '.join(unknown)}.")
    return TopologyEntry(
        id=data["id"],
        summary=_text(path, data, "summary"),
        fits=_text_list(path, data, "fits"),
        avoid_if=_text_list(path, data, "avoid_if"),
        components=tuple(components),
    )


def _check_services_fields(path: Path, data: dict) -> tuple[tuple[str, ...], tuple[str, ...] | None]:
    suggested = _text_list(path, data, "suggested_services") if "suggested_services" in data else ()
    for item in suggested:
        role, _, engine = item.partition(":")
        if role not in SERVICE_ROLES or not engine:
            raise _fail(path, f"suggested_services entry '{item}' must be '<role>:<engine>' with a known role.")
    service_roles = None
    if "service_roles" in data:
        service_roles = _text_list(path, data, "service_roles")
        unknown_roles = [r for r in service_roles if r not in SERVICE_ROLES]
        if unknown_roles:
            raise _fail(path, f"service_roles references unknown role: {', '.join(unknown_roles)}.")
    return suggested, service_roles


def _load_stack(path: Path, topologies: dict[str, TopologyEntry], known_topologies: set[str]) -> StackEntry:
    """A flat sidecar (`generic`, `docs-modern`) lists its topologies; one under a component
    directory is compatible with the topologies that include its component."""
    data = _read_sidecar(path)
    suggested, service_roles = _check_services_fields(path, data)
    if path.parent.name in COMPONENTS:
        return _load_component_stack(path, data, topologies, suggested, service_roles)
    compatible = _text_list(path, data, "compatible_topologies", non_empty=True)
    default = _text(path, data, "default_topology")
    unknown = [item for item in compatible if item not in known_topologies]
    if unknown:
        raise _fail(path, f"compatible_topologies references unknown topology: {', '.join(unknown)}.")
    if default not in compatible:
        raise _fail(path, f"default_topology '{default}' is not listed in compatible_topologies.")
    covers = _text_list(path, data, "covers") if "covers" in data else ()
    return StackEntry(
        id=data["id"],
        summary=_text(path, data, "summary"),
        language=_text(path, data, "language"),
        fits=_text_list(path, data, "fits"),
        avoid_if=_text_list(path, data, "avoid_if"),
        compatible_topologies=compatible,
        default_topology=default,
        suggested_services=suggested,
        service_roles=service_roles,
        covers=tuple(covers),
        template=data["id"],
    )


def _url_list(path: Path, value: object, label: str) -> tuple[str, ...]:
    if (
        not isinstance(value, list)
        or not value
        or not all(isinstance(item, str) and item.startswith("https://") for item in value)
    ):
        raise _fail(path, f"{label} must be a non-empty list of https URLs.")
    return tuple(value)


def _load_component_stack(
    path: Path,
    data: dict,
    topologies: dict[str, TopologyEntry],
    suggested: tuple[str, ...],
    service_roles: tuple[str, ...] | None,
) -> StackEntry:
    component = _text(path, data, "component")
    if component != path.parent.name:
        raise _fail(path, f"component '{component}' does not match its directory '{path.parent.name}'.")
    covers = _text_list(path, data, "covers", non_empty=True)
    unknown = [item for item in covers if item not in COMPONENTS]
    if unknown or component not in covers:
        raise _fail(path, "covers must list known components and include the stack's own component.")
    raw_factors = data.get("factors")
    if not isinstance(raw_factors, dict) or set(raw_factors) != set(FACTOR_KEYS):
        raise _fail(path, f"field 'factors' must have exactly: {', '.join(FACTOR_KEYS)}.")
    factors: dict[str, str] = {}
    for key in FACTOR_KEYS:
        value = raw_factors[key]
        if not isinstance(value, str) or not value.strip():
            raise _fail(path, f"factor '{key}' must be a non-empty text.")
        factors[key] = value
    hosting = [token.strip() for token in factors["hosting_fit"].split(",")]
    if not all(token in HOSTING_FITS for token in hosting):
        raise _fail(path, f"factor 'hosting_fit' must list values of: {', '.join(HOSTING_FITS)}.")
    raw_sources = data.get("sources")
    if not isinstance(raw_sources, dict) or set(raw_sources) != set(FACTOR_KEYS):
        raise _fail(path, "field 'sources' must give the sources of every factor.")
    sources = {key: _url_list(path, raw_sources[key], f"sources.{key}") for key in FACTOR_KEYS}
    command = _text_list(path, data, "default_test_command", non_empty=True)
    supported = data.get("supported_services")
    if not isinstance(supported, dict) or not all(
        isinstance(engine, str)
        and isinstance(item, dict)
        and isinstance(item.get("driver"), str)
        and item["driver"]
        and isinstance(item.get("url"), str)
        and item["url"]
        for engine, item in supported.items()
    ):
        raise _fail(path, "field 'supported_services' must map each engine to {driver, url}.")
    compatible = tuple(
        topology_id
        for topology_id, topology in sorted(topologies.items())
        if component in topology.components
    )
    if not compatible:
        raise _fail(path, "no topology includes the stack's component.")
    default = data.get("default_topology") or (
        "fullstack-separated" if component == "backend" or len(covers) > 1 else "front-end-only"
    )
    if default not in compatible:
        default = compatible[0]
    return StackEntry(
        id=data["id"],
        summary=_text(path, data, "summary"),
        language=_text(path, data, "language"),
        fits=_text_list(path, data, "fits", non_empty=True),
        avoid_if=_text_list(path, data, "avoid_if", non_empty=True),
        compatible_topologies=compatible,
        default_topology=default,
        suggested_services=suggested,
        service_roles=service_roles,
        component=component,
        covers=tuple(covers),
        factors=factors,
        factor_sources=sources,
        default_test_command=tuple(command),
        package_manager=_text(path, data, "package_manager"),
        supported_services={engine: dict(item) for engine, item in supported.items()},
        architecture=_text(path, data, "architecture"),
        template=f"{component}/{data['id']}",
    )


def _str_map(path: Path, data: dict, field_name: str, *, required: bool = True) -> dict[str, str]:
    value = data.get(field_name, {} if not required else None)
    if not isinstance(value, dict) or not all(
        isinstance(k, str) and k and isinstance(v, str) for k, v in value.items()
    ):
        raise _fail(path, f"field '{field_name}' must be an object of strings.")
    return dict(value)


def _load_service(path: Path) -> ServiceEntry:
    data = _read_sidecar(path)
    role = _text(path, data, "role")
    if role not in SERVICE_ROLES:
        raise _fail(path, f"role '{role}' must be one of {', '.join(SERVICE_ROLES)}.")
    image = _text(path, data, "image")
    name, _, tag = image.rpartition(":")
    if not name or not tag or tag == "latest" or "/" in tag:
        raise _fail(path, f"image '{image}' must pin a version (name:tag, not latest).")
    ports = data.get("ports")
    if (
        not isinstance(ports, list)
        or not ports
        or not all(isinstance(p, int) and not isinstance(p, bool) and 0 < p < 65536 for p in ports)
    ):
        raise _fail(path, "field 'ports' must be a non-empty list of TCP ports.")
    env = _str_map(path, data, "env")
    fixed_env = _str_map(path, data, "fixed_env", required=False)
    health = data.get("healthcheck")
    if not isinstance(health, dict):
        raise _fail(path, "field 'healthcheck' must be an object.")
    test = health.get("test")
    if not isinstance(test, list) or len(test) < 2 or not all(isinstance(t, str) and t for t in test):
        raise _fail(path, "healthcheck 'test' must be a Compose test list such as [\"CMD\", ...].")
    if test[0] not in ("CMD", "CMD-SHELL"):
        raise _fail(path, "healthcheck 'test' must start with CMD or CMD-SHELL.")
    for key in ("interval", "timeout"):
        if not isinstance(health.get(key), str) or not health[key]:
            raise _fail(path, f"healthcheck '{key}' must be a duration such as '10s'.")
    retries = health.get("retries")
    if isinstance(retries, bool) or not isinstance(retries, int) or retries <= 0:
        raise _fail(path, "healthcheck 'retries' must be a positive integer.")
    volume = data.get("volume")
    if volume is not None:
        if (
            not isinstance(volume, dict)
            or not isinstance(volume.get("name"), str)
            or not volume["name"]
            or not isinstance(volume.get("path"), str)
            or not volume["path"].startswith("/")
        ):
            raise _fail(path, "field 'volume' must be null or {name, path} with an absolute path.")
        volume = {"name": volume["name"], "path": volume["path"]}
    drivers = data.get("drivers")
    if not isinstance(drivers, dict) or set(drivers) != set(SERVICE_LANGUAGES):
        raise _fail(path, f"field 'drivers' must have exactly: {', '.join(SERVICE_LANGUAGES)}.")
    clean_drivers: dict[str, dict[str, str]] = {}
    for language, driver in drivers.items():
        if (
            not isinstance(driver, dict)
            or not isinstance(driver.get("package"), str)
            or not driver["package"]
            or not isinstance(driver.get("url"), str)
            or not driver["url"]
            or not all(isinstance(v, str) for v in driver.values())
        ):
            raise _fail(path, f"drivers.{language} must be an object of strings with 'package' and 'url'.")
        clean_drivers[language] = dict(driver)
    sources = _text_list(path, data, "sources", non_empty=True)
    if not all(s.startswith("https://") for s in sources):
        raise _fail(path, "every entry of 'sources' must be an https URL.")
    migrations = data.get("migrations")
    if migrations is not None:
        migrations = _str_map(path, data, "migrations")
    hostname = data.get("hostname")
    if hostname is not None and (not isinstance(hostname, str) or not hostname):
        raise _fail(path, "field 'hostname' must be a non-empty string.")
    return ServiceEntry(
        id=data["id"],
        role=role,
        image=image,
        ports=tuple(ports),
        env=env,
        fixed_env=fixed_env,
        healthcheck=dict(health),
        volume=volume,
        connection_env=_text(path, data, "connection_env"),
        drivers=clean_drivers,
        sources=sources,
        hostname=hostname,
        migrations=migrations,
    )


def load_services(templates_dir: Path) -> dict[str, ServiceEntry]:
    """`templates/services/<engine>.json`; a templates folder without it has no services."""
    directory = Path(templates_dir) / "services"
    services = {}
    if directory.is_dir():
        for path in sorted(directory.glob("*.json")):
            entry = _load_service(path)
            services[entry.id] = entry
    return services


def _sidecarless(directory: Path) -> tuple[str, ...]:
    """Ids of Markdown templates that have no .json sidecar next to them."""
    return tuple(
        markdown.stem
        for markdown in sorted(directory.glob("*.md"))
        if not markdown.with_suffix(".json").exists()
    )


def load_catalog(templates_dir: Path) -> Catalog:
    templates_dir = Path(templates_dir)
    topology_dir = templates_dir / "topologies"
    stack_dir = templates_dir / "stacks"
    sidecarless_topologies = _sidecarless(topology_dir)
    sidecarless_stacks = _sidecarless(stack_dir)

    topologies = {}
    for path in sorted(topology_dir.glob("*.json")):
        entry = _load_topology(path)
        topologies[entry.id] = entry
    known_topologies = set(topologies) | set(sidecarless_topologies)
    stacks = {}
    for path in [*sorted(stack_dir.glob("*.json")), *sorted(stack_dir.glob("*/*.json"))]:
        entry = _load_stack(path, topologies, known_topologies)
        if entry.id in stacks:
            raise _fail(path, f"the stack id '{entry.id}' is defined twice.")
        stacks[entry.id] = entry
    services = load_services(templates_dir)
    for entry in stacks.values():
        unknown = [engine for engine in (entry.supported_services or {}) if engine not in services]
        if services and unknown:
            raise CatalogError(
                f"RAPID1401 Invalid catalog sidecar '{entry.id}.json': supported_services names an engine "
                f"that is not in the catalog: {', '.join(unknown)}."
            )
    return Catalog(
        stacks=stacks,
        topologies=topologies,
        sidecarless_stacks=sidecarless_stacks,
        sidecarless_topologies=sidecarless_topologies,
        services=services,
    )


_LANGUAGE_NAMES = {
    "python": "Python",
    "typescript": "TypeScript",
    "javascript": "JavaScript",
    "go": "Go",
    "rust": "Rust",
    "java": "Java",
    "csharp": "C#",
    "php": "PHP",
    "ruby": "Ruby",
}


def _display(category: str, value: str) -> str:
    if category == "language":
        return _LANGUAGE_NAMES.get(value.lower(), value)
    return value


def _detected(model: ProjectModel, category: str) -> str:
    seen: list[str] = []
    for value in model.values(category):
        shown = _display(category, value)
        if shown not in seen:
            seen.append(shown)
    return ", ".join(seen) if seen else "not detected"


def is_generic_stack(content: str) -> bool:
    """True when the text carries the exact header written by build_generic_stack."""
    return any(line.strip() == GENERIC_STACK_HEADER for line in content.splitlines())


NOT_SCANNED = "not scanned (--no-scan)"


def build_generic_stack(model: ProjectModel, *, scanned: bool = True) -> str:
    """Render a tech-stack.md from what the scanner detected (pure).

    With `scanned=False` nothing was searched, so facts read "not scanned" instead of
    claiming "not detected".
    """

    def value(category: str) -> str:
        return _detected(model, category) if scanned else NOT_SCANNED

    lines = [
        GENERIC_STACK_HEADER,
        f"- **Language:** {value('language')}.",
        f"- **Package manager:** {value('package_manager')}.",
        f"- **Framework:** {value('framework')}.",
        f"- **Testing:** {value('testing')}.",
        f"- **Convention:** {GENERIC_STACK_RULE}",
        "- **Version Control:** Git.",
    ]
    return "\n".join(lines) + "\n"


CUSTOM_STACK_ID = "custom"
CUSTOM_STACK_SECTIONS = ("Runtime", "Framework", "Testing")


def missing_custom_stack_sections(text: str) -> tuple[str, ...]:
    """Sections a harness-written tech-stack.md must carry (RAPID1409 when any is missing).

    A section is a heading (`## Runtime`) or a labelled line (`- **Runtime:** ...`, `Runtime: ...`).
    """
    missing = []
    for section in CUSTOM_STACK_SECTIONS:
        label = re.escape(section)
        pattern = re.compile(
            rf"^[ \t]*(?:#{{1,6}}[ \t]+(?:\*\*|__)?{label}\b"
            rf"|(?:[-*+][ \t]+)?(?:\*\*|__)?{label}[ \t]*(?:\*\*|__)?[ \t]*:)",
            re.IGNORECASE | re.MULTILINE,
        )
        if not pattern.search(text):
            missing.append(section)
    return tuple(missing)


SETUP_DOC_IDS = ("brief", "business", "data-model", "architecture", "deployment")
_CONTEXT_PRIORITIES = {"LOW", "MEDIUM", "HIGH", "CRITICAL"}


@dataclass(frozen=True)
class SetupQuestion:
    id: str
    text: str
    required: bool = True
    options: tuple[str, ...] = ()


@dataclass(frozen=True)
class RequiredSection:
    """A section the drafted doc must contain; any of `titles` (aliases) satisfies it."""

    id: str
    titles: tuple[str, ...]


@dataclass(frozen=True)
class ConditionalSection:
    """A section required only while `when` holds (e.g. `service:database`)."""

    id: str
    titles: tuple[str, ...]
    when: str


CONDITION_PREFIXES = ("service:",)


@dataclass(frozen=True)
class SetupDocBank:
    id: str
    file: str
    title: str
    questions: tuple[SetupQuestion, ...]
    required_sections: tuple[RequiredSection, ...]
    max_chars: int
    context_priority: str
    conditional_sections: tuple[ConditionalSection, ...] = ()


def _questions(path: Path, data: dict) -> tuple[SetupQuestion, ...]:
    raw = data.get("questions")
    if not isinstance(raw, list) or not raw:
        raise _fail(path, "field 'questions' must be a non-empty list.")
    questions = []
    for item in raw:
        if not isinstance(item, dict):
            raise _fail(path, "each question must be an object.")
        required = item.get("required", True)
        if not isinstance(required, bool):
            raise _fail(path, "question 'required' must be a boolean.")
        options = item.get("options", [])
        if not isinstance(options, list) or not all(isinstance(o, str) and o for o in options):
            raise _fail(path, "question 'options' must be a list of non-empty strings.")
        questions.append(
            SetupQuestion(_text(path, item, "id"), _text(path, item, "text"), required, tuple(options))
        )
    return tuple(questions)


def _required_sections(path: Path, data: dict) -> tuple[RequiredSection, ...]:
    raw = data.get("required_sections")
    if not isinstance(raw, list) or not raw:
        raise _fail(path, "field 'required_sections' must be a non-empty list.")
    sections = []
    for item in raw:
        if not isinstance(item, dict):
            raise _fail(path, "each required section must be an object with 'id' and 'titles'.")
        sections.append(
            RequiredSection(_text(path, item, "id"), _text_list(path, item, "titles", non_empty=True))
        )
    return tuple(sections)


def _conditional_sections(path: Path, data: dict) -> tuple[ConditionalSection, ...]:
    raw = data.get("conditional_sections", [])
    if not isinstance(raw, list):
        raise _fail(path, "field 'conditional_sections' must be a list.")
    sections = []
    for item in raw:
        if not isinstance(item, dict):
            raise _fail(path, "each conditional section must be an object with 'id', 'titles' and 'when'.")
        when = _text(path, item, "when")
        if not when.startswith(CONDITION_PREFIXES) or not when.partition(":")[2]:
            raise _fail(path, f"conditional section 'when' must start with one of {', '.join(CONDITION_PREFIXES)}.")
        sections.append(
            ConditionalSection(_text(path, item, "id"), _text_list(path, item, "titles", non_empty=True), when)
        )
    return tuple(sections)


def load_setup_doc_banks(templates_dir: Path) -> dict[str, SetupDocBank]:
    directory = Path(templates_dir) / "setup" / "docs"
    banks = {}
    for doc_id in SETUP_DOC_IDS:
        path = directory / f"{doc_id}.json"
        data = _read_sidecar(path)
        max_chars = data.get("max_chars")
        if isinstance(max_chars, bool) or not isinstance(max_chars, int) or max_chars <= 0:
            raise _fail(path, "field 'max_chars' must be a positive integer.")
        priority = _text(path, data, "context_priority").upper()
        if priority not in _CONTEXT_PRIORITIES:
            raise _fail(path, f"context_priority must be one of {sorted(_CONTEXT_PRIORITIES)}.")
        questions = _questions(path, data)
        sections = _required_sections(path, data)
        conditional = _conditional_sections(path, data)
        question_ids = {question.id for question in questions}
        missing = [section.id for section in (*sections, *conditional) if section.id not in question_ids]
        if missing:
            raise _fail(path, f"required sections without a question of the same id: {', '.join(missing)}.")
        banks[doc_id] = SetupDocBank(
            id=doc_id,
            file=_text(path, data, "file"),
            title=_text(path, data, "title"),
            questions=questions,
            required_sections=sections,
            max_chars=max_chars,
            context_priority=priority,
            conditional_sections=conditional,
        )
    return banks


def load_stack_questions(templates_dir: Path) -> tuple[SetupQuestion, ...]:
    path = Path(templates_dir) / "setup" / "stack-questions.json"
    return _questions(path, _read_sidecar(path))
