# Despliegue en Dokploy

Plantilla de partida para `docs/DEPLOYMENT.md`. Rapid OS no despliega: lo haces tú.

## Destino
- **Dokploy** es una alternativa de código abierto y autoalojada a Heroku, Vercel y Netlify, basada en Docker y Traefik. Tú pones y mantienes el servidor.
- Aplicaciones desde Git o imagen, o un `compose.yaml` completo (modo Docker Compose o Stack con Swarm).

## Configuración y secretos
- Variables a nivel de proyecto, entorno o servicio. En modo Compose se guardan en un `.env` junto al compose y hay que referenciarlas (`env_file` o `${VAR}`).
- Los secretos pueden venir de un gestor externo (HashiCorp Vault, Infisical, AWS Secrets Manager, Doppler, Azure Key Vault) sin guardarse en Dokploy. Nunca en el repositorio.

## Servicios gestionados
| Rol | Opción en Dokploy |
|---|---|
| database (postgresql, mysql, mariadb, mongodb) | Bases de datos de Dokploy, con copias automáticas a S3 |
| cache (redis) | Redis de Dokploy |
| valkey, rabbitmq, kafka | Sin servicio gestionado documentado: se despliegan con compose |

Como el servidor es tuyo, las actualizaciones, el disco y las copias son responsabilidad del equipo.

## Verificación y reversión
- Comprobar logs y el endpoint de salud tras el despliegue.
- Reversión: Rollback basado en registro (imagen por despliegue) o rollback automático de Swarm si fallan los healthchecks (necesita `/health` y `curl` en el contenedor).

## Fuentes oficiales
- https://docs.dokploy.com/docs/core
- https://docs.dokploy.com/docs/core/databases
- https://docs.dokploy.com/docs/core/docker-compose
- https://docs.dokploy.com/docs/core/variables
- https://docs.dokploy.com/docs/core/applications/rollbacks
- https://docs.dokploy.com/docs/core/volume-backups
