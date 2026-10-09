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

El instalador oficial descarga el repositorio en `$HOME\.rapid-os`, fija la versión estable `v3.0.0` y registra la función `rapid` en tu perfil de PowerShell (`$PROFILE`):

```powershell
irm https://raw.githubusercontent.com/alyconr/Rapid-OS/v3.0.0/install.ps1 | iex
```

### ¿Qué hace este script?
1. Comprueba que `git` y `python` estén disponibles.
2. Clona el repositorio oficial en `$HOME\.rapid-os`.
3. Hace checkout de la versión estable `v3.0.0`.
4. Añade a tu archivo de perfil `$PROFILE` la función:
   ```powershell
   function rapid { python "$InstallDir\rapid.py" $args }
   ```
5. Tras completarse, recarga tu perfil ejecutando:
   ```powershell
   . $PROFILE
   ```
   O simplemente reinicia tu ventana de PowerShell.

:::tip Política de ejecución de PowerShell
Si PowerShell muestra el error `Running scripts is disabled on this system`, ajusta la política de ejecución del usuario actual:
```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```
:::

---

## 3. Método B: Instalación en un Entorno Virtual de Python (`venv`)

Si prefieres aislar Rapid OS dentro de un entorno virtual de desarrollo:

```powershell
# 1. Crear el entorno virtual
python -m venv rapid-env

# 2. Activar el entorno virtual
.\rapid-env\Scripts\Activate.ps1

# 3. Instalar la versión estable desde GitHub
python -m pip install git+https://github.com/alyconr/Rapid-OS.git@v3.0.0

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
