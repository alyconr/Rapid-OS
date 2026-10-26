---
title: Mantener la documentación
description: Arquitectura de la documentación de Rapid OS y reglas para evitar drift entre producto, CLI y sitio.
---

# Mantener la documentación

La documentación pública de Rapid OS usa **Docusaurus** como capa de presentación y mantiene el contenido Markdown canónico en `docs/`.

## Estructura

```text
docs/                         # contenido canónico
website/
├── docusaurus.config.ts      # configuración del sitio
├── sidebars.ts               # arquitectura de navegación
├── src/css/custom.css        # tema
└── package.json              # dependencias y scripts
```

Docusaurus lee directamente `../docs`, por lo que no debe crearse una segunda copia de los mismos documentos dentro de `website/docs`.

## Regla de Product Truth

La documentación debe describir únicamente comportamiento verificable en el parser, dominio, tests o contratos del release.

Antes de documentar una capability nueva:

1. confirmar que existe en código;
2. confirmar comandos y flags reales;
3. confirmar si el comando es read-only o state-writing;
4. documentar archivos que crea o modifica;
5. documentar exit codes y diagnósticos relevantes;
6. diferenciar capacidad declarada, evidencia y veredicto;
7. ejecutar el build de Docusaurus.

## Desarrollo local

```bash
cd website
npm install
npm run start
```

## Build de producción

```bash
cd website
npm install
npm run build
```

Los broken links deben tratarse como errores de build.
