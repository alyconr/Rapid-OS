---
title: Stacks and Components
description: Choose a technology stack for each project topology component from the Rapid OS catalog.
---

# Stacks and Components

Each topology component selects its technology from a broad catalog. The agent makes a recommendation based on the brief, business rules, team, workload, and costs; a person decides. Rapid OS records the decision, writes the matching `tech-stack.md`, and provides modular architecture guidance in the stack's language.

## Components by topology

| Topology | Components | What is selected |
|---|---|---|
| `backend-only` | `backend` | One backend stack; no frontend and no `backend/` folder (an API or a service consumed by other systems) |
| `front-end-only` | `frontend` | One frontend stack |
| `fullstack-separated` | `frontend`, `backend` | One stack for each |
| `fullstack-baas` | `frontend`, `baas` | One frontend stack and one BaaS provider (`supabase` or `firebase`), chosen like any other stack |
| `doc-site` | `docs` | `docs-modern` |

`rapid setup next` asks for `choose_stack` once per component, in topology order (`frontend` before `backend`). If topology has not yet been chosen, the first stack decision can be for any component; topology is then selected from compatible options, and remaining components are chosen afterward.

```bash
rapid setup set topology fullstack-separated
rapid setup set stack vue-vite --component frontend
rapid setup set stack go --component backend
```

A framework covering multiple components (`nextjs`, `nuxt`, `sveltekit`, and, in monolithic mode, `ruby-rails`, `python-django`, and `php-laravel`) fills all topology components in one selection; `--component` limits it to one. A component the stack cannot fill returns `RAPID1413`; a stack incompatible with the topology returns `RAPID1402`.

## The catalog

Each stack has two files under `templates/stacks/<component>/`: `<id>.json` (the profile shown to the agent by `rapid setup next`) and `<id>.md` (the `tech-stack.md` with runtime and supported version, framework, validation, data access, tests, and linters). An invalid profile returns `RAPID1401`.

### Backend

| Stack | Language | Covers | Hosting | Package manager | Tests |
|---|---|---|---|---|---|
| `python-fastapi` | Python | backend | containers, PaaS | uv | `pytest` |
| `python-django` | Python | backend, frontend | containers, PaaS | pip | `python manage.py test` |
| `node-nestjs` | TypeScript | backend | containers, PaaS, serverless | pnpm | `pnpm test` |
| `node-fastify` | TypeScript | backend | containers, PaaS, serverless | pnpm | `pnpm test` |
| `go` | Go | backend | containers, PaaS | go modules | `go test ./...` |
| `rust-axum` | Rust | backend | containers, PaaS | cargo | `cargo test` |
| `ruby-rails` | Ruby | backend, frontend | containers, PaaS | bundler | `bin/rails test` |
| `dotnet-aspnetcore` | C# | backend | containers, PaaS | nuget | `dotnet test` |
| `java-spring-boot` | Java | backend | containers, PaaS | maven | `./mvnw test` |
| `kotlin-spring-boot` | Kotlin | backend | containers, PaaS | gradle | `./gradlew test` |
| `php-laravel` | PHP | backend, frontend | containers, PaaS, serverless | composer | `php artisan test` |

### Frontend

| Stack | Language | Covers | Hosting | Package manager | Tests |
|---|---|---|---|---|---|
| `react-vite` | TypeScript | frontend | serverless, PaaS | pnpm | `pnpm exec vitest run` |
| `nextjs` | TypeScript | frontend, backend | containers, PaaS, serverless | pnpm | `pnpm exec vitest run` |
| `angular` | TypeScript | frontend | serverless, PaaS | pnpm | `ng test --no-watch --no-progress` |
| `vue-vite` | TypeScript | frontend | serverless, PaaS | pnpm | `pnpm exec vitest run` |
| `nuxt` | TypeScript | frontend, backend | containers, PaaS, serverless | pnpm | `pnpm exec vitest run` |
| `svelte-vite` | TypeScript | frontend | serverless, PaaS | pnpm | `pnpm exec vitest run` |
| `sveltekit` | TypeScript | frontend, backend | containers, PaaS, serverless | pnpm | `pnpm exec vitest run` |
| `astro` | TypeScript | frontend | serverless, PaaS, containers | pnpm | `pnpm exec vitest run` |

### BaaS providers

The `baas` component of `fullstack-baas` is filled by `supabase` or `firebase` (`templates/stacks/baas/`). A provider cannot fill another component, and it only fits `fullstack-baas`. Besides the factors above, each profile describes `data_model` (Postgres relational against Firestore documents), `auth`, `realtime`, `server_functions` (Edge Functions or Cloud Functions), `local_development` and `exit_strategy` (self-hosting Supabase against Firebase lock-in), each with its official `sources`.

| Provider | Data | Server functions | Local development | Tests |
|---|---|---|---|---|
| `supabase` | Postgres, schema in `supabase/migrations/`, RLS policies | Edge Functions (`supabase/functions/<module>/`) | `supabase init`, `supabase start` (needs Docker or another container runtime) | the frontend's; `supabase test db` (policies) in CI and as a person action |
| `firebase` | Firestore collections and documents, rules in `firestore.rules` and `storage.rules` | Cloud Functions (`functions/src/<module>/`) | Emulator Suite: `firebase emulators:start` | the frontend's; `firebase emulators:exec "<pm> run test:rules"` in CI and as a person action |

The person runs the local commands, as with `docker compose up -d`: `rapid setup finish` lists them in `person_actions` (`supabase init` only while `supabase/config.toml` does not exist, then `supabase start`; or `firebase init` and `firebase emulators:start`). Rapid OS writes `.env.example` with the local variables of the provider (prefixed as the frontend framework requires, such as `NEXT_PUBLIC_` or `VITE_`) and no real secret: the secret key and the service-account credentials have no value and no client prefix.

**The topology guide depends on the frontend and the provider.** `standards/topology.md` of `fullstack-baas` is written for what was decided. A frontend rendered on a server (`nextjs`, `nuxt`, `sveltekit`) mutates from the server with the provider client built for it. A browser-only frontend (`react-vite`, `vue-vite`, `svelte-vite`, `angular`, `astro`) uses the SDK in the client, so the provider's access rules are the only barrier and privileged work goes in the provider's server functions. It is rewritten when the stacks change.

**The architecture rule covers the SDK and the functions.** `architecture.json` gets a rule for the frontend and one for the `baas` component, both at the project root. The provider SDK (`@supabase/supabase-js` and `@supabase/ssr`, or `firebase` and `firebase-admin`) is imported only from the `data-access` layer of a feature and from the single provider client in `shared` (`supabase-client`, `firebase-client`; a server-rendered frontend also keeps `supabase-server` or `firebase-server`); `rapid arch check` reports anything else as `restricted_import`, also in files outside the modules, except test files. The functions follow the module rule: `supabase/functions/<m>` with `supabase/functions/_shared`, or `functions/src/<m>` with `functions/src/shared`; the `npm:` and `jsr:` specifiers of Deno are read without the scheme. A project on a BaaS has no backend rule of its own.

**Security.** `security.md` adds a section per provider mapped to OWASP and ASVS: Supabase with RLS on every table of an exposed schema and policies tested by `supabase test db`, and the secret key (`sb_secret_...`, `service_role`) never in the client; Firebase with deny-by-default rules tested in the emulator, App Check, and service-account credentials only on the server. The CI workflow adds a job that runs those tests (`supabase test db`, or `firebase emulators:exec "npm run test:rules"`).

**Documents.** `docs/DATA_MODEL.md` follows the data model decided, not only the BaaS (see [Infrastructure services](infrastructure-services.md#project-documents)): Supabase is relational (`Tablas`, `Migraciones`) and adds `Políticas RLS`; Firebase is a document store (`Colecciones y documentos`, `Índices`, `Validación del esquema`) and adds `Reglas de seguridad`. `ARCHITECTURE.md` and `DEPLOYMENT.md` need `Proveedor BaaS`. The deployment platforms include `netlify` and `firebase-hosting`, and `vercel` has a section for Supabase. The scanner suggests the provider and `fullstack-baas` for a frontend with `supabase/` or `@supabase/supabase-js`, or `firebase.json`, `.firebaserc` or the `firebase` dependency; with both providers in one repository it suggests none.

**Test command.** `rapid setup set test-command --recommended` proposes only the frontend's command (`pnpm exec vitest run`): `gate.tests` must pass without Docker or Java. The provider's rules tests (`supabase test db`; `firebase emulators:exec "<pm> run test:rules"`, with the package manager of the frontend) come in `rules_test` of `set_test_command`, run in the CI workflow, and are a person action after `supabase start` or `firebase emulators:start`.

`generic` (repository conventions detected by the scanner) and `custom` (a `tech-stack.md` supplied with `rapid setup stack --custom --file -`) cover all components. `docs-modern` covers `docs`.

## Stack factors

Each profile includes qualitative (not invented numerical) `factors` and official `sources`: `performance`, `memory_footprint`, `cold_start`, `concurrency_model`, `typing`, `productivity`, `learning_curve`, `maintainability`, `ecosystem_maturity`, `hiring_pool`, and `hosting_fit` (`serverless`, `containers`, or `PaaS`). Popularity factors cite professional developer percentages from the 2025 Stack Overflow survey; other factors cite official language or framework documentation. A `baas` profile adds `data_model`, `auth`, `realtime`, `server_functions`, `local_development` and `exit_strategy`. Profiles also include `fits`, `avoid_if`, `default_test_command`, `package_manager`, and `supported_services` (infrastructure service engines and their drivers).

## How the agent recommends a stack

`choose_stack` provides options and factors, questions from `templates/setup/stack-questions.json` (team expertise, expected load and latency, infrastructure budget, real-time needs, compute-intensive or AI/ML workloads, maintenance horizon, and organizational constraints), and this instruction:

> Ask questions the brief does not answer. Recommend one option and an alternative, explain the difference using catalog factors applied to this product (for example, memory use and concurrency versus development speed), and do not claim anything the catalog does not say. The person decides.

`recommended` is what the scanner detected in an existing repository (for example, `go.mod`, `Cargo.toml` with `axum`, `Gemfile` with `rails`, `*.csproj`, `pom.xml` or `build.gradle(.kts)` with `spring-boot`, `composer.json` with `laravel/framework`, `angular.json`, or frontend packages in `package.json`). If a repository has more than one backend or frontend, it makes no recommendation for that component.

## Who decided

Every stack decision in `setup.json` records `decided_by`: `person` (the default, also for files from before the field) or `agent`. When the person delegates ("decide for me"), the agent chooses, says which one and why, and records it with `rapid setup set stack <id> --component <component> --decided-by agent`; `rapid setup next` gives that command in `delegation` for the `baas` component. `tech-stack.md` then says the agent chose it and that it is not a confirmed decision (and keeps `decided_by.<component>=agent` in its `rapid-stack` marker), and `rapid setup show` marks it `(agente)`. Choosing the stack again without the flag makes it the person's.

## Services follow the backend stack

`rapid setup set services` is checked against the backend component's stack (or a stack that covers it). An engine not listed in `supported_services` returns `RAPID1402` with supported engines. The driver, `.env.example` connection URL, and database lines in `tech-stack.md` come from the same declaration.

## Previous IDs

IDs from before the per-component catalog remain accepted in `setup.json`, `rapid setup set stack`, and existing `tech-stack.md` content. See the [`setup.json` migration guide](../guides/setup-json-migration.md).
