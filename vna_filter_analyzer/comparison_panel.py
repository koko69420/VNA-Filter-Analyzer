"""Comparison panel for analyzing differences across 2-4 filter measurements."""

from typing import List, Optional
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QGroupBox,
    QTableWidget, QTableWidgetItem, QHeaderView, QComboBox,
    QPushButton, QTextEdit, QFileDialog, QMessageBox, QFrame
)

from .data_model import MeasurementData
from .comparison import (
    compare_measurements,
    calculate_differences,
    generate_dgs_summary,
    DifferenceMetrics,
)
from .csv_export import export_results_to_csv, export_results_to_excel


class ComparisonPanel(QWidget):
    """Panel displaying side-by-side metrics and improvement analysis for up to 4 filters."""

    export_requested = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.measurements: List[MeasurementData] = []
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(12)

        # 1. Header Toolbar
        hdr_bar = QHBoxLayout()
        lbl_title = QLabel("Multi-Filter Comparative Characterization")
        lbl_title.setStyleSheet("font-weight: bold; color: #38bdf8; font-size: 14px;")
        hdr_bar.addWidget(lbl_title)
        hdr_bar.addStretch()

        self.btn_export_csv = QPushButton("Export CSV")
        self.btn_export_csv.setObjectName("SecondaryBtn")
        self.btn_export_csv.clicked.connect(self._export_csv)
        hdr_bar.addWidget(self.btn_export_csv)

        self.btn_export_excel = QPushButton("Export Excel (.xlsx)")
        self.btn_export_excel.clicked.connect(self._export_excel)
        hdr_bar.addWidget(self.btn_export_excel)

        layout.addLayout(hdr_bar)

        # 2. Side-by-Side Comparison Table
        grp_comp = QGroupBox("Side-by-Side Comparison Table")
        comp_layout = QVBoxLayout(grp_comp)

        self.table_comp = QTableWidget()
        self.table_comp.setSortingEnabled(True)
        self.table_comp.verticalHeader().setVisible(False)
        self.table_comp.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        comp_layout.addWidget(self.table_comp)
        layout.addWidget(grp_comp, 3)

        # 3. Pairwise Difference & DGS Analysis
        grp_diff = QGroupBox("Difference & Measured Improvement Analysis")
        diff_layout = QVBoxLayout(grp_diff)

        sel_bar = QHBoxLayout()
        sel_bar.addWidget(QLabel("Baseline Filter:"))
        self.combo_baseline = QComboBox()
        self.combo_baseline.currentIndexChanged.connect(self._update_difference_analysis)
        sel_bar.addWidget(self.combo_baseline)

        sel_bar.addWidget(QLabel("Compare With (Test):"))
        self.combo_test = QComboBox()
        self.combo_test.currentIndexChanged.connect(self._update_difference_analysis)
        sel_bar.addWidget(self.combo_test)
        sel_bar.addStretch()
        diff_layout.addLayout(sel_bar)

        # Narrative Summary Box
        self.txt_narrative = QTextEdit()
        self.txt_narrative.setReadOnly(True)
        self.txt_narrative.setStyleSheet(
            "QTextEdit { background-color: #161922; border: 1px solid #2d3748; border-radius: 4px; padding: 6px; font-size: 12px; color: #e2e8f0; }"
        )
        self.txt_narrative.setMaximumHeight(130)
        diff_layout.addWidget(self.txt_narrative)

        layout.addWidget(grp_diff, 2)

    def set_measurements(self, measurements: List[MeasurementData]):
        self.measurements = [m for m in measurements if m.metrics is not None]
        self._update_comparison_table()
        self._populate_combos()
        self._update_difference_analysis()

    def _update_comparison_table(self):
        if not self.measurements:
            self.table_comp.setRowCount(0)
            self.table_comp.setColumnCount(0)
            return

        rows, df = compare_measurements(self.measurements)
        if df.empty:
            return

        cols = list(df.columns)
        self.table_comp.setColumnCount(len(cols))
        self.table_comp.setHorizontalHeaderLabels(cols)
        self.table_comp.setRowCount(len(df))

        for r_idx in range(len(df)):
            for c_idx, col_name in enumerate(cols):
                val = str(df.iloc[r_idx][col_name])
                item = QTableWidgetItem(val)
                if c_idx >= 2:
                    item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                self.table_comp.setItem(r_idx, c_idx, item)

    def _populate_combos(self):
        self.combo_baseline.blockSignals(True)
        self.combo_test.blockSignals(True)
        self.combo_baseline.clear()
        self.combo_test.clear()

        names = [m.name for m in self.measurements]
        self.combo_baseline.addItems(names)
        self.combo_test.addItems(names)

        # Smart default selection: if "Without DGS" and "DGS" exist, select them
        base_idx = 0
        test_idx = 1 if len(names) > 1 else 0
        for idx, n in enumerate(names):
            if "without" in n.lower() or "wodgs" in n.lower():
                base_idx = idx
            elif "dgs" in n.lower() and "without" not in n.lower():
                test_idx = idx

        if base_idx < len(names):
            self.combo_baseline.setCurrentIndex(base_idx)
        if test_idx < len(names):
            self.combo_test.setCurrentIndex(test_idx)

        self.combo_baseline.blockSignals(False)
        self.combo_test.blockSignals(False)

    def _update_difference_analysis(self):
        if len(self.measurements) < 2:
            self.txt_narrative.setText("Load at least 2 measurements to compute difference & improvement metrics.")
            return

        b_idx = self.combo_baseline.currentIndex()
        t_idx = self.combo_test.currentIndex()

        if b_idx < 0 or t_idx < 0 or b_idx >= len(self.measurements) or t_idx >= len(self.measurements):
            return

        baseline_m = self.measurements[b_idx]
        test_m = self.measurements[t_idx]

        if baseline_m == test_m:
            self.txt_narrative.setText("Select two different filters to compare.")
            return

        diff = calculate_differences(baseline_m, test_m)
        if not diff:
            return

        lines = [
            f"<b>Comparison: {diff.test_name} relative to Baseline ({diff.baseline_name})</b>",
            "<hr style='border: 0; border-top: 1px solid #3b465c;'/>",
        ]
        for bullet in diff.narrative_summary:
            lines.append(f"• {bullet}")

        lines.append("<br/><i>Engineering Note: Statements represent measured laboratory differences from VNA data.</i>")
        self.txt_narrative.setHtml("<br/>".join(lines))

    def _export_csv(self):
        if not self.measurements:
            QMessageBox.warning(self, "Export CSV", "No analyzed measurements available to export.")
            return
        path, _ = QFileDialog.getSaveFileName(self, "Export Comparison Table to CSV", "filter_comparison.csv", "CSV Files (*.csv)")
        if path:
            export_results_to_csv(self.measurements, path)
            QMessageBox.information(self, "Export Complete", f"Comparison table saved to:\n{path}")

    def _export_excel(self):
        if not self.measurements:
            QMessageBox.warning(self, "Export Excel", "No analyzed measurements available to export.")
            return
        path, _ = QFileDialog.getSaveFileName(self, "Export Results to Excel", "filter_analysis_results.xlsx", "Excel Files (*.xlsx)")
        if path:
            export_results_to_excel(self.measurements, path)
            QMessageBox.information(self, "Export Complete", f"Excel report saved to:\n{path}")
