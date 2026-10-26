---
title: Rapid OS Installation
description: Installation options, platform compatibility, and recommended methods for Rapid OS v3.
---

# Rapid OS Installation

Rapid OS is distributed as a command-line tool (`rapid` or `python rapid.py`). Its governance core is implemented entirely in Python and has no mandatory external dependencies for basic operation.

## Choose an installation method

There are two main ways to install Rapid OS, depending on your workflow:

### 1. Quick installer by operating system (recommended)

The automated installers clone the repository to `~/.rapid-os`, pin a stable version, and install a `rapid` executable on your PATH. This is recommended when using shortcuts or hooks: agents can find `rapid` only when it is an executable on PATH, not an alias or a virtual environment activated in another terminal.

- [Windows installation](/installation/windows): PowerShell script for Windows 10/11.
- [Linux installation](/installation/linux): Bash script for Ubuntu, Debian, Fedora, Arch, and derivatives.
- [macOS installation](/installation/macos): Apple Silicon (M1/M2/M3/M4) and Intel.
- [WSL installation](/installation/wsl): guide for Windows Subsystem for Linux.

### 2. Install with `pip` in a virtual environment

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\\Scripts\\Activate.ps1
python -m pip install git+https://github.com/alyconr/Rapid-OS.git@v3.1.1
```

## User-wide shortcuts

Since version 3.2.0, `rapid shortcuts install --global --harness <id>` installs `/rapid-init` and other `/rapid-*` shortcuts once for all your projects (Claude Code, Codex, Cursor, and Antigravity; VS Code is not supported: `RAPID1413`). The installer offers this at the end if the installed `rapid` supports it. Stable version `v3.1.1` does not include this feature. See [Verification](/installation/verification); `RAPID1414` means `rapid` is not on PATH.

## Stable and development versions

:::info Installation channels
- **Stable (`v3.1.1`)**: pinned to the official [`v3.1.1` tag](https://github.com/alyconr/Rapid-OS/releases/tag/v3.1.1). Recommended for production and development teams.
- **Development (`main`)**: checked out from the actively developed `main` branch and includes the latest features before formal packaging.
:::

## Next steps

1. Review the [system requirements](/installation/requirements).
2. Follow the guide for your operating system.
3. [Verify the installation](/installation/verification) to ensure the CLI responds correctly.
4. Install shortcuts in your project with `rapid init --shortcuts` (or `rapid shortcuts install` in an initialized project), then follow [Getting Started](/getting-started).
