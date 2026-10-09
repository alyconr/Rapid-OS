---
title: Instalación en WSL (Windows Subsystem for Linux)
description: Guía de instalación y mejores prácticas para ejecutar Rapid OS dentro de WSL 2 en Windows.
---

# Instalación en WSL (Windows Subsystem for Linux)

WSL 2 te permite ejecutar un entorno completo de Linux directamente sobre Windows. Esta guía explica cómo instalar y ejecutar Rapid OS dentro de WSL para obtener el máximo rendimiento y compatibilidad.

---

## 1. Consideraciones clave de WSL 2

:::tip Ubicación óptima del proyecto
Para evitar problemas de rendimiento y permisos entre sistemas de archivos:
- **Recomendado:** Clona y ejecuta tus proyectos dentro del sistema de archivos nativo de Linux (ej. `/home/usuario/proyectos/`).
- **Evitar:** Trabajar en carpetas montadas de Windows (`/mnt/c/...`) para proyectos gobernados, ya que la latencia del sistema de archivos es significativamente mayor.
:::

---

## 2. Prerrequisitos dentro de WSL

Abre tu terminal de WSL (ej. Ubuntu en WSL) y actualiza los paquetes básicos:

```bash
sudo apt update
sudo apt install -y python3 python3-pip python3-venv git
```

Comprueba las versiones instaladas:
```bash
python3 --version
git --version
```

---

## 3. Instalación de Rapid OS en WSL

Dentro de tu shell de WSL, ejecuta el script de instalación para Linux:

```bash
curl -sL https://raw.githubusercontent.com/alyconr/Rapid-OS/v3.0.0/install.sh | bash
```

Una vez completado, actualiza la sesión de shell:
```bash
source ~/.bashrc
```

Comprueba el comando:
```bash
rapid --version
```

---

## 4. Diferencias entre Windows nativo y WSL

| Aspecto | Windows Nativo (PowerShell) | WSL 2 (Bash/Zsh) |
| :--- | :--- | :--- |
| **Ruta de instalación** | `C:\Users\<usuario>\.rapid-os` | `/home/<usuario>/.rapid-os` |
| **Comando de shell** | `python "$HOME\.rapid-os\rapid.py"` | `python3 "$HOME/.rapid-os/rapid.py"` |
| **Separador de rutas** | `\` (backslash) | `/` (slash) |
| **Coding Harnesses** | VS Code en Windows, Cursor en Windows | VS Code en modo Remote-WSL |

Si utilizas VS Code o Cursor con la extensión **WSL Remote**, el coding harness opera dentro de WSL y tendrá acceso directo al comando `rapid` instalado en Linux.
