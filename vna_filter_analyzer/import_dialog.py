"""Import preview and manual column configuration dialog."""

import os
from typing import Dict, Optional
import pandas as pd
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel,
    QComboBox, QPushButton, QTableWidget, QTableWidgetItem,
    QGroupBox, QHeaderView, QTextEdit, QFrame
)

from .csv_parser import detect_columns, detect_delimiter, parse_metadata_headers, ColumnDetection


class ImportPreviewDialog(QDialog):
    """Dialog showing a 15-row preview of the CSV and allowing manual column mapping."""

    def __init__(self, file_path: str, parent=None):
        super().__init__(parent)
        self.file_path = file_path
        self.setWindowTitle(f"Import VNA Measurement - {os.path.basename(file_path)}")
        self.resize(750, 560)

        self.df_preview: Optional[pd.DataFrame] = None
        self.detection: Optional[ColumnDetection] = None
        self.metadata: Dict[str, str] = {}

        self._load_preview()
        self._init_ui()

    def _load_preview(self):
        delim = detect_delimiter(self.file_path)
        self.metadata = parse_metadata_headers(self.file_path)

        # Count header lines
        header_line_idx = 0
        with open(self.file_path, "r", encoding="utf-8", errors="replace") as f:
            for idx, line in enumerate(f):
                line_str = line.strip()
                if not line_str or line_str.startswith(("#", "!", "//", "*", "[")):
                    header_line_idx = idx + 1
                else:
                    break

        try:
            self.df_preview = pd.read_csv(
                self.file_path,
                sep=delim,
                skiprows=header_line_idx,
                nrows=15,
                skipinitialspace=True,
                encoding="utf-8",
                on_bad_lines="skip",
            )
        except Exception:
            self.df_preview = pd.read_csv(
                self.file_path,
                sep=None,
                engine="python",
                skiprows=header_line_idx,
                nrows=15,
                encoding="utf-8",
                on_bad_lines="skip",
            )

        self.df_preview.columns = [str(c).strip().strip('"').strip("'") for c in self.df_preview.columns]
        self.detection = detect_columns(self.df_preview)

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        # Top Information Banner
        info_frame = QFrame()
        info_frame.setStyleSheet("background-color: #1e2430; border: 1px solid #2d3748; border-radius: 6px; padding: 6px;")
        info_layout = QVBoxLayout(info_frame)
        info_layout.setContentsMargins(6, 4, 6, 4)

        lbl_file = QLabel(f"<b>File:</b> {self.file_path}")
        info_layout.addWidget(lbl_file)

        if self.metadata:
            meta_str = " | ".join([f"<b>{k}:</b> {v}" for k, v in list(self.metadata.items())[:3]])
            lbl_meta = QLabel(f"Detected Metadata: {meta_str}")
            lbl_meta.setStyleSheet("color: #38bdf8; font-size: 11px;")
            info_layout.addWidget(lbl_meta)

        layout.addWidget(info_frame)

        # Data Preview Table
        grp_prev = QGroupBox("File Data Preview (First 15 Rows)")
        prev_layout = QVBoxLayout(grp_prev)

        self.table = QTableWidget()
        cols = list(self.df_preview.columns)
        self.table.setColumnCount(len(cols))
        self.table.setHorizontalHeaderLabels(cols)
        self.table.setRowCount(len(self.df_preview))
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)

        for r in range(len(self.df_preview)):
            for c in range(len(cols)):
                val = str(self.df_preview.iloc[r, c])
                self.table.setItem(r, c, QTableWidgetItem(val))

        prev_layout.addWidget(self.table)
        layout.addWidget(grp_prev, 2)

        # Column Mapping Group
        grp_map = QGroupBox("Column Mapping & Frequency Units")
        map_layout = QGridLayout(grp_map)

        # Frequency Column
        map_layout.addWidget(QLabel("Frequency Column:"), 0, 0)
        self.combo_freq = QComboBox()
        self.combo_freq.addItems(cols)
        if self.detection.freq_col in cols:
            self.combo_freq.setCurrentText(self.detection.freq_col)
        map_layout.addWidget(self.combo_freq, 0, 1)

        # Frequency Unit
        map_layout.addWidget(QLabel("Frequency Unit:"), 0, 2)
        self.combo_unit = QComboBox()
        self.combo_unit.addItems(["Hz", "kHz", "MHz", "GHz"])
        unit_idx = {"Hz": 0, "kHz": 1, "MHz": 2, "GHz": 3}.get(self.detection.freq_unit_name, 0)
        self.combo_unit.setCurrentIndex(unit_idx)
        map_layout.addWidget(self.combo_unit, 0, 3)

        # S-parameter mappings
        none_cols = ["(None)"] + cols

        # S21
        map_layout.addWidget(QLabel("S21 (Transmission):"), 1, 0)
        self.combo_s21 = QComboBox()
        self.combo_s21.addItems(none_cols)
        s21_detected = self.detection.s_params.get("S21")
        if s21_detected in cols:
            self.combo_s21.setCurrentText(s21_detected)
        map_layout.addWidget(self.combo_s21, 1, 1)

        # S11
        map_layout.addWidget(QLabel("S11 (Reflection):"), 1, 2)
        self.combo_s11 = QComboBox()
        self.combo_s11.addItems(none_cols)
        s11_detected = self.detection.s_params.get("S11")
        if s11_detected in cols:
            self.combo_s11.setCurrentText(s11_detected)
        map_layout.addWidget(self.combo_s11, 1, 3)

        # S12
        map_layout.addWidget(QLabel("S12:"), 2, 0)
        self.combo_s12 = QComboBox()
        self.combo_s12.addItems(none_cols)
        s12_detected = self.detection.s_params.get("S12")
        if s12_detected in cols:
            self.combo_s12.setCurrentText(s12_detected)
        map_layout.addWidget(self.combo_s12, 2, 1)

        # S22
        map_layout.addWidget(QLabel("S22:"), 2, 2)
        self.combo_s22 = QComboBox()
        self.combo_s22.addItems(none_cols)
        s22_detected = self.detection.s_params.get("S22")
        if s22_detected in cols:
            self.combo_s22.setCurrentText(s22_detected)
        map_layout.addWidget(self.combo_s22, 2, 3)

        layout.addWidget(grp_map)

        # Dialog Buttons
        btn_bar = QHBoxLayout()
        btn_bar.addStretch()

        self.btn_cancel = QPushButton("Cancel")
        self.btn_cancel.setObjectName("SecondaryBtn")
        self.btn_cancel.clicked.connect(self.reject)
        btn_bar.addWidget(self.btn_cancel)

        self.btn_import = QPushButton("Import Measurement")
        self.btn_import.clicked.connect(self.accept)
        btn_bar.addWidget(self.btn_import)

        layout.addLayout(btn_bar)

    def get_selected_mapping(self):
        """Return the user-selected columns and unit multiplier."""
        freq_col = self.combo_freq.currentText()
        unit_str = self.combo_unit.currentText()
        unit_mult = {"Hz": 1.0, "kHz": 1e3, "MHz": 1e6, "GHz": 1e9}.get(unit_str, 1.0)

        s21 = self.combo_s21.currentText() if self.combo_s21.currentText() != "(None)" else None
        s11 = self.combo_s11.currentText() if self.combo_s11.currentText() != "(None)" else None
        s12 = self.combo_s12.currentText() if self.combo_s12.currentText() != "(None)" else None
        s22 = self.combo_s22.currentText() if self.combo_s22.currentText() != "(None)" else None

        return {
            "freq_col": freq_col,
            "freq_unit_mult": unit_mult,
            "s21_col": s21,
            "s11_col": s11,
            "s12_col": s12,
            "s22_col": s22,
        }
