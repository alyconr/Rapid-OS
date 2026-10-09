---
title: Auditoría de cobertura documental
description: Cobertura inicial de la documentación frente a las capacidades implementadas en Rapid OS v3.
---

# Auditoría de cobertura documental

Esta página resume la primera auditoría de documentación realizada sobre Rapid OS v3. Su propósito es mantener una relación explícita entre **producto implementado** y **producto documentado**.

## Baseline auditado

La primera versión del portal se construyó contra el estado de release de Rapid OS v3.0.0 que incluye:

- packaging PEP 517/518;
- CLI global `rapid`;
- compatibilidad v2;
- Project Intelligence;
- Context Compiler;
- Spec Registry;
- Execution Policy y Run Registry;
- Harness Capability Registry;
- Evidence Engine;
- Behavioral Evals;
- validación y diagnósticos;
- instaladores estables;
- matriz de CI Python 3.10–3.13.

## Cobertura por área

| Área implementada | Documento principal | Estado |
| --- | --- | --- |
| Propósito y límites del producto | [Qué es Rapid OS](../concepts/what-is-rapid-os) | Cubierto |
| Instalación y requisitos | [Getting Started](../getting-started) | Cubierto |
| Casos de uso | [Casos de uso](../guides/use-cases) | Cubierto |
| Flujo end-to-end | [Governance Loop](../governance-loop) | Cubierto |
| Project Intelligence | [Arquitectura v3](../architecture/rapid-os-v3) | Cubierto técnicamente |
| Context Compiler | [Arquitectura v3](../architecture/rapid-os-v3) | Cubierto técnicamente |
| Spec Registry | [CLI](../cli) + [Arquitectura v3](../architecture/rapid-os-v3) | Cubierto |
| Execution Policy / Runs | [CLI](../cli) + [Governance Loop](../governance-loop) | Cubierto |
| Harness profiles y capabilities | [Capabilities y permisos](../guides/permissions-capabilities) | Cubierto |
| Evidence Engine | [Governance Loop](../governance-loop) + [CLI](../cli) | Cubierto |
| Behavioral Evals | [Governance Loop](../governance-loop) + [CLI](../cli) | Cubierto |
| Estructura de archivos | [Estructura de archivos](../guides/project-layout) | Cubierto |
| Diagnósticos RAPIDxxx | [CLI](../cli) | Cubierto |
| Release v3.0.0 | [Release v3.0.0](../release-v3.0.0) | Cubierto |
| Release checklist | [Release checklist](../release-checklist) | Cubierto |
| Mantenimiento del portal | [Mantener la documentación](../contributing/documentation) | Cubierto |

## Hallazgos principales

### 1. La documentación existente era técnicamente rica, pero estaba orientada al repositorio

Los documentos de arquitectura y CLI describen bien contratos internos, diagnósticos y entidades, pero un usuario nuevo necesitaba una capa anterior que respondiera:

- qué es Rapid OS;
- para qué sirve;
- cuándo usarlo;
- qué no hace;
- cómo empezar;
- qué archivos modifica;
- cómo interpretar “permisos” y capabilities.

La nueva arquitectura de información cubre esa capa.

### 2. “Permisos” requería una definición de producto

Rapid OS no implementa un sistema de autorización del sistema operativo. El concepto equivalente dentro del producto es el **Harness Capability Registry**. La documentación separa ahora:

- capability declarada;
- compatibilidad del harness;
- requirement del contrato;
- evidencia observable;
- veredicto de evaluación.

### 3. La fuente documental debía ser única

El portal Docusaurus usa directamente `docs/` como fuente. No existe una segunda carpeta de contenido dentro de `website/`.

Esto reduce drift entre documentación visible en GitHub y documentación publicada.

### 4. El portal debe fallar cuando la documentación se rompe

La configuración usa broken links como error y el workflow de CI ejecuta:

```bash
npm ci
npm run typecheck
npm run build
```

Un PR que rompa navegación o compilación documental debe fallar antes de merge.

## Próxima cobertura recomendada

La siguiente iteración debería profundizar en tutoriales operativos, no solo referencia:

1. tutorial completo “primer proyecto gobernado”;
2. recetas por modo: feature, bugfix, refactor, hardening y research;
3. ejemplos completos de `evidence.json` por cada `EvidenceKind`;
4. cookbook de políticas `.rapid-os/policy.json`;
5. cookbook de `HarnessProfile`;
6. troubleshooting por diagnóstico `RAPIDxxx`;
7. integración CI/CD;
8. despliegue oficial del portal documental.
