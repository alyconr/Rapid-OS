#!/bin/bash
set -euo pipefail

REPO_URL="https://github.com/alyconr/Rapid-OS.git"
RAPID_VERSION="v3.0.0"
INSTALL_DIR="$HOME/.rapid-os"

echo "🔍 Checking dependencies..."

if ! command -v git &> /dev/null; then
    echo "❌ Error: Git is not installed. Please install git first."
    exit 1
fi

if ! command -v python3 &> /dev/null; then
    echo "❌ Error: Python 3 is not installed. Please install Python 3.10+ first."
    exit 1
fi

echo "🚀 Installing Rapid OS ${RAPID_VERSION} (stable release)..."

if [ -d "$INSTALL_DIR/.git" ]; then
    echo "🔄 Fetching tags and checking out Rapid OS ${RAPID_VERSION} in $INSTALL_DIR..."
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

chmod +x "$INSTALL_DIR/rapid.py"

SHELL_RC="$HOME/.bashrc"
[ -f "$HOME/.zshrc" ] && SHELL_RC="$HOME/.zshrc"

if [ ! -f "$SHELL_RC" ]; then
    touch "$SHELL_RC"
fi

if ! grep -q "alias rapid=" "$SHELL_RC"; then
    {
        echo ""
        echo "# Rapid OS CLI"
        echo "alias rapid='python3 \"$INSTALL_DIR/rapid.py\"'"
    } >> "$SHELL_RC"
    echo "✅ Alias added to $SHELL_RC"
    echo "👉 Run: source \"$SHELL_RC\" (or 'python3 -m pip install \"$INSTALL_DIR\"') to start using 'rapid'."
else
    echo "✅ Rapid OS ${RAPID_VERSION} is ready."
fi