# Migración de `setup.json` a stacks por componente

`setup.json` guardaba un solo `stack`. Ahora guarda `stacks`, uno por componente de la topología. Ningún proyecto existente se rompe: el archivo anterior se lee como el nuevo, sin escribir nada, y se reescribe en el formato nuevo la próxima vez que Rapid OS guarda una decisión.

## Antes y después

```json
{ "stack": { "id": "python-api", "source": "catalog" } }
```

```json
{
  "stacks": { "backend": { "id": "python-fastapi", "source": "catalog" } }
}
```

`source` sigue siendo `catalog`, `generic` o `custom`; `profile` (opcional) nombra una variante del `tech-stack.md`. Un stack que cubre varios componentes se guarda bajo cada uno de ellos.

## Cómo se leen los ids de antes

| Id anterior | Ahora |
|---|---|
| `python-api` | `backend` → `python-fastapi` |
| `python-ai` | `backend` → `python-fastapi` y `ai: true` (si el archivo no decía otra cosa) |
| `nodejs-ai` | `backend` → `node-fastify` y `ai: true` (si el archivo no decía otra cosa) |
| `web-modern` | `frontend` y `backend` → `nextjs` |
| `frontend-creative` | `frontend` → `react-vite` con el perfil `creative` |
| `docs-modern` | `docs` → `docs-modern` |
| `generic` | todos los componentes → `generic` |
| `custom` (o un id que no está en el catálogo) | todos los componentes → ese stack |

El resto del archivo (`topology`, `archetype`, `agents`, `test_command`, `docs`, `services`, `ai`, `finished`) no cambia. Un proyecto terminado sigue terminado: aunque ahora la topología pida un componente más (por ejemplo, el frontend de un `fullstack-separated` que antes solo tenía `python-api`), el onboarding no se reabre; `rapid setup next` lo propone solo si lo cambias.

## Qué pasa con los archivos

- `tech-stack.md` y `architecture.json` no se tocan mientras la decisión no cambie. Un `tech-stack.md` anterior se interpreta por su título (`PYTHON API`, `MODERN WEB`...) y, en los archivos nuevos, por la marca `<!-- rapid-stack: backend=go -->` que Rapid OS escribe al final de cada bloque.
- El `architecture.json` anterior (`modules_root`, `shared_root`, `public_entry`, `layers`, `domain_forbidden_imports`) sigue leyéndose igual. Los campos nuevos son opcionales: `roles`, `module_pattern`, `public_contract`, `public_policy`, `public_dirs`, `namespace_root`, `aliases`, `pure_layer`, `delegate`, `component`, `root` y `rules` (varias reglas, una por componente).
- La validación de un proyecto existente (`RAPID404`) sigue usando para los ids anteriores las topologías que aceptaban.

## Qué cambia si vuelves a decidir

`rapid setup set stack python-api` sigue funcionando y llena `backend` con `python-fastapi` (y `ai` si el id era de IA), pero ahora el frontend de un `fullstack-separated` hay que elegirlo aparte (`rapid setup set stack react-vite --component frontend`). Un stack del catálogo nuevo se elige por su id (`go`, `vue-vite`...); ver [Stacks y componentes](../concepts/stacks.md).
