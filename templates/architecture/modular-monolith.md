# ARQUITECTURA: MONOLITO MODULAR

Esta es una regla, no una sugerencia. Todo código nuevo la cumple. Rapid OS la verifica en cada run con `rapid arch check` (gate `gate.architecture`).

Las responsabilidades son las mismas en todos los lenguajes: **entrada** (HTTP, eventos), **aplicación** (casos de uso y puertos), **dominio** (reglas sin framework), **infraestructura** (persistencia y adaptadores) y el **contrato público** del módulo. Lo que cambia es el nombre de la carpeta o del paquete y el mecanismo que hace público el contrato; ambos están en «Estructura por stack», más abajo.

## Módulos por capacidad de negocio

- Organiza el sistema en **módulos por capacidad de negocio** (por ejemplo: citas, pagos, talleres), nunca en capas globales (`controllers/`, `services/`, `models/` en la raíz).
- Un módulo es una capacidad que el negocio nombraría sin hablar de tecnología. Si dudas entre dos módulos, es uno solo hasta que haya una razón para separarlos.

## Estructura de cada módulo

Cada módulo tiene exactamente estas piezas, con los nombres de tu stack:

- entrada: HTTP, eventos y esquemas de entrada y salida;
- aplicación: casos de uso. Aquí viven los puertos (interfaces) si el módulo es hexagonal;
- dominio: entidades, reglas e invariantes. Sin framework web ni ORM;
- infraestructura: repositorios, ORM y adaptadores de sistemas externos;
- un **único punto público**: lo único que otros módulos pueden usar.

## Dirección de dependencias

- entrada -> aplicación -> dominio.
- infraestructura -> aplicación y dominio (implementa los puertos).
- El dominio no importa nada de las otras capas ni librerías de framework web, ORM o clientes externos.
- El punto público expone lo que el módulo ofrece y puede usar las capas de su propio módulo.

## Entre módulos

- Un módulo solo usa el **punto público** de otro módulo. Nunca sus capas.
- Cada módulo es **dueño de sus tablas**: otro módulo no las lee ni las escribe directamente. Si necesita esos datos, los pide por el punto público.

## shared/

- `shared/` es un núcleo mínimo: configuración, sesión de base de datos y errores base.
- `shared/` no importa ningún módulo. Si algo de `shared/` empieza a depender de un módulo, ese código pertenece a un módulo.

## Cuándo un módulo es hexagonal

Usa puertos y adaptadores (los puertos en la capa de aplicación, los adaptadores en la de infraestructura) cuando el módulo:

- integra un sistema externo (pagos, mensajería, IA, correo);
- tiene un dominio con reglas complejas que deben probarse sin infraestructura;
- o se prevé cambiar de proveedor.

Un CRUD simple no necesita hexagonal: repositorio directo en infraestructura y casos de uso simples en aplicación.

## Por qué esta forma

- No se empieza con microservicios: un monolito modular da los mismos límites con un solo despliegue, y un módulo con su punto público y sus tablas propias se extrae después si hace falta.
- No se usan capas globales: obligan a tocar toda la raíz por cada cambio y la migración posterior a módulos es costosa; empezar por módulos evita esa migración.

## Estructura por stack

## Verificación

- Ejecuta `rapid arch check` antes de dar una tarea por terminada. Informa cada violación con archivo, línea, import y regla.
- La regla en forma de máquina está en `.rapid-os/standards/architecture.json`. Nunca desactives ni edites `.rapid-os/standards/architecture.json` para que un check pase: cambia el código o pide a la persona que cambie la regla.
- Un proyecto existente no se migra de golpe: la regla aplica al código nuevo, dentro de la carpeta de módulos. La migración se hace con `/rapid-refactor`.
