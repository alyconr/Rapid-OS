---
title: Installation Troubleshooting
description: Diagnose and resolve common problems when installing and configuring Rapid OS.
---

# Installation Troubleshooting

This guide collects common installation errors and verified solutions.

## 1. The `rapid` command is not recognized (*command not found*)

### Cause
Since v3.1.1, installers put a `rapid` executable on `PATH` (`~/.local/bin/rapid` on Linux/macOS/WSL, `$HOME\.rapid-os\bin\rapid.exe` on Windows). If it is not recognized, the terminal may have been opened before installation, or the directory is not on `PATH`.

### Solution

- **Windows (PowerShell):** Open a new window and check:
  ```powershell
  Get-Command rapid                                   # ...\.rapid-os\bin\rapid.exe
  [Environment]::GetEnvironmentVariable("Path", "User") -split ";" | Select-String rapid-os
  ```
  If the directory is missing, run the installer again.
- **Linux / macOS / WSL:** Open a new terminal (or run `source ~/.bashrc` / `source ~/.zshrc`) and check:
  ```bash
  command -v rapid        # ~/.local/bin/rapid
  ls -l ~/.local/bin/rapid
  ```

## 1.1. `rapid` works in your terminal but not in the agent

### Symptom
A shortcut such as `/rapid-feature` fails with `rapid: command not found`, or a Claude Code hook cannot find `rapid`.

### Cause
The agent runs commands in its own non-interactive shell (Claude Code uses Git Bash on Windows). That shell cannot see aliases, `$PROFILE` functions, or a virtual environment activated only in your terminal. Installers before v3.1.1 configured an alias or function, which causes this issue.

### Solution
1. Install with the v3.1.1 installer or `pipx install git+https://github.com/alyconr/Rapid-OS.git@v3.1.1`.
2. Open a new terminal, check `rapid --version`, and launch the agent from it.
3. In Claude Code, `! which rapid` should find the executable.

## 2. PowerShell execution policy error (*ExecutionPolicy*)

### Symptom
```text
File ...\install.ps1 cannot be loaded because running scripts is disabled on this system.
```

### Solution
Windows blocks remote PowerShell scripts by default. Enable `RemoteSigned` for your current user (administrator permissions are not required):

```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

Then run the installer again:
```powershell
irm https://raw.githubusercontent.com/alyconr/Rapid-OS/v3.1.1/install.ps1 | iex
```

## 3. Incompatible Python version (< 3.10)

### Symptom
The installer or CLI reports syntax errors (`SyntaxError`) or the installer exits with:
```text
Error: Python 3 is not installed. Please install Python 3.10+ first.
```

### Solution
Rapid OS requires Python 3.10 or later for static typing and pattern matching.
1. Install Python 3.10, 3.11, 3.12, or 3.13 from [python.org](https://www.python.org/).
2. On Windows, select **Add python.exe to PATH**.
3. On Linux, install a current `python3` with your distribution's package manager.

## 4. Clone conflict in `$HOME/.rapid-os`

### Symptom
```text
Error: .../.rapid-os already exists and is not a Git repository.
```

### Solution
If an old, unversioned folder with that name already exists, back it up or rename it:
```bash
mv ~/.rapid-os ~/.rapid-os.bak
```
Then run the installer again.

## 5. `rapid doctor` reports warnings

Run `rapid doctor --json` to get structured diagnostics with the exact warning code (`TOOLxxx`, `CONFIGxxx`, and so on). Most warnings indicate missing optional tools (such as Node.js/npx for remote skills) and do not affect the main governance loop.
