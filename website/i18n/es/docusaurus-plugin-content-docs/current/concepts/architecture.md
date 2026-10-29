---
title: Arquitectura de referencia, el monolito modular
description: La regla de arquitectura con la que arranca todo proyecto, los nombres idiomáticos de cada lenguaje, cuándo un módulo es hexagonal y cómo Rapid OS la verifica en cada run.
---

# Arquitectura de referencia, el monolito modular

Todo proyecto con stack de catálogo arranca como **monolito modular**: módulos por capacidad de negocio, capas dentro de cada módulo y puertos y adaptadores (hexagonal) solo en los módulos que lo justifican. La regla llega al agente como un estándar y Rapid OS la verifica en cada run, en el idioma del stack elegido.

Los stacks `generic`, `custom` y `docs-modern` no reciben la regla. Ver [Stacks y componentes](./stacks.md).

## La regla (igual en todos los lenguajes)

Las responsabilidades no cambian; cambian los nombres y el mecanismo.

- El sistema se organiza en **módulos por capacidad de negocio** (citas, pagos, talleres), nunca en capas globales (`controllers/`, `services/`, `models/` en la raíz).
- Cada módulo tiene una **entrada** (HTTP, eventos), una **aplicación** (casos de uso; aquí viven los puertos si el módulo es hexagonal), un **dominio** (entidades, reglas e invariantes, sin framework web ni ORM), una **infraestructura** (persistencia y adaptadores externos) y **un único contrato público**.
- Dirección de dependencias: entrada → aplicación → dominio; infraestructura → aplicación y dominio (implementa los puertos); el dominio no importa nada de las otras capas ni librerías de framework web, ORM o clientes externos.
- Entre módulos solo se usa el contrato público del otro módulo, nunca sus capas.
- Cada módulo es dueño de sus tablas: otro módulo no las lee ni las escribe directamente.
- `shared/` es un núcleo mínimo (configuración, sesión de base de datos, errores base) y no importa ningún módulo.

No se empieza con microservicios: un monolito modular da los mismos límites con un solo despliegue, y un módulo con contrato público y tablas propias se extrae después si hace falta.

## Los nombres de cada lenguaje

| Stack | Módulos en | Entrada | Aplicación | Dominio | Infraestructura | Contrato público |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `python-fastapi` | `app/modules/<m>/` | `api/` | `application/` | `domain/` | `infrastructure/` | `public.py` |
| `python-django` | `apps/<m>/` (una app por módulo) | `api/` (vistas y serializers) | `services/` | `domain/` | `models.py` | `public.py` |
| `node-nestjs` | `src/modules/<m>/` | `controllers/` | `application/` | `domain/` | `infrastructure/` | `<m>.module.ts` (sus `exports`) o `index.ts` |
| `node-fastify` | `src/modules/<m>/` | `routes/` | `application/` | `domain/` | `infrastructure/` | `index.ts` |
| `go` | `internal/<m>/` | `http/` | `app/` | `domain/` | `store/` o `adapters/` | el paquete raíz del módulo (identificadores exportados) |
| `rust-axum` | `src/modules/<m>/` | `routes.rs` | `application.rs` | `domain.rs` | `infra.rs` | `mod.rs` (`pub use`); el resto `pub(crate)` |
| `ruby-rails` | `packs/<m>/` (packwerk) | `app/controllers` | `app/use_cases` | `app/domain` (POROs) | `app/models` (Active Record) | `app/public/` |
| `dotnet-aspnetcore` | `src/Modules/<M>/` | `<M>.Api` | `<M>.Application` | `<M>.Domain` | `<M>.Infrastructure` | el proyecto `<M>.Contracts` |
| `java-spring-boot`, `kotlin-spring-boot` | `src/main/{java,kotlin}/com/example/app/<m>/` | `web/` | `application/` | `domain/` | `infrastructure/` | los tipos del paquete raíz del módulo (Spring Modulith) |
| `php-laravel` | `app/Modules/<M>/` | `Http/` | `Application/` | `Domain/` | `Infrastructure/` | `Contracts/` y un ServiceProvider por módulo |
| `nextjs`, `nuxt`, `sveltekit` (servidor) | `src/modules/<m>/` (`server/modules/` en Nuxt, `src/lib/server/modules/` en SvelteKit) | `api/` | `application/` | `domain/` | `infrastructure/` | `index.ts` |

`architecture.md` se genera con los nombres del lenguaje elegido, el árbol de ese stack y una tabla final que mapea cada nombre a su responsabilidad canónica.

### El frontend

Los ocho stacks de frontend (`react-vite`, `nextjs`, `angular`, `vue-vite`, `nuxt`, `svelte-vite`, `sveltekit`, `astro`) organizan por **funcionalidad**: `src/features/<f>/` (`src/app/features/` en Angular, `app/features/` en Nuxt, `src/lib/features/` en SvelteKit) con

| Carpeta | Responsabilidad |
| :--- | :--- |
| `ui/` | componentes |
| `state/` | estado de la funcionalidad |
| `data-access/` | llamadas a la API |
| `model/` | tipos y reglas de presentación |
| `index.ts` | contrato público |

`ui` puede importar `state` y `model`; `state`, `data-access` y `model`; `data-access`, `model`; `model` no importa nada de las otras capas ni un framework de interfaz (`react`, `vue`, `svelte`, `@angular/core`...). Una funcionalidad solo importa el `index.ts` de otra.

### Backend y frontend en el mismo proyecto

Cuando el backend y el frontend son stacks distintos viven en `backend/` y `frontend/` y `architecture.json` trae dos reglas. Cuando un solo framework cubre ambos (`nextjs`, `nuxt`, `sveltekit`) las dos reglas están en la raíz, en `src/modules` y `src/features`. Un proyecto con una sola de las dos usa la raíz.

## Cuándo un módulo es hexagonal

Usa puertos en la capa de aplicación y adaptadores en la de infraestructura cuando el módulo integra un sistema externo (pagos, mensajería, IA, correo), cuando su dominio tiene reglas complejas que deben probarse sin infraestructura, o cuando se prevé cambiar de proveedor. Un CRUD simple no lo necesita.

## Cómo llega al proyecto

`rapid setup finish` (y `rapid init`) escribe dos archivos en `.rapid-os/standards/`:

| Archivo | Para quién | Qué contiene |
| :--- | :--- | :--- |
| `architecture.md` | El agente | La regla con el árbol y los nombres de cada stack. Entra al contexto y a los archivos de agente como estándar, sin banner de supuesto. |
| `architecture.json` | Rapid OS | La regla en forma de máquina (ver abajo). |

Si ya existen, no se sobrescriben al terminar de nuevo el onboarding (tu edición se respeta). Si cambias a un stack sin la regla, Rapid OS no borra estos archivos: bórralos tú si ya no aplican.

`architecture.json` guarda `language`, `component`, `modules_root`, `shared_root`, `public_entry`, qué capas puede importar cada capa (`layers`) y las librerías prohibidas en la capa pura (`domain_forbidden_imports`), y desde el catálogo por componentes también `roles` (qué carpeta o paquete es cada capa canónica; `{m}` nombra al módulo), `module_pattern`, `public_contract`, `public_policy` (`entry`: solo el punto público; `root`: todo lo que no sea una capa), `public_dirs`, `namespace_root` (Java, Kotlin, C# y PHP), `aliases` (TypeScript), `pure_layer`, `delegate`, `root` y `rules` cuando hay varias. Los archivos anteriores siguen leyéndose igual. En Java y Kotlin cambia `com.example.app` por tu paquete real; en C# y PHP, `namespace_root` por tu espacio de nombres raíz.

El documento `docs/ARCHITECTURE.md` del onboarding exige las secciones **Módulos**, **Reglas de dependencia** y **Servicios de infraestructura**, y parte de este estándar.

## Cómo se verifica

`rapid arch check` lee los imports de los archivos bajo `modules_root` y `shared_root` e informa cada violación con archivo, línea, import y regla (`RAPID1420`). No ejecuta nada ni añade dependencias:

| Lenguaje | Qué lee |
| :--- | :--- |
| Python | `ast`; si el archivo no se puede parsear (sintaxis más nueva que el Python que ejecuta Rapid OS), sus líneas `import` y `from ... import`, también entre paréntesis y en varias líneas |
| TypeScript y JavaScript | `import`, `export ... from`, `import()` y `require`; el bloque `<script>` de `.vue` y `.svelte` y el frontmatter y los `<script>` de `.astro` |
| Go | `import` (se ignoran los `_test.go`) |
| Java y Kotlin | `import` |
| C# | `using` y las referencias de los `.csproj` (`ProjectReference` y `PackageReference`) |
| Rust | `use` (con `crate::`, `super::` y `self::`) |
| PHP | `use` |
| Ruby | no hay imports que leer: delega en `bin/packwerk check` |

Las violaciones son:

- una capa que importa una capa que no le toca;
- un módulo que importa de otro algo distinto de su contrato público;
- `shared` que importa un módulo;
- el `__init__.py` de un módulo de Python que importa algo distinto de su propio `public.py`;
- la capa pura (`domain`, o `model` en el frontend) que importa una librería prohibida.

Los imports se escriben desde la raíz del componente. Cuando un componente vive en una subcarpeta (`backend/` y `frontend/` en un fullstack separado, campo `root` de la regla), el verificador antepone esa carpeta a los imports absolutos de Python (`app.modules...`), a los `aliases` (`@/` es `src/` dentro del componente) y a las rutas `src/...`, de modo que `backend/app/modules/talleres/...` que importa `app.modules.pagos.infrastructure...` es una violación `cross_module`, igual que en un proyecto en la raíz.

Un archivo Python que no se puede parsear nunca se trata como código inválido: el proyecto puede usar un Python más nuevo (por ejemplo `except A, B:` de la PEP 758 en 3.14) que el que ejecuta Rapid OS. Se lee por líneas, `rapid arch check` imprime `WARNING <archivo>: leído sin AST: sintaxis más nueva que el Python de Rapid OS (3.x)` (`warnings[]` en `--json`) y sus imports se juzgan como los de cualquier otro.

Solo cuentan como módulos los directorios de `modules_root`. Sale con 1 si hay violaciones, con 0 si no las hay, si todavía no hay módulos o (con un aviso) si el proyecto no tiene `architecture.json`.

### Ruby on Rails

Rails carga el código por convención: no hay imports que leer. `rapid arch check` ejecuta `bin/packwerk check` y lo dice. Si packwerk no está, avisa (`RAPID1420 packwerk no está disponible...`) y termina con 1: el gate no se da por satisfecho. Instálalo con `bundle add packwerk --group development && bundle binstub packwerk`.

### Herramientas idiomáticas como prueba complementaria

Donde existe la herramienta del ecosistema, `architecture.md` la nombra como prueba complementaria que el scaffold puede añadir: Spring Modulith (`ApplicationModules.of(Application.class).verify()`), packwerk, Deptrac (PHP) y NetArchTest (.NET). El gate sigue siendo `rapid arch check`.

### En un run con worktree

El worktree de un run no tiene `.rapid-os/`: el ledger y la regla viven en el proyecto principal. Si no hay `architecture.json` en el directorio actual y hay una sesión activa cuyo contrato incluye `gate.architecture`, `rapid arch check` lee la regla del proyecto principal (la raíz de la sesión) y analiza el código del directorio actual, es decir, del worktree. Si el run exige el gate y no encuentra la regla en ninguno de los dos sitios, termina con `RAPID1420 el run exige gate.architecture y no hay architecture.json` (exit 1): sin regla, el gate no puede parecer satisfecho. Fuera de un run, sin `architecture.json` sigue siendo exit 0 con un aviso.

### El gate `gate.architecture`

En los runs de `feature`, `bugfix` y `refactor`, si existe `architecture.json`, el contrato incluye el gate de máquina `gate.architecture`. `rapid next` lo propone como una verificación más, igual que `gate.tests`:

```bash
rapid check --gate gate.architecture -- rapid arch check --new-only
```

`rapid finish` no da `PASS` mientras ese gate no esté satisfecho. El gate no se puede dispensar (no es waivable). Nunca desactives ni edites `architecture.json` para que un check pase: cambia el código o pide a la persona que cambie la regla.

## Proyectos existentes

La regla aplica al **código nuevo**, y Rapid OS juzga un run por lo que el run añade. `rapid start` toma una foto de las violaciones que el proyecto ya tiene (archivo, regla e import, sin el número de línea, que cambia al editar) junto a la baseline de tests y la guarda en `session.json` (`start_architecture`). Desde entonces:

- `gate.architecture` (`rapid arch check --new-only`) y la recomprobación final de `rapid finish` fallan solo por violaciones que **no** están en la foto. Las previas se informan como deuda (`N violaciones previas; no bloquean este run`) y se propone `/rapid-refactor`.
- `rapid arch check` a secas sigue listando y fallando por todas. `--json` marca cada violación `new` o `previous` y añade `counts`, `new_only` y `baseline`.
- En un run de **refactor**, una violación previa en un archivo que el run tocó cuenta como nueva: no se puede tocar un archivo y dejarlo violando.
- Sin run activo, con un run cerrado o con un run anterior a la foto, todas cuentan como previas y nada bloquea.

La regla aplica al **código nuevo**. En un repositorio con capas globales, `rapid arch check` informa violaciones solo dentro de `modules_root`; no exige migrar. La migración a módulos se hace con `/rapid-refactor`, y en un proyecto nuevo la tarea de scaffold pide un módulo de ejemplo con sus capas y su contrato público.

## Límites

- Los imports se resuelven desde la raíz del proyecto; un alias propio fuera de los de `architecture.json` (`aliases`) no se reconoce.
- Go resuelve un import buscando la carpeta de los módulos (`internal`) dentro de la ruta, así que no necesita leer `go.mod`.
- Las reglas de instrucción que no son de importación (por ejemplo, que cada módulo sea dueño de sus tablas) las cumple el agente; el verificador juzga solo `modules_root` y `shared_root`.
