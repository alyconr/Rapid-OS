# Despliegue en AWS

Plantilla de partida para `docs/DEPLOYMENT.md`. Rapid OS no despliega: lo haces tú.

## Destino
- Contenedores en **Amazon ECS con AWS Fargate** (cómputo sin servidores que gestionar). Imagen en Amazon ECR.
- **AWS App Runner ya no está abierto a clientes nuevos**; AWS recomienda ECS Express Mode a quien no sea cliente. No lo elijas para un proyecto nuevo.
- Infraestructura como código (Terraform o CloudFormation) y CI/CD desde GitHub Actions: build, push a ECR, actualización del servicio.

## Configuración y secretos
- Una configuración por entorno (dev, staging, producción) en variables de la definición de tarea.
- Secretos en **AWS Secrets Manager** (credenciales de base de datos, claves de API, tokens); la tarea los lee en el arranque. Nunca en el repositorio ni en `.env` versionado.

## Servicios gestionados
| Rol | Servicio de AWS |
|---|---|
| database (postgresql, mysql, mariadb) | Amazon RDS |
| database (mongodb) | Amazon DocumentDB (compatible con MongoDB, no es MongoDB) |
| cache (redis, valkey) | Amazon ElastiCache (motores Valkey y Redis OSS) |
| queue (rabbitmq) | Amazon MQ (RabbitMQ) |
| stream (kafka) | Amazon MSK (Apache Kafka) |

## Verificación y reversión
- Healthcheck del contenedor y del balanceador antes de dirigir tráfico; revisar logs y métricas tras el despliegue.
- Reversión: volver a la revisión anterior de la definición de tarea (imagen anterior en ECR); las migraciones de datos deben ser compatibles hacia atrás.

## Fuentes oficiales
- https://docs.aws.amazon.com/AmazonECS/latest/developerguide/Welcome.html
- https://docs.aws.amazon.com/AmazonECS/latest/developerguide/AWS_Fargate.html
- https://docs.aws.amazon.com/apprunner/latest/dg/what-is-apprunner.html
- https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/Welcome.html
- https://docs.aws.amazon.com/documentdb/latest/developerguide/what-is.html
- https://docs.aws.amazon.com/AmazonElastiCache/latest/dg/WhatIs.html
- https://docs.aws.amazon.com/amazon-mq/latest/developer-guide/welcome.html
- https://docs.aws.amazon.com/msk/latest/developerguide/what-is-msk.html
- https://docs.aws.amazon.com/secretsmanager/latest/userguide/intro.html
