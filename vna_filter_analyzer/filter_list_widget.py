"""Filter management sidebar widget (handles 1-4 loaded measurements)."""

from typing import List, Optional
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QListWidget, QListWidgetItem, QCheckBox, QColorDialog,
    QInputDialog, QMessageBox, QFrame, QComboBox
)

from .data_model import MeasurementData


class FilterItemWidget(QFrame):
    """Custom widget inside list item for a single measurement."""

    visibility_changed = Signal(int, bool)
    color_changed = Signal(int, str)
    style_changed = Signal(int, str)
    rename_requested = Signal(int)
    remove_requested = Signal(int)

    def __init__(self, index: int, measurement: MeasurementData, parent=None):
        super().__init__(parent)
        self.index = index
        self.m = measurement
        self.setStyleSheet(
            "FilterItemWidget { background-color: #1a1d24; border: 1px solid #2d3748; border-radius: 5px; padding: 4px; }"
            "FilterItemWidget:hover { border-color: #38bdf8; }"
        )

        layout = QHBoxLayout(self)
        layout.setContentsMargins(6, 4, 6, 4)
        layout.setSpacing(6)

        # Visibility Checkbox
        self.chk_visible = QCheckBox()
        self.chk_visible.setChecked(self.m.visible)
        self.chk_visible.setToolTip("Toggle plot visibility")
        self.chk_visible.toggled.connect(lambda checked: self.visibility_changed.emit(self.index, checked))
        layout.addWidget(self.chk_visible)

        # Color Swatch Button
        self.btn_color = QPushButton()
        self.btn_color.setFixedSize(20, 20)
        self._update_color_swatch(self.m.color)
        self.btn_color.setToolTip("Change curve color")
        self.btn_color.clicked.connect(self._choose_color)
        layout.addWidget(self.btn_color)

        # Filter Name Label
        self.lbl_name = QLabel(self.m.name)
        self.lbl_name.setStyleSheet("font-weight: 600; color: #f1f5f9;")
        self.lbl_name.setToolTip("Double-click to rename")
        layout.addWidget(self.lbl_name, 1)

        # Line Style Combo
        self.combo_style = QComboBox()
        self.combo_style.addItems(["Solid", "Dash", "Dot"])
        style_idx = {"solid": 0, "dash": 1, "dot": 2}.get(self.m.line_style, 0)
        self.combo_style.setCurrentIndex(style_idx)
        self.combo_style.setFixedWidth(72)
        self.combo_style.currentIndexChanged.connect(self._on_style_changed)
        layout.addWidget(self.combo_style)

        # Rename Button
        self.btn_rename = QPushButton("Rename")
        self.btn_rename.setObjectName("SecondaryBtn")
        self.btn_rename.setFixedWidth(58)
        self.btn_rename.clicked.connect(lambda: self.rename_requested.emit(self.index))
        layout.addWidget(self.btn_rename)

        # Remove Button (X)
        self.btn_remove = QPushButton("×")
        self.btn_remove.setObjectName("DangerBtn")
        self.btn_remove.setFixedSize(22, 22)
        self.btn_remove.setToolTip("Remove measurement")
        self.btn_remove.clicked.connect(lambda: self.remove_requested.emit(self.index))
        layout.addWidget(self.btn_remove)

    def _update_color_swatch(self, hex_color: str):
        self.btn_color.setStyleSheet(
            f"background-color: {hex_color}; border: 1px solid #ffffff; border-radius: 3px;"
        )

    def _choose_color(self):
        col = QColorDialog.getColor(QColor(self.m.color), self, "Select Curve Color")
        if col.isValid():
            hex_col = col.name()
            self.m.color = hex_col
            self._update_color_swatch(hex_col)
            self.color_changed.emit(self.index, hex_col)

    def _on_style_changed(self, idx: int):
        styles = ["solid", "dash", "dot"]
        chosen = styles[idx]
        self.m.line_style = chosen
        self.style_changed.emit(self.index, chosen)

    def update_display(self):
        self.lbl_name.setText(self.m.name)
        self.chk_visible.setChecked(self.m.visible)
        self._update_color_swatch(self.m.color)


class FilterListWidget(QWidget):
    """Sidebar widget managing the loaded measurement list."""

    add_files_requested = Signal()
    selection_changed = Signal(int)
    data_changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.measurements: List[MeasurementData] = []
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        # Section Header
        hdr_layout = QHBoxLayout()
        lbl_title = QLabel("Loaded Measurements (1–4)")
        lbl_title.setStyleSheet("font-weight: bold; color: #38bdf8; font-size: 13px;")
        hdr_layout.addWidget(lbl_title)

        self.lbl_count = QLabel("0/4")
        self.lbl_count.setStyleSheet("color: #94a3b8; font-weight: bold;")
        hdr_layout.addWidget(self.lbl_count)
        layout.addLayout(hdr_layout)

        # Add CSV Files Button
        self.btn_add = QPushButton("+ Add CSV Files")
        self.btn_add.setStyleSheet("padding: 8px; font-size: 12px; font-weight: bold;")
        self.btn_add.clicked.connect(self.add_files_requested.emit)
        layout.addWidget(self.btn_add)

        # Measurements List
        self.list_widget = QListWidget()
        self.list_widget.setStyleSheet(
            "QListWidget { background-color: #14171d; border: 1px solid #2d3748; border-radius: 6px; padding: 4px; }"
            "QListWidget::item { margin-bottom: 4px; }"
            "QListWidget::item:selected { background-color: #0369a1; border-radius: 4px; }"
        )
        self.list_widget.currentRowChanged.connect(self._on_row_selected)
        layout.addWidget(self.list_widget, 1)

        # Quick Actions Helper Info
        info_lbl = QLabel("Tip: Up to 4 filters can be compared concurrently. Select a filter to view individual metrics.")
        info_lbl.setWordWrap(True)
        info_lbl.setStyleSheet("color: #64748b; font-size: 11px;")
        layout.addWidget(info_lbl)

    def set_measurements(self, measurements: List[MeasurementData]):
        self.measurements = measurements
        self.list_widget.clear()
        self.lbl_count.setText(f"{len(measurements)}/4")
        self.btn_add.setEnabled(len(measurements) < 4)

        for idx, m in enumerate(measurements):
            item = QListWidgetItem(self.list_widget)
            widget = FilterItemWidget(idx, m)
            widget.visibility_changed.connect(self._on_visibility_changed)
            widget.color_changed.connect(self._on_color_changed)
            widget.style_changed.connect(self._on_style_changed)
            widget.rename_requested.connect(self._rename_filter)
            widget.remove_requested.connect(self._remove_filter)

            item.setSizeHint(widget.sizeHint())
            self.list_widget.addItem(item)
            self.list_widget.setItemWidget(item, widget)

        if measurements and self.list_widget.currentRow() < 0:
            self.list_widget.setCurrentRow(0)

    def _on_row_selected(self, row: int):
        if 0 <= row < len(self.measurements):
            self.selection_changed.emit(row)

    def _on_visibility_changed(self, idx: int, visible: bool):
        if 0 <= idx < len(self.measurements):
            self.measurements[idx].visible = visible
            self.data_changed.emit()

    def _on_color_changed(self, idx: int, color: str):
        if 0 <= idx < len(self.measurements):
            self.measurements[idx].color = color
            self.data_changed.emit()

    def _on_style_changed(self, idx: int, style: str):
        if 0 <= idx < len(self.measurements):
            self.measurements[idx].line_style = style
            self.data_changed.emit()

    def _rename_filter(self, idx: int):
        if not (0 <= idx < len(self.measurements)):
            return
        m = self.measurements[idx]
        new_name, ok = QInputDialog.getText(self, "Rename Filter", "Enter filter label (e.g. 'DGS', 'Without DGS'):", text=m.name)
        if ok and new_name.strip():
            m.name = new_name.strip()
            self.set_measurements(self.measurements)
            self.data_changed.emit()

    def _remove_filter(self, idx: int):
        if not (0 <= idx < len(self.measurements)):
            return
        m = self.measurements[idx]
        resp = QMessageBox.question(
            self, "Remove Filter", f"Remove '{m.name}' from current session?",
            QMessageBox.Yes | QMessageBox.No
        )
        if resp == QMessageBox.Yes:
            self.measurements.pop(idx)
            self.set_measurements(self.measurements)
            self.data_changed.emit()
