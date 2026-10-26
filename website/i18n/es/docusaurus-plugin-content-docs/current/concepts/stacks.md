# Stacks y componentes

Cada componente de la topología elige su tecnología en un catálogo amplio. El agente recomienda con criterio (el brief, las reglas de negocio, el equipo, la carga y los costos) y la persona decide. Rapid OS no elige: registra la decisión, escribe el `tech-stack.md` correspondiente y la arquitectura modular en el idioma del stack.

## Componentes por topología

La topología dice qué piezas tiene el proyecto, y cada pieza necesita su stack:

| Topología | Componentes | Qué se pregunta |
|---|---|---|
| `front-end-only` | `frontend` | un stack de frontend |
| `fullstack-separated` | `frontend`, `backend` | uno de cada |
| `fullstack-baas` | `frontend`, `baas` | solo el frontend: el backend como servicio no tiene stack en el catálogo |
| `doc-site` | `docs` | `docs-modern` |

`rapid setup next` emite `choose_stack` una vez por componente, en el orden de la topología (`frontend` antes que `backend`). Si la persona todavía no decidió la topología, la primera decisión puede ser el stack de cualquier componente: la topología se pregunta después, con solo las opciones compatibles, y el resto de componentes se pregunta al final.

```bash
rapid setup set topology fullstack-separated
rapid setup set stack vue-vite --component frontend
rapid setup set stack go --component backend
```

Un framework que cubre varios componentes (`nextjs`, `nuxt`, `sveltekit`, y en modo monolítico `ruby-rails`, `python-django` y `php-laravel`) llena todos los que la topología pide con una sola elección; `--component` lo limita a uno. Un componente que el stack no puede llenar es `RAPID1413`, y un stack que no encaja con la topología es `RAPID1402`.

## El catálogo

Cada stack son dos archivos en `templates/stacks/<componente>/`: `<id>.json` (la ficha que `rapid setup next` muestra al agente) y `<id>.md` (el `tech-stack.md`: runtime y versión soportada actual, framework, validación, acceso a datos, pruebas y linters). Una ficha inválida es `RAPID1401`.

### Backend

| Stack | Lenguaje | Cubre | Hosting | Gestor | Pruebas |
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

| Stack | Lenguaje | Cubre | Hosting | Gestor | Pruebas |
|---|---|---|---|---|---|
| `react-vite` | TypeScript | frontend | serverless, PaaS | pnpm | `pnpm exec vitest run` |
| `nextjs` | TypeScript | frontend, backend | containers, PaaS, serverless | pnpm | `pnpm exec vitest run` |
| `angular` | TypeScript | frontend | serverless, PaaS | pnpm | `ng test --no-watch --no-progress` |
| `vue-vite` | TypeScript | frontend | serverless, PaaS | pnpm | `pnpm exec vitest run` |
| `nuxt` | TypeScript | frontend, backend | containers, PaaS, serverless | pnpm | `pnpm exec vitest run` |
| `svelte-vite` | TypeScript | frontend | serverless, PaaS | pnpm | `pnpm exec vitest run` |
| `sveltekit` | TypeScript | frontend, backend | containers, PaaS, serverless | pnpm | `pnpm exec vitest run` |
| `astro` | TypeScript | frontend | serverless, PaaS, containers | pnpm | `pnpm exec vitest run` |

`generic` (la convención del repositorio, construida con lo que detecta el escáner) y `custom` (el `tech-stack.md` que escribe el agente con `rapid setup stack --custom --file -`) cubren todos los componentes. `docs-modern` cubre `docs`.

### Los factores

Cada ficha trae `factors`, cualitativos (nunca puntajes inventados), y `sources` con las URL oficiales de cada uno:

`performance`, `memory_footprint`, `cold_start`, `concurrency_model`, `typing`, `productivity`, `learning_curve`, `maintainability`, `ecosystem_maturity`, `hiring_pool` y `hosting_fit` (`serverless`, `containers` o `PaaS`).

Los factores de popularidad (`hiring_pool`) citan los porcentajes de desarrolladores profesionales de la encuesta de Stack Overflow 2025; los demás, la documentación oficial del lenguaje o del framework. La ficha también trae `fits`, `avoid_if`, `default_test_command`, `package_manager` y `supported_services` (los motores de [servicios de infraestructura](./infrastructure-services.md) con su driver).

## Cómo recomienda el agente

`choose_stack` entrega al agente las opciones con sus factores, las preguntas de `templates/setup/stack-questions.json` (lenguajes que domina el equipo, carga y latencia esperadas, presupuesto de infraestructura, tiempo real, cómputo intensivo o IA/ML, horizonte de mantenimiento y restricciones de la organización) y esta instrucción:

> Haz las preguntas que el brief no responda. Recomienda una opción y una alternativa, y explica la diferencia con los factors del catálogo aplicados a este producto (p. ej. consumo de memoria y concurrencia frente a velocidad de desarrollo). No afirmes nada que el catálogo no diga. La persona decide.

`recommended` es lo que el escáner detectó en un repositorio existente (por ejemplo `go.mod`, `Cargo.toml` con `axum`, `Gemfile` con `rails`, `*.csproj`, `pom.xml` o `build.gradle(.kts)` con `spring-boot`, `composer.json` con `laravel/framework`, `angular.json`, o `vue`, `nuxt`, `svelte`, `@sveltejs/kit` y `astro` en `package.json`). Con más de un backend (o frontend) en el mismo repositorio no sugiere nada para ese componente.

## Los servicios siguen al stack del backend

`rapid setup set services` se valida contra el stack del componente `backend` (o el que lo cubre): un motor que el stack no declara en `supported_services` es `RAPID1402` con la lista de los que sí. El driver y la URL de conexión de `.env.example` y las líneas de base de datos del `tech-stack.md` salen de esa misma declaración.

## Ids anteriores

Los ids de antes del catálogo por componentes se siguen aceptando en `setup.json`, en `rapid setup set stack` y en el contenido de un `tech-stack.md` existente. Ver la [guía de migración de `setup.json`](../guides/setup-json-migration.md).
