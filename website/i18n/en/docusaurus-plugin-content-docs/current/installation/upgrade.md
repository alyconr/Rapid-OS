---
title: Upgrade Rapid OS
description: How to upgrade your Rapid OS installation to newer stable versions.
---

# Upgrade Rapid OS

Keeping Rapid OS up to date gives you new scan rules, performance improvements, and current diagnostics.

## 1. Upgrade with the official installer

If you installed Rapid OS with the official script in `$HOME/.rapid-os`:

### Windows (PowerShell)
Run the official installer again. It detects the existing directory and updates the Git tags:
```powershell
irm https://raw.githubusercontent.com/alyconr/Rapid-OS/v3.1.1/install.ps1 | iex
```

Or update manually from the installation directory:
```powershell
git -C "$HOME\.rapid-os" fetch --tags --force origin
git -C "$HOME\.rapid-os" checkout --detach v3.1.1
```

### Linux and macOS (Bash/Zsh)
```bash
curl -sL https://raw.githubusercontent.com/alyconr/Rapid-OS/v3.1.1/install.sh | bash
```

Or update manually:
```bash
git -C "$HOME/.rapid-os" fetch --tags --force origin
git -C "$HOME/.rapid-os" checkout --detach v3.1.1
```

## 2. Upgrade with `pip`

If Rapid OS is installed in a virtual environment:

```bash
# Activate the virtual environment
source .venv/bin/activate  # or .venv\Scripts\Activate.ps1 on Windows

# Upgrade from the desired tag
python -m pip install --upgrade git+https://github.com/alyconr/Rapid-OS.git@v3.1.1
```

## 3. Upgrade a development installation

If you use a local clone in editable mode (`pip install -e .`):

```bash
cd Rapid-OS
git pull origin main
rapid doctor
```

## 4. Verify after upgrading

Check that the version is expected and diagnostics report no unexpected issues:

```bash
rapid --version
rapid doctor
```

## 5. From 3.0 to 3.1

Rapid OS 3.1 adds the intent layer (`rapid start|next|check|...`), `/rapid-<mode>` shortcuts, and Claude Code hooks. The v3.0 commands and flags are unchanged, and **nothing needs to be migrated** in specs, runs, evidence, or evaluations. Existing evaluation reports (ruleset 1) remain valid; ruleset 2 is the default for new evaluations, and `--ruleset 1` remains available.

1. Upgrade the package and check its version:
   ```bash
   python -m pip install --upgrade git+https://github.com/alyconr/Rapid-OS.git@v3.1.1
   rapid --version   # Rapid OS 3.1.1
   ```
2. Reinstall shortcuts in each project (this is idempotent; manually changed files are backed up as `.bak`):
   ```bash
   rapid init --shortcuts          # new or uninitialized project
   rapid shortcuts install         # initialized project
   ```
3. Optional, Claude Code only: add hooks with `--hooks` (`rapid shortcuts install --hooks` or `rapid init --hooks`).
4. Add local session state to `.gitignore`:
   ```gitignore
   .rapid-os/session.json
   .rapid-os/scratch/
   ```
5. Set `test_command` in `.rapid-os/config.json` (for example, `"python -m unittest discover"`); `rapid check` uses it when no command is supplied.
6. Verify with `rapid doctor`.

See the [Rapid OS v3.1.1 release notes](../release-v3.1.1.md) for details and known limitations.
