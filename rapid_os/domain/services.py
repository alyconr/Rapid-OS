"""Infrastructure services of a project: parsing the decision, the local Compose environment and
the database lines of `tech-stack.md`. Pure: no I/O.

The decision (`rapid setup set services database:mysql@now,cache:redis@later`) is stored in
`.rapid-os/setup.json`. Rapid OS, not the agent, writes `compose.yaml` and `.env.example` from the
catalog (`templates/services`) for the services that are `@now`.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Iterable

from rapid_os.domain.catalog import SERVICE_ROLES, Catalog, ServiceEntry, StackEntry
from rapid_os.domain.setup import SERVICE_WHEN, ServiceChoice

NO_SERVICES = "none"
COMPOSE_FILE_NAMES = ("compose.yaml", "compose.yml", "docker-compose.yaml", "docker-compose.yml")
DEFAULT_COMPOSE_FILE = "compose.yaml"
ENV_EXAMPLE_FILE = ".env.example"
LOCAL_SERVICES_ACTION = {
    "id": "local-services",
    "why": (
        "El sandbox del harness no ejecuta Docker: los servicios los levantas tú para probar el modelo "
        "de datos y las integraciones"
    ),
    "command": "docker compose up -d",
}


class ServiceInputError(ValueError):
    """An invalid `services` decision. `code` is RAPID1413 (bad input) or RAPID1402 (stack mismatch)."""

    def __init__(self, code: str, message: str):
        super().__init__(f"{code} {message}")
        self.code = code
        self.message = message


# --- the decision ---------------------------------------------------------------------------


def format_services(choices: Iterable[ServiceChoice]) -> str:
    text = ",".join(f"{c.role}:{c.engine}@{c.when}" for c in choices)
    return text or NO_SERVICES


def parse_services(value: str, catalog: Catalog) -> tuple[ServiceChoice, ...]:
    """`role:engine[@now|@later],...` or `none`. Unknown role or engine, an engine of another role
    or a bad `@when` is RAPID1413 with the valid list."""
    text = (value or "").strip()
    if not text:
        raise ServiceInputError("RAPID1413", "Missing value for 'rapid setup set services' (use 'none' for no services).")
    if text.lower() == NO_SERVICES:
        return ()
    choices: list[ServiceChoice] = []
    for raw in text.split(","):
        item = raw.strip()
        if not item:
            continue
        spec, at, when = item.partition("@")
        when = (when.strip().lower() if at else "now") or "now"
        role, colon, engine = spec.partition(":")
        role, engine = role.strip().lower(), engine.strip().lower()
        if not colon or not role or not engine:
            raise ServiceInputError(
                "RAPID1413",
                f"Invalid service '{item}': use <role>:<engine>[@now|@later], for example database:mysql@now.",
            )
        if role not in SERVICE_ROLES:
            raise ServiceInputError(
                "RAPID1413", f"Unknown service role '{role}'. Roles: {', '.join(SERVICE_ROLES)}."
            )
        if engine not in catalog.services:
            known = catalog.engines_for_role(role)
            raise ServiceInputError(
                "RAPID1413",
                f"Unknown {role} engine '{engine}'. Engines for {role}: {', '.join(known) or 'none in the catalog'}.",
            )
        entry = catalog.services[engine]
        if entry.role != role:
            raise ServiceInputError(
                "RAPID1413",
                f"'{engine}' is a {entry.role}, not a {role}. Engines for {role}: "
                f"{', '.join(catalog.engines_for_role(role)) or 'none in the catalog'}.",
            )
        if when not in SERVICE_WHEN:
            raise ServiceInputError(
                "RAPID1413", f"Invalid moment '@{when}' for '{role}:{engine}': use {' or '.join('@' + w for w in SERVICE_WHEN)}."
            )
        if any(c.role == role and c.engine == engine for c in choices):
            raise ServiceInputError("RAPID1413", f"Service '{role}:{engine}' is listed twice.")
        choices.append(ServiceChoice(role, engine, when))
    if not choices:
        raise ServiceInputError("RAPID1413", "Missing services (use 'none' for no services).")
    return tuple(choices)


def driver_for(
    catalog: Catalog, engine: str, language: str, stack: StackEntry | None = None
) -> dict[str, str] | None:
    """`{package, url[, orm]}` of the client library for an engine: the stack's own when its sidecar
    declares `supported_services`, else the engine's driver for Python or TypeScript."""
    if stack is not None and stack.supported_services is not None:
        item = stack.supported_services.get(engine)
        if item is None:
            return None
        driver = {"package": item["driver"], "url": item["url"]}
        if item.get("orm"):
            driver["orm"] = item["orm"]
        return driver
    service = catalog.services.get(engine)
    return service.drivers.get(language) if service is not None else None


def check_stack_compatibility(choices: Iterable[ServiceChoice], stack_id: str | None, catalog: Catalog) -> None:
    """RAPID1402 when the stack cannot use a chosen service (like an incompatible topology)."""
    entry = catalog.entry(stack_id or "")
    if entry is None:
        return  # custom or sidecarless stacks accept every service
    language = entry.language.lower()
    for choice in choices:
        if entry.service_roles is not None and choice.role not in entry.service_roles:
            usable = ", ".join(entry.service_roles) or "none"
            raise ServiceInputError(
                "RAPID1402",
                f"Stack '{entry.id}' and service '{choice.role}:{choice.engine}' are incompatible: "
                f"this stack does not use {choice.role} services (roles it supports: {usable}). "
                "Choose another stack or 'none'.",
            )
        if entry.supported_services is not None:
            if choice.engine not in entry.supported_services:
                supported = ", ".join(sorted(entry.supported_services)) or "none"
                raise ServiceInputError(
                    "RAPID1402",
                    f"Stack '{entry.id}' ({entry.language}) has no driver for '{choice.engine}'. "
                    f"Engines it supports: {supported}.",
                )
            continue
        service = catalog.services.get(choice.engine)
        if service is not None and language in ("python", "typescript") and language not in service.drivers:
            raise ServiceInputError(
                "RAPID1402",
                f"Stack '{entry.id}' ({entry.language}) has no driver for '{choice.engine}'. "
                f"Drivers exist for: {', '.join(sorted(service.drivers))}.",
            )


def stack_language(catalog: Catalog, stack_id: str | None, fallback: str = "typescript") -> str:
    """`python` or `typescript`: the language of the drivers and connection URLs for the stack."""
    entry = catalog.entry(stack_id or "")
    language = entry.language.lower() if entry is not None else fallback
    return language if language in ("python", "typescript") else fallback


def services_now(choices: Iterable[ServiceChoice] | None) -> tuple[ServiceChoice, ...]:
    return tuple(c for c in (choices or ()) if c.when == "now")


def describe_services(choices: Iterable[ServiceChoice] | None, catalog: Catalog) -> list[dict[str, str]]:
    """The decision as the agent needs it to write the documents: role, engine, version, moment."""
    described = []
    for choice in choices or ():
        entry = catalog.services.get(choice.engine)
        described.append(
            {
                "role": choice.role,
                "engine": choice.engine,
                "version": entry.version if entry else "",
                "image": entry.image if entry else "",
                "when": choice.when,
            }
        )
    return described


def has_service_role(choices: Iterable[ServiceChoice] | None, role: str) -> bool:
    return any(c.role == role for c in (choices or ()))


def active_conditions(choices: Iterable[ServiceChoice] | None) -> frozenset[str]:
    """Conditions of the document banks (`service:<role>`) that hold for the decision."""
    return frozenset(f"service:{c.role}" for c in (choices or ()))


# --- compose.yaml ---------------------------------------------------------------------------

_COMPOSE_HEADER = """# Entorno local escrito por Rapid OS: un servicio por cada decisión "now" de .rapid-os/setup.json.
# Copia .env.example a .env para cambiar valores; sin .env se usan los de ejemplo (solo para desarrollo local).
# Rapid OS añade aquí los servicios que pasan de "later" a "now", pero nunca modifica los que ya están.
# Los puertos solo se abren en 127.0.0.1. Levanta los servicios con: docker compose up -d
"""


def _q(value: str) -> str:
    return json.dumps(value, ensure_ascii=False)


def compose_block(entry: ServiceEntry) -> list[str]:
    """The `services:` entry of one engine (two-space indented lines, no trailing newline)."""
    lines = [f"  {entry.id}:", f"    image: {entry.image}"]
    if entry.hostname:
        lines.append(f"    hostname: {entry.hostname}")
    if entry.env or entry.fixed_env:
        lines.append("    environment:")
        for name, example in entry.env.items():
            lines.append(f"      {name}: {_q('${' + name + ':-' + example + '}')}")
        for name, fixed in entry.fixed_env.items():
            lines.append(f"      {name}: {_q(fixed)}")
    lines.append("    ports:")
    for port in entry.ports:
        lines.append(f"      - {_q(f'127.0.0.1:{port}:{port}')}")
    if entry.volume:
        lines += ["    volumes:", f"      - {entry.volume['name']}:{entry.volume['path']}"]
    health = entry.healthcheck
    lines += [
        "    healthcheck:",
        f"      test: [{', '.join(_q(t) for t in health['test'])}]",
        f"      interval: {health['interval']}",
        f"      timeout: {health['timeout']}",
        f"      retries: {health['retries']}",
    ]
    if health.get("start_period"):
        lines.append(f"      start_period: {health['start_period']}")
    return lines


def render_compose(choices: Iterable[ServiceChoice], catalog: Catalog) -> str:
    """`compose.yaml` with one service per `@now` choice, from the catalog."""
    entries = [catalog.services[c.engine] for c in services_now(tuple(choices)) if c.engine in catalog.services]
    lines = _COMPOSE_HEADER.splitlines()
    lines.append("services:")
    for entry in entries:
        lines += compose_block(entry)
    volumes = [e.volume["name"] for e in entries if e.volume]
    if volumes:
        lines.append("volumes:")
        lines += [f"  {name}:" for name in volumes]
    return "\n".join(lines) + "\n"


@dataclass(frozen=True)
class ComposeMerge:
    text: str
    added: tuple[str, ...] = ()
    warning: str | None = None


_TOP_KEY = re.compile(r"^([A-Za-z0-9_.-]+):[ \t]*(#.*)?$")
_TOP_KEY_ANY = re.compile(r"^([A-Za-z0-9_.-]+):")
_SERVICE_KEY = re.compile(r"^  ([A-Za-z0-9_.-]+):[ \t]*(#.*)?$")


def merge_compose(existing: str, choices: Iterable[ServiceChoice], catalog: Catalog) -> ComposeMerge:
    """Add to an existing compose file only the `@now` services it lacks; never change what is there.

    It reads the block style Rapid OS writes (top-level keys at column 0, services at two spaces).
    A file it cannot read that way is left untouched with a warning."""
    unreadable = ComposeMerge(
        existing,
        (),
        "No se pudo leer el archivo compose como YAML de bloques: Rapid OS no lo toca. "
        "Añade a mano los servicios que faltan (ver docs/concepts/infrastructure-services.md).",
    )
    text = existing.replace("\r\n", "\n")
    lines = text.split("\n")
    top_keys: list[tuple[int, str]] = []
    for index, line in enumerate(lines):
        if not line.strip() or line.lstrip().startswith("#") or line.strip() == "---":
            continue
        if line[0] == "\t" or (line[0] == " " and "\t" in line[: len(line) - len(line.lstrip())]):
            return unreadable
        if line[0] != " ":
            if not _TOP_KEY_ANY.match(line):
                return unreadable
            top_keys.append((index, _TOP_KEY_ANY.match(line).group(1)))
    names = [name for _i, name in top_keys]
    if names.count("services") != 1 or names.count("volumes") > 1:
        return unreadable
    services_at = next(i for i, n in top_keys if n == "services")
    if not _TOP_KEY.match(lines[services_at]):
        return unreadable  # `services: {...}` or any inline value
    end = next((i for i, _n in top_keys if i > services_at), len(lines))
    existing_services: set[str] = set()
    for line in lines[services_at + 1 : end]:
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        child = _SERVICE_KEY.match(line)
        if child:
            existing_services.add(child.group(1))
        elif not line.startswith("   ") and not line.startswith("  #"):
            return unreadable  # a child that is not a two-space service key and not deeper content
    wanted = [
        catalog.services[c.engine]
        for c in services_now(tuple(choices))
        if c.engine in catalog.services and c.engine not in existing_services
    ]
    if not wanted:
        return ComposeMerge(existing)

    volumes_at = next((i for i, n in top_keys if n == "volumes"), None)
    if volumes_at is not None and not _TOP_KEY.match(lines[volumes_at]):
        return unreadable
    # Insert the new services after the last non-blank line of the services section.
    insert_at = end
    while insert_at > services_at + 1 and not lines[insert_at - 1].strip():
        insert_at -= 1
    block: list[str] = []
    for entry in wanted:
        block += compose_block(entry)
    out = lines[:insert_at] + block + lines[insert_at:]
    new_volumes = [e.volume["name"] for e in wanted if e.volume]
    if new_volumes:
        if volumes_at is None:
            while out and not out[-1].strip():
                out.pop()
            out += ["volumes:"] + [f"  {name}:" for name in new_volumes] + [""]
        else:
            shifted = volumes_at + len(block)
            vol_end = next((i + len(block) for i, _n in top_keys if i > volumes_at), len(out))
            present = {m.group(1) for ln in out[shifted + 1 : vol_end] if (m := re.match(r"^  ([A-Za-z0-9_.-]+):", ln))}
            at = vol_end
            while at > shifted + 1 and not out[at - 1].strip():
                at -= 1
            out = out[:at] + [f"  {name}:" for name in new_volumes if name not in present] + out[at:]
    merged = "\n".join(out)
    if "\r\n" in existing:
        merged = merged.replace("\n", "\r\n")
    return ComposeMerge(merged, tuple(e.id for e in wanted))


# --- .env.example ---------------------------------------------------------------------------

_ENV_HEADER = """# Variables del entorno local. Copia este archivo a .env (que está en .gitignore).
# Son valores de ejemplo para desarrollo local, nunca secretos reales.
"""


def env_entries(
    choices: Iterable[ServiceChoice], catalog: Catalog, language: str, stack: StackEntry | None = None
) -> list[tuple[str, str, str]]:
    """(service, NAME, value) for the `@now` services: their variables and their connection URL."""
    entries: list[tuple[str, str, str]] = []
    used: set[str] = set()
    for choice in services_now(tuple(choices)):
        entry = catalog.services.get(choice.engine)
        if entry is None:
            continue
        for name, value in entry.env.items():
            entries.append((entry.id, name, value))
            used.add(name)
        connection = entry.connection_env
        if connection in used:  # two databases: the second one gets its engine as prefix
            connection = f"{entry.id.upper()}_{connection}"
        used.add(connection)
        driver = driver_for(catalog, entry.id, language, stack) or entry.drivers.get(language) or {}
        entries.append((entry.id, connection, driver.get("url", "")))
    return entries


def render_env_example(
    choices: Iterable[ServiceChoice], catalog: Catalog, language: str, stack: StackEntry | None = None
) -> str:
    lines = _ENV_HEADER.splitlines()
    current = None
    for service, name, value in env_entries(choices, catalog, language, stack):
        if service != current:
            lines += ["", f"# {service}"]
            current = service
        lines.append(f"{name}={value}")
    return "\n".join(lines) + "\n"


def merge_env_example(
    existing: str, choices: Iterable[ServiceChoice], catalog: Catalog, language: str, stack: StackEntry | None = None
) -> str:
    """Append only the variables the file does not define yet; never change a line that is there."""
    defined = {m.group(1) for ln in existing.splitlines() if (m := re.match(r"^\s*([A-Za-z_][A-Za-z0-9_]*)=", ln))}
    missing = [(s, n, v) for s, n, v in env_entries(choices, catalog, language, stack) if n not in defined]
    if not missing:
        return existing
    out = existing.rstrip("\n")
    current = None
    for service, name, value in missing:
        if service != current:
            out += f"\n\n# {service}"
            current = service
        out += f"\n{name}={value}"
    return out + "\n"


# --- tech-stack.md --------------------------------------------------------------------------

_DISPLAY = {
    "postgresql": "PostgreSQL",
    "mysql": "MySQL",
    "mariadb": "MariaDB",
    "mongodb": "MongoDB",
    "redis": "Redis",
    "valkey": "Valkey",
    "rabbitmq": "RabbitMQ",
    "kafka": "Kafka",
}
_ROLE_LABEL = {
    "cache": "Cache",
    "queue": "Queue",
    "stream": "Streaming",
    "search": "Search",
    "object-storage": "Object storage",
}


def render_tech_stack(
    text: str, language: str, choices: Iterable[ServiceChoice] | None, catalog: Catalog, stack: StackEntry | None = None
) -> str:
    """The database and driver lines of a stack's `tech-stack.md`, from the services decision.

    The stack no longer imposes the engine: `- **Database:**` (and the `- **ORM:**` line, which only
    SQL engines keep) are rewritten, and the other roles add a line each. Text without those lines
    keeps them out unless a database was chosen."""
    chosen = tuple(choices or ())
    database = next((c for c in chosen if c.role == "database"), None)
    entry = catalog.services.get(database.engine) if database else None
    when = " (más adelante)" if database and database.when == "later" else ""
    driver = driver_for(catalog, entry.id, language, stack) if entry else None

    lines = text.split("\n")
    had_database_line = any(ln.startswith("- **Database:**") for ln in lines)
    kept = [ln for ln in lines if not ln.startswith("- **ORM:**") and not ln.startswith("- **Database:**")]
    new: list[str] = []
    if entry is not None and driver is not None:
        orm = driver.get("orm")
        if orm:
            new.append(f"- **ORM:** {orm}.")
        label = f"{_DISPLAY.get(entry.id, entry.id)} {entry.version}{' LTS' if entry.lts else ''}"
        new.append(f"- **Database:** {label} + {driver['package']}{when}.")
        if not orm and language == "python" and (stack is None or stack.language.lower() == "python"):
            new.append("- **Migrations:** versioned scripts (no SQL ORM for this engine).")
    elif had_database_line:
        new.append("- **Database:** none (no database service was decided).")
    for choice in chosen:
        if choice.role == "database":
            continue
        service = catalog.services.get(choice.engine)
        if service is None:
            continue
        label = _ROLE_LABEL.get(choice.role, choice.role.title())
        package = (driver_for(catalog, service.id, language, stack) or {}).get("package", "")
        moment = " (más adelante)" if choice.when == "later" else ""
        engine = f"{_DISPLAY.get(service.id, service.id)} {service.version}{' LTS' if service.lts else ''}"
        new.append(f"- **{label}:** {engine} + {package}{moment}.".replace(" + .", "."))
    # Right before Version Control when the stack has that line, else at the end.
    at = next((i for i, ln in enumerate(kept) if ln.startswith("- **Version Control:**")), None)
    if at is None:
        trailing = [""] if kept and kept[-1] == "" else []
        body = kept[: len(kept) - len(trailing)]
        return "\n".join(body + new + trailing)
    return "\n".join(kept[:at] + new + kept[at:])
