---
title: Reference Architecture: The Modular Monolith
description: The default architecture rule, idiomatic names by language, when to use hexagonal modules, and how Rapid OS verifies each run.
---

# Reference Architecture: The Modular Monolith

Projects using catalog stacks start as a **modular monolith**: modules organized by business capability, layers within each module, and ports and adapters (hexagonal architecture) only where justified. Rapid OS provides the rule to the agent as a standard and checks it in each run, using names appropriate to the selected stack.

The `generic`, `custom`, and `docs-modern` stacks do not receive this rule. See [Stacks and Components](./stacks.md).

## The rule (same across languages)

Responsibilities remain the same; names and mechanisms vary.

- Organize the system into **business-capability modules** (appointments, payments, workshops), never global layers (`controllers/`, `services/`, `models/` at the root).
- Each module has an **entry point** (HTTP, events), **application** (use cases; ports live here when the module is hexagonal), **domain** (entities, rules, invariants, without web framework or ORM), **infrastructure** (persistence and external adapters), and **one public contract**.
- Dependency direction: entry → application → domain; infrastructure → application and domain (implements ports). Domain imports none of the other layers or web frameworks, ORMs, or external clients.
- Modules use another module's public contract only, never its internal layers.
- Each module owns its tables; other modules do not read or write them directly.
- `shared/` is a minimal core (configuration, database session, base errors) and imports no modules.

Do not start with microservices. A modular monolith provides the same boundaries with one deployment; a module with a public contract and owned tables can be extracted later if needed.

## Names by language

| Stack | Module root | Entry | Application | Domain | Infrastructure | Public contract |
|---|---|---|---|---|---|---|
| `python-fastapi` | `app/modules/<m>/` | `api/` | `application/` | `domain/` | `infrastructure/` | `public.py` |
| `python-django` | `apps/<m>/` (one app per module) | `api/` (views and serializers) | `services/` | `domain/` | `models.py` | `public.py` |
| `node-nestjs` | `src/modules/<m>/` | `controllers/` | `application/` | `domain/` | `infrastructure/` | `<m>.module.ts` exports or `index.ts` |
| `node-fastify` | `src/modules/<m>/` | `routes/` | `application/` | `domain/` | `infrastructure/` | `index.ts` |
| `go` | `internal/<m>/` | `http/` | `app/` | `domain/` | `store/` or `adapters/` | Module root package (exported identifiers) |
| `rust-axum` | `src/modules/<m>/` | `routes.rs` | `application.rs` | `domain.rs` | `infra.rs` | `mod.rs` (`pub use`); rest `pub(crate)` |
| `ruby-rails` | `packs/<m>/` (packwerk) | `app/controllers` | `app/use_cases` | `app/domain` (POROs) | `app/models` (Active Record) | `app/public/` |
| `dotnet-aspnetcore` | `src/Modules/<M>/` | `<M>.Api` | `<M>.Application` | `<M>.Domain` | `<M>.Infrastructure` | `<M>.Contracts` project |
| `java-spring-boot`, `kotlin-spring-boot` | `src/main/{java,kotlin}/com/example/app/<m>/` | `web/` | `application/` | `domain/` | `infrastructure/` | Module root types (Spring Modulith) |
| `php-laravel` | `app/Modules/<M>/` | `Http/` | `Application/` | `Domain/` | `Infrastructure/` | `Contracts/` and a module ServiceProvider |
| `nextjs`, `nuxt`, `sveltekit` (server) | `src/modules/<m>/` (Nuxt: `server/modules/`; SvelteKit: `src/lib/server/modules/`) | `api/` | `application/` | `domain/` | `infrastructure/` | `index.ts` |

Generated `architecture.md` uses the selected language's names, its stack tree, and a final table mapping each name to its canonical responsibility.

### Frontend

The eight frontend stacks (`react-vite`, `nextjs`, `angular`, `vue-vite`, `nuxt`, `svelte-vite`, `sveltekit`, `astro`) organize by **feature** under `src/features/<f>/` (Angular: `src/app/features/`; Nuxt: `app/features/`; SvelteKit: `src/lib/features/`):

| Directory | Responsibility |
|---|---|
| `ui/` | Components |
| `state/` | Feature state |
| `data-access/` | API calls |
| `model/` | Presentation types and rules |
| `index.ts` | Public contract |

`ui` may import `state` and `model`; `state` and `data-access` may import `model`; `model` imports neither other layers nor UI frameworks (`react`, `vue`, `svelte`, `@angular/core`, and others). A feature imports only another feature's `index.ts`.

### Backend and frontend in one project

With different backend and frontend stacks, code lives in `backend/` and `frontend/`, and `architecture.json` has two rules. If one framework covers both (`nextjs`, `nuxt`, `sveltekit`), both rules live at the root under `src/modules` and `src/features`. A project with only one component uses the root.

## When a module should be hexagonal

Use ports in the application layer and adapters in infrastructure when a module integrates an external system (payments, messaging, AI, email), has complex domain rules that must be tested without infrastructure, or may change providers. A simple CRUD module does not need this.

## How the rule reaches a project

`rapid setup finish` (and `rapid init`) writes two files under `.rapid-os/standards/`:

| File | For | Contents |
|---|---|---|
| `architecture.md` | Agent | Rule, stack tree, and language-specific names. Included in context and agent files as a standard, without an assumption banner. |
| `architecture.json` | Rapid OS | Machine-readable rule. |

Existing files are not overwritten on a later onboarding finish. If you switch to a stack without the rule, Rapid OS does not delete these files; remove them yourself if they no longer apply.

`architecture.json` stores the language, component, module and shared roots, public entry point, allowed layer imports, and forbidden imports in the pure layer. Component catalog profiles may also include roles, module pattern, public contract/policy, public directories, namespace root, aliases, pure layer, delegate, root, and multiple rules. Older files remain readable. In Java and Kotlin, replace `com.example.app` with the real package; in C# and PHP, set the real root namespace.

The onboarding `docs/ARCHITECTURE.md` requires **Modules**, **Dependency Rules**, and **Infrastructure Services** sections and builds on this standard.

## How verification works

`rapid arch check` reads imports under `modules_root` and `shared_root` and reports each violation with file, line, import, and rule (`RAPID1420`). It does not execute application code or add dependencies.

| Language | What it reads |
|---|---|
| Python | `ast` |
| TypeScript / JavaScript | `import`, `export ... from`, `import()`, `require`; Vue/Svelte `<script>`; Astro frontmatter and `<script>` |
| Go | `import` (ignores `_test.go`) |
| Java / Kotlin | `import` |
| C# | `using` and `.csproj` `ProjectReference` / `PackageReference` |
| Rust | `use` (`crate::`, `super::`, `self::`) |
| PHP | `use` |
| Ruby | Delegates to `bin/packwerk check` |

Violations include an illegal layer import, importing a module's non-public internals, `shared` importing a module, a Python module `__init__.py` importing anything other than its own `public.py`, and a pure layer importing a forbidden library. Only directories under `modules_root` count as modules. Exit code is 1 for violations; it is 0 when clean, before modules exist, or (with a warning) if `architecture.json` is absent.

### Ruby on Rails

Rails loads code by convention, so there are no imports to read. `rapid arch check` runs `bin/packwerk check`. If packwerk is missing, it warns (`RAPID1420`) and exits 1; the gate is not satisfied. Install it with `bundle add packwerk --group development && bundle binstub packwerk`.

### Idiomatic tools as additional checks

Where an ecosystem tool exists, `architecture.md` names it as an optional scaffold check: Spring Modulith (`ApplicationModules.of(Application.class).verify()`), packwerk, Deptrac (PHP), and NetArchTest (.NET). The gate remains `rapid arch check`.

### In a worktree run

A run worktree has no `.rapid-os/`; the ledger and rule are in the main project. If the current directory lacks `architecture.json` but an active session's contract includes `gate.architecture`, `rapid arch check` reads the rule from the main project and checks code in the current directory (the worktree). If a required gate has no rule in either location, it returns `RAPID1420` and exit code 1. Outside a run, missing `architecture.json` returns exit code 0 with a warning.

### The `gate.architecture` gate

For `feature`, `bugfix`, and `refactor` runs with `architecture.json`, the contract includes the required, non-waivable machine gate `gate.architecture`. `rapid next` proposes it like `gate.tests`:

```bash
rapid check --gate gate.architecture -- rapid arch check
```

`rapid finish` cannot return `PASS` until the gate is satisfied. Never disable or edit `architecture.json` just to pass a check; change the code or ask a person to change the rule.
