"""Application preferences and settings dialog."""

from typing import List
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel,
    QComboBox, QSpinBox, QLineEdit, QPushButton, QGroupBox,
    QDialogButtonBox
)


class SettingsDialog(QDialog):
    """Preferences dialog for analysis parameters and theme."""

    def __init__(self, parent=None, is_dark: bool = True):
        super().__init__(parent)
        self.setWindowTitle("Settings & Preferences")
        self.resize(480, 360)
        self.is_dark = is_dark

        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        # Appearance Group
        grp_app = QGroupBox("Appearance")
        app_layout = QGridLayout(grp_app)

        app_layout.addWidget(QLabel("Interface Theme:"), 0, 0)
        self.combo_theme = QComboBox()
        self.combo_theme.addItems(["Dark (Engineering)", "Light"])
        self.combo_theme.setCurrentIndex(0 if self.is_dark else 1)
        app_layout.addWidget(self.combo_theme, 0, 1)
        layout.addWidget(grp_app)

        # Stopband Analysis Defaults
        grp_stop = QGroupBox("Stopband Rejection Test Frequencies")
        stop_layout = QVBoxLayout(grp_stop)

        stop_layout.addWidget(QLabel("Enter test frequencies separated by commas (in GHz):"))
        self.edit_stop_freqs = QLineEdit("2.0, 2.5, 4.5, 5.0")
        stop_layout.addWidget(self.edit_stop_freqs)
        layout.addWidget(grp_stop)

        # Default Smoothing Settings
        grp_smooth = QGroupBox("Default Smoothing Parameters")
        smooth_layout = QGridLayout(grp_smooth)

        smooth_layout.addWidget(QLabel("Default Algorithm:"), 0, 0)
        self.combo_algo = QComboBox()
        self.combo_algo.addItems(["Savitzky-Golay", "Moving Average"])
        smooth_layout.addWidget(self.combo_algo, 0, 1)

        smooth_layout.addWidget(QLabel("Default Window Length:"), 1, 0)
        self.spin_win = QSpinBox()
        self.spin_win.setRange(3, 101)
        self.spin_win.setSingleStep(2)
        self.spin_win.setValue(15)
        smooth_layout.addWidget(self.spin_win, 1, 1)

        layout.addWidget(grp_smooth)

        # Buttons
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def get_settings(self):
        """Parse and return configured settings."""
        # Parse frequencies
        raw_text = self.edit_stop_freqs.text().strip()
        freqs_hz = []
        for part in raw_text.split(","):
            part = part.strip()
            try:
                val = float(part)
                freqs_hz.append(val * 1e9)
            except ValueError:
                pass

        if not freqs_hz:
            freqs_hz = [2.0e9, 2.5e9, 4.5e9, 5.0e9]

        return {
            "dark_theme": (self.combo_theme.currentIndex() == 0),
            "stopband_freqs_hz": freqs_hz,
            "smoothing_algo": "savgol" if self.combo_algo.currentIndex() == 0 else "moving_avg",
            "smoothing_window": self.spin_win.value(),
        }
