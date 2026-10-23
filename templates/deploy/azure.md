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
| database (mariadb), cache (valkey), queue (rabbitmq) | No confirmado en la documentación consultada: se alojan como contenedor propio |

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
