"""Raw data inspection table panel."""

from typing import Optional
import pandas as pd
from PySide6.QtCore import Qt
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QTableWidget,
    QTableWidgetItem, QHeaderView, QComboBox, QPushButton,
    QLineEdit, QFileDialog, QMessageBox
)

from .data_model import MeasurementData


class RawDataPanel(QWidget):
    """Tab displaying raw imported tabular data with search, sorting, and clipboard copy."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.m: Optional[MeasurementData] = None
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        # Toolbar
        bar = QHBoxLayout()
        bar.addWidget(QLabel("Filter:"))
        self.combo_filter = QComboBox()
        self.combo_filter.currentIndexChanged.connect(self._on_filter_changed)
        bar.addWidget(self.combo_filter)

        bar.addSpacing(16)
        bar.addWidget(QLabel("Search/Filter:"))
        self.edit_search = QLineEdit()
        self.edit_search.setPlaceholderText("Filter frequency or dB values...")
        self.edit_search.textChanged.connect(self._filter_rows)
        bar.addWidget(self.edit_search)

        bar.addStretch()

        self.btn_copy = QPushButton("Copy Selected")
        self.btn_copy.setObjectName("SecondaryBtn")
        self.btn_copy.clicked.connect(self._copy_selection)
        bar.addWidget(self.btn_copy)

        self.btn_export = QPushButton("Export CSV")
        self.btn_export.setObjectName("SecondaryBtn")
        self.btn_export.clicked.connect(self._export_csv)
        bar.addWidget(self.btn_export)

        layout.addLayout(bar)

        # Data Table
        self.table = QTableWidget()
        self.table.setSortingEnabled(True)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        layout.addWidget(self.table)

        # Status footer
        self.lbl_status = QLabel("0 data points displayed")
        self.lbl_status.setStyleSheet("color: #64748b; font-size: 11px;")
        layout.addWidget(self.lbl_status)

        self.measurements = []

    def set_measurements(self, measurements: list[MeasurementData]):
        self.measurements = measurements
        self.combo_filter.blockSignals(True)
        self.combo_filter.clear()
        for m in measurements:
            self.combo_filter.addItem(m.name)
        self.combo_filter.blockSignals(False)

        if measurements:
            self.set_measurement(measurements[0])
        else:
            self.table.setRowCount(0)
            self.table.setColumnCount(0)
            self.lbl_status.setText("0 data points displayed")

    def _on_filter_changed(self, idx: int):
        if 0 <= idx < len(self.measurements):
            self.set_measurement(self.measurements[idx])

    def set_measurement(self, measurement: Optional[MeasurementData]):
        self.m = measurement
        if not measurement:
            self.table.setRowCount(0)
            self.table.setColumnCount(0)
            self.lbl_status.setText("0 data points displayed")
            return

        headers = ["Frequency (Hz)", "Freq (GHz)"] + list(measurement.clean_s_params.keys())
        self.table.setColumnCount(len(headers))
        self.table.setHorizontalHeaderLabels(headers)

        num_rows = len(measurement.clean_freq_hz)
        self.table.setRowCount(num_rows)

        freqs = measurement.clean_freq_hz
        for r in range(num_rows):
            f = freqs[r]
            self.table.setItem(r, 0, QTableWidgetItem(f"{f:.1f}"))
            self.table.setItem(r, 1, QTableWidgetItem(f"{f/1e9:.5f}"))

            for c_idx, (p_name, vals) in enumerate(measurement.clean_s_params.items()):
                val = vals[r] if r < len(vals) else 0.0
                self.table.setItem(r, 2 + c_idx, QTableWidgetItem(f"{val:.3f}"))

        self.lbl_status.setText(f"{num_rows} raw measurement points | Source: {measurement.file_path or 'Generated'}")

    def _filter_rows(self, text: str):
        query = text.strip().lower()
        for r in range(self.table.rowCount()):
            if not query:
                self.table.setRowHidden(r, False)
                continue
            matched = False
            for c in range(self.table.columnCount()):
                item = self.table.item(r, c)
                if item and query in item.text().lower():
                    matched = True
                    break
            self.table.setRowHidden(r, not matched)

    def _copy_selection(self):
        selection = self.table.selectedRanges()
        if not selection:
            return
        lines = []
        for r in range(selection[0].topRow(), selection[0].bottomRow() + 1):
            row_vals = []
            for c in range(selection[0].leftColumn(), selection[0].rightColumn() + 1):
                item = self.table.item(r, c)
                row_vals.append(item.text() if item else "")
            lines.append("\t".join(row_vals))
        text = "\n".join(lines)
        QGuiApplication.clipboard().setText(text)

    def _export_csv(self):
        if not self.m:
            return
        path, _ = QFileDialog.getSaveFileName(self, "Export Raw Data", f"{self.m.name}_data.csv", "CSV Files (*.csv)")
        if path:
            data = {"Frequency (Hz)": self.m.clean_freq_hz, "Frequency (GHz)": self.m.clean_freq_hz / 1e9}
            for p, vals in self.m.clean_s_params.items():
                data[f"{p} (dB)"] = vals
            pd.DataFrame(data).to_csv(path, index=False)
            QMessageBox.information(self, "Export Complete", f"Data exported to:\n{path}")
