---
title: Instalación en macOS
description: Guía paso a paso para instalar y configurar Rapid OS en macOS con Apple Silicon o Intel.
---

# Instalación en macOS

Esta guía cubre la instalación de Rapid OS v3 en macOS (Sonoma, Ventura, Monterey o superior), tanto para arquitectura Apple Silicon (M1/M2/M3/M4) como procesadores Intel.

---

## 1. Prerrequisitos en macOS

macOS incluye una versión básica de Python para el sistema que no debe modificarse. Se recomienda instalar una versión moderna de Python y Git mediante [Homebrew](https://brew.sh/):

```bash
# 1. Instalar Homebrew si no lo tienes
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

# 2. Instalar Python 3.12 y Git
brew install python@3.12 git
```

Comprueba que el Python de Homebrew esté activo:
```bash
python3 --version
git --version
```

---

## 2. Método A: Instalador automático Shell (Recomendado)

Abre la aplicación Terminal y ejecuta:

```bash
curl -sL https://raw.githubusercontent.com/alyconr/Rapid-OS/v3.1.1/install.sh | bash
```

### Comportamiento del script en macOS:
- Descarga el repositorio en `~/.rapid-os`.
- Fija la versión estable `v3.1.1`.
- Crea un entorno de Python propio en `~/.rapid-os/.venv`, instala Rapid OS en él y enlaza el ejecutable en `~/.local/bin/rapid`.
- Si `~/.local/bin` no está en tu PATH, lo añade a `~/.zshrc` (el shell por defecto de macOS), y quita el `alias rapid=` de instaladores anteriores.
- Abre una terminal nueva, o ejecuta `source ~/.zshrc`.

:::note Shortcuts globales (desde 3.2.0)
Al terminar, el instalador pregunta para qué agentes instalar los shortcuts en tu carpeta de usuario: escribe el tuyo (por ejemplo `claude`) y `/rapid-init`, `/rapid-feature` y el resto quedan disponibles en todos tus proyectos. Equivale a `rapid shortcuts install --global --harness <id>`, que puedes ejecutar después si te lo saltaste. Solo lo pregunta si el `rapid` instalado tiene `--global` y hay una terminal interactiva, y nunca instala nada sin tu respuesta. La versión estable actual (`v3.1.1`) no tiene `--global`, así que no lo pregunta; en ella instala los shortcuts en cada proyecto con `rapid init --shortcuts`.
:::

:::warning Shortcuts y hooks necesitan `rapid` en el PATH
Los agentes y sus hooks no ven alias de shell: lanza tu agente desde una terminal donde `rapid --version` funcione.
:::

---

## 3. Método B: Instalación en un Entorno Virtual (`venv`)

Para mantener Rapid OS encapsulado en un entorno virtual propio:

```bash
# 1. Crear entorno virtual
python3 -m venv ~/.virtualenvs/rapid-env

# 2. Activar entorno virtual
source ~/.virtualenvs/rapid-env/bin/activate

# 3. Instalar la versión estable
pip install git+https://github.com/alyconr/Rapid-OS.git@v3.1.1

# 4. Probar
rapid --version
```

Para disponer de `rapid` en cualquier terminal sin activar el venv:
```bash
mkdir -p ~/.local/bin
ln -sf ~/.virtualenvs/rapid-env/bin/rapid ~/.local/bin/rapid
```
Y añade `export PATH="$HOME/.local/bin:$PATH"` a tu archivo `~/.zshrc` si no estaba presente.

---

## 4. Método C: Instalación de Desarrollo

Si estás contribuyendo a Rapid OS:

```bash
git clone https://github.com/alyconr/Rapid-OS.git
cd Rapid-OS
python3 -m pip install -e .
python3 rapid.py doctor
```

---

## 5. Verificación

```bash
rapid --version
rapid doctor
```

Continúa a [Verificación de la instalación](./verification.md).

---

## 6. Empieza a usar los shortcuts

Si respondiste con tu agente a la pregunta final del instalador, ya está: abre tu agente en la carpeta de tu proyecto y escribe:

```text
/rapid-init
```

Si te la saltaste, una sola vez: `rapid shortcuts install --global --harness claude` (cambia `claude` por tu agente). En VS Code, en la versión `v3.1.1`, o si prefieres versionar los shortcuts con el repositorio, instálalos en la raíz del proyecto:

```bash
rapid init --shortcuts
```

Después, en tu agente: `/rapid-feature <objetivo>`. Detalle en la [guía de shortcuts](../guides/shortcuts.md) y en [Primeros pasos](../getting-started.md).
