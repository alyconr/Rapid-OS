# Servicios de infraestructura

Los servicios de infraestructura de un proyecto (base de datos, caché, cola, streaming) **salen de una decisión registrada, no del stack**. El stack solo sugiere un mínimo (`suggested_services`, por ejemplo `database:postgresql`); la persona decide, con el porqué y el momento de cada servicio.

## La decisión

Después de `brief` y `business`, y antes de `data-model`, `architecture` y `deployment`, el conductor de `rapid setup next` devuelve la acción `choose_services`. El agente propone los servicios a partir del brief y las reglas de negocio (empieza por lo mínimo: una base de datos), y la persona responde:

```bash
rapid setup set services database:postgresql@now,queue:rabbitmq@later
rapid setup set services none
```

- Formato: `<rol>:<motor>[@now|@later]`, separados por comas. Sin sufijo es `@now`.
- Roles: `database`, `cache`, `queue`, `stream`, `search`, `object-storage`.
- `@now`: se necesita para la primera historia; Rapid OS escribe su contenedor. `@later`: queda decidido pero sin contenedor.
- `none` es una decisión válida (un sitio estático no necesita servicios).
- Un rol o motor desconocido, o una pareja incompatible, es `RAPID1413`; un motor que el stack no soporta es `RAPID1402`.
- Después de `setup finish`, `rapid setup set services ...` se aplica al instante y no reabre el onboarding.

## Catálogo

Cada motor es un archivo `templates/services/<motor>.json` validado por `rapid_os.domain.catalog` (`RAPID1401`) con rol, imagen oficial con versión mayor fijada, puertos, variables, healthcheck, volumen, variable de conexión, drivers por lenguaje y las `sources` oficiales.

| Rol | Motores |
|---|---|
| database | `postgresql`, `mysql`, `mariadb`, `mongodb` |
| cache | `redis`, `valkey` |
| queue | `rabbitmq` |
| stream | `kafka` (KRaft, un nodo) |

## Qué escribe Rapid OS

Al cerrar el onboarding de un repositorio vacío, `rapid setup finish` escribe (no el agente):

- `compose.yaml`: un servicio por cada `@now`, imagen fijada, healthcheck, volumen con nombre y puertos solo en `127.0.0.1`.
- `.env.example` con las variables de conexión, y `.env` añadido a `.gitignore`.
- `tech-stack.md` con la base de datos y el driver del motor elegido (el stack ya no los impone).

Si ya hay un `compose.yaml`, al pasar un servicio de `@later` a `@now` solo se añaden los que faltan: lo existente no se modifica, y un YAML que no se puede leer se deja intacto con un aviso. Los archivos se anuncian en la salida de `finish` y en la revisión de borradores.

## Probar el modelo de datos sin que el gate dependa de Docker

El sandbox del harness no ejecuta Docker. Por eso `rapid setup finish` y `rapid status` ofrecen la acción de la persona `local-services` (`docker compose up -d`) mientras exista el `compose.yaml`. La tarea de scaffold pide que la configuración se lea de `.env.example`, que el esquema vaya en migraciones, que las pruebas unitarias no usen servicios externos y que las de integración tengan un marcador propio: `gate.tests` pasa sin Docker.

## Documentos

- `docs/ARCHITECTURE.md` exige la sección `Servicios de infraestructura`.
- `docs/DATA_MODEL.md` exige `Base de datos local` cuando hay un servicio `database` (`RAPID1403` si falta).
- `docs/DEPLOYMENT.md` es opcional y va el último; ver la [guía de despliegue](../guides/deployment.md).
