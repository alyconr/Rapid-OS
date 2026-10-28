#!/bin/bash
set -euo pipefail

REPO_URL="https://github.com/alyconr/Rapid-OS.git"
RAPID_VERSION="v3.2.0-rc.1"
INSTALL_DIR="$HOME/.rapid-os"
VENV_DIR="$INSTALL_DIR/.venv"
BIN_DIR="$HOME/.local/bin"

echo "🔍 Checking dependencies..."

if ! command -v git &> /dev/null; then
    echo "❌ Error: Git is not installed. Please install git first."
    exit 1
fi

if ! command -v python3 &> /dev/null; then
    echo "❌ Error: Python 3 is not installed. Please install Python 3.10+ first."
    exit 1
fi

if ! python3 -c 'import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)'; then
    echo "❌ Error: Rapid OS needs Python 3.10 or newer (found $(python3 --version 2>&1))."
    exit 1
fi

case "$RAPID_VERSION" in
    *-rc*) RELEASE_KIND="release candidate" ;;
    *) RELEASE_KIND="stable release" ;;
esac

echo "🚀 Installing Rapid OS ${RAPID_VERSION} (${RELEASE_KIND})..."

if [ -d "$INSTALL_DIR/.git" ]; then
    echo "🔄 Fetching tags and checking out Rapid OS ${RAPID_VERSION} in $INSTALL_DIR..."
    # Installers before v3.1.1 ran `chmod +x rapid.py`; ignore that mode change so checkout works.
    git -C "$INSTALL_DIR" config core.fileMode false
    git -C "$INSTALL_DIR" fetch --tags --force origin
    git -C "$INSTALL_DIR" checkout --detach "$RAPID_VERSION"
elif [ -e "$INSTALL_DIR" ]; then
    echo "❌ Error: $INSTALL_DIR already exists and is not a Git repository."
    echo "   Remove or rename $INSTALL_DIR, or install via 'pip install .' from a checkout."
    exit 1
else
    echo "⬇️  Cloning Rapid OS repository and checking out ${RAPID_VERSION}..."
    git clone "$REPO_URL" "$INSTALL_DIR"
    git -C "$INSTALL_DIR" fetch --tags --force origin
    git -C "$INSTALL_DIR" checkout --detach "$RAPID_VERSION"
fi

# Keep the private environment out of `git status` in the checkout.
if ! grep -qx ".venv/" "$INSTALL_DIR/.git/info/exclude" 2>/dev/null; then
    echo ".venv/" >> "$INSTALL_DIR/.git/info/exclude"
fi

# A real `rapid` executable, not a shell alias: coding harnesses (Claude Code, Codex, Cursor...)
# and their hooks run commands in non-interactive shells, where aliases do not exist.
if [ ! -x "$VENV_DIR/bin/python" ]; then
    echo "📦 Creating a private Python environment in $VENV_DIR..."
    if ! python3 -m venv "$VENV_DIR"; then
        echo "❌ Error: could not create a Python virtual environment."
        echo "   On Debian/Ubuntu install it with: sudo apt install python3-venv"
        exit 1
    fi
fi

echo "📦 Installing the rapid command..."
"$VENV_DIR/bin/python" -m pip install --quiet --disable-pip-version-check -e "$INSTALL_DIR"

mkdir -p "$BIN_DIR"
ln -sf "$VENV_DIR/bin/rapid" "$BIN_DIR/rapid"

SHELL_RC="$HOME/.bashrc"
[ -f "$HOME/.zshrc" ] && SHELL_RC="$HOME/.zshrc"

if [ ! -f "$SHELL_RC" ]; then
    touch "$SHELL_RC"
fi

# Installers before v3.1.1 added an alias that shadows the executable in interactive shells.
if grep -q "^alias rapid=" "$SHELL_RC"; then
    cp "$SHELL_RC" "$SHELL_RC.rapid-os.bak"
    grep -v -e "^alias rapid=" -e "^# Rapid OS CLI$" "$SHELL_RC.rapid-os.bak" > "$SHELL_RC"
    echo "🧹 Removed the old 'rapid' alias from $SHELL_RC (backup: $SHELL_RC.rapid-os.bak)."
fi

NEEDS_NEW_TERMINAL=0
case ":$PATH:" in
    *":$BIN_DIR:"*) ;;
    *)
        if ! grep -q 'Rapid OS: user bin on PATH' "$SHELL_RC"; then
            {
                echo ""
                echo "# Rapid OS: user bin on PATH"
                echo 'export PATH="$HOME/.local/bin:$PATH"'
            } >> "$SHELL_RC"
            echo "✅ Added $BIN_DIR to PATH in $SHELL_RC"
        fi
        NEEDS_NEW_TERMINAL=1
        ;;
esac

echo "✅ $("$BIN_DIR/rapid" --version) installed at $BIN_DIR/rapid"
if [ "$NEEDS_NEW_TERMINAL" -eq 1 ]; then
    echo "👉 Open a new terminal (or run: source \"$SHELL_RC\") before using 'rapid'."
fi
echo "👉 Launch your coding agent (claude, codex, cursor...) from a terminal where 'rapid --version' works."

# Opt-in, never by default and never without a terminal: /rapid-init and the /rapid-<mode>
# shortcuts in your user-level skills folder, so they work in every project without a per-project
# install. Supported: claude, codex, cursor, antigravity (VS Code has no user-level folder).
# Only offered when the installed version has `--global` (releases before 3.2.0 do not).
# With `curl | bash` stdin is the pipe, so the answer is read from the controlling terminal.
# [ -r /dev/tty ] can be true without a terminal (cron, containers), hence the open test.
if ! "$BIN_DIR/rapid" shortcuts install --help 2>/dev/null | grep -q -- '--global'; then
    : # this version has no user-level install: nothing to offer
elif [ -r /dev/tty ] && (: < /dev/tty) 2>/dev/null; then
    printf '%s' "👉 Install /rapid-init and the /rapid-* shortcuts for your coding agents in your home folder (all projects)? Harnesses (comma-separated: claude,codex,cursor,antigravity) or Enter for none: "
    read -r RAPID_INIT_HARNESSES < /dev/tty || RAPID_INIT_HARNESSES=""
    if [ -n "$RAPID_INIT_HARNESSES" ]; then
        HARNESS_ARGS=""
        for H in $(echo "$RAPID_INIT_HARNESSES" | tr ',' ' '); do
            HARNESS_ARGS="$HARNESS_ARGS --harness $H"
        done
        # shellcheck disable=SC2086
        "$BIN_DIR/rapid" shortcuts install --global $HARNESS_ARGS || echo "WARNING: Could not install the shortcuts; run 'rapid shortcuts install --global --harness <id>' later."
    fi
else
    echo "👉 Tip: 'rapid shortcuts install --global --harness claude' installs /rapid-init and the /rapid-* shortcuts for all your projects."
fi
