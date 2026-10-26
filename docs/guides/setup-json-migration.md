---
title: Migrating from `setup.json` to Component Stacks
description: How Rapid OS migrates projects from a single stack to per-component stacks.
---

# Migrating from `setup.json` to Component Stacks

`setup.json` used to store one `stack`. It now stores `stacks`, one per topology component. Existing projects do not break: the old file is read as the new format without being changed, then rewritten in the new format the next time Rapid OS saves a decision.

## Before and after

```json
{ "stack": { "id": "python-api", "source": "catalog" } }
```

```json
{
  "stacks": { "backend": { "id": "python-fastapi", "source": "catalog" } }
}
```

`source` remains `catalog`, `generic`, or `custom`; optional `profile` names a variant from `tech-stack.md`. A stack that covers multiple components is stored under each component.

## How previous IDs map

| Previous ID | New mapping |
|---|---|
| `python-api` | `backend` → `python-fastapi` |
| `python-ai` | `backend` → `python-fastapi` and `ai: true` (unless the file says otherwise) |
| `nodejs-ai` | `backend` → `node-fastify` and `ai: true` (unless the file says otherwise) |
| `web-modern` | `frontend` and `backend` → `nextjs` |
| `frontend-creative` | `frontend` → `react-vite` with the `creative` profile |
| `docs-modern` | `docs` → `docs-modern` |
| `generic` | All components → `generic` |
| `custom` (or an ID absent from the catalog) | All components → that stack |

The rest of the file (`topology`, `archetype`, `agents`, `test_command`, `docs`, `services`, `ai`, `finished`) is unchanged. A completed project stays completed: even if the topology now requires another component (for example, the frontend of a `fullstack-separated` project that previously had only `python-api`), onboarding does not reopen. `rapid setup next` proposes it only if you change the topology.

## What happens to other files

- `tech-stack.md` and `architecture.json` are untouched unless the decision changes. Older `tech-stack.md` files are interpreted by title (`PYTHON API`, `MODERN WEB`, and so on), and newer files use the `<!-- rapid-stack: backend=go -->` marker Rapid OS writes at the end of each block.
- The previous `architecture.json` fields (`modules_root`, `shared_root`, `public_entry`, `layers`, `domain_forbidden_imports`) continue to be read. New fields are optional: `roles`, `module_pattern`, `public_contract`, `public_policy`, `public_dirs`, `namespace_root`, `aliases`, `pure_layer`, `delegate`, `component`, `root`, and `rules` (multiple rules, one per component).
- Validation of existing projects (`RAPID404`) continues to accept the topologies associated with previous IDs.

## What changes when you make a new decision

`rapid setup set stack python-api` still works and sets `backend` to `python-fastapi` (and `ai` if the ID is for AI). For `fullstack-separated`, choose the frontend separately with `rapid setup set stack react-vite --component frontend`. Select a new catalog stack by its ID (`go`, `vue-vite`, and others); see [Stacks and Components](../concepts/stacks.md).
