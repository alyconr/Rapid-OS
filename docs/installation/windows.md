---
title: Instalación en Windows
description: Guía paso a paso para instalar y configurar Rapid OS en Windows 10 y 11 con PowerShell.
---

# Instalación en Windows

Esta guía detalla la instalación de Rapid OS v3 en entornos Windows 10 y Windows 11 utilizando PowerShell.

---

## 1. Prerrequisitos en Windows

Asegúrate de contar con Python y Git instalados y registrados en las variables de entorno del sistema (`PATH`):

1. **Python 3.10+:** Descárgalo desde [python.org](https://www.python.org/downloads/windows/). Durante la instalación, marca la casilla **"Add python.exe to PATH"**.
2. **Git for Windows:** Descárgalo desde [git-scm.com](https://git-scm.com/download/win).
3. **PowerShell:** Abre Windows PowerShell o PowerShell 7.

Verifica en tu consola:

```powershell
python --version
git --version
```

---

## 2. Método A: Instalador automático de PowerShell (Recomendado)

El instalador oficial descarga el repositorio en `$HOME\.rapid-os`, fija la versión estable `v3.1.1` e instala un ejecutable `rapid.exe` en tu PATH de usuario:

```powershell
irm https://raw.githubusercontent.com/alyconr/Rapid-OS/v3.1.1/install.ps1 | iex
```

### ¿Qué hace este script?
1. Comprueba que `git` y `python` (3.10+) estén disponibles.
2. Clona el repositorio oficial en `$HOME\.rapid-os`.
3. Hace checkout de la versión estable `v3.1.1`.
4. Crea un entorno de Python propio en `$HOME\.rapid-os\.venv` e instala Rapid OS en él.
5. Copia `rapid.exe` a `$HOME\.rapid-os\bin` y añade esa carpeta a tu PATH de usuario. Solo `rapid.exe` queda en el PATH: el `python.exe` del entorno no reemplaza al tuyo.
6. Si un instalador anterior dejó una función `rapid` en tu `$PROFILE`, la quita (con copia `.rapid-os.bak`).
7. Abre una ventana nueva de PowerShell para que tome el PATH.

:::note `/rapid-init` global (desde 3.2.0)
Al terminar, el instalador puede ofrecer `/rapid-init` en tu carpeta de usuario (`rapid shortcuts install --global --only rapid-init --harness <id>`), para que funcione en cualquier proyecto sin instalarlo en cada uno. Solo lo ofrece si el `rapid` instalado tiene `--global` y hay una terminal interactiva, y nunca por defecto. La versión estable actual (`v3.1.1`) no tiene `--global`, así que no lo ofrece; en ella instala el shortcut en cada proyecto con `rapid init --shortcuts`.
:::

:::warning Shortcuts y hooks necesitan `rapid` en el PATH
Claude Code ejecuta los comandos de los shortcuts y los hooks en Git Bash, no en PowerShell. Por eso `rapid` tiene que ser un ejecutable en el PATH: una función de PowerShell o un `rapid` dentro de un `venv` activado solo en tu terminal no le llegan al agente. El instalador (Método A) y `pipx` lo resuelven; compruébalo dentro de Claude Code con `! which rapid`.
:::

:::tip Política de ejecución de PowerShell
Si PowerShell muestra el error `Running scripts is disabled on this system`, ajusta la política de ejecución del usuario actual:
```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```
:::

---

## 3. Método B: Instalación en un Entorno Virtual de Python (`venv`)

Si prefieres aislar Rapid OS dentro de un entorno virtual de desarrollo. Ten en cuenta que así `rapid` solo existe donde el `venv` está activado: para usar shortcuts y hooks con tu agente, usa el Método A o `pipx install git+https://github.com/alyconr/Rapid-OS.git@v3.1.1`.

```powershell
# 1. Crear el entorno virtual
python -m venv rapid-env

# 2. Activar el entorno virtual
.\rapid-env\Scripts\Activate.ps1

# 3. Instalar la versión estable desde GitHub
python -m pip install git+https://github.com/alyconr/Rapid-OS.git@v3.1.1

# 4. Verificar
rapid --version
```

---

## 4. Método C: Instalación desde el código fuente (Desarrollo)

Para trabajar sobre la rama `main` de desarrollo o contribuir a Rapid OS:

```powershell
git clone https://github.com/alyconr/Rapid-OS.git
cd Rapid-OS
python -m pip install -e .
python rapid.py guide
```

---

## 5. Verificación

Comprueba que el comando responda:

```powershell
rapid --version
rapid doctor
```

Continúa a la sección de [Verificación detallada](./verification.md).

---

## 6. Instalar los shortcuts en tu proyecto

Con `rapid` funcionando, ya puedes trabajar con shortcuts. Desde la raíz de tu repositorio:

```powershell
rapid init --shortcuts
```

Esto inicializa `.rapid-os/` y genera los `/rapid-*` para los agentes que elijas. En un proyecto ya inicializado usa `rapid shortcuts install`. Después, en tu agente: `/rapid-feature <objetivo>`. Detalle en la [guía de shortcuts](../guides/shortcuts.md) y en [Primeros pasos](../getting-started.md).
