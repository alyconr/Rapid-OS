#!/bin/bash
set -e
# RECUERDA: CAMBIA LA URL POR TU REPO REAL ANTES DE PUBLICAR
REPO_URL="https://github.com/alyconr/Rapid-OS.git"
INSTALL_DIR="$HOME/.rapid-os"

echo "🚀 Installing Rapid OS v1.0..."

# 1. Clonar o Actualizar
if [ -d "$INSTALL_DIR" ]; then
    echo "🔄 Actualizando Rapid OS..."
    git -C "$INSTALL_DIR" pull origin main
else
    echo "⬇️  Clonando Repositorio..."
    git clone "$REPO_URL" "$INSTALL_DIR"
fi

# 2. Permisos
chmod +x "$INSTALL_DIR/rapid.py"

# 3. Configurar Alias
SHELL_RC="$HOME/.bashrc"
[ -f "$HOME/.zshrc" ] && SHELL_RC="$HOME/.zshrc"

if ! grep -q "rapid=" "$SHELL_RC"; then
    echo "" >> "$SHELL_RC"
    echo "# Rapid OS CLI" >> "$SHELL_RC"
    echo "alias rapid='python3 $INSTALL_DIR/rapid.py'" >> "$SHELL_RC"
    echo "✅ Alias agregado a $SHELL_RC"
    echo "👉 Ejecuta: source $SHELL_RC para empezar."
else
    echo "✅ Rapid OS ya está instalado y actualizado."
fi