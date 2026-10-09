---
title: Gobernar un proyecto existente
description: Cómo adoptar Rapid OS en repositorios con código preexistente sin riesgo para el código de negocio.
---

# Gobernar un proyecto existente

Adoptar Rapid OS en un repositorio que ya se encuentra en producción o desarrollo activo es un proceso seguro y no invasivo. Rapid OS está diseñado para **analizar y gobernar sin modificar tu código de negocio**.

---

## 1. Localizar la raíz del repositorio

El CLI de Rapid OS opera siempre sobre el directorio de trabajo actual (`current working directory`). Posiciónate en la raíz del repositorio (donde reside el archivo `.git` o los archivos principales de configuración del proyecto):

```bash
cd /ruta/a/tu-proyecto-existente
```

---

## 2. Diagnóstico previo con `rapid doctor`

Ejecuta un chequeo inicial para comprobar el estado del entorno en ese directorio:

```bash
rapid doctor
```

Si el proyecto aún no tiene Rapid OS, reportará que `.rapid-os/config.json` no existe. Esto es esperado.

---

## 3. Escaneo en modo solo lectura (`rapid scan`)

Antes de crear cualquier archivo, ejecuta el escáner del proyecto:

```bash
rapid scan
```

O para ver la evidencia detallada de cada hecho detectado:

```bash
rapid scan --verbose
```

### ¿Qué analiza el escáner?
Rapid OS busca marcadores estándar del ecosistema de software:
- **Lenguajes y empaquetadores:** `pyproject.toml`, `package.json`, `Cargo.toml`, `go.mod`, `pom.xml`, etc.
- **Frameworks:** Django, FastAPI, Flask, React, Next.js, Vue, Spring, etc.
- **Testing:** `pytest`, `unittest`, `jest`, `vitest`, `mocha`, etc.
- **Contenedores y orquestación:** `Dockerfile`, `docker-compose.yml`.
- **Estructura:** Detección de monorepos (`pnpm-workspace.yaml`, `lerna.json`, carpetas de apps).

### ¿Qué NO lee el escáner (Seguridad de secretos)?
- **No analiza archivos de secretos:** Ignora automáticamente `.env`, archivos con claves privadas (`.pem`, `.key`), tokens y directorios ignorados como `.git`, `node_modules`, `venv`, `__pycache__` o `.docusaurus`.
- **No modifica código fuente:** `rapid scan` es **100% de solo lectura**.

---

## 4. Persistir la inteligencia del proyecto

Una vez que revises los hechos descubiertos, persiste la instantánea de inteligencia:

```bash
rapid scan --write
```

Esto crea exclusivamente `.rapid-os/project.json`, permitiendo que las etapas posteriores reutilicen la información sin volver a recorrer el árbol de archivos.

---

## 5. Inicializar gobernanza con `rapid init`

Para establecer los estándares del proyecto y los archivos de contexto para coding agents, ejecuta:

```bash
rapid init
```

### Protección de archivos existentes con `.bak`
Si tu proyecto ya cuenta con archivos como `.cursorrules`, `CLAUDE.md`, `INSTRUCTIONS.md` o `.rapid-os/config.json`:
- Rapid OS **no los elimina sin aviso**.
- Crea automáticamente un respaldo con extensión `.bak` (por ejemplo, `.cursorrules.bak`) antes de actualizar el contenido.
- Puedes inspeccionar la diferencia o fusionar tus reglas previas dentro de los nuevos archivos de estándares en `.rapid-os/standards/`.

---

## 6. Validación de integridad (`rapid validate`)

Verifica que la configuración y los estándares del proyecto sean coherentes:

```bash
rapid validate
```

Para activar una verificación estricta donde cualquier advertencia produzca un código de salida distinto de cero:

```bash
rapid validate --strict
```

### Cómo interpretar advertencias comunes
- `STD001–STD004`: Falta algún archivo estándar recomendado en `.rapid-os/standards/` (ej. `tech-stack.md` o `topology.md`).
- `CONFIG001–CONFIG004`: Inconsistencias menores en la configuración del proyecto.
- `RAPID600–RAPID604`: Discrepancias en la instantánea de Project Intelligence.

Una vez que `rapid validate` retorne código `0`, tu repositorio cuenta con una línea base de gobernanza verificada y está listo para recibir especificaciones y compilaciones de contexto.
