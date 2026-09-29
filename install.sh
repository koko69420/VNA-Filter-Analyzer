#!/usr/bin/env bash
# ==============================================================================
# Installer for Rohde & Schwarz VNA Filter Analyzer on Ubuntu Linux
# ==============================================================================
set -e

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"
cd "$DIR"

echo "=== Installing Rohde & Schwarz VNA Filter Analyzer ==="

# 1. Setup Python Virtual Environment if needed
if [ ! -d "$DIR/.venv" ]; then
    echo "Creating Python virtual environment in .venv..."
    python3 -m venv "$DIR/.venv"
fi

echo "Installing required Python dependencies..."
"$DIR/.venv/bin/pip" install --upgrade pip
"$DIR/.venv/bin/pip" install -r "$DIR/requirements.txt"

# 2. Make scripts executable
chmod +x "$DIR/run.sh"
chmod +x "$DIR/install.sh"
chmod +x "$DIR/main.py"

# 3. Install Application Icons
ICON_PNG="$DIR/vna_filter_analyzer/resources/icon.png"
ICON_SVG="$DIR/vna_filter_analyzer/resources/icon.svg"

USER_ICON_DIR_PNG="$HOME/.local/share/icons/hicolor/256x256/apps"
USER_ICON_DIR_SVG="$HOME/.local/share/icons/hicolor/scalable/apps"

mkdir -p "$USER_ICON_DIR_PNG"
mkdir -p "$USER_ICON_DIR_SVG"

if [ -f "$ICON_PNG" ]; then
    cp "$ICON_PNG" "$USER_ICON_DIR_PNG/vna-filter-analyzer.png"
fi
if [ -f "$ICON_SVG" ]; then
    cp "$ICON_SVG" "$USER_ICON_DIR_SVG/vna-filter-analyzer.svg"
fi

# 4. Generate and Install .desktop Launcher
USER_APPS_DIR="$HOME/.local/share/applications"
mkdir -p "$USER_APPS_DIR"

DESKTOP_FILE="$USER_APPS_DIR/VNA-Filter-Analyzer.desktop"

cat << EOF > "$DESKTOP_FILE"
[Desktop Entry]
Version=1.0
Type=Application
Name=VNA Filter Analyzer
GenericName=RF & Microwave Filter Analyzer
Comment=Rohde & Schwarz VNA Filter Measurement & Comparison Tool
Exec="$DIR/run.sh" %F
Icon=$ICON_PNG
Terminal=false
Categories=Development;Engineering;Science;
StartupWMClass=VNA Filter Analyzer
MimeType=text/csv;application/vnd.ms-excel;text/plain;
Keywords=VNA;Filter;Rohde;Schwarz;S21;S11;Bandwidth;DGS;RF;Microwave;
EOF

chmod +x "$DESKTOP_FILE"

# 5. Update Desktop Database & Icon Cache
if command -v update-desktop-database >/dev/null 2>&1; then
    update-desktop-database "$USER_APPS_DIR" || true
fi
if command -v gtk-update-icon-cache >/dev/null 2>&1; then
    gtk-update-icon-cache -f -t "$HOME/.local/share/icons/hicolor" >/dev/null 2>&1 || true
fi

echo ""
echo "✅ Installation complete!"
echo "• The application 'VNA Filter Analyzer' is now available in your Ubuntu Application Drawer."
echo "• You can also launch it anytime from the terminal by running: ./run.sh"
echo "=============================================================================="
