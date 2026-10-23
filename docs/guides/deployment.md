# Despliegue

Rapid OS no despliega: documenta el destino y deja el despliegue a la persona. El onboarding ofrece un documento opcional, `docs/DEPLOYMENT.md`, el último de la lista, con las secciones `Destino`, `Configuración y secretos`, `Servicios gestionados` y `Verificación y reversión`. La primera pregunta es la plataforma: `aws`, `azure`, `vercel`, `render`, `railway` o `dokploy`.

Si la persona prefiere decidirlo después, lo omite (`rapid setup doc deployment --skip`) y lo retoma cuando quiera:

```bash
rapid deploy --target railway       # imprime la plantilla de la plataforma (no escribe nada)
rapid setup doc deployment --reopen # reabre el documento del proyecto
```

`rapid deploy` ya no escribe `DEPLOY.md`: imprime `templates/deploy/<plataforma>.md` y el comando para reabrir el documento. Una plataforma desconocida es `RAPID1413`.

## Plataformas y servicios

Las plantillas citan las páginas oficiales consultadas. Donde la documentación consultada no confirma un servicio gestionado, la plantilla lo dice y el servicio se aloja como contenedor propio.

| Plataforma | Destino | database | cache | queue | stream |
|---|---|---|---|---|---|
| aws | ECS con Fargate (App Runner ya no admite clientes nuevos) | RDS (PostgreSQL, MySQL, MariaDB); DocumentDB es compatible con MongoDB | ElastiCache (Valkey, Redis OSS) | Amazon MQ (RabbitMQ) | MSK (Kafka) |
| azure | Container Apps o App Service | PostgreSQL y MySQL flexible server; Cosmos DB for MongoDB | Azure Managed Redis | Service Bus (no es RabbitMQ) | Event Hubs con endpoint Kafka |
| vercel | Frontend y funciones; no una API con conexiones persistentes | Marketplace (Neon, Supabase, MongoDB Atlas...) | Marketplace (Upstash, Redis Cloud) | fuera de Vercel | fuera de Vercel |
| render | Web service Docker y private services | Render Postgres | Render Key Value (Valkey) | contenedor con disco | contenedor con disco |
| railway | Servicios en un proyecto con red privada | Plantilla de PostgreSQL (un nodo) | contenedor con volumen | contenedor con volumen | contenedor con volumen |
| dokploy | Servidor propio con Docker y Traefik | PostgreSQL, MySQL, MariaDB, MongoDB | Redis | compose | compose |

**Vercel** sirve frontend y funciones con duración máxima por invocación; una API con WebSockets o procesos largos va en otra plataforma. Los secretos viven siempre en el gestor de la plataforma, nunca en el repositorio.
