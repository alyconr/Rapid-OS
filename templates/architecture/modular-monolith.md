# ARQUITECTURA: MONOLITO MODULAR

Esta es una regla, no una sugerencia. Todo código nuevo la cumple. Rapid OS la verifica en cada run con `rapid arch check` (gate `gate.architecture`).

## Módulos por capacidad de negocio

- Organiza el sistema en **módulos por capacidad de negocio** (por ejemplo: citas, pagos, talleres), nunca en capas globales (`controllers/`, `services/`, `models/` en la raíz).
- Un módulo es una capacidad que el negocio nombraría sin hablar de tecnología. Si dudas entre dos módulos, es uno solo hasta que haya una razón para separarlos.

## Estructura de cada módulo

Cada módulo tiene exactamente estas piezas:

- `api/`: entrada HTTP y esquemas de entrada y salida.
- `application/`: casos de uso. Aquí viven los puertos (interfaces) si el módulo es hexagonal.
- `domain/`: entidades, reglas e invariantes. Sin framework web ni ORM.
- `infrastructure/`: repositorios, ORM y adaptadores de sistemas externos.
- Un **único punto público** (`public.py` en Python, `index.ts` en TypeScript): lo único que otros módulos pueden importar.
- En Python, el `__init__.py` de un módulo está vacío o solo reexporta desde su `public.py`; nunca importa de `api`, `application`, `domain` ni `infrastructure`. Si no, importar el paquete del módulo sería una puerta trasera a sus capas.

## Dirección de dependencias

- `api` -> `application` -> `domain`.
- `infrastructure` -> `application` y `domain` (implementa los puertos).
- `domain` no importa nada de las otras capas ni librerías de framework web, ORM o clientes externos.
- El punto público expone lo que el módulo ofrece y puede importar las capas de su propio módulo.

## Entre módulos

- Un módulo solo importa el **punto público** de otro módulo. Nunca sus capas (`api`, `application`, `domain`, `infrastructure`).
- Cada módulo es **dueño de sus tablas**: otro módulo no las lee ni las escribe directamente. Si necesita esos datos, los pide por el punto público.

## shared/

- `shared/` es un núcleo mínimo: configuración, sesión de base de datos y errores base.
- `shared/` no importa ningún módulo. Si algo de `shared/` empieza a depender de un módulo, ese código pertenece a un módulo.

## Cuándo un módulo es hexagonal

Usa puertos y adaptadores (los puertos en `application/`, los adaptadores en `infrastructure/`) cuando el módulo:

- integra un sistema externo (pagos, mensajería, IA, correo);
- tiene un dominio con reglas complejas que deben probarse sin infraestructura;
- o se prevé cambiar de proveedor.

Un CRUD simple no necesita hexagonal: repositorio directo en `infrastructure/` y casos de uso simples en `application/`.

## Por qué esta forma

- No se empieza con microservicios: un monolito modular da los mismos límites con un solo despliegue, y un módulo con su punto público y sus tablas propias se extrae después si hace falta.
- No se usan capas globales: obligan a tocar toda la raíz por cada cambio y la migración posterior a módulos es costosa; empezar por módulos evita esa migración.

## Estructura por stack

### python-api y python-ai

```text
app/
  main.py                      # composición: crea la app y conecta los módulos
  shared/                      # configuración, sesión de BD, errores base
  modules/
    <m>/
      public.py                # único punto público del módulo
      api/                     # rutas y esquemas
      application/             # casos de uso (y puertos si es hexagonal)
      domain/                  # entidades, reglas, invariantes
      infrastructure/          # repositorios, ORM, adaptadores
```

Rutas: `app/modules/<m>/{api,application,domain,infrastructure}/` más `app/modules/<m>/public.py`, y `app/shared/`. Los imports son absolutos desde la raíz del proyecto: `from app.modules.<m>.public import ...`.

### nodejs-ai y web-modern

```text
src/
  shared/                      # configuración, cliente de BD, errores base
  modules/
    <m>/
      index.ts                 # único punto público del módulo
      api/                     # handlers y esquemas
      application/             # casos de uso (y puertos si es hexagonal)
      domain/                  # entidades, reglas, invariantes
      infrastructure/          # repositorios, ORM, adaptadores
  app/                         # solo web-modern: la UI (páginas y componentes)
```

Rutas: `src/modules/<m>/{api,application,domain,infrastructure}/` más `src/modules/<m>/index.ts`, y `src/shared/`. En `web-modern` la UI vive en `src/app/` y solo importa el `index.ts` de los módulos, nunca sus capas.

## Verificación

- Ejecuta `rapid arch check` antes de dar una tarea por terminada. Informa cada violación con archivo, línea, import y regla.
- La regla en forma de máquina está en `.rapid-os/standards/architecture.json`. Nunca desactives ni edites `.rapid-os/standards/architecture.json` para que un check pase: cambia el código o pide a la persona que cambie la regla.
- Un proyecto existente no se migra de golpe: la regla aplica al código nuevo, dentro de la carpeta de módulos. La migración se hace con `/rapid-refactor`.
