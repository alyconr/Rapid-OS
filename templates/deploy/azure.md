# Despliegue en Azure

Plantilla de partida para `docs/DEPLOYMENT.md`. Rapid OS no despliega: lo haces tú.

## Destino
- Contenedores en **Azure Container Apps** (plataforma sin servidores para contenedores) o **Azure App Service** para aplicaciones web y APIs. Imagen en Azure Container Registry.
- CI/CD desde GitHub Actions; infraestructura como código (Bicep o Terraform).

## Configuración y secretos
- Una configuración por entorno en variables de la aplicación.
- Secretos en **Azure Key Vault**; nunca en el repositorio.

## Servicios gestionados
| Rol | Servicio de Azure |
|---|---|
| database (postgresql) | Azure Database for PostgreSQL |
| database (mysql) | Azure Database for MySQL flexible server |
| database (mongodb) | Azure Cosmos DB for MongoDB (compatible; Microsoft no ejecuta MongoDB) |
| cache (redis) | Azure Managed Redis |
| queue | Azure Service Bus (cola o tema propio de Azure, no es RabbitMQ) |
| stream (kafka) | Azure Event Hubs con endpoint Kafka (niveles standard, premium y dedicated) |
| database (mariadb) | Azure Database for MariaDB se retiró el 19 de septiembre de 2025 (así lo anunció Microsoft; la página oficial de Learn que sigue disponible lo llama «on the retirement path» y recomienda migrar a Azure Database for MySQL): usa MySQL flexible server, o MariaDB en un contenedor en Azure Container Apps |
| cache (valkey), queue (rabbitmq) | Sin servicio gestionado documentado: contenedor en Azure Container Apps |

## Verificación y reversión
- Sondas de salud y revisiones de la aplicación; comprobar logs y métricas tras desplegar.
- Reversión: activar la revisión anterior (Container Apps) o el slot anterior (App Service); las migraciones deben ser compatibles hacia atrás.

## Fuentes oficiales
- https://learn.microsoft.com/en-us/azure/container-apps/overview
- https://learn.microsoft.com/en-us/azure/app-service/overview
- https://learn.microsoft.com/en-us/azure/postgresql/flexible-server/overview
- https://learn.microsoft.com/en-us/azure/mysql/flexible-server/overview
- https://learn.microsoft.com/en-us/azure/cosmos-db/mongodb/introduction
- https://learn.microsoft.com/en-us/azure/redis/overview
- https://learn.microsoft.com/en-us/azure/service-bus-messaging/service-bus-messaging-overview
- https://learn.microsoft.com/en-us/azure/event-hubs/azure-event-hubs-apache-kafka-overview
- https://learn.microsoft.com/en-us/azure/key-vault/general/overview
- https://learn.microsoft.com/en-us/azure/mariadb/overview (página oficial de Learn: «on the retirement path», recomienda Azure Database for MySQL; no trae la fecha)
- https://techcommunity.microsoft.com/t5/azure-database-for-mysql-blog/azure-database-for-mariadb-is-being-retired-on-19-september-2025/ba-p/3935681 (anuncio de Microsoft con la fecha, 19 de septiembre de 2025; no se pudo abrir desde el entorno de verificación: la fecha consta en el título de su URL y en https://petri.com/microsoft-sunsetting-azure-database-for-mariadb/)
