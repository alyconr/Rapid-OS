#!/bin/bash
set -euo pipefail

REPO_URL="https://github.com/alyconr/Rapid-OS.git"
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

echo "🚀 Installing Rapid OS v3.0.0..."

if [ -d "$INSTALL_DIR/.git" ]; then
    echo "🔄 Updating existing Rapid OS installation in $INSTALL_DIR..."
    git -C "$INSTALL_DIR" pull --ff-only origin main
elif [ -e "$INSTALL_DIR" ]; then
    echo "❌ Error: $INSTALL_DIR already exists and is not a Git repository."
    echo "   Remove or rename $INSTALL_DIR, or install via 'pip install .' from a checkout."
    exit 1
else
    echo "⬇️  Cloning Rapid OS repository..."
    git clone "$REPO_URL" "$INSTALL_DIR"
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
    echo "👉 Run: source \"$SHELL_RC\" (or 'pip install -e \"$INSTALL_DIR\"') to start using 'rapid'."
else
    echo "✅ Rapid OS v3.0.0 is ready."
fi