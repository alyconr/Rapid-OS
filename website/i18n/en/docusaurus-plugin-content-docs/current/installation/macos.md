---
title: Install on macOS
description: Step-by-step guide to installing and configuring Rapid OS on Apple Silicon and Intel Macs.
---

# Install on macOS

This guide covers installing Rapid OS v3 on macOS (Sonoma, Ventura, Monterey, or later) on both Apple Silicon (M1/M2/M3/M4) and Intel processors.

## 1. macOS prerequisites

macOS includes a basic system Python version that you should not modify. We recommend installing a current version of Python and Git with [Homebrew](https://brew.sh/):

```bash
# 1. Install Homebrew if you do not have it
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

# 2. Install Python 3.12 and Git
brew install python@3.12 git
```

Check that the Homebrew Python is active:
```bash
python3 --version
git --version
```

## 2. Method A: Shell installer (recommended)

Open Terminal and run:

```bash
curl -sL https://raw.githubusercontent.com/alyconr/Rapid-OS/v3.1.1/install.sh | bash
```

### What the script does on macOS
- Downloads the repository to `~/.rapid-os`.
- Pins stable version `v3.1.1`.
- Creates a dedicated Python environment in `~/.rapid-os/.venv`, installs Rapid OS into it, and links the executable at `~/.local/bin/rapid`.
- Adds `~/.local/bin` to `~/.zshrc` (the default macOS shell) if needed, and removes a `rapid` alias left by older installers.
- Opens a new terminal, or run `source ~/.zshrc`.

:::note Global shortcuts (since 3.2.0)
At the end, the installer asks which agents should receive shortcuts in your user directory. Enter yours (for example, `claude`) to make `/rapid-init`, `/rapid-feature`, and the other shortcuts available in every project. This is equivalent to `rapid shortcuts install --global --harness <id>`. The prompt appears only if the installed `rapid` supports `--global` and the terminal is interactive; nothing is installed without your response. Stable version `v3.1.1` does not support `--global`, so it does not prompt; install shortcuts in each project with `rapid init --shortcuts` instead.
:::

:::warning Shortcuts and hooks need `rapid` on PATH
Agents and their hooks cannot see shell aliases. Launch your agent from a terminal where `rapid --version` works.
:::

## 3. Method B: Install in a virtual environment (`venv`)

To keep Rapid OS isolated in its own virtual environment:

```bash
# 1. Create a virtual environment
python3 -m venv ~/.virtualenvs/rapid-env

# 2. Activate it
source ~/.virtualenvs/rapid-env/bin/activate

# 3. Install the stable version
pip install git+https://github.com/alyconr/Rapid-OS.git@v3.1.1

# 4. Check the installation
rapid --version
```

To make `rapid` available in any terminal without activating the environment:
```bash
mkdir -p ~/.local/bin
ln -sf ~/.virtualenvs/rapid-env/bin/rapid ~/.local/bin/rapid
```
If needed, add `export PATH="$HOME/.local/bin:$PATH"` to `~/.zshrc`.

## 4. Method C: Development install

If you are contributing to Rapid OS:

```bash
git clone https://github.com/alyconr/Rapid-OS.git
cd Rapid-OS
python3 -m pip install -e .
python3 rapid.py doctor
```

## 5. Verify

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

If you skipped the prompt, run `rapid shortcuts install --global --harness claude` once (replace `claude` with your agent). With VS Code, stable version `v3.1.1`, or if you want to version shortcuts in the repository, install them at the project root:

```bash
rapid init --shortcuts
```

Then enter `/rapid-feature <goal>` in your agent. See the [shortcuts guide](../guides/shortcuts.md) and [Getting Started](../getting-started.md).
