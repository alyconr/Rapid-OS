---
title: Install on Linux
description: Step-by-step guide to installing and configuring Rapid OS on Linux distributions.
---

# Install on Linux

This guide explains how to install and configure Rapid OS v3 on Linux distributions based on Ubuntu, Debian, Fedora, Arch Linux, and their derivatives.

## 1. Linux prerequisites

Install Python 3.10+, the `venv` module, and Git with your distribution's package manager:

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

Verify in your terminal:
```bash
python3 --version
git --version
```

## 2. Method A: Shell installer (recommended)

The installer clones the repository into `~/.rapid-os`, pins stable version `v3.1.1`, and installs a `rapid` executable in `~/.local/bin`:

```bash
curl -sL https://raw.githubusercontent.com/alyconr/Rapid-OS/v3.1.1/install.sh | bash
```

### What does the installer do?
1. Checks for `python3` (3.10+) and `git`.
2. Clones the repository into `$HOME/.rapid-os`.
3. Checks out stable version `v3.1.1`.
4. Creates a dedicated Python environment in `$HOME/.rapid-os/.venv` and installs Rapid OS into it (Debian/Ubuntu also requires the `python3-venv` package).
5. Links `~/.local/bin/rapid` to that environment and adds `~/.local/bin` to `~/.bashrc` or `~/.zshrc` if it is not already on PATH.
6. Removes an `alias rapid=` left in that file by an older installer, saving a `.rapid-os.bak` copy.
7. Open a new terminal, or run `source ~/.bashrc` (or `source ~/.zshrc`).

:::note Global shortcuts (since 3.2.0)
At the end, the installer asks which agents should receive shortcuts in your user directory. Enter yours (for example, `claude`) to make `/rapid-init`, `/rapid-feature`, and the other shortcuts available across projects. This is equivalent to `rapid shortcuts install --global --harness <id>`. The prompt appears only when the installed `rapid` supports `--global` and the terminal is interactive; nothing is installed without your response. Stable version `v3.1.1` does not support `--global`, so it does not prompt; install shortcuts in each project with `rapid init --shortcuts` instead.
:::

:::warning Shortcuts and hooks need `rapid` on PATH
Agents (Claude Code, Codex, Cursor, and others) and their hooks run commands in non-interactive shells, where aliases are unavailable. `rapid` must be an executable on the PATH of the terminal from which you launch the agent. Check with `bash -c 'command -v rapid'`.
:::

:::warning Do not use sudo pip install
Do not use `sudo pip install` to install packages globally. Use the installer script or a virtual environment (`venv`).
:::

## 3. Method B: Install in a virtual environment (`venv`)

To install Rapid OS with `pip` in an isolated environment:

```bash
# 1. Create the virtual environment
python3 -m venv ~/.venvs/rapid-env

# 2. Activate it
source ~/.venvs/rapid-env/bin/activate

# 3. Install Rapid OS from GitHub
pip install git+https://github.com/alyconr/Rapid-OS.git@v3.1.1

# 4. Check the installation
rapid --version
```

To use `rapid` without activating the environment each time, create a symbolic link in `~/.local/bin/`:
```bash
mkdir -p ~/.local/bin
ln -sf ~/.venvs/rapid-env/bin/rapid ~/.local/bin/rapid
```
Make sure `~/.local/bin` is on your `PATH`.

## 4. Method C: Development install

To work directly on the Rapid OS source code:
```bash
git clone https://github.com/alyconr/Rapid-OS.git
cd Rapid-OS
python3 -m pip install -e .
python3 rapid.py guide
```

## 5. Verify

Run:
```bash
rapid --version
rapid doctor
```

Continue to [Verify the Installation](./verification.md).

## 6. Start using shortcuts

If you selected your agent in the installer's final prompt, open it in your project folder and enter:
```text
/rapid-init
```

If you skipped the prompt, run `rapid shortcuts install --global --harness claude` once (replace `claude` with your agent). With VS Code, stable version `v3.1.1`, or if you want to version shortcuts with the repository, install them at the project root:
```bash
rapid init --shortcuts
```

Then enter `/rapid-feature <goal>` in your agent. See the [shortcuts guide](../guides/shortcuts.md) and [Getting Started](../getting-started.md).
