---
title: Solución de problemas de instalación
description: Diagnóstico y resolución de incidencias comunes al instalar y configurar Rapid OS.
---

# Solución de problemas de instalación

Esta guía recopila los errores más habituales reportados durante la instalación de Rapid OS y sus soluciones comprobadas.

---

## 1. El comando `rapid` no se reconoce (*command not found*)

### Causa
Desde la v3.1.1 los instaladores dejan un ejecutable `rapid` en el `PATH` (`~/.local/bin/rapid` en Linux/macOS/WSL, `$HOME\.rapid-os\bin\rapid.exe` en Windows). Si no se reconoce, la terminal se abrió antes de la instalación o esa carpeta no está en el `PATH`.

### Solución

- **En Windows (PowerShell):** abre una ventana nueva y comprueba:
  ```powershell
  Get-Command rapid                                   # ...\.rapid-os\bin\rapid.exe
  [Environment]::GetEnvironmentVariable("Path", "User") -split ";" | Select-String rapid-os
  ```
  Si la carpeta no aparece, vuelve a ejecutar el instalador.

- **En Linux / macOS / WSL:** abre una terminal nueva (o `source ~/.bashrc` / `source ~/.zshrc`) y comprueba:
  ```bash
  command -v rapid        # ~/.local/bin/rapid
  ls -l ~/.local/bin/rapid
  ```

---

## 1.1. `rapid` funciona en tu terminal pero no dentro del agente (*rapid: command not found* en un shortcut o hook)

### Síntoma
Un shortcut como `/rapid-feature` falla en su primer paso con `rapid: command not found`, o un hook de Claude Code no encuentra `rapid`.

### Causa
El agente ejecuta comandos en su propio shell no interactivo (Claude Code usa Git Bash en Windows). Ese shell no ve alias, funciones de `$PROFILE` ni un `venv` activado solo en tu terminal. Los instaladores anteriores a v3.1.1 configuraban un alias o una función, que tiene este problema.

### Solución
1. Instala con el instalador v3.1.1 o con `pipx install git+https://github.com/alyconr/Rapid-OS.git@v3.1.1`.
2. Abre una terminal nueva, comprueba `rapid --version` y lanza el agente desde ella.
3. Dentro de Claude Code, `! which rapid` debe encontrarlo.

---

## 2. Error de política de ejecución en PowerShell (*ExecutionPolicy*)

### Síntoma
```text
File ...\install.ps1 cannot be loaded because running scripts is disabled on this system.
```

### Solución
Windows bloquea por defecto la ejecución de scripts remotos en PowerShell. Habilita `RemoteSigned` para tu usuario actual (no requiere permisos de Administrador):

```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

Luego vuelve a ejecutar el instalador:
```powershell
irm https://raw.githubusercontent.com/alyconr/Rapid-OS/v3.1.1/install.ps1 | iex
```

---

## 3. Versión de Python incompatible (< 3.10)

### Síntoma
El instalador o el CLI arrojan errores de sintaxis (`SyntaxError`) o el instalador cancela con:
```text
Error: Python 3 is not installed. Please install Python 3.10+ first.
```

### Solución
Rapid OS requiere Python 3.10 como versión mínima para el tipado estático y coincidencia de patrones.
1. Instala Python 3.10, 3.11, 3.12 o 3.13 desde [python.org](https://www.python.org/).
2. En Windows, asegúrate de marcar **"Add python.exe to PATH"**.
3. En Linux, instala `python3` actualizado desde el gestor de paquetes de tu distribución.

---

## 4. Conflictos al clonar en `$HOME/.rapid-os`

### Síntoma
```text
Error: .../.rapid-os already exists and is not a Git repository.
```

### Solución
Si ya tenías una carpeta antigua no versionada con ese nombre:
1. Respalda o renombra la carpeta:
   ```bash
   mv ~/.rapid-os ~/.rapid-os.bak
   ```
2. Vuelve a ejecutar el instalador.

---

## 5. El comando `rapid doctor` reporta advertencias

Ejecuta `rapid doctor --json` para obtener un diagnóstico estructurado con el código de advertencia exacto (`TOOLxxx`, `CONFIGxxx`, etc.). La mayoría de advertencias indican herramientas opcionales faltantes (como Node.js/npx para skills remotas) que no afectan el ciclo de gobernanza principal.
