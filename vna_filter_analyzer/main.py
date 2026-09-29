"""Application entry point for Rohde & Schwarz VNA Filter Analyzer."""

import sys
import os
import argparse

# Ensure project root is in sys.path
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from PySide6.QtCore import Qt, QCoreApplication
from PySide6.QtGui import QIcon, QFont
from PySide6.QtWidgets import QApplication

from vna_filter_analyzer.main_window import MainWindow


def main():
    parser = argparse.ArgumentParser(description="Rohde & Schwarz VNA Filter Analyzer")
    parser.add_argument("files", nargs="*", help="Optional initial CSV/S2P measurement files to load (up to 4)")
    args = parser.parse_args()

    # Qt Environment configuration for modern Linux desktops (Wayland/X11)
    if "QT_QPA_PLATFORM" not in os.environ:
        # Default to Wayland if available, fallback to xcb
        if os.environ.get("WAYLAND_DISPLAY"):
            os.environ["QT_QPA_PLATFORM"] = "wayland;xcb"

    app = QApplication(sys.argv)
    app.setApplicationName("VNA Filter Analyzer")
    app.setApplicationDisplayName("VNA Filter Analyzer")
    app.setOrganizationName("Rohde & Schwarz Microwave Lab")
    app.setDesktopFileName("VNA-Filter-Analyzer.desktop")

    # App Icon
    icon_path = os.path.join(os.path.dirname(__file__), "resources", "icon.png")
    if os.path.exists(icon_path):
        app.setWindowIcon(QIcon(icon_path))

    window = MainWindow()

    # Load initial files if supplied
    if args.files:
        valid_files = [os.path.abspath(f) for f in args.files if os.path.exists(f)]
        if valid_files:
            window.load_files(valid_files[:4], show_preview=False)

    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
