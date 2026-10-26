---
title: Install on Windows
description: Step-by-step guide to installing and configuring Rapid OS on Windows 10 and 11 with PowerShell.
---

# Install on Windows

This guide covers installing Rapid OS v3 on Windows 10 and Windows 11 with PowerShell.

## 1. Windows prerequisites

Make sure Python and Git are installed and available on your system `PATH`:

1. **Python 3.10+:** Download it from [python.org](https://www.python.org/downloads/windows/). Select **Add python.exe to PATH** during installation.
2. **Git for Windows:** Download it from [git-scm.com](https://git-scm.com/download/win).
3. **PowerShell:** Open Windows PowerShell or PowerShell 7.

Verify in your console:

```powershell
python --version
git --version
```

## 2. Method A: PowerShell installer (recommended)

The official installer downloads the repository to `$HOME\.rapid-os`, pins stable version `v3.1.1`, and installs a `rapid.exe` executable on your user PATH:

```powershell
irm https://raw.githubusercontent.com/alyconr/Rapid-OS/v3.1.1/install.ps1 | iex
```

### What does this script do?
1. Checks that `git` and `python` (3.10+) are available.
2. Clones the official repository into `$HOME\.rapid-os`.
3. Checks out stable version `v3.1.1`.
4. Creates a dedicated Python environment in `$HOME\.rapid-os\.venv` and installs Rapid OS into it.
5. Copies `rapid.exe` to `$HOME\.rapid-os\bin` and adds that directory to your user PATH. Only `rapid.exe` is added; the environment's `python.exe` does not replace yours.
6. Removes a `rapid` function left in `$PROFILE` by an older installer, saving a `.rapid-os.bak` copy.
7. Open a new PowerShell window so it picks up the updated PATH.

:::note Global shortcuts (since 3.2.0)
At the end, the installer asks which agents should receive shortcuts in your user directory. Enter yours (for example, `claude`) to make `/rapid-init`, `/rapid-feature`, and the other shortcuts available in every project. This is equivalent to `rapid shortcuts install --global --harness <id>`. The prompt appears only when the installed `rapid` supports `--global` and the terminal is interactive; nothing is installed without your response. Stable version `v3.1.1` does not support `--global`, so it does not prompt; install shortcuts in each project with `rapid init --shortcuts` instead.
:::

:::warning Shortcuts and hooks need `rapid` on PATH
Claude Code runs shortcut and hook commands in Git Bash, not PowerShell. `rapid` must therefore be an executable on PATH: a PowerShell function or a command in a virtual environment activated only in your terminal is not visible to the agent. The installer (Method A) and `pipx` handle this. Check inside Claude Code with `! which rapid`.
:::

:::tip PowerShell execution policy
If PowerShell reports `Running scripts is disabled on this system`, adjust the execution policy for the current user:
```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```
:::

## 3. Method B: Install in a Python virtual environment (`venv`)

With this method, `rapid` is available only while the environment is activated. For shortcuts and hooks with your agent, use Method A or `pipx install git+https://github.com/alyconr/Rapid-OS.git@v3.1.1`.

```powershell
# 1. Create the virtual environment
python -m venv rapid-env

# 2. Activate the environment
.\rapid-env\Scripts\Activate.ps1

# 3. Install the stable version from GitHub
python -m pip install git+https://github.com/alyconr/Rapid-OS.git@v3.1.1

# 4. Verify
rapid --version
```

## 4. Method C: Install from source (development)

To work on the development `main` branch or contribute to Rapid OS:

```powershell
git clone https://github.com/alyconr/Rapid-OS.git
cd Rapid-OS
python -m pip install -e .
python rapid.py guide
```

## 5. Verify

Check that the commands respond:
```powershell
rapid --version
rapid doctor
```

Continue to [Detailed installation verification](./verification.md).

## 6. Start using shortcuts

If you selected your agent in the installer's final prompt, open it in your project folder and enter:
```text
/rapid-init
```

If you skipped the prompt, run `rapid shortcuts install --global --harness claude` once (replace `claude` with your agent). With VS Code, stable version `v3.1.1`, or if you want to version shortcuts with the repository, install them at the project root:
```powershell
rapid init --shortcuts
```

Then enter `/rapid-feature <goal>` in your agent. See the [shortcuts guide](../guides/shortcuts.md) and [Getting Started](../getting-started.md).
