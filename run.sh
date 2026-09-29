#!/usr/bin/env bash
# ==============================================================================
# Rohde & Schwarz VNA Filter Analyzer Launcher
# ==============================================================================
set -e

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"
cd "$DIR"

# Locate virtual environment
if [ -d "$DIR/.venv" ]; then
    PYTHON_EXEC="$DIR/.venv/bin/python3"
elif command -v python3 >/dev/null 2>&1; then
    PYTHON_EXEC="python3"
else
    echo "Error: Python 3 not found. Please run ./install.sh first."
    exit 1
fi

# Set display platform variables for Ubuntu Wayland/X11
if [ -n "$WAYLAND_DISPLAY" ]; then
    export QT_QPA_PLATFORM="wayland;xcb"
else
    export QT_QPA_PLATFORM="xcb"
fi

export QT_AUTO_SCREEN_SCALE_FACTOR=1
export PYTHONUNBUFFERED=1

exec "$PYTHON_EXEC" "$DIR/main.py" "$@"
