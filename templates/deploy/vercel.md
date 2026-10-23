# Despliegue en Vercel

Plantilla de partida para `docs/DEPLOYMENT.md`. Rapid OS no despliega: lo haces tú.

## Destino
- **Frontend y funciones**: Vercel sirve el frontend y ejecuta Vercel Functions (una invocación por petición, escala sola y a cero).
- **No es el destino de una API con conexiones persistentes** (WebSockets, procesos largos, workers): las funciones tienen duración máxima (300 s por defecto; hasta 800 s en Pro, según la documentación consultada) y límite de 4,5 MB por cuerpo. Esa API va en otra plataforma (aws, azure, render, railway o dokploy) y el frontend en Vercel.

## Configuración y secretos
- Variables de entorno por entorno: Production, Preview y Development (`vercel env pull` las baja a `.env` local).
- Las variables marcadas como secretas son de solo escritura tras guardarlas. Un cambio aplica solo a despliegues nuevos. Nunca en el repositorio.

## Servicios gestionados
Vercel no aloja bases de datos propias en esta guía: se conectan por el Marketplace de integraciones.
| Rol | Opción |
|---|---|
| database (postgresql) | Integraciones del Marketplace (Neon, Supabase, Prisma Postgres, entre otras) |
| database (mongodb) | MongoDB Atlas (Marketplace) |
| cache (redis) | Upstash for Redis o Redis Cloud (Marketplace) |
| mysql, mariadb, queue, stream | No confirmado en la documentación consultada: fuera de Vercel |

## Verificación y reversión
- Revisar el despliegue de Preview antes de promoverlo; comprobar logs tras producción.
- Reversión: Instant Rollback desde el panel (no cambia las variables de entorno); `vercel promote` deshace el rollback.

## Fuentes oficiales
- https://vercel.com/docs/functions
- https://vercel.com/docs/functions/limitations
- https://vercel.com/docs/environment-variables
- https://vercel.com/marketplace
- https://vercel.com/docs/instant-rollback
