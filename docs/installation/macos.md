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
curl -sL https://raw.githubusercontent.com/alyconr/Rapid-OS/v3.0.0/install.sh | bash
```

### Comportamiento del script en macOS:
- Descarga el repositorio en `~/.rapid-os`.
- Fija la versión estable `v3.0.0`.
- Detecta automáticamente el shell por defecto de macOS (`zsh`) y escribe el alias en `~/.zshrc`:
  ```bash
  alias rapid='python3 "$HOME/.rapid-os/rapid.py"'
  ```
- Recarga tu configuración ejecutando:
  ```bash
  source ~/.zshrc
  ```

---

## 3. Método B: Instalación en un Entorno Virtual (`venv`)

Para mantener Rapid OS encapsulado en un entorno virtual propio:

```bash
# 1. Crear entorno virtual
python3 -m venv ~/.virtualenvs/rapid-env

# 2. Activar entorno virtual
source ~/.virtualenvs/rapid-env/bin/activate

# 3. Instalar la versión estable
pip install git+https://github.com/alyconr/Rapid-OS.git@v3.0.0

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
