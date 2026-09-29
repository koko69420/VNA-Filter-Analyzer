"""Detailed filter characterization and analysis panel."""

from typing import List, Optional
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel,
    QGroupBox, QComboBox, QDoubleSpinBox, QSpinBox, QCheckBox,
    QPushButton, QTableWidget, QTableWidgetItem, QHeaderView,
    QScrollArea, QFrame, QMessageBox
)

from .data_model import MeasurementData, FilterMetrics
from .units import format_frequency, format_bandwidth, format_db, format_percentage
from .filter_metrics import calculate_filter_metrics
from .smoothing import apply_smoothing, check_smoothing_shift
from .peak_detection import detect_passbands


class KPICard(QFrame):
    """Modern engineering summary metric card."""

    def __init__(self, title: str, value: str = "---", subtext: str = "", parent=None):
        super().__init__(parent)
        self.setStyleSheet(
            "KPICard { background-color: #1a1d24; border: 1px solid #2d3748; border-radius: 6px; padding: 6px; }"
        )
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(2)

        self.lbl_title = QLabel(title.upper())
        self.lbl_title.setStyleSheet("color: #94a3b8; font-size: 10px; font-weight: bold; letter-spacing: 0.5px;")
        layout.addWidget(self.lbl_title)

        self.lbl_val = QLabel(value)
        self.lbl_val.setStyleSheet("color: #38bdf8; font-size: 16px; font-weight: bold;")
        layout.addWidget(self.lbl_val)

        self.lbl_sub = QLabel(subtext)
        self.lbl_sub.setStyleSheet("color: #64748b; font-size: 10px;")
        layout.addWidget(self.lbl_sub)

    def set_data(self, value: str, subtext: str = ""):
        self.lbl_val.setText(value)
        if subtext:
            self.lbl_sub.setText(subtext)


class AnalysisPanel(QWidget):
    """Results and parameter controls panel for the active filter measurement."""

    analysis_changed = Signal()  # Emitted when parameters, smoothing, or overrides change

    def __init__(self, parent=None):
        super().__init__(parent)
        self.m: Optional[MeasurementData] = None
        self._init_ui()

    def _init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(8, 8, 8, 8)
        main_layout.setSpacing(10)

        # Scroll area for compact responsive layout
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(12)

        # 1. Multiple Passband Alert Banner
        self.banner_passband = QFrame()
        self.banner_passband.setStyleSheet("background-color: #78350f; border: 1px solid #d97706; border-radius: 6px; padding: 6px;")
        banner_layout = QHBoxLayout(self.banner_passband)
        banner_layout.setContentsMargins(8, 4, 8, 4)
        self.lbl_banner = QLabel("⚠️ Multiple transmission peaks detected. Select the primary passband to analyze:")
        self.lbl_banner.setStyleSheet("color: #fef3c7; font-weight: bold;")
        banner_layout.addWidget(self.lbl_banner)

        self.combo_passbands = QComboBox()
        self.combo_passbands.currentIndexChanged.connect(self._on_passband_selected)
        banner_layout.addWidget(self.combo_passbands)
        self.banner_passband.setVisible(False)
        layout.addWidget(self.banner_passband)

        # 2. Key KPI Summary Cards Banner
        kpi_grid = QGridLayout()
        kpi_grid.setSpacing(8)

        self.card_fc = KPICard("Center Frequency", "---", "Peak S21 transmission")
        self.card_il = KPICard("Insertion Loss", "---", "-Peak S21 magnitude")
        self.card_bw = KPICard("-3 dB Bandwidth", "---", "fH - fL")
        self.card_fbw = KPICard("Fractional BW", "---", "(BW / Fc) × 100%")
        self.card_q = KPICard("Loaded Q", "---", "Fc / BW (-3dB)")
        self.card_rl = KPICard("Return Loss", "---", "-Min in-band S11")
        self.card_vswr = KPICard("VSWR @ Fc", "---", "(1+|Γ|) / (1-|Γ|)")
        self.card_ripple = KPICard("Passband Ripple", "---", "Max - Min in passband")

        kpi_grid.addWidget(self.card_fc, 0, 0)
        kpi_grid.addWidget(self.card_il, 0, 1)
        kpi_grid.addWidget(self.card_bw, 0, 2)
        kpi_grid.addWidget(self.card_fbw, 0, 3)
        kpi_grid.addWidget(self.card_q, 1, 0)
        kpi_grid.addWidget(self.card_rl, 1, 1)
        kpi_grid.addWidget(self.card_vswr, 1, 2)
        kpi_grid.addWidget(self.card_ripple, 1, 3)

        layout.addLayout(kpi_grid)

        # 3. Two-Column Layout for Controls & Detailed Tables
        cols_layout = QHBoxLayout()
        cols_layout.setSpacing(12)

        # Left Column: Analysis Controls & Smoothing
        left_col = QVBoxLayout()
        left_col.setSpacing(10)

        # Group: Threshold & S-Parameter
        grp_thresh = QGroupBox("Analysis Threshold & S-Parameter")
        thresh_layout = QGridLayout(grp_thresh)

        thresh_layout.addWidget(QLabel("Bandwidth Ref Level:"), 0, 0)
        self.combo_threshold = QComboBox()
        self.combo_threshold.addItems(["-1 dB", "-3 dB", "-6 dB", "-10 dB"])
        self.combo_threshold.setCurrentIndex(1)  # Default -3 dB
        self.combo_threshold.currentIndexChanged.connect(self._on_threshold_changed)
        thresh_layout.addWidget(self.combo_threshold, 0, 1)

        thresh_layout.addWidget(QLabel("Active S-Parameter:"), 1, 0)
        self.combo_sparam = QComboBox()
        self.combo_sparam.currentIndexChanged.connect(self._on_sparam_changed)
        thresh_layout.addWidget(self.combo_sparam, 1, 1)
        left_col.addWidget(grp_thresh)

        # Group: Manual Marker Overrides
        grp_override = QGroupBox("Manual Marker Overrides")
        over_layout = QGridLayout(grp_override)

        self.chk_manual = QCheckBox("Enable Manual Markers")
        self.chk_manual.toggled.connect(self._on_manual_toggled)
        over_layout.addWidget(self.chk_manual, 0, 0, 1, 2)

        over_layout.addWidget(QLabel("Manual Fc (GHz):"), 1, 0)
        self.spin_fc = QDoubleSpinBox()
        self.spin_fc.setRange(0.001, 100.0)
        self.spin_fc.setDecimals(4)
        self.spin_fc.setSingleStep(0.01)
        self.spin_fc.setEnabled(False)
        self.spin_fc.valueChanged.connect(self._on_manual_val_changed)
        over_layout.addWidget(self.spin_fc, 1, 1)

        over_layout.addWidget(QLabel("Manual fL (GHz):"), 2, 0)
        self.spin_fl = QDoubleSpinBox()
        self.spin_fl.setRange(0.001, 100.0)
        self.spin_fl.setDecimals(4)
        self.spin_fl.setSingleStep(0.01)
        self.spin_fl.setEnabled(False)
        self.spin_fl.valueChanged.connect(self._on_manual_val_changed)
        over_layout.addWidget(self.spin_fl, 2, 1)

        over_layout.addWidget(QLabel("Manual fH (GHz):"), 3, 0)
        self.spin_fh = QDoubleSpinBox()
        self.spin_fh.setRange(0.001, 100.0)
        self.spin_fh.setDecimals(4)
        self.spin_fh.setSingleStep(0.01)
        self.spin_fh.setEnabled(False)
        self.spin_fh.valueChanged.connect(self._on_manual_val_changed)
        over_layout.addWidget(self.spin_fh, 3, 1)

        self.btn_reset_markers = QPushButton("Reset to Auto Detection")
        self.btn_reset_markers.setObjectName("SecondaryBtn")
        self.btn_reset_markers.clicked.connect(self._reset_manual_markers)
        over_layout.addWidget(self.btn_reset_markers, 4, 0, 1, 2)

        left_col.addWidget(grp_override)

        # Group: Display Smoothing
        grp_smooth = QGroupBox("Display Smoothing (Visualization Only)")
        smooth_layout = QGridLayout(grp_smooth)

        smooth_layout.addWidget(QLabel("Display Mode:"), 0, 0)
        self.combo_disp_mode = QComboBox()
        self.combo_disp_mode.addItems(["Raw", "Smoothed", "Both"])
        self.combo_disp_mode.currentIndexChanged.connect(self._on_display_mode_changed)
        smooth_layout.addWidget(self.combo_disp_mode, 0, 1)

        smooth_layout.addWidget(QLabel("Filter Algorithm:"), 1, 0)
        self.combo_smooth_algo = QComboBox()
        self.combo_smooth_algo.addItems(["Savitzky-Golay", "Moving Average"])
        self.combo_smooth_algo.currentIndexChanged.connect(self._on_smooth_settings_changed)
        smooth_layout.addWidget(self.combo_smooth_algo, 1, 1)

        smooth_layout.addWidget(QLabel("Window Length:"), 2, 0)
        self.spin_window = QSpinBox()
        self.spin_window.setRange(3, 101)
        self.spin_window.setSingleStep(2)
        self.spin_window.setValue(15)
        self.spin_window.valueChanged.connect(self._on_smooth_settings_changed)
        smooth_layout.addWidget(self.spin_window, 2, 1)

        notice_lbl = QLabel("*Note: Calculated metrics are always extracted from raw measurement points, not smoothed curves.")
        notice_lbl.setWordWrap(True)
        notice_lbl.setStyleSheet("color: #64748b; font-size: 10px;")
        smooth_layout.addWidget(notice_lbl, 3, 0, 1, 2)

        left_col.addWidget(grp_smooth)
        left_col.addStretch()
        cols_layout.addLayout(left_col, 1)

        # Right Column: Detailed Metrics & Stopband Tables
        right_col = QVBoxLayout()
        right_col.setSpacing(10)

        # Detailed Parameters Table
        grp_table = QGroupBox("Passband & Cutoff Characteristics")
        tbl_layout = QVBoxLayout(grp_table)

        self.table_metrics = QTableWidget()
        self.table_metrics.setColumnCount(3)
        self.table_metrics.setHorizontalHeaderLabels(["Characteristic", "Value", "Notes / Limits"])
        self.table_metrics.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.table_metrics.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.table_metrics.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self.table_metrics.verticalHeader().setVisible(False)
        tbl_layout.addWidget(self.table_metrics)
        right_col.addWidget(grp_table)

        # Stopband & Selectivity Table
        grp_stop = QGroupBox("Stopband Rejection & Roll-Off Selectivity")
        stop_layout = QVBoxLayout(grp_stop)

        self.table_stopband = QTableWidget()
        self.table_stopband.setColumnCount(3)
        self.table_stopband.setHorizontalHeaderLabels(["Test Condition", "Rejection / Slope", "Measurement Point"])
        self.table_stopband.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.table_stopband.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.table_stopband.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self.table_stopband.verticalHeader().setVisible(False)
        stop_layout.addWidget(self.table_stopband)
        right_col.addWidget(grp_stop)

        cols_layout.addLayout(right_col, 2)
        layout.addLayout(cols_layout)

        # Bottom Engineering Disclaimer
        disclaimer = QLabel(
            "Engineering Notice: All metrics (Loaded Q, Cutoff, Bandwidth, VSWR) are calculated from the raw VNA data. "
            "Values are provided for engineering characterization and must be validated against instrument calibration standards."
        )
        disclaimer.setStyleSheet("color: #64748b; font-style: italic; font-size: 11px; padding: 4px;")
        disclaimer.setWordWrap(True)
        layout.addWidget(disclaimer)

        scroll.setWidget(container)
        main_layout.addWidget(scroll)

    def set_measurement(self, measurement: Optional[MeasurementData]):
        self.m = measurement
        if measurement is None:
            self._clear_display()
            return

        # Update S-parameter options
        self.combo_sparam.blockSignals(True)
        self.combo_sparam.clear()
        for p in measurement.available_s_params():
            self.combo_sparam.addItem(p)
        if measurement.active_s_param in measurement.available_s_params():
            self.combo_sparam.setCurrentText(measurement.active_s_param)
        self.combo_sparam.blockSignals(False)

        # Check detected passbands
        s21 = measurement.clean_s_params.get("S21", next(iter(measurement.clean_s_params.values())))
        if not measurement.detected_passbands:
            measurement.detected_passbands = detect_passbands(measurement.clean_freq_hz, s21)

        self.combo_passbands.blockSignals(True)
        self.combo_passbands.clear()
        if len(measurement.detected_passbands) > 1:
            self.banner_passband.setVisible(True)
            for pb in measurement.detected_passbands:
                self.combo_passbands.addItem(pb.label)
            self.combo_passbands.setCurrentIndex(measurement.active_passband_idx)
        else:
            self.banner_passband.setVisible(False)
        self.combo_passbands.blockSignals(False)

        # Sync manual controls
        self.chk_manual.blockSignals(True)
        self.chk_manual.setChecked(measurement.use_manual_markers)
        self._update_manual_spinboxes_state(measurement.use_manual_markers)
        if measurement.metrics:
            self.spin_fc.setValue(measurement.metrics.center_freq_hz / 1e9)
            self.spin_fl.setValue(measurement.metrics.f_lower_hz / 1e9)
            self.spin_fh.setValue(measurement.metrics.f_upper_hz / 1e9)
        self.chk_manual.blockSignals(False)

        # Sync smoothing
        self.combo_disp_mode.blockSignals(True)
        self.combo_disp_mode.setCurrentText(measurement.display_mode)
        self.combo_disp_mode.blockSignals(False)

        self.spin_window.blockSignals(True)
        self.spin_window.setValue(measurement.smoothing_window)
        self.spin_window.blockSignals(False)

        # Compute smoothing for display
        self._recompute_smoothing()

        # Recalculate metrics
        self._recalculate_metrics()

    def _clear_display(self):
        for card in [self.card_fc, self.card_il, self.card_bw, self.card_fbw, self.card_q, self.card_rl, self.card_vswr, self.card_ripple]:
            card.set_data("---")
        self.table_metrics.setRowCount(0)
        self.table_stopband.setRowCount(0)
        self.banner_passband.setVisible(False)

    def _on_passband_selected(self, idx: int):
        if self.m and 0 <= idx < len(self.m.detected_passbands):
            self.m.active_passband_idx = idx
            self._recalculate_metrics()

    def _on_threshold_changed(self, idx: int):
        vals = [1.0, 3.0, 6.0, 10.0]
        if self.m:
            self.m.bw_threshold_db = vals[idx]
            self._recalculate_metrics()

    def _on_sparam_changed(self, text: str):
        if self.m and text:
            self.m.active_s_param = text
            self._recalculate_metrics()

    def _on_manual_toggled(self, checked: bool):
        if self.m:
            self.m.use_manual_markers = checked
            self._update_manual_spinboxes_state(checked)
            self._recalculate_metrics()

    def _update_manual_spinboxes_state(self, enabled: bool):
        self.spin_fc.setEnabled(enabled)
        self.spin_fl.setEnabled(enabled)
        self.spin_fh.setEnabled(enabled)

    def _on_manual_val_changed(self):
        if self.m and self.m.use_manual_markers:
            self.m.manual_fc_hz = self.spin_fc.value() * 1e9
            self.m.manual_fl_hz = self.spin_fl.value() * 1e9
            self.m.manual_fh_hz = self.spin_fh.value() * 1e9
            self._recalculate_metrics()

    def _reset_manual_markers(self):
        if self.m:
            self.chk_manual.setChecked(False)
            self.m.use_manual_markers = False
            self.m.manual_fc_hz = None
            self.m.manual_fl_hz = None
            self.m.manual_fh_hz = None
            self._recalculate_metrics()

    def _on_display_mode_changed(self, text: str):
        if self.m:
            self.m.display_mode = text
            self.analysis_changed.emit()

    def _on_smooth_settings_changed(self):
        if self.m:
            self.m.smoothing_method = "savgol" if self.combo_smooth_algo.currentIndex() == 0 else "moving_avg"
            self.m.smoothing_window = self.spin_window.value()
            self._recompute_smoothing()
            self.analysis_changed.emit()

    def _recompute_smoothing(self):
        if not self.m:
            return
        w = self.m.smoothing_window
        method = self.m.smoothing_method
        for p, data in self.m.clean_s_params.items():
            self.m.smoothed_s_params[p] = apply_smoothing(data, method=method, window_len=w)

    def _recalculate_metrics(self):
        if not self.m:
            return

        s21 = self.m.clean_s_params.get(self.m.active_s_param, next(iter(self.m.clean_s_params.values())))
        s11 = self.m.clean_s_params.get("S11")

        search_fc = None
        if self.m.detected_passbands and 0 <= self.m.active_passband_idx < len(self.m.detected_passbands):
            search_fc = self.m.detected_passbands[self.m.active_passband_idx].fc_hz

        self.m.metrics = calculate_filter_metrics(
            freq_hz=self.m.clean_freq_hz,
            s21_db=s21,
            s11_db=s11,
            threshold_db=self.m.bw_threshold_db,
            center_freq_search_hz=search_fc,
            manual_fc_hz=self.m.manual_fc_hz if self.m.use_manual_markers else None,
            manual_fl_hz=self.m.manual_fl_hz if self.m.use_manual_markers else None,
            manual_fh_hz=self.m.manual_fh_hz if self.m.use_manual_markers else None,
        )

        self._update_kpi_cards()
        self._update_detailed_tables()
        self.analysis_changed.emit()

    def _update_kpi_cards(self):
        met = self.m.metrics
        if not met:
            return

        self.card_fc.set_data(format_frequency(met.center_freq_hz), "Peak transmission")
        self.card_il.set_data(format_db(met.insertion_loss_db), f"Peak S21: {met.peak_s21_db:.2f} dB")
        self.card_bw.set_data(format_bandwidth(met.bandwidth_hz), f"-{met.bw_threshold_db:g} dB crossing")
        self.card_fbw.set_data(format_percentage(met.fractional_bw_pct), "(BW / Fc) × 100")
        self.card_q.set_data(f"{met.loaded_q:.2f}", "Loaded Q (Fc / BW)")
        self.card_rl.set_data(format_db(met.return_loss_db) if met.return_loss_db is not None else "N/A", f"Min S11: {met.min_s11_db:.1f} dB" if met.min_s11_db is not None else "")
        self.card_vswr.set_data(f"{met.vswr_at_fc:.2f}" if met.vswr_at_fc is not None else "N/A", f"Min in-band: {met.min_vswr:.2f}" if met.min_vswr is not None else "")
        self.card_ripple.set_data(format_db(met.passband_ripple_db) if met.passband_ripple_db is not None else "N/A", "Peak-to-peak in-band")

    def _update_detailed_tables(self):
        met = self.m.metrics
        if not met:
            return

        # Passband rows
        rows = [
            ("Center Frequency (Fc)", format_frequency(met.center_freq_hz), "Parabolic vertex interpolation"),
            ("Peak Transmission (S21)", format_db(met.peak_s21_db), "Maximum transmission magnitude"),
            ("Insertion Loss", format_db(met.insertion_loss_db), "Positive attenuation convention (-Peak S21)"),
            (f"Lower Cutoff (fL, -{met.bw_threshold_db:g}dB)", format_frequency(met.f_lower_hz), "Interpolated crossing frequency"),
            (f"Upper Cutoff (fH, -{met.bw_threshold_db:g}dB)", format_frequency(met.f_upper_hz), "Interpolated crossing frequency"),
            (f"Bandwidth (BW, -{met.bw_threshold_db:g}dB)", format_bandwidth(met.bandwidth_hz), "fH - fL"),
            ("Fractional Bandwidth (FBW)", format_percentage(met.fractional_bw_pct), "Bandwidth normalized to Fc"),
            ("Loaded Q Factor", f"{met.loaded_q:.2f}", "Fc / BW (3 dB loaded Q)"),
            ("Passband Ripple", format_db(met.passband_ripple_db) if met.passband_ripple_db is not None else "N/A", "Max S21 - Min S21 across [fL, fH]"),
            ("Min In-Band S11", format_db(met.min_s11_db) if met.min_s11_db is not None else "N/A", "Measured minimum reflection"),
            ("Return Loss (RL)", format_db(met.return_loss_db) if met.return_loss_db is not None else "N/A", "-Min(S11) in-band"),
            ("VSWR at Fc", f"{met.vswr_at_fc:.2f}" if met.vswr_at_fc is not None else "N/A", "Voltage Standing Wave Ratio at Fc"),
            ("Min VSWR in Passband", f"{met.min_vswr:.2f}" if met.min_vswr is not None else "N/A", "Best impedance matching point"),
        ]

        self.table_metrics.setRowCount(len(rows))
        for r_idx, (k, v, notes) in enumerate(rows):
            self.table_metrics.setItem(r_idx, 0, QTableWidgetItem(k))
            val_item = QTableWidgetItem(v)
            val_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self.table_metrics.setItem(r_idx, 1, val_item)
            self.table_metrics.setItem(r_idx, 2, QTableWidgetItem(notes))

        # Stopband rows
        stop_rows = [
            ("Lower Stopband Attenuation", format_db(met.lower_stopband_atten_db) if met.lower_stopband_atten_db is not None else "N/A", f"Frequencies below {format_frequency(met.f_lower_hz)}"),
            ("Upper Stopband Attenuation", format_db(met.upper_stopband_atten_db) if met.upper_stopband_atten_db is not None else "N/A", f"Frequencies above {format_frequency(met.f_upper_hz)}"),
            ("Lower Skirt Roll-Off", f"{met.lower_transition_slope_db_per_ghz:.1f} dB/GHz" if met.lower_transition_slope_db_per_ghz is not None else "N/A", "Selectivity transition slope below passband"),
            ("Upper Skirt Roll-Off", f"{met.upper_transition_slope_db_per_ghz:.1f} dB/GHz" if met.upper_transition_slope_db_per_ghz is not None else "N/A", "Selectivity transition slope above passband"),
        ]

        for f_hz, rej_db in met.stopband_rejections.items():
            stop_rows.append((f"Rejection @ {format_frequency(f_hz)}", format_db(rej_db), "Specified out-of-band test point"))

        self.table_stopband.setRowCount(len(stop_rows))
        for r_idx, (cond, val, pt) in enumerate(stop_rows):
            self.table_stopband.setItem(r_idx, 0, QTableWidgetItem(cond))
            val_item = QTableWidgetItem(val)
            val_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self.table_stopband.setItem(r_idx, 1, val_item)
            self.table_stopband.setItem(r_idx, 2, QTableWidgetItem(pt))
