---
title: Actualización de Rapid OS
description: Cómo actualizar tu instalación de Rapid OS a nuevas versiones estables.
---

# Actualización de Rapid OS

Mantener actualizada tu instalación de Rapid OS te permite acceder a nuevas reglas de escaneo, mejoras de rendimiento y diagnósticos actualizados.

---

## 1. Actualización con el instalador oficial

Si instalaste Rapid OS mediante el script oficial en `$HOME/.rapid-os`:

### En Windows (PowerShell)
Vuelve a ejecutar el instalador oficial. El script detectará la carpeta existente y actualizará las etiquetas de Git:
```powershell
irm https://raw.githubusercontent.com/alyconr/Rapid-OS/v3.0.0/install.ps1 | iex
```

O de forma manual desde el directorio de instalación:
```powershell
git -C "$HOME\.rapid-os" fetch --tags --force origin
git -C "$HOME\.rapid-os" checkout --detach v3.0.0
```

### En Linux y macOS (Bash/Zsh)
```bash
curl -sL https://raw.githubusercontent.com/alyconr/Rapid-OS/v3.0.0/install.sh | bash
```

O de forma manual:
```bash
git -C "$HOME/.rapid-os" fetch --tags --force origin
git -C "$HOME/.rapid-os" checkout --detach v3.0.0
```

---

## 2. Actualización mediante `pip`

Si instalaste Rapid OS dentro de un entorno virtual:

```bash
# Activar entorno virtual
source .venv/bin/activate  # O en Windows: .venv\Scripts\Activate.ps1

# Actualizar el paquete desde el tag deseado
python -m pip install --upgrade git+https://github.com/alyconr/Rapid-OS.git@v3.0.0
```

---

## 3. Actualización de instalación de desarrollo

Si utilizas un clon local en modo editable (`pip install -e .`):

```bash
cd Rapid-OS
git pull origin main
rapid doctor
```

---

## 4. Verificación post-actualización

Tras actualizar, comprueba que la versión sea la esperada y que el diagnóstico no reporte anomalías:

```bash
rapid --version
rapid doctor
```
