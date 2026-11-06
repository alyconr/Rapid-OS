---
title: Deployment
description: Document a deployment target and managed services for a Rapid OS project.
---

# Deployment

Rapid OS does not deploy software. It documents the target and leaves deployment to a person. During onboarding, it offers an optional `docs/DEPLOYMENT.md` document as the last item in the list. The document has sections for `Target`, `Configuration and secrets`, `Managed services`, and `Verification and rollback`. The first question asks for a platform: `aws`, `azure`, `vercel`, `render`, `railway`, or `dokploy`.

If you prefer to decide later, skip it (`rapid setup doc deployment --skip`) and return to it at any time:

```bash
rapid deploy --target railway       # prints the platform template; writes nothing
rapid setup doc deployment --reopen # reopens the project document
```

`rapid deploy` no longer writes `DEPLOY.md`: it prints `templates/deploy/<platform>.md` and the command to reopen the document. An unknown platform returns `RAPID1413`.

## Platforms and services

The templates cite the official pages consulted. If the consulted documentation does not describe a managed service, the template says "no managed service" and the service must be hosted in your own container.

| Platform | Target | Database | Cache | Queue | Stream |
|---|---|---|---|---|---|
| aws | ECS with Fargate (App Runner no longer accepts new customers) | RDS (PostgreSQL, MySQL, MariaDB); DocumentDB is MongoDB-compatible | ElastiCache (Valkey, Redis OSS) | Amazon MQ (RabbitMQ) | MSK (Kafka) |
| azure | Container Apps or App Service | PostgreSQL and MySQL Flexible Server; Cosmos DB for MongoDB | Azure Managed Redis | Service Bus (not RabbitMQ) | Event Hubs with Kafka endpoint |
| vercel | Frontend and functions; not an API with persistent connections | Marketplace (Neon, Supabase, MongoDB Atlas...) | Marketplace (Upstash, Redis Cloud) | Outside Vercel | Outside Vercel |
| cloudflare | Workers with Static Assets; an API in Workers (Hono), FastAPI in Python Workers only with synchronous data access | Hyperdrive to an external PostgreSQL or MySQL; D1 for SQLite | KV (not Redis) | Queues (not RabbitMQ) | Outside Cloudflare |
| netlify | Frontend (and the Deploy Previews); with Supabase the data lives in the provider | Supabase (provider) | Outside Netlify | Outside Netlify | Outside Netlify |
| firebase-hosting | Static frontend or SPA; Cloud Functions for the server code | Cloud Firestore | Outside Firebase | Outside Firebase | Outside Firebase |
| render | Docker web service and private services | Render Postgres | Render Key Value (Valkey) | Container with disk | Container with disk |
| railway | Services in a project with a private network | PostgreSQL template (single node) | Container with volume | Container with volume | Container with volume |
| dokploy | Self-hosted server with Docker and Traefik | PostgreSQL, MySQL, MariaDB, MongoDB | Redis | Compose | Compose |

**Vercel** serves frontends and functions with a maximum duration per invocation; put an API with WebSockets or long-running processes on another platform. Keep secrets in the platform's secret manager, never in the repository.

**Cloudflare** recommends Workers with Static Assets for new projects; Pages keeps working. A Worker runs per request, not as a persistent process, so a stack that needs one goes to another platform or to Cloudflare Containers, with the frontend on Cloudflare. FastAPI runs in Python Workers only with synchronous data access: when the stack and the data access option decided do not fit Workers, the `deployment` action carries a note in `platform_notes.cloudflare`, which informs and blocks nothing. `rapid deploy --target cloudflare` prints the template, and the scanner reports `wrangler.toml`, `wrangler.json` and `wrangler.jsonc` as the `cloudflare` provider.
