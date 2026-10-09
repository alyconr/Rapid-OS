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

El script de instalación clona el repositorio en `~/.rapid-os`, fija la versión estable `v3.0.0` y añade un alias seguro en tu archivo `~/.bashrc` o `~/.zshrc`:

```bash
curl -sL https://raw.githubusercontent.com/alyconr/Rapid-OS/v3.0.0/install.sh | bash
```

### ¿Qué realiza el instalador?
1. Verifica la existencia de `python3` (3.10+) y `git`.
2. Clona el repositorio en `$HOME/.rapid-os`.
3. Hace checkout seguro de la versión `v3.0.0`.
4. Asigna permisos de ejecución a `rapid.py`.
5. Agrega el alias a tu archivo de inicio de shell (`~/.bashrc` o `~/.zshrc`):
   ```bash
   alias rapid='python3 "$HOME/.rapid-os/rapid.py"'
   ```
6. Aplica los cambios inmediatamente o ejecuta:
   ```bash
   source ~/.bashrc   # o source ~/.zshrc
   ```

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
pip install git+https://github.com/alyconr/Rapid-OS.git@v3.0.0

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
