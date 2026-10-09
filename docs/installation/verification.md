---
title: Verificación de la instalación
description: Comandos oficiales para comprobar la correcta instalación y funcionamiento de Rapid OS.
---

# Verificación de la instalación

Una vez instalado Rapid OS en tu sistema, ejecuta los siguientes cuatro comandos para validar que el CLI responde correctamente y que tu entorno está listo para gobernar proyectos.

---

## 1. Versión del producto (`rapid --version`)

Verifica la versión instalada:

```bash
rapid --version
```

**Resultado esperado:**
```text
Rapid OS 3.0.0
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

## Todo listo

Si los cuatro comandos respondieron con éxito, tu instalación es correcta y reproducible. Ahora puedes avanzar al tutorial: **[Tu primer proyecto gobernado](../getting-started/first-project.md)**.
