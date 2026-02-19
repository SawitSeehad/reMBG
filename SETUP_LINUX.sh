#!/bin/bash

echo "========================================================"
echo "     pvBG - AUTOMATIC SETUP"
echo "     (Linux Edition)"
echo "========================================================"

cd "$(dirname "$0")"
PROJECT_DIR=$(pwd)

if ! command -v python3 &> /dev/null; then
    echo "[ERROR] Python3 is not installed."
    exit 1
fi

if [ ! -d "venv" ]; then
    echo "[1/3] Creating virtual environment..."
    python3 -m venv venv
fi

echo "[2/3] Installing dependencies..."
source venv/bin/activate
pip install -r requirements.txt

echo "[3/3] Creating pvBG Launcher..."

DESKTOP_FILE="$HOME/Desktop/pvBG.desktop"
ICON_PATH="$PROJECT_DIR/assets/icon.png"  

cat > "$DESKTOP_FILE" <<EOL
[Desktop Entry]
Version=1.0
Type=Application
Name=pvBG
Comment=Offline Background Remover
Exec=$PROJECT_DIR/venv/bin/python3 $PROJECT_DIR/src/gui.py
Icon=$ICON_PATH
Path=$PROJECT_DIR
Terminal=false
StartupNotify=true
EOL

chmod +x "$DESKTOP_FILE"

echo ""
echo "========================================================"
echo "     SUCCESS! pvBG INSTALLED."
echo "========================================================"
echo "Please check your Desktop for 'pvBG'."
echo "Right-Click -> 'Allow Launching' if needed."