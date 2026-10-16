---
title: Verificación de la instalación
description: Comandos oficiales para comprobar la correcta instalación y funcionamiento de Rapid OS.
---

# Verificación de la instalación

Una vez instalado Rapid OS en tu sistema, ejecuta los siguientes comandos para validar que el CLI responde correctamente y que tu entorno está listo para gobernar proyectos.

---

## 1. Versión del producto (`rapid --version`)

Verifica la versión instalada:

```bash
rapid --version
```

**Resultado esperado:**
```text
Rapid OS 3.1.0
```

Si este comando no responde o indica que la orden no fue encontrada, consulta la guía de [Solución de problemas](../troubleshooting/installation.md).

---

## 2. Ayuda general (`rapid --help`)

Comprueba que el parser de argumentos y los subcomandos principales estén disponibles:

```bash
rapid --help
```

**Resultado esperado:**
Un listado con la descripción de Rapid OS y los comandos disponibles (`init`, `scan`, `context`, `spec`, `policy`, `run`, `harness`, `evidence`, `eval`, `validate`, `doctor`, `guide`, etc.).

---

## 3. Guía rápida de flujo (`rapid guide`)

Rapid OS incluye una guía interactiva y de solo lectura que describe el flujo de 8 pasos del ciclo de gobernanza:

```bash
rapid guide
```

**Resultado esperado:**
Un resumen visual en terminal que muestra el ciclo de gobernanza v3 y clasifica qué comandos son de **solo lectura** (*Read-only*) y cuáles **escriben estado** (*Writes*).

---

## 4. Diagnóstico del entorno (`rapid doctor`)

Inspecciona la configuración del entorno, la ubicación de templates y las herramientas disponibles:

```bash
rapid doctor
```

**Resultado esperado:**
```text
==> Rapid OS Doctor

Configuration:
  Project config: .rapid-os/config.json (Not found - run 'rapid init')
  Rapid home:     /home/<usuario>/.rapid-os

Environment:
  Node.js:        Available (v20.x.x)  # O Not installed (opcional)
  npx:            Available            # O Not installed (opcional)
  Python:         3.12.x

Templates:
  Bundled:        Available (stacks, archetypes, topologies)

Status: OK (Warnings: 0, Errors: 0)
```

:::note Project config no encontrado es normal aquí
Si ejecutas `rapid doctor` fuera de un proyecto inicializado con Rapid OS, es completamente normal que indique `Project config: .rapid-os/config.json (Not found - run 'rapid init')`. Esto simplemente confirma que el directorio actual no tiene aún gobernanza activa.
:::

---

## 5. Shortcuts instalados (`rapid shortcuts list`)

Dentro de un proyecto donde ejecutaste `rapid init --shortcuts` (o `rapid shortcuts install`), comprueba el estado de cada archivo generado:

```bash
rapid shortcuts list
```

**Resultado esperado:** los shortcuts de tus harness en estado `installed`. Si alguno aparece como `outdated` (tras actualizar Rapid OS), ejecuta `rapid shortcuts install`; si aparece `missing`, instálalo. Con `--json` obtienes el mismo estado para scripts. Si seleccionaste Cursor o VS Code junto con Claude, Codex o Antigravity verás `WARNING RAPID1321`: es solo un aviso de carpetas solapadas (ver [Si combinas harnesses](../guides/shortcuts.md#si-combinas-harnesses)).

---

## 6. Diagnóstico dentro del proyecto (`rapid doctor`)

Con el proyecto inicializado, `rapid doctor` revisa también la capa porcelain. Dos avisos son esperables y no indican un fallo de instalación:

- **`RAPID1319`**: no se pudo leer el árbol de procesos, así que `rapid approve` no puede comprobar si lo lanza un agente. Aprobar sigue exigiendo una terminal interactiva.
- **`RAPID1339`**: hay hooks de Claude Code instalados pero `rapid` no se resuelve en el `PATH` que ve Claude Code. Instala Rapid OS donde lo vea (por ejemplo `pipx install rapid-os`) o añade su directorio de scripts al `PATH`; si no usas hooks, no aparece.

---

## Todo listo

Si los comandos respondieron con éxito, tu instalación es correcta y reproducible. Ahora puedes avanzar a [Primeros pasos](../getting-started.md) o al tutorial: **[Tu primer proyecto gobernado](../getting-started/first-project.md)**.
