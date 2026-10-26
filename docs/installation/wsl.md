---
title: Install on WSL (Windows Subsystem for Linux)
description: Installation guide and best practices for running Rapid OS in WSL 2 on Windows.
---

# Install on WSL (Windows Subsystem for Linux)

WSL 2 lets you run a full Linux environment directly on Windows. This guide explains how to install and run Rapid OS in WSL for better performance and compatibility.

## 1. Key WSL 2 considerations

:::tip Best location for your project
To avoid filesystem performance and permission issues between operating systems:
- **Recommended:** Clone and run projects inside the native Linux filesystem (for example, `/home/user/projects/`).
- **Avoid:** Working in mounted Windows directories (`/mnt/c/...`) for governed projects because filesystem latency is significantly higher.
:::

## 2. Prerequisites in WSL

Open your WSL terminal (for example, Ubuntu on WSL) and update the basic packages:

```bash
sudo apt update
sudo apt install -y python3 python3-pip python3-venv git
```

Check the installed versions:
```bash
python3 --version
git --version
```

## 3. Install Rapid OS in WSL

In your WSL shell, run the Linux installation script:

```bash
curl -sL https://raw.githubusercontent.com/alyconr/Rapid-OS/v3.1.1/install.sh | bash
```

When it finishes, refresh the shell session:
```bash
source ~/.bashrc
```

Check the command:
```bash
rapid --version
```

Then install shortcuts once for all your projects with `rapid shortcuts install --global --harness claude` (replace `claude` with your agent; available since 3.2.0). With version `v3.1.1`, or if you want to version shortcuts with the repository, run `rapid init --shortcuts` at the project root inside WSL. See the [shortcuts guide](../guides/shortcuts.md).

## 4. Native Windows and WSL differences

| Aspect | Native Windows (PowerShell) | WSL 2 (Bash/Zsh) |
| :--- | :--- | :--- |
| **Installation path** | `C:\Users\<user>\.rapid-os` | `/home/<user>/.rapid-os` |
| **Shell command** | `python "$HOME\.rapid-os\rapid.py"` | `python3 "$HOME/.rapid-os/rapid.py"` |
| **Path separator** | `\` (backslash) | `/` (slash) |
| **Coding harnesses** | VS Code on Windows, Cursor on Windows | VS Code in Remote-WSL mode |

When you use VS Code or Cursor with the **WSL Remote** extension, the coding harness runs inside WSL and can directly access the `rapid` command installed in Linux.
