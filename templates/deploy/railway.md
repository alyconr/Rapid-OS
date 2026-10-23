# Despliegue en Railway

Plantilla de partida para `docs/DEPLOYMENT.md`. Rapid OS no despliega: lo haces tú.

## Destino
- Un **proyecto** con un **servicio** por componente (código o imagen Docker). Los servicios de un proyecto comparten una red privada: se alcanzan en `<servicio>.railway.internal`.
- Healthcheck: ruta configurada en el servicio (p. ej. `/health`); el despliegue nuevo solo se activa cuando responde 2xx.

## Configuración y secretos
- Variables por servicio y entorno; referencias entre servicios con `${{Servicio.VARIABLE}}`. Nunca secretos en el repositorio.

## Servicios gestionados
| Rol | Opción en Railway |
|---|---|
| database (postgresql) | Plantilla de PostgreSQL: un solo nodo que Railway mantiene; la alta disponibilidad y las copias se activan aparte |
| mysql, mariadb, mongodb, redis, valkey, rabbitmq, kafka | Sin servicio gestionado documentado: servicio con la imagen oficial y un volumen |

Un servicio solo puede tener un volumen y los servicios con volumen no admiten réplicas.

## Verificación y reversión
- Revisar el healthcheck y los logs del despliegue.
- Reversión: Rollback sobre un despliegue anterior (no disponible más allá de la retención de imágenes del plan).

## Fuentes oficiales
- https://docs.railway.com/overview/the-basics
- https://docs.railway.com/guides/postgresql
- https://docs.railway.com/databases/build-a-database-service
- https://docs.railway.com/reference/variables
- https://docs.railway.com/reference/volumes
- https://docs.railway.com/reference/deployments
- https://docs.railway.com/reference/healthchecks
- https://docs.railway.com/reference/private-networking
