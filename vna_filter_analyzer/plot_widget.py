"""Interactive RF plotting widget supporting Plotly (via QWebEngineView) and Matplotlib fallback."""

import json
from typing import List, Optional

import numpy as np
import plotly.graph_objects as go
from PySide6.QtCore import Qt, Signal, QUrl
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QToolButton,
    QStackedWidget, QSizePolicy, QFrame
)

# Attempt WebEngine import
try:
    from PySide6.QtWebEngineWidgets import QWebEngineView
    HAS_WEBENGINE = True
except ImportError:
    HAS_WEBENGINE = False

from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.figure import Figure

from .data_model import MeasurementData
from .units import format_frequency, format_bandwidth


class PlotWidget(QWidget):
    """Primary interactive plotting widget for VNA frequency responses."""

    cursor_moved = Signal(float, float)  # freq_hz, db_val

    def __init__(self, parent=None, is_dark: bool = True):
        super().__init__(parent)
        self.is_dark = is_dark
        self.active_param = "S21"
        self.normalized = False
        self.show_markers = True
        self.primary_index = 0
        self.measurements: List[MeasurementData] = []
        self.use_webengine = HAS_WEBENGINE

        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        # Plot Controls Header Toolbar
        ctrl_bar = QFrame()
        ctrl_bar.setStyleSheet("background-color: #1e2430; border-bottom: 1px solid #2d3748; padding: 2px;")
        ctrl_layout = QHBoxLayout(ctrl_bar)
        ctrl_layout.setContentsMargins(8, 3, 8, 3)
        ctrl_layout.setSpacing(6)

        self.title_lbl = QLabel("Filter Frequency Response")
        self.title_lbl.setStyleSheet("font-weight: bold; color: #38bdf8; font-size: 13px;")
        ctrl_layout.addWidget(self.title_lbl)

        ctrl_layout.addStretch()

        # Marker Toggle Button
        self.btn_markers = QToolButton()
        self.btn_markers.setText("Markers: ON")
        self.btn_markers.setCheckable(True)
        self.btn_markers.setChecked(True)
        self.btn_markers.clicked.connect(self._toggle_markers)
        ctrl_layout.addWidget(self.btn_markers)

        # Normalize Responses Toggle
        self.btn_normalize = QToolButton()
        self.btn_normalize.setText("Normalize (0 dB)")
        self.btn_normalize.setCheckable(True)
        self.btn_normalize.setChecked(False)
        self.btn_normalize.setToolTip("Shift traces so their peak is aligned to 0 dB for direct shape comparison")
        self.btn_normalize.clicked.connect(self._toggle_normalize)
        ctrl_layout.addWidget(self.btn_normalize)

        # Backend Toggle (Plotly / Matplotlib)
        if HAS_WEBENGINE:
            self.btn_backend = QToolButton()
            self.btn_backend.setText("Engine: Plotly")
            self.btn_backend.setToolTip("Switch rendering engine between Plotly (interactive web) and Matplotlib (native vector)")
            self.btn_backend.clicked.connect(self._toggle_backend)
            ctrl_layout.addWidget(self.btn_backend)

        # Autoscale Button
        self.btn_autoscale = QToolButton()
        self.btn_autoscale.setText("Autoscale")
        self.btn_autoscale.clicked.connect(self.update_plot)
        ctrl_layout.addWidget(self.btn_autoscale)

        layout.addWidget(ctrl_bar)

        # Stacked display area for WebEngine / Matplotlib
        self.stack = QStackedWidget()
        layout.addWidget(self.stack, 1)

        # Page 0: WebEngineView (Plotly)
        if HAS_WEBENGINE:
            self.web_view = QWebEngineView()
            self.web_view.setStyleSheet("background: transparent;")
            self.stack.addWidget(self.web_view)
        else:
            self.web_view = None

        # Page 1: Matplotlib Canvas Fallback
        self.mpl_fig = Figure(facecolor="#1a1d24" if self.is_dark else "#f8fafc")
        self.mpl_canvas = FigureCanvasQTAgg(self.mpl_fig)
        self.mpl_ax = self.mpl_fig.add_subplot(111)
        self.stack.addWidget(self.mpl_canvas)

        if not HAS_WEBENGINE:
            self.stack.setCurrentIndex(1)
        else:
            self.stack.setCurrentIndex(0)

        # Interactive Cursor Coordinates readout bar
        self.cursor_bar = QLabel("Hover over plot to inspect coordinates | Frequency: --- | Magnitude: ---")
        self.cursor_bar.setStyleSheet("background-color: #14171d; color: #94a3b8; padding: 4px 8px; font-family: monospace; font-size: 11px;")
        layout.addWidget(self.cursor_bar)

    def set_dark_mode(self, is_dark: bool):
        self.is_dark = is_dark
        self.mpl_fig.patch.set_facecolor("#1a1d24" if is_dark else "#f8fafc")
        self.update_plot()

    def set_data(self, measurements: List[MeasurementData], active_param: str = "S21", primary_idx: int = 0):
        self.measurements = measurements
        self.active_param = active_param
        self.primary_index = primary_idx
        self.title_lbl.setText(f"{active_param} Transmission & Reflection Response")
        self.update_plot()

    def _toggle_markers(self):
        self.show_markers = self.btn_markers.isChecked()
        self.btn_markers.setText("Markers: ON" if self.show_markers else "Markers: OFF")
        self.update_plot()

    def _toggle_normalize(self):
        self.normalized = self.btn_normalize.isChecked()
        self.update_plot()

    def _toggle_backend(self):
        if not HAS_WEBENGINE:
            return
        if self.use_webengine:
            self.use_webengine = False
            self.btn_backend.setText("Engine: Matplotlib")
            self.stack.setCurrentIndex(1)
        else:
            self.use_webengine = True
            self.btn_backend.setText("Engine: Plotly")
            self.stack.setCurrentIndex(0)
        self.update_plot()

    def update_plot(self):
        valid = [m for m in self.measurements if m.visible and self.active_param in m.clean_s_params]

        if self.use_webengine and self.web_view is not None:
            self._render_plotly(valid)
        else:
            self._render_matplotlib(valid)

    def _render_plotly(self, valid: List[MeasurementData]):
        fig = go.Figure()
        theme_bg = "#1a1d24" if self.is_dark else "#ffffff"
        grid_color = "#2d3748" if self.is_dark else "#e2e8f0"
        text_color = "#f1f5f9" if self.is_dark else "#1e293b"

        if not valid:
            fig.update_layout(
                paper_bgcolor=theme_bg,
                plot_bgcolor=theme_bg,
                font=dict(color=text_color),
                annotations=[dict(text="No measurement files loaded. Click 'Add CSV Files' to import.", showarrow=False, font=dict(size=14, color="#94a3b8"))],
            )
            html = fig.to_html(include_plotlyjs="cdn", full_html=True)
            self.web_view.setHtml(html)
            return

        # Determine frequency units (GHz or MHz)
        max_freq = max(float(m.clean_freq_hz[-1]) for m in valid)
        freq_scale = 1e9 if max_freq >= 1e8 else 1e6
        unit_str = "GHz" if freq_scale == 1e9 else "MHz"

        # Traces
        for idx, m in enumerate(valid):
            x = m.clean_freq_hz / freq_scale
            y = np.copy(m.clean_s_params[self.active_param])
            if self.normalized:
                y -= np.max(y)

            label = m.name if not self.normalized else f"{m.name} (Norm 0 dB)"
            dash_style = "solid" if m.line_style == "solid" else ("dash" if m.line_style == "dash" else "dot")

            # Main trace
            fig.add_trace(go.Scatter(
                x=x,
                y=y,
                mode="lines",
                name=label,
                line=dict(color=m.color, width=2.2, dash=dash_style),
                hovertemplate=f"<b>{m.name}</b><br>Freq: %{{x:.4f}} {unit_str}<br>{self.active_param}: %{{y:.2f}} dB<extra></extra>",
            ))

            # Smoothed trace if mode is 'Both'
            if m.display_mode == "Both" and self.active_param in m.smoothed_s_params:
                y_sm = np.copy(m.smoothed_s_params[self.active_param])
                if self.normalized:
                    y_sm -= np.max(y_sm)
                fig.add_trace(go.Scatter(
                    x=x,
                    y=y_sm,
                    mode="lines",
                    name=f"{m.name} (Smoothed)",
                    line=dict(color=m.color, width=1.5, dash="dot"),
                    hovertemplate=f"<b>{m.name} (Smoothed)</b><br>Freq: %{{x:.4f}} {unit_str}<br>{self.active_param}: %{{y:.2f}} dB<extra></extra>",
                ))

        # Markers for primary active filter
        if self.show_markers and valid:
            primary_m = valid[self.primary_index % len(valid)]
            met = primary_m.metrics
            if met is not None and self.active_param in ("S21", "S12"):
                fc = met.center_freq_hz / freq_scale
                fl = met.f_lower_hz / freq_scale
                fh = met.f_upper_hz / freq_scale
                peak_val = met.peak_s21_db if not self.normalized else 0.0
                ref_3db = peak_val - met.bw_threshold_db

                # Shaded passband region [fl, fh]
                fig.add_vrect(
                    x0=fl,
                    x1=fh,
                    fillcolor="#38bdf8",
                    opacity=0.12,
                    layer="below",
                    line_width=0,
                    annotation_text=f"BW: {format_bandwidth(met.bandwidth_hz)}",
                    annotation_position="bottom right",
                    annotation_font=dict(size=11, color="#38bdf8"),
                )

                # Center Frequency marker (Fc)
                fig.add_vline(
                    x=fc,
                    line=dict(color="#ef4444", width=1.8, dash="dash"),
                    annotation_text=f"Fc = {format_frequency(met.center_freq_hz)}",
                    annotation_position="top left",
                    annotation_font=dict(size=11, color="#ef4444", family="sans-serif"),
                )

                # Cutoff markers (fL, fH)
                fig.add_vline(
                    x=fl,
                    line=dict(color="#10b981", width=1.4, dash="dot"),
                    annotation_text=f"fL = {format_frequency(met.f_lower_hz)}",
                    annotation_position="bottom left",
                    annotation_font=dict(size=10, color="#10b981"),
                )
                fig.add_vline(
                    x=fh,
                    line=dict(color="#a855f7", width=1.4, dash="dot"),
                    annotation_text=f"fH = {format_frequency(met.f_upper_hz)}",
                    annotation_position="bottom right",
                    annotation_font=dict(size=10, color="#a855f7"),
                )

                # Horizontal -3 dB line
                fig.add_hline(
                    y=ref_3db,
                    line=dict(color="#94a3b8", width=1.2, dash="dashdot"),
                    annotation_text=f"-{met.bw_threshold_db:g}dB Ref ({ref_3db:.2f} dB)",
                    annotation_position="top right",
                    annotation_font=dict(size=10, color="#94a3b8"),
                )

                # Peak point marker
                fig.add_trace(go.Scatter(
                    x=[fc],
                    y=[peak_val],
                    mode="markers+text",
                    name="Peak S21",
                    marker=dict(color="#ef4444", size=9, symbol="diamond"),
                    text=[f"{peak_val:.2f} dB"],
                    textposition="top center",
                    textfont=dict(color="#ef4444", size=11),
                    hoverinfo="skip",
                    showlegend=False,
                ))

        fig.update_layout(
            paper_bgcolor=theme_bg,
            plot_bgcolor=theme_bg,
            font=dict(color=text_color, family="-apple-system, BlinkMacSystemFont, Segoe UI, Roboto, sans-serif"),
            margin=dict(l=60, r=40, t=40, b=50),
            hovermode="x unified",
            xaxis=dict(
                title=f"Frequency ({unit_str})",
                gridcolor=grid_color,
                zerolinecolor=grid_color,
                showgrid=True,
            ),
            yaxis=dict(
                title=f"{self.active_param} Magnitude (dB)",
                gridcolor=grid_color,
                zerolinecolor=grid_color,
                showgrid=True,
            ),
            legend=dict(
                orientation="h",
                yanchor="bottom",
                y=1.02,
                xanchor="right",
                x=1,
                bgcolor="rgba(0,0,0,0.2)",
            ),
        )

        # Convert to self-contained HTML
        html_content = fig.to_html(include_plotlyjs="cdn", full_html=True)
        self.web_view.setHtml(html_content)

    def _render_matplotlib(self, valid: List[MeasurementData]):
        self.mpl_ax.clear()
        bg_color = "#1a1d24" if self.is_dark else "#ffffff"
        text_color = "#f1f5f9" if self.is_dark else "#1e293b"
        grid_color = "#2d3748" if self.is_dark else "#e2e8f0"

        self.mpl_ax.set_facecolor(bg_color)
        self.mpl_fig.patch.set_facecolor(bg_color)

        if not valid:
            self.mpl_ax.text(0.5, 0.5, "No measurements loaded.", color="#94a3b8", ha="center", va="center", transform=self.mpl_ax.transAxes)
            self.mpl_canvas.draw()
            return

        max_freq = max(float(m.clean_freq_hz[-1]) for m in valid)
        freq_scale = 1e9 if max_freq >= 1e8 else 1e6
        unit_str = "GHz" if freq_scale == 1e9 else "MHz"

        for m in valid:
            x = m.clean_freq_hz / freq_scale
            y = np.copy(m.clean_s_params[self.active_param])
            if self.normalized:
                y -= np.max(y)
            label = m.name if not self.normalized else f"{m.name} (Norm 0 dB)"
            self.mpl_ax.plot(x, y, label=label, color=m.color, linewidth=1.8)

        if self.show_markers and valid:
            primary_m = valid[self.primary_index % len(valid)]
            met = primary_m.metrics
            if met is not None and self.active_param in ("S21", "S12"):
                fc = met.center_freq_hz / freq_scale
                fl = met.f_lower_hz / freq_scale
                fh = met.f_upper_hz / freq_scale
                peak_val = met.peak_s21_db if not self.normalized else 0.0
                ref_3db = peak_val - met.bw_threshold_db

                self.mpl_ax.axvspan(fl, fh, color="#38bdf8", alpha=0.15)
                self.mpl_ax.axvline(fc, color="#ef4444", linestyle="--", label=f"Fc = {format_frequency(met.center_freq_hz)}")
                self.mpl_ax.axvline(fl, color="#10b981", linestyle=":", label=f"fL = {format_frequency(met.f_lower_hz)}")
                self.mpl_ax.axvline(fh, color="#a855f7", linestyle=":", label=f"fH = {format_frequency(met.f_upper_hz)}")
                self.mpl_ax.axhline(ref_3db, color="#94a3b8", linestyle="-.", alpha=0.8)
                self.mpl_ax.plot([fc], [peak_val], marker="o", color="#ef4444")

        self.mpl_ax.set_xlabel(f"Frequency ({unit_str})", color=text_color)
        self.mpl_ax.set_ylabel(f"{self.active_param} (dB)", color=text_color)
        self.mpl_ax.tick_params(colors=text_color)
        self.mpl_ax.grid(True, linestyle="--", color=grid_color, alpha=0.7)
        self.mpl_ax.legend(facecolor=bg_color, edgecolor=grid_color, labelcolor=text_color, fontsize=9)
        self.mpl_fig.tight_layout()
        self.mpl_canvas.draw()
