---
title: Installation Troubleshooting
description: Diagnosing and resolving common issues when installing and configuring Rapid OS.
---

# Installation Troubleshooting

This guide collects the most common errors reported during Rapid OS installation and their proven solutions.

---

## 1. The `rapid` command is not recognized (*command not found*)

### Cause
Since v3.1.1 the installers leave a `rapid` executable on the `PATH` (`~/.local/bin/rapid` on Linux/macOS/WSL, `$HOME\.rapid-os\bin\rapid.exe` on Windows). If it is not recognized, the terminal was opened before the installation or that folder is not on the `PATH`.

### Solution

- **On Windows (PowerShell):** open a new window and check:
  ```powershell
  Get-Command rapid                                   # ...\.rapid-os\bin\rapid.exe
  [Environment]::GetEnvironmentVariable("Path", "User") -split ";" | Select-String rapid-os
  ```
  If the folder does not appear, run the installer again.

- **On Linux / macOS / WSL:** open a new terminal (or `source ~/.bashrc` / `source ~/.zshrc`) and check:
  ```bash
  command -v rapid        # ~/.local/bin/rapid
  ls -l ~/.local/bin/rapid
  ```

---

## 1.1. `rapid` works in your terminal but not inside the agent (*rapid: command not found* in a shortcut or hook)

### Symptom
A shortcut such as `/rapid-feature` fails on its first step with `rapid: command not found`, or a Claude Code hook cannot find `rapid`.

### Cause
The agent runs commands in its own non-interactive shell (Claude Code uses Git Bash on Windows). That shell does not see aliases, `$PROFILE` functions, or a `venv` activated only in your terminal. Installers prior to v3.1.1 configured an alias or a function, which has this problem.

### Solution
1. Install with the v3.1.1 installer or with `pipx install git+https://github.com/alyconr/Rapid-OS.git@v3.1.1`.
2. Open a new terminal, check `rapid --version`, and launch the agent from it.
3. Inside Claude Code, `! which rapid` must find it.

---

## 2. PowerShell execution policy error (*ExecutionPolicy*)

### Symptom
```text
File ...\install.ps1 cannot be loaded because running scripts is disabled on this system.
```

### Solution
Windows blocks running remote scripts in PowerShell by default. Enable `RemoteSigned` for your current user (it does not require Administrator permissions):

```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

Then run the installer again:
```powershell
irm https://raw.githubusercontent.com/alyconr/Rapid-OS/v3.1.1/install.ps1 | iex
```

---

## 3. Incompatible Python version (< 3.10)

### Symptom
The installer or the CLI throws syntax errors (`SyntaxError`) or the installer aborts with:
```text
Error: Python 3 is not installed. Please install Python 3.10+ first.
```

### Solution
Rapid OS requires Python 3.10 as the minimum version for static typing and pattern matching.
1. Install Python 3.10, 3.11, 3.12, or 3.13 from [python.org](https://www.python.org/).
2. On Windows, make sure to check **"Add python.exe to PATH"**.
3. On Linux, install an up-to-date `python3` from your distribution's package manager.

---

## 4. Conflicts when cloning into `$HOME/.rapid-os`

### Symptom
```text
Error: .../.rapid-os already exists and is not a Git repository.
```

### Solution
If you already had an old unversioned folder with that name:
1. Back up or rename the folder:
   ```bash
   mv ~/.rapid-os ~/.rapid-os.bak
   ```
2. Run the installer again.

---

## 5. The `rapid doctor` command reports warnings

Run `rapid doctor --json` to get a structured diagnosis with the exact warning code (`TOOLxxx`, `CONFIGxxx`, etc.). Most warnings indicate missing optional tools (such as Node.js/npx for remote skills) that do not affect the main governance cycle.
