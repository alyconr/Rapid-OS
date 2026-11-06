# Despliegue en Cloudflare

Plantilla de partida para `docs/DEPLOYMENT.md`. Rapid OS no despliega: lo haces tú.

## Destino
- **Frontend estático o SSR**: Workers con Static Assets, la vía que Cloudflare recomienda para proyectos nuevos. Pages sigue funcionando y es la opción de un proyecto que ya está allí, pero Cloudflare indica empezar los nuevos en Workers.
- **API en Workers**: Hono es el encaje natural (stack `hono`). Un Worker no es un proceso persistente: se ejecuta por petición en un isolate de V8, con un límite de 128 MB de memoria y de CPU por petición (10 ms en Free; hasta 5 min en Paid).
- **FastAPI en Python Workers**: con `asgi.entrypoint` y `pywrangler`, y solo con acceso a datos síncrono: Cloudflare no admite SQLAlchemy async, por falta de greenlet. Con Hyperdrive exige `compatibility_date` 2026-09-08 o posterior.
- **Stacks que necesitan un proceso persistente**: la API va en otra plataforma (aws, azure, render, railway o dokploy) y el frontend en Cloudflare. Cloudflare Containers es la otra salida: ejecuta imágenes de contenedor controladas desde un Worker, en el plan Workers Paid.

## Configuración y secretos
- `wrangler.jsonc` es el formato que Cloudflare recomienda para proyectos nuevos: `vars`, bindings, entornos (`env.<nombre>`), `compatibility_date` y `compatibility_flags`. `vars` y los bindings no se heredan: se declaran en cada entorno.
- Desde la `compatibility_date` 2026-08-04, Node.js compatibility viene activa sin flag; antes hay que añadir `nodejs_compat`, que los drivers de base de datos necesitan.
- Secretos: `wrangler secret put <NOMBRE>`; nunca en `wrangler.jsonc` ni en el código.
- En local: `.dev.vars` o `.env`, uno de los dos, junto a la configuración de Wrangler. `.dev.vars*` y `.env*` van en `.gitignore`: nunca en el repositorio.

## Servicios gestionados
| Rol | Opción |
|---|---|
| database (postgresql, mysql) | Hyperdrive hacia una base externa (Supabase, Neon...), con conexiones en pool. Desde JS/TS: `pg` ≥ 8.16.3 (recomendado) o `postgres` ≥ 3.4.5; `mysql2` ≥ 3.13.0 |
| database (sqlite) | D1, con semántica de SQLite y sus propias migraciones (`wrangler d1 migrations`) |
| queue | Queues. Semántica distinta de RabbitMQ: entrega al menos una vez, en lotes y con reintentos, así que el consumidor debe ser idempotente |
| object-storage | R2 |
| cache, clave-valor | KV. No es Redis: consistencia eventual (un cambio puede tardar 60 s o más en otras ubicaciones) y sin operaciones atómicas |
| tiempo real, WebSockets | Durable Objects, con la API de hibernación de WebSockets |
| mongodb, redis | Sin servicio propio documentado: fuera de Cloudflare |

## Con Supabase
- Crea la configuración de Hyperdrive con la cadena **Direct connection** de Supabase, no con las de pool: Hyperdrive ya gestiona el pool. Desde el Worker conecta con `pg` o Postgres.js, no con el cliente JavaScript de Supabase.
- Realtime se usa desde el cliente, con el SDK de Supabase en el navegador.
- Las migraciones y las Edge Functions no se despliegan con Wrangler: desde CI con la CLI de Supabase (`supabase link --project-ref <id>`, `supabase db push`, `supabase functions deploy`), con `SUPABASE_ACCESS_TOKEN` y `SUPABASE_DB_PASSWORD` como secretos del CI.

## Verificación y reversión
- Despliegue gradual: `wrangler versions upload` sube una versión sin desplegarla y `wrangler versions deploy` reparte el tráfico por porcentajes entre dos versiones. `wrangler deploy` manda la nueva versión al 100 %.
- Reversión: `wrangler rollback` (o el panel) devuelve el 100 % del tráfico a una versión anterior. No cambia los recursos conectados: si la estructura de los datos cambió entre versiones, el código anterior puede fallar.

## Fuentes oficiales
- https://developers.cloudflare.com/workers/best-practices/workers-best-practices/
- https://developers.cloudflare.com/workers/static-assets/
- https://developers.cloudflare.com/pages/
- https://developers.cloudflare.com/workers/reference/how-workers-works/
- https://developers.cloudflare.com/workers/platform/limits/
- https://hono.dev/docs/getting-started/cloudflare-workers
- https://developers.cloudflare.com/workers/languages/python/packages/fastapi/
- https://developers.cloudflare.com/hyperdrive/examples/python-workers/
- https://developers.cloudflare.com/containers/
- https://developers.cloudflare.com/workers/wrangler/configuration/
- https://developers.cloudflare.com/workers/configuration/environment-variables/
- https://developers.cloudflare.com/workers/runtime-apis/nodejs/
- https://developers.cloudflare.com/workers/configuration/secrets/
- https://developers.cloudflare.com/hyperdrive/
- https://developers.cloudflare.com/hyperdrive/reference/supported-databases-and-features/
- https://developers.cloudflare.com/hyperdrive/examples/connect-to-postgres/
- https://developers.cloudflare.com/hyperdrive/examples/connect-to-mysql/
- https://developers.cloudflare.com/d1/
- https://developers.cloudflare.com/d1/reference/migrations/
- https://developers.cloudflare.com/queues/
- https://developers.cloudflare.com/queues/reference/delivery-guarantees/
- https://developers.cloudflare.com/r2/
- https://developers.cloudflare.com/kv/concepts/how-kv-works/
- https://developers.cloudflare.com/durable-objects/best-practices/websockets/
- https://developers.cloudflare.com/hyperdrive/examples/connect-to-postgres/postgres-database-providers/supabase/
- https://supabase.com/docs/guides/realtime
- https://supabase.com/docs/guides/functions/deploy
- https://supabase.com/docs/guides/deployment/managing-environments
- https://developers.cloudflare.com/workers/versions-and-deployments/
- https://developers.cloudflare.com/workers/versions-and-deployments/gradual-deployments/
- https://developers.cloudflare.com/workers/versions-and-deployments/rollbacks/
