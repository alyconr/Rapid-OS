---
title: Sprint 1 — Validación de la base documental
description: Registro de auditoría y requisitos para cerrar el primer sprint de Docusaurus.
---

# Sprint 1 — Validación de la base documental

## Objetivo y alcance

Consolidar el portal Docusaurus sin alterar las capacidades del núcleo Python de Rapid OS. Este documento registra criterios verificables, evidencia y límites de la auditoría inicial.

### Baseline

- Producto: Rapid OS v3.0.0, release-readiness PR #33.
- Documentación: PR #34, rama `docs/docusaurus-v3`.
- Fuente canónica: `docs/`.
- Aplicación del sitio: `website/`.
- Documentación funcional existente: `docs/cli.md`, `docs/governance-loop.md`, `docs/architecture/rapid-os-v3.md` y guías de release.

## Controles implementados

| Control | Evidencia esperada |
| --- | --- |
| Fuente de contenido única | `docs.path = '../docs'`, sin `website/docs/` |
| Navegación válida | Todos los IDs del sidebar corresponden a archivos Markdown |
| Enlaces internos | Docusaurus `onBrokenLinks: 'throw'` y build del sitio |
| Contrato CLI y fronteras del producto | `tests/test_documentation_contract.py` |
| Compatibilidad del núcleo | Workflow existente de tests Python |
| Compilación documental | Workflow Documentation: `npm run typecheck` y `npm run build` |
| Revisión de release | PR documental separado del PR de release |

## Brechas antes de publicar una versión estable del portal

1. **Lockfile reproducible**: generar y confirmar `website/package-lock.json` con npm, reemplazar `npm install` por `npm ci` y activar caché usando `website/package-lock.json`. No crear manualmente un lockfile sin resolución de dependencias.
2. **Validación en entorno limpio**: verificar build después de instalar con lockfile y repetir sobre el Node.js mínimo declarado.
3. **Pruebas de instalación de Rapid OS**: mantener independientes las pruebas de release Python/wheel/sdist y las del portal Docusaurus.
4. **Versión publicada y dominio**: el valor de `url`/ `baseUrl` representa la ruta prevista para GitHub Pages, no constituye evidencia de despliegue.
5. **Consistencia editorial**: la interfaz está en español, pero algunas referencias técnicas canónicas siguen en inglés; traducir progresivamente sin mantener copias divergentes.
6. **Auditoría de contenido detallada**: en sprints posteriores contrastar cada ejemplo avanzado contra parser, schema y pruebas, además del control estático mínimo.

## Definition of Done del Sprint 1

- [x] Sitio y contenido separados en `website/` y `docs/`.
- [x] Portal con navegación por objetivos del usuario.
- [x] Documentación del propósito, casos de uso, capacidades y límites del producto.
- [x] Workflow dedicado a typecheck y build.
- [x] Detección de enlaces internos rotos configurada.
- [x] Pruebas estáticas de contrato documental añadidas al repositorio.
- [ ] `website/package-lock.json` generado y validado por npm.
- [ ] CI con instalación reproducible `npm ci`.
- [ ] Validación final de la revisión más reciente de PR #34.

**Criterio de cierre:** no declarar Sprint 1 terminado hasta que todas las casillas estén verificadas en CI y el PR permanezca libre de regresiones.
