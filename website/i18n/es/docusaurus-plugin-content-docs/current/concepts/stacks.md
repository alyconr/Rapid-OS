# Stacks y componentes

Cada componente de la topología elige su tecnología en un catálogo amplio. El agente recomienda con criterio (el brief, las reglas de negocio, el equipo, la carga y los costos) y la persona decide. Rapid OS no elige: registra la decisión, escribe el `tech-stack.md` correspondiente y la arquitectura modular en el idioma del stack.

## Componentes por topología

La topología dice qué piezas tiene el proyecto, y cada pieza necesita su stack:

| Topología | Componentes | Qué se pregunta |
|---|---|---|
| `front-end-only` | `frontend` | un stack de frontend |
| `fullstack-separated` | `frontend`, `backend` | uno de cada |
| `fullstack-baas` | `frontend`, `baas` | un stack de frontend y un proveedor BaaS (`supabase` o `firebase`), elegidos como cualquier otro stack |
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
| `hono` | TypeScript | backend | edge, serverless | pnpm | `pnpm test` |
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

`performance`, `memory_footprint`, `cold_start`, `concurrency_model`, `typing`, `productivity`, `learning_curve`, `maintainability`, `ecosystem_maturity`, `hiring_pool` y `hosting_fit` (`serverless`, `containers`, `PaaS` o `edge`).

Los factores de popularidad (`hiring_pool`) citan los porcentajes de desarrolladores profesionales de la encuesta de Stack Overflow 2025; los demás, la documentación oficial del lenguaje o del framework. La ficha también trae `fits`, `avoid_if`, `default_test_command`, `package_manager` y `supported_services` (los motores de [servicios de infraestructura](./infrastructure-services.md) con su driver).

## Proveedores BaaS

El componente `baas` de `fullstack-baas` lo llena `supabase` o `firebase` (`templates/stacks/baas/`). Además de los factores de arriba, cada ficha describe `data_model` (Postgres relacional frente a documentos de Firestore), `auth`, `realtime`, `server_functions` (Edge Functions o Cloud Functions), `local_development` y `exit_strategy` (autoalojamiento de Supabase frente al lock-in de Firebase), cada uno con sus `sources` oficiales.

| Proveedor | Datos | Funciones en servidor | Desarrollo local | Pruebas |
|---|---|---|---|---|
| `supabase` | Postgres, esquema en `supabase/migrations/`, políticas RLS | Edge Functions (`supabase/functions/<módulo>/`) | `supabase init`, `supabase start` (necesita Docker u otro runtime de contenedores) | las del frontend; `supabase test db` (políticas) en CI y como acción de la persona |
| `firebase` | colecciones y documentos de Firestore, reglas en `firestore.rules` y `storage.rules` | Cloud Functions (`functions/src/<módulo>/`) | Emulator Suite: `firebase emulators:start` | las del frontend; `firebase emulators:exec "<gestor> run test:rules"` en CI y como acción de la persona |

Los comandos locales los ejecuta la persona, como `docker compose up -d`: `rapid setup finish` los lista en `person_actions`. Rapid OS escribe `.env.example` con las variables locales del proveedor (con el prefijo que exige el framework del frontend, como `NEXT_PUBLIC_` o `VITE_`) y sin secretos reales.

**La guía de topología depende del frontend y del proveedor.** Con un frontend con renderizado en servidor (`nextjs`, `nuxt`, `sveltekit`) las mutaciones salen del servidor; con uno solo de navegador (`react-vite`, `vue-vite`, `svelte-vite`, `angular`, `astro`) el SDK corre en el cliente, las reglas de acceso del proveedor son la única barrera y lo privilegiado va en funciones de servidor del proveedor.

**Comando de test.** `rapid setup set test-command --recommended` propone solo el del frontend (`pnpm exec vitest run`): `gate.tests` debe pasar sin Docker ni Java. Las pruebas de reglas del proveedor (`supabase test db`; `firebase emulators:exec "<gestor> run test:rules"`, con el gestor de paquetes del frontend) vienen en `rules_test` de `set_test_command`, corren en el workflow de CI y son una acción de la persona tras `supabase start` o `firebase emulators:start`.

**La regla de arquitectura cubre el SDK y las funciones.** El SDK del proveedor solo se importa desde `data-access` de cada funcionalidad y desde un cliente único en `shared`; las funciones siguen la regla de módulos (`supabase/functions/<m>` o `functions/src/<m>`). `rapid arch check` lo verifica. `security.md` añade una sección por proveedor (RLS probada y claves; reglas con denegación por defecto probadas en el emulador, App Check y credenciales solo en el servidor) y el CI corre esas pruebas. El comando de test recomendado combina `supabase test db` con el del frontend, o envuelve el del frontend en `firebase emulators:exec`.

**Quién decidió.** Cada decisión de stack en `setup.json` registra `decided_by` (`person` o `agent`). Si la persona delega («decide tú»), el agente elige, lo dice con sus razones y lo registra con `--decided-by agent`; `tech-stack.md` indica que la eligió el agente y que no es una decisión confirmada.

## Cómo recomienda el agente

`choose_stack` entrega al agente las opciones con sus factores, las preguntas de `templates/setup/stack-questions.json` (lenguajes que domina el equipo, carga y latencia esperadas, presupuesto de infraestructura, tiempo real, cómputo intensivo o IA/ML, horizonte de mantenimiento y restricciones de la organización) y esta instrucción:

> Haz las preguntas que el brief no responda. Recomienda una opción y una alternativa, y explica la diferencia con los factors del catálogo aplicados a este producto (p. ej. consumo de memoria y concurrencia frente a velocidad de desarrollo). No afirmes nada que el catálogo no diga. La persona decide.

`recommended` es lo que el escáner detectó en un repositorio existente (por ejemplo `go.mod`, `Cargo.toml` con `axum`, `Gemfile` con `rails`, `*.csproj`, `pom.xml` o `build.gradle(.kts)` con `spring-boot`, `composer.json` con `laravel/framework`, `angular.json`, o `vue`, `nuxt`, `svelte`, `@sveltejs/kit` y `astro` en `package.json`). Con más de un backend (o frontend) en el mismo repositorio no sugiere nada para ese componente.

## Acceso a datos

Cada stack de backend declara cómo llega a su base de datos en `data_access`: sus `options`, cada una un ORM, un query builder, un driver o un ODM (`kind`), con los `models` y `engines` en los que encaja, los `runtimes` donde corre, sus `migrations` (herramienta y comandos `generate` y `apply`) o su `schema_validation`, sus `notes` y sus `sources` oficiales. `default` nombra la opción recomendada de cada modelo de datos. Los stacks de frontend y BaaS no lo declaran.

| Stack | Relacional por defecto | Otras relacionales | Documentos por defecto | Otras de documentos |
|---|---|---|---|---|
| `node-fastify` | `drizzle` | `prisma`, `kysely` | `mongodb-driver` | `mongoose` |
| `node-nestjs` | `typeorm` | `drizzle`, `prisma`, `kysely` | `mongoose` | `mongodb-driver` |
| `hono` | `drizzle` | `prisma`, `kysely` | ninguna (el catálogo no tiene MongoDB desde Workers) | ninguna |
| `python-fastapi` | `sqlalchemy-async` | `sqlalchemy-sync`, `sqlmodel` | `pymongo-async` | `beanie` |
| `python-django` | `django-orm` | ninguna | `django-mongodb-backend` | ninguna |
| `go` | `pgx-sqlc` (PostgreSQL) | `gorm`, `ent` | `mongo-go-driver` | ninguna |
| `rust-axum` | `sqlx` | `sea-orm`, `diesel` | `mongodb-crate` | ninguna |
| `java-spring-boot` | `spring-data-jpa` | `spring-data-jdbc`, `jooq` | `spring-data-mongodb` | ninguna |
| `kotlin-spring-boot` | `spring-data-jpa` | `spring-data-jdbc`, `jooq`, `exposed` | `spring-data-mongodb` | ninguna |
| `dotnet-aspnetcore` | `ef-core` | `dapper` | `mongodb-csharp-driver` | `mongodb-ef-core` |
| `php-laravel` | `eloquent` | ninguna | `laravel-mongodb` | ninguna |
| `ruby-rails` | `active-record` | ninguna | `mongoid` | ninguna |

Cuando el default no encaja con el motor, se recomienda la primera opción que sí: `go` con MySQL recomienda `gorm`, y `node-fastify` con MariaDB solo tiene `prisma`.

**Prisma** figura como Prisma ORM 7 con `prisma migrate`: el tag `latest` de npm apunta a la versión candidata 8.0.0, que sustituye esos comandos y aún no da soporte estable a MySQL ni a MariaDB. **`sqlalchemy-sync`** existe para Python Workers, donde Cloudflare solo admite ORMs síncronos de SQLAlchemy; conecta con psycopg o pymysql en lugar de los drivers async. **`jooq`** solo lista PostgreSQL, porque el sitio de jOOQ no se pudo consultar para sus otros motores.

El paso del onboarding es [`choose_data_access`](./infrastructure-services.md#acceso-a-datos). El `tech-stack.md` compilado nombra la opción elegida, y la acción de `data-model` trae sus comandos de migración o su validación de esquema.

## Hono

`hono` es Hono sobre Cloudflare Workers, con tests en Vitest y `@cloudflare/vitest-plugin`. Sus `supported_services` son PostgreSQL y MySQL, por Hyperdrive. `rapid setup set services` rechaza lo que necesita un proceso persistente con `RAPID1402` y nombra la alternativa de la plataforma: RabbitMQ y Kafka reciben Cloudflare Queues, con su semántica distinta. D1 es la base alternativa de `hono.md` y de la plantilla de Cloudflare; todavía no es un servicio del catálogo. El mismo código corre en Node.js, Bun y Deno. Encaja en las topologías `backend-only` y `fullstack-separated`, con la misma estructura de módulos que `node-fastify`.

## Los servicios siguen al stack del backend

`rapid setup set services` se valida contra el stack del componente `backend` (o el que lo cubre): un motor que el stack no declara en `supported_services` es `RAPID1402` con la lista de los que sí. El driver y la URL de conexión de `.env.example` y las líneas de base de datos del `tech-stack.md` salen de esa misma declaración.

## Ids anteriores

Los ids de antes del catálogo por componentes se siguen aceptando en `setup.json`, en `rapid setup set stack` y en el contenido de un `tech-stack.md` existente. Ver la [guía de migración de `setup.json`](../guides/setup-json-migration.md).
