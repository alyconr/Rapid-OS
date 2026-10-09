---
title: Solución de problemas de instalación
description: Diagnóstico y resolución de incidencias comunes al instalar y configurar Rapid OS.
---

# Solución de problemas de instalación

Esta guía recopila los errores más habituales reportados durante la instalación de Rapid OS y sus soluciones comprobadas.

---

## 1. El comando `rapid` no se reconoce (*command not found*)

### Causa
El alias o función de shell no se ha cargado en la sesión actual de la terminal, o el ejecutable no se encuentra en el `PATH`.

### Solución

- **En Windows (PowerShell):**
  Recarga tu perfil ejecutando:
  ```powershell
  . $PROFILE
  ```
  O comprueba si la función está presente en tu perfil:
  ```powershell
  Get-Content $PROFILE
  ```
  Si no está, puedes añadirla manualmente:
  ```powershell
  Add-Content -Path $PROFILE -Value "`nfunction rapid { python `"$HOME\.rapid-os\rapid.py`" `$args }"
  ```

- **En Linux / macOS / WSL:**
  Recarga la configuración de tu terminal:
  ```bash
  source ~/.bashrc   # En Linux o WSL
  source ~/.zshrc    # En macOS o zsh
  ```
  O comprueba que el alias esté presente en el archivo:
  ```bash
  grep "alias rapid=" ~/.bashrc
  ```

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
irm https://raw.githubusercontent.com/alyconr/Rapid-OS/v3.0.0/install.ps1 | iex
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
