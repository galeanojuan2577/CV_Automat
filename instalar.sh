#!/bin/bash
set -e

PROYECTO_DIR="$(cd "$(dirname "$(readlink -f "$0")")" && pwd)"
echo "=== Instalación Asistente de CV Inteligente ==="
echo "Directorio: $PROYECTO_DIR"
echo ""

# 1. Dependencias Python (intentar venv, fallback a --break-system-packages)
echo "[1/4] Instalando dependencias Python..."
if python3 -m venv "$PROYECTO_DIR/venv" 2>/dev/null; then
    source "$PROYECTO_DIR/venv/bin/activate"
    pip install --upgrade pip -q
    pip install -r "$PROYECTO_DIR/requirements.txt" -q
    echo "  ✓ Dependencias instaladas en venv"
else
    echo "  ⚠ python3-venv no disponible. Instalando con --break-system-packages..."
    pip install --break-system-packages -r "$PROYECTO_DIR/requirements.txt" -q
    echo "  ✓ Dependencias instaladas (system)"
fi

# 2. Modelo Ollama
echo "[2/4] Descargando modelo llama3.2 (esto puede tomar varios minutos)..."
if command -v ollama &> /dev/null; then
    ollama pull llama3.2
    echo "  ✓ Modelo llama3.2 descargado"
else
    echo "  ⚠ ollama no encontrado. Instálalo desde https://ollama.com"
    echo "    Luego ejecuta: ollama pull llama3.2"
fi

# 3. LibreOffice
echo "[3/4] Instalando LibreOffice..."
if ! command -v libreoffice &> /dev/null; then
    sudo apt update && sudo apt install -y libreoffice
    echo "  ✓ LibreOffice instalado"
else
    echo "  ✓ LibreOffice ya instalado"
fi

# 4. Copiar comando 'trabajo'
echo "[4/4] Instalando comando 'trabajo'..."
sudo cp "$PROYECTO_DIR/trabajo.sh" /usr/local/bin/trabajo
sudo chmod +x /usr/local/bin/trabajo
echo "  ✓ Comando 'trabajo' instalado en /usr/local/bin/trabajo"

echo ""
echo "============================================"
echo "✅ Instalación completa."
echo "   Escribe 'trabajo' en la terminal para iniciar."
echo "============================================"
