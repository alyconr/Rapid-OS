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
| Omitido | `docs.<id>.status` es `skipped` en `.rapid-os/setup.json` | Una sola línea: `No hay <título> definido: pregunta, no inventes.` |

La misma regla aplica en `rapid context` y en los archivos de agente (`CLAUDE.md`, `.cursorrules`, ...). Un borrador solo deja de ser supuesto cuando una persona lo confirma de forma explícita.

## Convivencia con `standards/business.md`

Si existen `standards/business.md` y `doc.business`, gana `doc.business`: el manifiesto de `rapid context` lista `standard.business` como omitido con la razón `superseded by doc.business`, y `rapid validate` avisa con `RAPID1410` cuando los cuerpos difieren (se comparan sin frontmatter y con los espacios normalizados). Si solo existe `standards/business.md`, nada cambia. Si el documento de negocio se omitió pero `standards/business.md` existe, el estándar sigue hablando por el negocio y no se agrega la línea de "pregunta, no inventes".

## Qué valida `rapid validate`

| Código | Nivel | Cuándo |
| :--- | :--- | :--- |
| `RAPID1400` | INFO | `.rapid-os/setup.json` existe y es válido. |
| `RAPID1406` | ERROR | `.rapid-os/setup.json` existe y no es válido. |
| `RAPID1408` | WARNING | Un documento redactado por el agente sigue sin confirmar. |
| `RAPID1403` | WARNING | Un documento redactado por el agente no tiene una sección requerida (un encabezado `## ` con cualquiera de sus títulos, sin distinguir mayúsculas). |
| `RAPID1404` | WARNING | Un documento redactado por el agente supera `max_chars` de su banco. |
| `RAPID1410` | WARNING | `standards/business.md` y `docs/BUSINESS_RULES.md` difieren. |

`RAPID1403` y `RAPID1404` solo se evalúan en documentos `drafted`: lo que la persona pegó no se valida. Detalle en [Diagnósticos](../troubleshooting/diagnostics.md).
