#!/bin/bash
set -e
# --- CONFIGURACIÓN ---
# REEMPLAZA CON TU REPO REAL:
REPO_URL="https://github.com/alyconr/Rapid-OS.git"
INSTALL_DIR="$HOME/.rapid-os"

# --- VALIDACIONES PREVIAS ---
echo "🔍 Checking dependencies..."

if ! command -v git &> /dev/null; then
    echo "❌ Error: Git is not installed. Please install git first."
    exit 1
fi

if ! command -v python3 &> /dev/null; then
    echo "❌ Error: Python3 is not installed. Please install python3 first."
    exit 1
fi

# --- INSTALACIÓN ---
echo "🚀 Installing Rapid OS v1.0..."

if [ -d "$INSTALL_DIR" ]; then
    echo "🔄 Updating Rapid OS..."
    git -C "$INSTALL_DIR" pull origin main
else
    echo "⬇️  Cloning Repository..."
    git clone "$REPO_URL" "$INSTALL_DIR"
fi

# Permisos
chmod +x "$INSTALL_DIR/rapid.py"

# --- CONFIGURACIÓN DE ALIAS ---
SHELL_RC="$HOME/.bashrc"
[ -f "$HOME/.zshrc" ] && SHELL_RC="$HOME/.zshrc"

if ! grep -q "rapid=" "$SHELL_RC"; then
    echo "" >> "$SHELL_RC"
    echo "# Rapid OS CLI" >> "$SHELL_RC"
    echo "alias rapid='python3 $INSTALL_DIR/rapid.py'" >> "$SHELL_RC"
    echo "✅ Alias added to $SHELL_RC"
    echo "👉 Run: source $SHELL_RC to start."
else
    echo "✅ Rapid OS is ready."
fi