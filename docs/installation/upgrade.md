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
irm https://raw.githubusercontent.com/alyconr/Rapid-OS/v3.1.1/install.ps1 | iex
```

O de forma manual desde el directorio de instalación:
```powershell
git -C "$HOME\.rapid-os" fetch --tags --force origin
git -C "$HOME\.rapid-os" checkout --detach v3.1.1
```

### En Linux y macOS (Bash/Zsh)
```bash
curl -sL https://raw.githubusercontent.com/alyconr/Rapid-OS/v3.1.1/install.sh | bash
```

O de forma manual:
```bash
git -C "$HOME/.rapid-os" fetch --tags --force origin
git -C "$HOME/.rapid-os" checkout --detach v3.1.1
```

---

## 2. Actualización mediante `pip`

Si instalaste Rapid OS dentro de un entorno virtual:

```bash
# Activar entorno virtual
source .venv/bin/activate  # O en Windows: .venv\Scripts\Activate.ps1

# Actualizar el paquete desde el tag deseado
python -m pip install --upgrade git+https://github.com/alyconr/Rapid-OS.git@v3.1.1
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

---

## 5. De 3.0 a 3.1

Rapid OS 3.1 añade la capa de intención (`rapid start|next|check|…`), los shortcuts `/rapid-<modo>` y los hooks de Claude Code. Los comandos y flags de v3.0 no cambian y **no hay nada que migrar** en specs, runs, evidencia ni evaluaciones: los reportes de evaluación existentes (ruleset 1) siguen siendo válidos; el ruleset 2 es el predeterminado para evaluaciones nuevas y `--ruleset 1` sigue disponible.

1. Actualiza el paquete y comprueba la versión:
   ```bash
   python -m pip install --upgrade git+https://github.com/alyconr/Rapid-OS.git@v3.1.1
   rapid --version   # Rapid OS 3.1.1
   ```
2. Reinstala los shortcuts en cada proyecto (idempotente; los archivos modificados a mano se respaldan como `.bak`):
   ```bash
   rapid init --shortcuts          # proyecto nuevo o sin inicializar
   rapid shortcuts install         # proyecto ya inicializado
   ```
3. Opcional, solo Claude Code: añade los hooks con `--hooks` (`rapid shortcuts install --hooks` o `rapid init --hooks`).
4. Añade a `.gitignore` el estado local de la sesión:
   ```gitignore
   .rapid-os/session.json
   .rapid-os/scratch/
   ```
5. Define `test_command` en `.rapid-os/config.json` (por ejemplo `"python -m unittest discover"`); `rapid check` lo usa cuando no se le pasa un comando.
6. Verifica con `rapid doctor`.

Detalles y límites conocidos en las [notas de la release v3.1.1](../release-v3.1.1.md).
