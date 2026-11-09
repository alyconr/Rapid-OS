"""How a backend reaches its database: the ORM, query builder, driver or ODM chosen from the stack's catalog.

The stack declares its options (`data_access` in `templates/stacks/backend/<id>.json`) and the onboarding
records the choice in `.rapid-os/setup.json`, optional there. Pure: no I/O.
"""

from __future__ import annotations

from dataclasses import replace
from typing import Mapping

from rapid_os.domain.catalog import ENGINE_DATA_MODEL, Catalog, DataAccessOption, StackEntry
from rapid_os.domain.setup import DataAccessChoice, SetupState

BACKEND = "backend"
DATA_ACCESS_INSTRUCTION = (
    "Recomienda `recommended` y una alternativa, con las `notes` de cada opción aplicadas a este producto; no afirmes "
    "nada que el catálogo no diga: cada opción trae sus `sources`. La persona decide."
)
DATA_ACCESS_DELEGATION = (
    "Si la persona delega la decisión («decide tú»), elige tú con esas razones, dile cuál elegiste y por qué, y "
    "regístrala con `--decided-by agent`."
)
MIGRATIONS_INSTRUCTION = (
    "La sección de migraciones nombra esta herramienta y estos comandos tal cual; sustituye solo lo que va entre "
    "`<` y `>`. `generate` en null significa que las migraciones se escriben a mano."
)
NO_MIGRATIONS_TOOL_INSTRUCTION = (
    "Esta opción no trae herramienta de migraciones: la sección de migraciones dice cuál usa el proyecto, sin darla por hecha."
)
SCHEMA_VALIDATION_INSTRUCTION = (
    "La sección de validación del esquema parte de `schema_validation`: es cómo se valida la forma de cada documento con esta opción."
)
# Where a Worker can run a backend: the runtimes of the catalog that are Cloudflare Workers.
WORKERS_RUNTIMES = frozenset({"workers", "python-workers"})
PYTHON_WORKERS_URL = "https://developers.cloudflare.com/hyperdrive/examples/python-workers/"
CONTAINERS_URL = "https://developers.cloudflare.com/containers/"
# What Cloudflare offers instead of each engine of the catalog that does not run from Workers. The one source of the
# `deployment` note, of `service_alternatives` in `hono.json` and of `templates/deploy/cloudflare.md` (a test compares).
QUEUES_ALTERNATIVE = (
    "Cloudflare Queues, con otra semántica: entrega al menos una vez, en lotes y con reintentos; el consumidor debe "
    "ser idempotente."
)
KV_ALTERNATIVE = "Workers KV para clave-valor de lectura frecuente: consistencia eventual y sin operaciones atómicas; no es Redis."
CLOUDFLARE_SERVICE_ALTERNATIVES = {
    "rabbitmq": QUEUES_ALTERNATIVE,
    "kafka": QUEUES_ALTERNATIVE,
    "redis": KV_ALTERNATIVE,
    "valkey": KV_ALTERNATIVE,
    "mongodb": "Cloudflare no tiene servicio propio de MongoDB documentado y Hyperdrive solo conecta PostgreSQL y MySQL: fuera de Cloudflare.",
    "mariadb": "Hyperdrive admite MariaDB, pero ninguna opción de acceso a datos de este catálogo la cita desde Workers: usa mysql o postgresql.",
}
CLOUDFLARE_SERVICE_SOURCES = {
    "rabbitmq": "https://developers.cloudflare.com/queues/reference/delivery-guarantees/",
    "kafka": "https://developers.cloudflare.com/queues/reference/delivery-guarantees/",
    "redis": "https://developers.cloudflare.com/kv/concepts/how-kv-works/",
    "valkey": "https://developers.cloudflare.com/kv/concepts/how-kv-works/",
    "mongodb": "https://developers.cloudflare.com/hyperdrive/reference/supported-databases-and-features/",
    "mariadb": "https://developers.cloudflare.com/hyperdrive/reference/supported-databases-and-features/",
}
ASYNC_SQLALCHEMY = "sqlalchemy-async"
SYNC_SQLALCHEMY = "sqlalchemy-sync"


def database_engine(state: SetupState) -> str | None:
    """The engine of the first `database` service, the one the data model follows."""
    return next((c.engine for c in (state.services or ()) if c.role == "database"), None)


def _stack_entry(state: SetupState, catalog: Catalog, component: str) -> StackEntry | None:
    choice = state.stacks.get(component)
    return catalog.entry(choice.id) if choice is not None else None


def recommended_option(entry: StackEntry, engine: str) -> DataAccessOption | None:
    """The stack's default for the engine's data model when it fits the engine; else the first one that does."""
    if entry.data_access is None:
        return None
    compatible = entry.data_access.for_engine(engine)
    default = entry.data_access.option(entry.data_access.default.get(ENGINE_DATA_MODEL.get(engine, ""), ""))
    if default is not None and default in compatible:
        return default
    return compatible[0] if compatible else None


def recommended_id(state: SetupState, catalog: Catalog, component: str = BACKEND) -> str | None:
    entry = _stack_entry(state, catalog, component)
    engine = database_engine(state)
    option = recommended_option(entry, engine) if entry is not None and engine else None
    return option.id if option else None


def chosen_option(state: SetupState, catalog: Catalog, component: str = BACKEND) -> DataAccessOption | None:
    choice = state.data_access.get(component)
    entry = _stack_entry(state, catalog, component)
    if choice is None or entry is None or entry.data_access is None:
        return None
    return entry.data_access.option(choice.id)


def effective_stack(entry: StackEntry | None, state: SetupState) -> StackEntry | None:
    """The stack with the client its chosen option needs (the driver and URL of `.env.example` and tech-stack)."""
    if entry is None or entry.data_access is None or entry.supported_services is None:
        return entry
    choice = state.data_access.get(entry.component or BACKEND)
    option = entry.data_access.option(choice.id) if choice is not None else None
    if option is None or not option.drivers:
        return entry
    return replace(entry, supported_services={**entry.supported_services, **option.drivers})


def needs_data_access_choice(state: SetupState, catalog: Catalog) -> bool:
    """A finished onboarding is not reopened for a decision that did not exist when it closed."""
    if state.finished or chosen_option(state, catalog) is not None:
        return False
    entry = _stack_entry(state, catalog, BACKEND)
    engine = database_engine(state)
    return bool(entry is not None and entry.data_access is not None and engine and entry.data_access.for_engine(engine))


def data_access_action_payload(state: SetupState, catalog: Catalog) -> dict:
    entry = _stack_entry(state, catalog, BACKEND)
    engine = database_engine(state)
    command = ["rapid", "setup", "set", "data-access", "<id>", "--component", BACKEND]
    return {
        "component": BACKEND,
        "stack": entry.id,
        "engine": engine,
        "model": ENGINE_DATA_MODEL[engine],
        "options": [option.to_dict() for option in entry.data_access.for_engine(engine)],
        "recommended": recommended_option(entry, engine).id,
        "instruction": DATA_ACCESS_INSTRUCTION,
        "delegation": {"instruction": DATA_ACCESS_DELEGATION, "command": [*command, "--decided-by", "agent"]},
        "command": command,
        "alt_command": ["rapid", "setup", "set", "data-access", "--recommended", "--component", BACKEND],
    }


def resolve_choice(
    state: SetupState, catalog: Catalog, value: str, *, component: str = BACKEND, decided_by: str = "person"
) -> tuple[str, DataAccessChoice]:
    """`rapid setup set data-access <id>`. A bad value raises ValueError("<RAPID code> <message>")."""
    entry = _stack_entry(state, catalog, component)
    if entry is None or entry.data_access is None:
        raise ValueError(f"RAPID1413 The {component} has no stack with 'data_access' options to choose from.")
    engine = database_engine(state)
    if engine is None:
        raise ValueError("RAPID1413 'data-access' needs a database service first: rapid setup set services database:<engine>.")
    compatible = entry.data_access.for_engine(engine)
    option = entry.data_access.option(value)
    if option is None:
        known = ", ".join(o.id for o in entry.data_access.options)
        raise ValueError(f"RAPID1413 Unknown data access option '{value}' for stack '{entry.id}'. Options: {known}.")
    if option not in compatible:
        usable = ", ".join(o.id for o in compatible) or "none"
        raise ValueError(
            f"RAPID1402 Option '{value}' and database '{engine}' are incompatible. Options for {engine}: {usable}."
        )
    return component, DataAccessChoice(option.id, decided_by)


def reconcile_data_access(state: SetupState, catalog: Catalog) -> tuple[SetupState, tuple[str, ...]]:
    """After the stack or the services change: a choice that no longer fits is undecided again, and the only
    option compatible with the engine is fixed and reported (it is no decision of the person)."""
    notes: list[str] = []
    choices: Mapping[str, DataAccessChoice] = dict(state.data_access)
    entry = _stack_entry(state, catalog, BACKEND)
    engine = database_engine(state)
    current = choices.get(BACKEND)
    if current is not None:
        option = entry.data_access.option(current.id) if entry is not None and entry.data_access else None
        undecided_services = state.services is None
        if option is None or (not undecided_services and engine not in option.engines):
            del choices[BACKEND]
            notes.append(f"La opción de acceso a datos '{current.id}' ya no encaja; vuelve a estar sin decidir.")
    if BACKEND not in choices and entry is not None and entry.data_access is not None and engine:
        compatible = entry.data_access.for_engine(engine)
        if len(compatible) == 1:
            choices[BACKEND] = DataAccessChoice(compatible[0].id, "auto")
            notes.append(
                f"Acceso a datos: {compatible[0].name} es la única opción de '{entry.id}' para {engine}; queda fijada."
            )
    return (replace(state, data_access=choices) if choices != dict(state.data_access) else state), tuple(notes)


def data_access_doc_payload(state: SetupState, catalog: Catalog) -> dict | None:
    """What the `data-model` document needs from the choice: the migrations tool or the schema validation."""
    option = chosen_option(state, catalog)
    if option is None:
        return None
    instructions = []
    if option.migrations is not None:
        instructions.append(MIGRATIONS_INSTRUCTION)
    elif "relational" in option.models:
        instructions.append(NO_MIGRATIONS_TOOL_INSTRUCTION)
    if option.schema_validation:
        instructions.append(SCHEMA_VALIDATION_INSTRUCTION)
    return {
        "id": option.id,
        "name": option.name,
        "kind": option.kind,
        "migrations": None if option.migrations is None else option.migrations.to_dict(),
        "schema_validation": option.schema_validation,
        "notes": option.notes,
        "sources": list(option.sources),
        "instruction": " ".join(instructions),
    }


def _judged_option(state: SetupState, catalog: Catalog, entry: StackEntry) -> DataAccessOption | None:
    """The option chosen; without a choice (a project finished before this step) the one recommended for the
    engine, which is the one `tech-stack.md` describes. None without a database."""
    option = chosen_option(state, catalog)
    if option is None:
        engine = database_engine(state)
        option = recommended_option(entry, engine) if engine else None
    return option


def _cloudflare_backend_line(state: SetupState, catalog: Catalog) -> tuple[str, str] | None:
    """Whether the backend decided runs in Workers: `(line, source)`, or None when it fits."""
    entry = _stack_entry(state, catalog, BACKEND)
    if entry is None or entry.data_access is None:
        return None
    option = _judged_option(state, catalog, entry)
    if option is None:
        if any(WORKERS_RUNTIMES & set(o.runtimes) for o in entry.data_access.options):
            return None
    elif WORKERS_RUNTIMES & set(option.runtimes):
        return None
    if option is not None and option.id == ASYNC_SQLALCHEMY:
        return (
            f"{entry.id} + {option.name} no corre en Python Workers: Cloudflare solo admite ORMs síncronos de "
            "SQLAlchemy, por falta de greenlet. Usa la variante síncrona "
            f"(`rapid setup set data-access {SYNC_SQLALCHEMY}`) o aloja la API fuera de Workers.",
            PYTHON_WORKERS_URL,
        )
    shown = f"{entry.id} + {option.name}" if option is not None else entry.id
    return (
        f"Este catálogo no documenta {shown} en Workers: aloja la API en otra plataforma o en Cloudflare "
        "Containers, y deja el frontend en Cloudflare.",
        CONTAINERS_URL,
    )


def _cloudflare_note(state: SetupState, catalog: Catalog) -> dict | None:
    """The backend and every decided service (`@now` or `@later`) without an equivalent in Workers, with the
    platform's alternative. It informs and blocks nothing; None when everything fits."""
    lines: list[str] = []
    sources: list[str] = []
    backend = _cloudflare_backend_line(state, catalog)
    if backend is not None:
        lines.append(backend[0])
        sources.append(backend[1])
    seen: set[str] = set()
    for choice in state.services or ():
        alternative = CLOUDFLARE_SERVICE_ALTERNATIVES.get(choice.engine)
        if alternative is None or choice.engine in seen:
            continue
        seen.add(choice.engine)
        lines.append(f"{choice.role}:{choice.engine}@{choice.when} no corre en Workers. Alternativa: {alternative}")
        if CLOUDFLARE_SERVICE_SOURCES[choice.engine] not in sources:
            sources.append(CLOUDFLARE_SERVICE_SOURCES[choice.engine])
    if not lines:
        return None
    return {"note": "\n".join(lines), "lines": lines, "sources": sources}


def platform_notes(state: SetupState, catalog: Catalog) -> dict[str, dict]:
    """Compatibility notes of the `deployment` document, by platform: the platform is its first question."""
    note = _cloudflare_note(state, catalog)
    return {"cloudflare": note} if note else {}
