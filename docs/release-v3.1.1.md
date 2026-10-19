# Rapid OS v3.1.1 Release Notes

**Release Version**: `3.1.1`  
**Artifact Schema Version**: `1` (unchanged from `3.1.0`)  
**Python Requirement**: Python `>=3.10` (`3.10`, `3.11`, `3.12`, and `3.13` verified in CI)

---

## 1. Overview

**Rapid OS v3.1.1** is a patch release that makes the stable installers work with coding harnesses. Before this release, `install.sh` added a shell alias and `install.ps1` added a PowerShell profile function. Shortcuts (`/rapid-<mode>`) and Claude Code hooks run `rapid` from the agent's own non-interactive shell (Git Bash on Windows), which sees neither aliases nor profile functions, so they failed with `rapid: command not found`.

No command, flag, JSON output or artifact changed. Everything documented in the [v3.1.0 release notes](./release-v3.1.0.md) still applies.

---

## 2. What changed

- **`install.sh` (Linux, macOS, WSL)**: creates a private Python environment in `~/.rapid-os/.venv`, installs Rapid OS in it (editable, so `git checkout --detach <tag>` in `~/.rapid-os` keeps upgrading it) and links the executable to `~/.local/bin/rapid`. If `~/.local/bin` is not on `PATH`, it adds it to `~/.bashrc` or `~/.zshrc`. It removes the `alias rapid=` line written by earlier installers (backup `*.rapid-os.bak`). Debian/Ubuntu need the `python3-venv` package.
- **`install.ps1` (Windows)**: creates `$HOME\.rapid-os\.venv`, installs Rapid OS in it, copies `rapid.exe` to `$HOME\.rapid-os\bin` and adds that folder to the user `PATH`. Only `rapid.exe` lands on `PATH`, so the environment's `python.exe` never replaces yours. It removes the `function rapid` written by earlier installers to `$PROFILE` (backup `*.rapid-os.bak`).
- **Documentation**: the installation pages and the troubleshooting guide explain that shortcuts and hooks need `rapid` as an executable on `PATH`, and how to check it from inside Claude Code (`! which rapid`).

---

## 3. Dependencies

The governance core still uses only the Python standard library. The installers need network access to clone the repository and to let `pip` fetch the build backend; optional integrations such as remote skills use Node.js/`npx` and need network access too.

---

## 4. Upgrade

```bash
curl -sL https://raw.githubusercontent.com/alyconr/Rapid-OS/v3.1.1/install.sh | bash   # Linux, macOS, WSL
```

```powershell
irm https://raw.githubusercontent.com/alyconr/Rapid-OS/v3.1.1/install.ps1 | iex       # Windows
```

Then open a new terminal and check:

```bash
rapid --version                      # Rapid OS 3.1.1
```

If you installed with `pip` or `pipx`, upgrade with `pip install --upgrade git+https://github.com/alyconr/Rapid-OS.git@v3.1.1` (or `pipx install --force ...`).
