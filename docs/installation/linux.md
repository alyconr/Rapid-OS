---
title: Instalación en Linux
description: Guía paso a paso para instalar y configurar Rapid OS en distribuciones Linux.
---

# Instalación en Linux

Esta guía describe cómo instalar y configurar Rapid OS v3 en distribuciones basadas en Linux (Ubuntu, Debian, Fedora, Arch Linux y derivados).

---

## 1. Prerrequisitos en Linux

Asegúrate de contar con Python 3.10+, el módulo `venv` y Git instalados mediante el gestor de paquetes de tu distribución:

### Ubuntu / Debian
```bash
sudo apt update
sudo apt install -y python3 python3-pip python3-venv git
```

### Fedora / RHEL
```bash
sudo dnf install -y python3 python3-pip git
```

### Arch Linux
```bash
sudo pacman -S python python-pip git
```

Verifica en tu terminal:
```bash
python3 --version
git --version
```

---

## 2. Método A: Instalador automático Shell (Recomendado)

El script de instalación clona el repositorio en `~/.rapid-os`, fija la versión estable `v3.1.1` e instala un ejecutable `rapid` en `~/.local/bin`:

```bash
curl -sL https://raw.githubusercontent.com/alyconr/Rapid-OS/v3.1.1/install.sh | bash
```

### ¿Qué realiza el instalador?
1. Verifica la existencia de `python3` (3.10+) y `git`.
2. Clona el repositorio en `$HOME/.rapid-os`.
3. Hace checkout seguro de la versión `v3.1.1`.
4. Crea un entorno de Python propio en `$HOME/.rapid-os/.venv` e instala Rapid OS en él (en Debian/Ubuntu necesita el paquete `python3-venv`).
5. Enlaza `~/.local/bin/rapid` a ese entorno y, si `~/.local/bin` no está en tu PATH, lo añade a `~/.bashrc` o `~/.zshrc`.
6. Si un instalador anterior dejó un `alias rapid=` en ese archivo, lo quita (con copia `.rapid-os.bak`).
7. Abre una terminal nueva, o ejecuta `source ~/.bashrc` (o `source ~/.zshrc`).

:::note Shortcuts globales (desde 3.2.0)
Al terminar, el instalador pregunta para qué agentes instalar los shortcuts en tu carpeta de usuario: escribe el tuyo (por ejemplo `claude`) y `/rapid-init`, `/rapid-feature` y el resto quedan disponibles en todos tus proyectos. Equivale a `rapid shortcuts install --global --harness <id>`, que puedes ejecutar después si te lo saltaste. Solo lo pregunta si el `rapid` instalado tiene `--global` y hay una terminal interactiva, y nunca instala nada sin tu respuesta. La versión estable actual (`v3.1.1`) no tiene `--global`, así que no lo pregunta; en ella instala los shortcuts en cada proyecto con `rapid init --shortcuts`.
:::

:::warning Shortcuts y hooks necesitan `rapid` en el PATH
Los agentes (Claude Code, Codex, Cursor...) y sus hooks ejecutan comandos en shells no interactivos, donde no existen los alias. Por eso `rapid` tiene que ser un ejecutable en el PATH de la terminal desde la que lanzas el agente. Compruébalo con `bash -c 'command -v rapid'`.
:::

:::warning No uses sudo pip install
No utilices `sudo pip install` para instalar paquetes en el sistema global. Utiliza el script instalador o un entorno virtual (`venv`).
:::

---

## 3. Método B: Instalación en Entorno Virtual (`venv`)

Si prefieres instalar Rapid OS mediante `pip` de forma aislada:

```bash
# 1. Crear entorno virtual
python3 -m venv ~/.venvs/rapid-env

# 2. Activar entorno virtual
source ~/.venvs/rapid-env/bin/activate

# 3. Instalar Rapid OS desde GitHub
pip install git+https://github.com/alyconr/Rapid-OS.git@v3.1.1

# 4. Comprobar instalación
rapid --version
```

Para acceder al comando sin activar el entorno cada vez, puedes crear un enlace simbólico en `~/.local/bin/`:
```bash
mkdir -p ~/.local/bin
ln -sf ~/.venvs/rapid-env/bin/rapid ~/.local/bin/rapid
```
(Asegúrate de que `~/.local/bin` esté incluido en tu variable `PATH`).

---

## 4. Método C: Instalación de Desarrollo

Para trabajar directamente sobre el código fuente de Rapid OS:

```bash
git clone https://github.com/alyconr/Rapid-OS.git
cd Rapid-OS
python3 -m pip install -e .
python3 rapid.py guide
```

---

## 5. Verificación

Ejecuta:

```bash
rapid --version
rapid doctor
```

Sigue hacia [Verificación de la instalación](./verification.md).

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
