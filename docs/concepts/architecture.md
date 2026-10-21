---
title: Arquitectura de referencia, el monolito modular
description: La regla de arquitectura con la que arranca todo proyecto con backend, el árbol de carpetas, cuándo un módulo es hexagonal y cómo Rapid OS la verifica en cada run.
---

# Arquitectura de referencia, el monolito modular

Todo proyecto con backend arranca como **monolito modular**: módulos por capacidad de negocio, capas dentro de cada módulo y puertos y adaptadores (hexagonal) solo en los módulos que lo justifican. La regla llega al agente como un estándar y Rapid OS la verifica en cada run.

Aplica a los stacks `python-api`, `python-ai`, `nodejs-ai` y `web-modern`. Los stacks `docs-modern`, `frontend-creative` y `generic` no la reciben.

## La regla

- El sistema se organiza en **módulos por capacidad de negocio** (citas, pagos, talleres), nunca en capas globales (`controllers/`, `services/`, `models/` en la raíz).
- Cada módulo tiene `api/` (entrada HTTP y esquemas), `application/` (casos de uso; aquí viven los puertos si el módulo es hexagonal), `domain/` (entidades, reglas e invariantes, sin framework web ni ORM), `infrastructure/` (repositorios, ORM y adaptadores externos) y **un único punto público** (`public.py` o `index.ts`).
- Dirección de dependencias: `api` → `application` → `domain`; `infrastructure` → `application` y `domain` (implementa los puertos); `domain` no importa nada de las otras capas.
- Entre módulos solo se importa el punto público del otro módulo, nunca sus capas.
- En Python, el `__init__.py` de un módulo está vacío o solo reexporta desde su `public.py`; así importar el paquete del módulo (`from app.modules.pagos import ...`) deja de ser una puerta trasera a sus capas. En TypeScript el `index.ts` ya es ese contrato.
- Cada módulo es dueño de sus tablas: otro módulo no las lee ni las escribe directamente.
- `shared/` es un núcleo mínimo (configuración, sesión de base de datos, errores base) y no importa ningún módulo.

No se empieza con microservicios: un monolito modular da los mismos límites con un solo despliegue, y un módulo con punto público y tablas propias se extrae después si hace falta. Tampoco se usan capas globales: obligan a tocar toda la raíz por cada cambio y la migración posterior a módulos es costosa.

## El árbol de carpetas

`python-api` y `python-ai`:

```text
app/
  main.py                      # composición
  shared/
  modules/
    <m>/
      public.py
      api/  application/  domain/  infrastructure/
```

`nodejs-ai` y `web-modern`:

```text
src/
  shared/
  modules/
    <m>/
      index.ts
      api/  application/  domain/  infrastructure/
  app/                         # solo web-modern: la UI; importa solo el index.ts de los módulos
```

## Cuándo un módulo es hexagonal

Usa puertos en `application/` y adaptadores en `infrastructure/` cuando el módulo integra un sistema externo (pagos, mensajería, IA, correo), cuando su dominio tiene reglas complejas que deben probarse sin infraestructura, o cuando se prevé cambiar de proveedor. Un CRUD simple no lo necesita.

## Cómo llega al proyecto

`rapid setup finish` (y `rapid init`) escribe dos archivos en `.rapid-os/standards/` cuando el stack es de la familia modular:

| Archivo | Para quién | Qué contiene |
| :--- | :--- | :--- |
| `architecture.md` | El agente | La regla anterior con el árbol del stack. Entra al contexto y a los archivos de agente como estándar, sin banner de supuesto. |
| `architecture.json` | Rapid OS | La regla en forma de máquina: `language`, `modules_root`, `shared_root`, `public_entry`, qué capas puede importar cada capa y las librerías prohibidas en `domain`. |

Si ya existen, no se sobrescriben al terminar de nuevo el onboarding (tu edición se respeta). Si cambias a un stack sin la regla, Rapid OS no borra estos archivos: bórralos tú si ya no aplican.

El documento `docs/ARCHITECTURE.md` del onboarding exige las secciones **Módulos** (cada módulo con su responsabilidad, sus tablas y si es hexagonal) y **Reglas de dependencia**, y parte de este estándar.

## Cómo se verifica

`rapid arch check` lee los imports de los archivos bajo `modules_root` y `shared_root` (Python con `ast`, TypeScript y JavaScript con expresiones regulares; no ejecuta nada) e informa cada violación con archivo, línea, import y regla (`RAPID1420`):

- una capa que importa una capa que no le toca;
- un módulo que importa de otro algo distinto de su punto público;
- `shared` que importa un módulo;
- el `__init__.py` de un módulo de Python que importa algo distinto de su propio `public.py`;
- `domain` que importa una librería prohibida (`fastapi`, `sqlalchemy`, `starlette`, `httpx` en Python; `next`, `react`, `express`, `@prisma/client` en TypeScript).

Solo cuentan como módulos los directorios de `modules_root`; un archivo suelto en esa carpeta (como su `__init__.py`) no lo es. Sale con 1 si hay violaciones, con 0 si no las hay, si todavía no hay módulos o (con un aviso) si el proyecto no tiene `architecture.json`.

### En un run con worktree

El worktree de un run no tiene `.rapid-os/`: el ledger y la regla viven en el proyecto principal. Si no hay `architecture.json` en el directorio actual y hay una sesión activa cuyo contrato incluye `gate.architecture`, `rapid arch check` lee la regla del proyecto principal (la raíz de la sesión) y analiza el código del directorio actual, es decir, del worktree. Si el run exige el gate y no encuentra la regla en ninguno de los dos sitios, termina con `RAPID1420 el run exige gate.architecture y no hay architecture.json` (exit 1): sin regla, el gate no puede parecer satisfecho. Fuera de un run, sin `architecture.json` sigue siendo exit 0 con un aviso.

### El gate `gate.architecture`

En los runs de `feature`, `bugfix` y `refactor`, si existe `architecture.json`, el contrato incluye el gate de máquina `gate.architecture`. `rapid next` lo propone como una verificación más, igual que `gate.tests`:

```bash
rapid check --gate gate.architecture -- rapid arch check
```

`rapid finish` no da `PASS` mientras ese gate no esté satisfecho. El gate no se puede dispensar (no es waivable). Nunca desactives ni edites `architecture.json` para que un check pase: cambia el código o pide a la persona que cambie la regla.

## Proyectos existentes

La regla aplica al **código nuevo**. En un repositorio con capas globales, `rapid arch check` informa violaciones solo dentro de `modules_root`; no exige migrar. La migración a módulos se hace con `/rapid-refactor`, y en un proyecto nuevo la tarea de scaffold pide un módulo de ejemplo con sus cuatro capas y su punto público.

## Límites

- Los imports se resuelven desde la raíz del proyecto (como en el árbol de arriba); un alias propio fuera de `@/` o `src/` no se reconoce.
- La regla "la UI solo importa el `index.ts` de los módulos" de `web-modern` es una instrucción para el agente; el verificador juzga solo `modules_root` y `shared_root`.
