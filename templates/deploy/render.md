# Despliegue en Render

Plantilla de partida para `docs/DEPLOYMENT.md`. Rapid OS no despliega: lo haces tú.

## Destino
- **Web service** con runtime Docker (o nativo): Render construye en cada push a la rama enlazada. Debe escuchar en `0.0.0.0` y en el puerto de la variable `PORT`.
- Servicios internos como **private services** (sin acceso desde internet). Infraestructura declarada en `render.yaml` (Blueprint).

## Configuración y secretos
- Variables en el panel o en `render.yaml`; grupos de variables compartidos entre servicios. Los secretos con `sync: false` se piden al crear; nunca valores secretos en el repositorio.

## Servicios gestionados
| Rol | Servicio de Render |
|---|---|
| database (postgresql) | Render Postgres (gestionado) |
| cache (redis, valkey) | Render Key Value (ejecuta Valkey) |
| mysql, mariadb, mongodb, rabbitmq, kafka | No gestionados en la documentación consultada: private service con Docker y disco persistente |

Un disco persistente impide los despliegues sin caída y el escalado del servicio.

## Verificación y reversión
- Healthcheck del web service; revisar logs tras el despliegue.
- Reversión: Rollback desde la página Deploys (reutiliza el artefacto de build mientras se conserve); no revierte discos. Desactiva los autodeploys.

## Fuentes oficiales
- https://render.com/docs/web-services
- https://render.com/docs/postgresql
- https://render.com/docs/key-value
- https://render.com/docs/private-services
- https://render.com/docs/disks
- https://render.com/docs/blueprint-spec
- https://render.com/docs/configure-environment-variables
- https://render.com/docs/rollbacks
