---
title: Stacks and Components
description: Choose a technology stack for each project topology component from the Rapid OS catalog.
---

# Stacks and Components

Each topology component selects its technology from a broad catalog. The agent makes a recommendation based on the brief, business rules, team, workload, and costs; a person decides. Rapid OS records the decision, writes the matching `tech-stack.md`, and provides modular architecture guidance in the stack's language.

## Components by topology

| Topology | Components | What is selected |
|---|---|---|
| `front-end-only` | `frontend` | One frontend stack |
| `fullstack-separated` | `frontend`, `backend` | One stack for each |
| `fullstack-baas` | `frontend`, `baas` | Frontend stack only; the catalog has no stack for a backend-as-a-service |
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

`generic` (repository conventions detected by the scanner) and `custom` (a `tech-stack.md` supplied with `rapid setup stack --custom --file -`) cover all components. `docs-modern` covers `docs`.

## Stack factors

Each profile includes qualitative (not invented numerical) `factors` and official `sources`: `performance`, `memory_footprint`, `cold_start`, `concurrency_model`, `typing`, `productivity`, `learning_curve`, `maintainability`, `ecosystem_maturity`, `hiring_pool`, and `hosting_fit` (`serverless`, `containers`, or `PaaS`). Popularity factors cite professional developer percentages from the 2025 Stack Overflow survey; other factors cite official language or framework documentation. Profiles also include `fits`, `avoid_if`, `default_test_command`, `package_manager`, and `supported_services` (infrastructure service engines and their drivers).

## How the agent recommends a stack

`choose_stack` provides options and factors, questions from `templates/setup/stack-questions.json` (team expertise, expected load and latency, infrastructure budget, real-time needs, compute-intensive or AI/ML workloads, maintenance horizon, and organizational constraints), and this instruction:

> Ask questions the brief does not answer. Recommend one option and an alternative, explain the difference using catalog factors applied to this product (for example, memory use and concurrency versus development speed), and do not claim anything the catalog does not say. The person decides.

`recommended` is what the scanner detected in an existing repository (for example, `go.mod`, `Cargo.toml` with `axum`, `Gemfile` with `rails`, `*.csproj`, `pom.xml` or `build.gradle(.kts)` with `spring-boot`, `composer.json` with `laravel/framework`, `angular.json`, or frontend packages in `package.json`). If a repository has more than one backend or frontend, it makes no recommendation for that component.

## Services follow the backend stack

`rapid setup set services` is checked against the backend component's stack (or a stack that covers it). An engine not listed in `supported_services` returns `RAPID1402` with supported engines. The driver, `.env.example` connection URL, and database lines in `tech-stack.md` come from the same declaration.

## Previous IDs

IDs from before the per-component catalog remain accepted in `setup.json`, `rapid setup set stack`, and existing `tech-stack.md` content. See the [`setup.json` migration guide](../guides/setup-json-migration.md).
