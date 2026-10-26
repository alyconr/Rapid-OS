---
title: Reference Architecture, the Modular Monolith
description: The architecture rule every project starts with, the idiomatic names for each language, when a module is hexagonal, and how Rapid OS verifies it on every run.
---

# Reference Architecture, the Modular Monolith

Every project with a catalog stack starts as a **modular monolith**: modules by business capability, layers inside each module, and ports and adapters (hexagonal) only in the modules that justify them. The rule reaches the agent as a standard, and Rapid OS verifies it on every run, in the idiom of the chosen stack.

The `generic`, `custom`, and `docs-modern` stacks do not receive the rule. See [Stacks and components](./stacks.md).

## The rule (the same in every language)

The responsibilities do not change; the names and the mechanism do.

- The system is organized into **modules by business capability** (appointments, payments, workshops), never into global layers (`controllers/`, `services/`, `models/` at the root).
- Each module has an **entry** (HTTP, events), an **application** (use cases; this is where the ports live if the module is hexagonal), a **domain** (entities, rules, and invariants, with no web framework or ORM), an **infrastructure** (persistence and external adapters), and **a single public contract**.
- Dependency direction: entry → application → domain; infrastructure → application and domain (it implements the ports); the domain imports nothing from the other layers nor web framework, ORM, or external client libraries.
- Between modules, only the other module's public contract is used, never its layers.
- Each module owns its tables: another module does not read or write them directly.
- `shared/` is a minimal core (configuration, database session, base errors) and does not import any module.

You do not start with microservices: a modular monolith gives the same boundaries with a single deployment, and a module with a public contract and its own tables can be extracted later if needed.

## The names in each language

| Stack | Modules in | Entry | Application | Domain | Infrastructure | Public contract |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `python-fastapi` | `app/modules/<m>/` | `api/` | `application/` | `domain/` | `infrastructure/` | `public.py` |
| `python-django` | `apps/<m>/` (one app per module) | `api/` (views and serializers) | `services/` | `domain/` | `models.py` | `public.py` |
| `node-nestjs` | `src/modules/<m>/` | `controllers/` | `application/` | `domain/` | `infrastructure/` | `<m>.module.ts` (its `exports`) or `index.ts` |
| `node-fastify` | `src/modules/<m>/` | `routes/` | `application/` | `domain/` | `infrastructure/` | `index.ts` |
| `go` | `internal/<m>/` | `http/` | `app/` | `domain/` | `store/` or `adapters/` | the module's root package (exported identifiers) |
| `rust-axum` | `src/modules/<m>/` | `routes.rs` | `application.rs` | `domain.rs` | `infra.rs` | `mod.rs` (`pub use`); everything else `pub(crate)` |
| `ruby-rails` | `packs/<m>/` (packwerk) | `app/controllers` | `app/use_cases` | `app/domain` (POROs) | `app/models` (Active Record) | `app/public/` |
| `dotnet-aspnetcore` | `src/Modules/<M>/` | `<M>.Api` | `<M>.Application` | `<M>.Domain` | `<M>.Infrastructure` | the `<M>.Contracts` project |
| `java-spring-boot`, `kotlin-spring-boot` | `src/main/{java,kotlin}/com/example/app/<m>/` | `web/` | `application/` | `domain/` | `infrastructure/` | the types in the module's root package (Spring Modulith) |
| `php-laravel` | `app/Modules/<M>/` | `Http/` | `Application/` | `Domain/` | `Infrastructure/` | `Contracts/` and one ServiceProvider per module |
| `nextjs`, `nuxt`, `sveltekit` (server) | `src/modules/<m>/` (`server/modules/` in Nuxt, `src/lib/server/modules/` in SvelteKit) | `api/` | `application/` | `domain/` | `infrastructure/` | `index.ts` |

`architecture.md` is generated with the names of the chosen language, the tree for that stack, and a final table that maps each name to its canonical responsibility.

### The frontend

The eight frontend stacks (`react-vite`, `nextjs`, `angular`, `vue-vite`, `nuxt`, `svelte-vite`, `sveltekit`, `astro`) are organized by **feature**: `src/features/<f>/` (`src/app/features/` in Angular, `app/features/` in Nuxt, `src/lib/features/` in SvelteKit) with

| Folder | Responsibility |
| :--- | :--- |
| `ui/` | components |
| `state/` | feature state |
| `data-access/` | API calls |
| `model/` | types and presentation rules |
| `index.ts` | public contract |

`ui` may import `state` and `model`; `state` may import `data-access` and `model`; `data-access` may import `model`; `model` imports nothing from the other layers nor a UI framework (`react`, `vue`, `svelte`, `@angular/core`...). A feature only imports another feature's `index.ts`.

### Backend and frontend in the same project

When the backend and frontend are different stacks, they live in `backend/` and `frontend/`, and `architecture.json` carries two rules. When a single framework covers both (`nextjs`, `nuxt`, `sveltekit`), both rules are at the root, in `src/modules` and `src/features`. A project with only one of the two uses the root.

## When a module is hexagonal

Use ports in the application layer and adapters in the infrastructure layer when the module integrates an external system (payments, messaging, AI, email), when its domain has complex rules that must be tested without infrastructure, or when a provider change is anticipated. A simple CRUD does not need it.

## How it reaches the project

`rapid setup finish` (and `rapid init`) writes two files in `.rapid-os/standards/`:

| File | For whom | What it contains |
| :--- | :--- | :--- |
| `architecture.md` | The agent | The rule with the tree and the names for each stack. It enters the context and the agent files as a standard, without an assumption banner. |
| `architecture.json` | Rapid OS | The rule in machine form (see below). |

If they already exist, they are not overwritten when onboarding finishes again (your edits are respected). If you switch to a stack without the rule, Rapid OS does not delete these files: delete them yourself if they no longer apply.

`architecture.json` stores `language`, `component`, `modules_root`, `shared_root`, `public_entry`, which layers each layer may import (`layers`), and the libraries forbidden in the pure layer (`domain_forbidden_imports`), and, since the per-component catalog, also `roles` (which folder or package is each canonical layer; `{m}` names the module), `module_pattern`, `public_contract`, `public_policy` (`entry`: only the public entry point; `root`: everything that is not a layer), `public_dirs`, `namespace_root` (Java, Kotlin, C#, and PHP), `aliases` (TypeScript), `pure_layer`, `delegate`, `root`, and `rules` when there are several. Earlier files are still read the same way. In Java and Kotlin, replace `com.example.app` with your real package; in C# and PHP, replace `namespace_root` with your root namespace.

The onboarding's `docs/ARCHITECTURE.md` document requires the **Modules**, **Dependency rules**, and **Infrastructure services** sections, and starts from this standard.

## How it is verified

`rapid arch check` reads the imports of the files under `modules_root` and `shared_root` and reports each violation with file, line, import, and rule (`RAPID1420`). It runs nothing and adds no dependencies:

| Language | What it reads |
| :--- | :--- |
| Python | `ast` |
| TypeScript and JavaScript | `import`, `export ... from`, `import()`, and `require`; the `<script>` block of `.vue` and `.svelte` and the frontmatter and `<script>` of `.astro` |
| Go | `import` (`_test.go` files are ignored) |
| Java and Kotlin | `import` |
| C# | `using` and the `.csproj` references (`ProjectReference` and `PackageReference`) |
| Rust | `use` (with `crate::`, `super::`, and `self::`) |
| PHP | `use` |
| Ruby | there are no imports to read: it delegates to `bin/packwerk check` |

The violations are:

- a layer that imports a layer it is not allowed to;
- a module that imports from another anything other than its public contract;
- `shared` importing a module;
- the `__init__.py` of a Python module importing anything other than its own `public.py`;
- the pure layer (`domain`, or `model` in the frontend) importing a forbidden library.

Only the directories under `modules_root` count as modules. It exits with 1 if there are violations, and with 0 if there are none, if there are no modules yet, or (with a warning) if the project has no `architecture.json`.

### Ruby on Rails

Rails loads code by convention: there are no imports to read. `rapid arch check` runs `bin/packwerk check` and says so. If packwerk is not available, it warns (`RAPID1420 packwerk no está disponible...`) and exits with 1: the gate is not considered satisfied. Install it with `bundle add packwerk --group development && bundle binstub packwerk`.

### Idiomatic tools as a complementary test

Where the ecosystem's tool exists, `architecture.md` names it as a complementary test that the scaffold can add: Spring Modulith (`ApplicationModules.of(Application.class).verify()`), packwerk, Deptrac (PHP), and NetArchTest (.NET). The gate remains `rapid arch check`.

### In a run with a worktree

A run's worktree has no `.rapid-os/`: the ledger and the rule live in the main project. If there is no `architecture.json` in the current directory and there is an active session whose contract includes `gate.architecture`, `rapid arch check` reads the rule from the main project (the session's root) and analyzes the code of the current directory, that is, of the worktree. If the run requires the gate and the rule is found in neither place, it exits with `RAPID1420 el run exige gate.architecture y no hay architecture.json` (exit 1): without a rule, the gate cannot appear satisfied. Outside a run, a missing `architecture.json` is still exit 0 with a warning.

### The `gate.architecture` gate

In `feature`, `bugfix`, and `refactor` runs, if `architecture.json` exists, the contract includes the machine gate `gate.architecture`. `rapid next` proposes it as one more verification, just like `gate.tests`:

```bash
rapid check --gate gate.architecture -- rapid arch check
```

`rapid finish` does not give `PASS` while that gate is not satisfied. The gate cannot be waived (it is not waivable). Never disable or edit `architecture.json` to make a check pass: change the code or ask the person to change the rule.

## Existing projects

The rule applies to **new code**. In a repository with global layers, `rapid arch check` reports violations only inside `modules_root`; it does not require migrating. The migration to modules is done with `/rapid-refactor`, and in a new project the scaffold task asks for an example module with its layers and its public contract.

## Limits

- Imports are resolved from the project root; a custom alias outside those in `architecture.json` (`aliases`) is not recognized.
- Go resolves an import by looking for the modules folder (`internal`) within the path, so it does not need to read `go.mod`.
- Instruction rules that are not about imports (for example, that each module owns its tables) are upheld by the agent; the checker judges only `modules_root` and `shared_root`.
