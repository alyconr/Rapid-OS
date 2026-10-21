---
title: Documentos del proyecto y su procedencia
description: Cómo los documentos del onboarding llegan al agente con su procedencia visible, ya sean confirmados, supuestos u omitidos.
---

# Documentos del proyecto y su procedencia

El onboarding produce hasta cuatro documentos (brief, reglas de negocio, modelo de datos y arquitectura). Rapid OS no trata igual lo que una persona escribió, lo que redactó el agente y lo que se omitió: el agente recibe cada cosa **marcada como lo que es**.

> Rapid OS nunca marca como confirmado lo que la persona no confirmó.

## Qué documento cuenta

| Documento | Archivo | Fuente de contexto |
| :--- | :--- | :--- |
| `brief` | `docs/PRODUCT_BRIEF.md` | `doc.brief` |
| `business` | `docs/BUSINESS_RULES.md` | `doc.business` |
| `data-model` | `docs/DATA_MODEL.md` | `doc.data-model` |
| `architecture` | `docs/ARCHITECTURE.md` | `doc.architecture` |

Un archivo cuenta solo si su frontmatter incluye `rapid-doc: <id>` y `source: provided` o `source: drafted`. Un `docs/README.md` o un `docs/ARCHITECTURE.md` escrito a mano, sin ese frontmatter, no entra al contexto. El frontmatter nunca se inyecta: el agente ve solo el cuerpo.

```markdown
---
rapid-doc: brief
source: drafted
status: draft
sha256: <hash del cuerpo>
---
## Problema
...
```

## Tres estados de procedencia

| Estado | Cómo se reconoce | Qué ve el agente |
| :--- | :--- | :--- |
| Confirmado | `source: provided`, o `source: drafted` con `status: confirmed` | El cuerpo, sin banner: es una regla. |
| Supuesto | `source: drafted` con `status: draft` | El cuerpo bajo la línea `> Supuestos redactados por el agente, no confirmados por la persona.` |
| Omitido | `docs.<id>.status` es `skipped` en `.rapid-os/setup.json` | Una sola línea: `<título>: sin definir. Pregunta, no inventes.` |

La misma regla aplica en `rapid context` y en los archivos de agente (`CLAUDE.md`, `.cursorrules`, ...). Un borrador solo deja de ser supuesto cuando una persona lo confirma de forma explícita.

## Cómo se escriben

Los documentos los escribe Rapid OS, no el agente: el agente envía solo el **cuerpo** y `rapid setup doc` añade el frontmatter, calcula el `sha256` del cuerpo y guarda un `.bak` del archivo anterior.

```bash
# Lo redactó el agente: status: draft hasta que una persona lo confirme.
printf '%s' "$BODY" | rapid setup doc business --source drafted --file -
# Lo aportó la persona: se guarda tal cual, status: confirmed.
rapid setup doc business --source provided --file notas.md
# La persona revisó el borrador: solo cambia el status, el cuerpo no se toca.
rapid setup doc business --confirm
```

- Un borrador (`drafted`) debe traer todas las secciones requeridas y caber en `max_chars`; si no, `rapid setup doc` lo rechaza con `RAPID1403`/`RAPID1404` (exit 1, no se escribe nada). Lo que aporta la persona (`provided`) no se valida.
- Un borrador no reemplaza un documento que aportó una persona (ni un archivo escrito a mano) sin `--replace` (`RAPID1405`).
- `--skip` y `--reopen` registran que un documento no hace falta, o lo devuelven a pendiente; `--confirm` y `--reopen` también regeneran `CLAUDE.md`, `.cursorrules`, ... cuando el proyecto ya tiene estándares.
- Un proyecto anterior con `standards/business.md` lo importa con `rapid setup doc business --from-legacy` (como `provided`; el original no se borra).
- `rapid init` usa la misma lógica: cada documento se importa, se escribe en la terminal, se deja pendiente para el agente (`/rapid-init`) o se omite. Con `--yes` quedan pendientes.

## Confirmar o dejar como supuesto

Antes de cerrar el onboarding, Rapid OS no da por buenos los borradores del agente: `rapid setup next` devuelve `review_drafts` (después de resolver todos los documentos y antes de `finish`) con la lista de borradores sin confirmar, y la persona decide **documento por documento**. Cada opción tiene una consecuencia distinta:

| Decisión | Qué pasa |
| :--- | :--- |
| **Confirmar** (`rapid setup doc <id> --confirm`) | Pasa a ser una regla del proyecto: el agente la cumple en cada run sin cuestionarla. Puedes devolverla a borrador con `rapid setup doc <id> --reopen`. |
| **Dejar como supuesto** (no confirmar) | El agente la recibe bajo el aviso «Supuestos redactados por el agente, no confirmados por la persona», puede cuestionarla y preguntarte, y cada run te recuerda que está sin confirmar (`RAPID1408`). La confirmas cuando quieras con `rapid setup doc <id> --confirm`. |

El agente te resume cada borrador en pocas líneas y te pregunta por cada uno; ejecuta `--confirm` solo para los que confirmas de forma explícita, nunca a partir de un «ok» o un «continúa» genéricos. Si quieres cambiar algo antes, reescribe el borrador (`rapid setup doc <id> --source drafted --replace`) y vuelve a preguntar. Cuando terminas, `rapid setup review --done` cierra la revisión: lo que no confirmaste queda como borrador. Confirmar un documento no cierra la revisión (puedes confirmar varios y luego cerrarla), y `rapid setup finish` con la revisión pendiente falla con `RAPID1407` y te dice el siguiente comando.

Si un borrador nuevo aparece después de cerrar la revisión (el agente reescribe uno, o devuelves uno a borrador con `--reopen`), la revisión vuelve a estar pendiente hasta el siguiente `rapid setup review --done`. Un onboarding ya terminado no se reabre.

## Convivencia con `standards/business.md`

Si existen `standards/business.md` y `doc.business`, gana `doc.business`: el manifiesto de `rapid context` lista `standard.business` como omitido con la razón `superseded by doc.business`, y `rapid validate` avisa con `RAPID1410` cuando los cuerpos difieren (se comparan sin frontmatter y con los espacios normalizados). Si solo existe `standards/business.md`, nada cambia. Si el documento de negocio se omitió pero `standards/business.md` existe, el estándar sigue hablando por el negocio y no se agrega la línea de "pregunta, no inventes".

## Qué valida `rapid validate`

| Código | Nivel | Cuándo |
| :--- | :--- | :--- |
| `RAPID1400` | INFO | `.rapid-os/setup.json` existe y es válido. |
| `RAPID1406` | ERROR | `.rapid-os/setup.json` existe y no es válido. |
| `RAPID1408` | WARNING | Un documento redactado por el agente sigue sin confirmar (uno por documento). |
| `RAPID1403` | WARNING | Un documento redactado por el agente no tiene una sección requerida (un encabezado `## ` con cualquiera de sus títulos, sin distinguir mayúsculas). En `rapid setup doc` es un rechazo, no un aviso. |
| `RAPID1404` | WARNING | Un documento redactado por el agente supera `max_chars` de su banco. En `rapid setup doc` es un rechazo, no un aviso. |
| `RAPID1410` | WARNING | `standards/business.md` y `docs/BUSINESS_RULES.md` difieren. |

`RAPID1403` y `RAPID1404` solo se evalúan en documentos `drafted`: lo que la persona pegó no se valida. Detalle en [Diagnósticos](../troubleshooting/diagnostics.md).

## La única edición posterior: marcar una historia

Rapid OS no vuelve a editar el brief, con una excepción acotada: cuando `rapid finish` termina en PASS y la spec del run lleva el tag `story:<ID>` (por ejemplo `story:H001`), cambia en la sección `## Historias` (o su alias) solo la línea `- [ ] H001:` a `- [x] H001:`. Antes copia el brief a `.rapid-os/backups/`, actualiza el `sha256` del frontmatter y regenera los archivos de agente; `source` y `status` no cambian, así que un borrador sigue siendo borrador y sigue entrando al contexto como supuesto. Un brief sin frontmatter `rapid-doc`, una historia ya marcada o inexistente, un veredicto distinto de PASS y `rapid finish --no-tick` no cambian nada.
