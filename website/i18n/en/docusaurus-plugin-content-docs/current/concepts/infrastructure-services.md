---
title: Infrastructure Services
description: How Rapid OS records a project's database, cache, queue, and streaming service decisions.
---

# Infrastructure Services

Project infrastructure services (database, cache, queue, streaming) **come from a recorded decision, not from the stack**. A stack only suggests a minimum (`suggested_services`, such as `database:postgresql`); a person decides which services to use, why, and when.

## The decision

After `brief` and `business`, and before `data-model`, `architecture`, and `deployment`, the `rapid setup next` orchestrator returns the `choose_services` action. The agent suggests services based on the brief and business rules (starting with the minimum, usually a database), and the person responds:

```bash
rapid setup set services database:postgresql@now,queue:rabbitmq@later
rapid setup set services none
```

- Format: `<role>:<engine>[@now|@later]`, separated by commas. Without a suffix, the default is `@now`.
- Roles: `database`, `cache`, `queue`, `stream`, `search`, `object-storage`.
- `@now`: needed for the first story; Rapid OS writes its container. `@later`: decided, but no container is written yet.
- `none` is a valid decision (a static site needs no services).
- An unknown role or engine, or an incompatible pair, returns `RAPID1413`; an engine unsupported by the stack returns `RAPID1402`.
- After `setup finish`, `rapid setup set services ...` applies immediately and does not reopen onboarding.

## Catalog

Each engine is a `templates/services/<engine>.json` file validated by `rapid_os.domain.catalog` (`RAPID1401`). It defines the role, official image with pinned major version, ports, variables, health check, volume, connection variable, language drivers, and official `sources`.

| Role | Engines |
|---|---|
| database | `postgresql`, `mysql`, `mariadb`, `mongodb` |
| cache | `redis`, `valkey` |
| queue | `rabbitmq` |
| stream | `kafka` (single-node KRaft) |

## What Rapid OS writes

When onboarding finishes for an empty repository, `rapid setup finish` (not the agent) writes:

- `compose.yaml`: one service per `@now`, pinned image, health check, named volume, and ports bound only to `127.0.0.1`.
- `.env.example` with connection variables, and adds `.env` to `.gitignore`.
- `tech-stack.md` with the chosen database and engine driver (the stack no longer imposes them).

If a `compose.yaml` already exists, changing a service from `@later` to `@now` adds only missing services. Existing services are not modified; unreadable YAML is left untouched with a warning. The `finish` output and draft review list the files.

## Test the data model without making the gate depend on Docker

The harness sandbox does not run Docker. Therefore, while `compose.yaml` exists, `rapid setup finish` and `rapid status` show a `local-services` action for the person (`docker compose up -d`). The scaffold task asks that configuration be read from `.env.example`, schema changes go into migrations, unit tests use no external services, and integration tests have their own marker. `gate.tests` can pass without Docker.

## Project documents

- `docs/ARCHITECTURE.md` requires an `Infrastructure Services` section.
- `docs/DATA_MODEL.md` requires `Local Database` when a `database` service is selected (`RAPID1403` if missing).
- `docs/DEPLOYMENT.md` is optional and comes last; see the [deployment guide](../guides/deployment.md).
