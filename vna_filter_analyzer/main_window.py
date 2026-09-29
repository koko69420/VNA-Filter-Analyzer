"""Main application window for Rohde & Schwarz VNA Filter Analyzer."""

import os
from typing import List, Optional

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QAction, QIcon, QKeySequence, QDragEnterEvent, QDropEvent
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QSplitter,
    QTabWidget, QToolBar, QStatusBar, QFileDialog, QMessageBox,
    QLabel, QComboBox, QToolButton, QDialog
)

from .data_model import MeasurementData
from .csv_parser import parse_vna_file, detect_columns
from .data_quality import check_data_quality
from .filter_metrics import calculate_filter_metrics
from .project import save_project, load_project

from .styles import DARK_THEME, LIGHT_THEME
from .plot_widget import PlotWidget
from .filter_list_widget import FilterListWidget
from .analysis_panel import AnalysisPanel
from .comparison_panel import ComparisonPanel
from .raw_data_panel import RawDataPanel
from .import_dialog import ImportPreviewDialog
from .settings_dialog import SettingsDialog

from .graph_export import export_figure
from .csv_export import export_results_to_csv, export_results_to_excel, export_results_to_json
from .report_export import generate_pdf_report


class MainWindow(QMainWindow):
    """Main application window."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Rohde & Schwarz VNA Filter Analyzer")
        self.resize(1280, 850)
        self.setAcceptDrops(True)

        self.measurements: List[MeasurementData] = []
        self.active_index = 0
        self.active_param = "S21"
        self.is_dark = True
        self.engineering_notes = ""

        # Set application icon
        icon_path = os.path.join(os.path.dirname(__file__), "..", "resources", "icon.png")
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))

        self._init_ui()
        self._apply_theme()
        self._update_status()

    def _init_ui(self):
        # 1. Menu Bar
        self._create_menu_bar()

        # 2. Main Tool Bar
        self._create_tool_bar()

        # 3. Central Splitter (Sidebar + Tabs)
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout(central_widget)
        main_layout.setContentsMargins(6, 6, 6, 6)

        splitter = QSplitter(Qt.Horizontal)

        # Left Sidebar: Filter List
        self.filter_list = FilterListWidget()
        self.filter_list.add_files_requested.connect(self.prompt_add_files)
        self.filter_list.selection_changed.connect(self._on_filter_selection_changed)
        self.filter_list.data_changed.connect(self._on_filter_data_changed)
        splitter.addWidget(self.filter_list)

        # Right Area: Tabs
        self.tabs = QTabWidget()

        # Tab 1: Overview (Plotly Interactive Plot)
        self.plot_widget = PlotWidget(is_dark=self.is_dark)
        self.tabs.addTab(self.plot_widget, "Overview / Interactive Plot")

        # Tab 2: Individual Analysis
        self.analysis_panel = AnalysisPanel()
        self.analysis_panel.analysis_changed.connect(self._on_analysis_changed)
        self.tabs.addTab(self.analysis_panel, "Individual Analysis")

        # Tab 3: Comparison
        self.comparison_panel = ComparisonPanel()
        self.tabs.addTab(self.comparison_panel, "Comparison Mode")

        # Tab 4: Raw Data
        self.raw_data_panel = RawDataPanel()
        self.tabs.addTab(self.raw_data_panel, "Raw Data")

        splitter.addWidget(self.tabs)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 3)

        main_layout.addWidget(splitter)

        # 4. Status Bar
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)

    def _create_menu_bar(self):
        menubar = self.menuBar()

        # File Menu
        file_menu = menubar.addMenu("&File")

        act_add = QAction("&Add Measurement File(s)...", self)
        act_add.setShortcut(QKeySequence("Ctrl+O"))
        act_add.triggered.connect(self.prompt_add_files)
        file_menu.addAction(act_add)

        act_rvitm = QAction("Import &RVITM Directory...", self)
        act_rvitm.triggered.connect(self.prompt_import_rvitm_folder)
        file_menu.addAction(act_rvitm)

        act_open_proj = QAction("Open &Project (.vna)...", self)
        act_open_proj.setShortcut(QKeySequence("Ctrl+P"))
        act_open_proj.triggered.connect(self.prompt_open_project)
        file_menu.addAction(act_open_proj)

        act_save_proj = QAction("&Save Project (.vna)...", self)
        act_save_proj.setShortcut(QKeySequence("Ctrl+S"))
        act_save_proj.triggered.connect(self.prompt_save_project)
        file_menu.addAction(act_save_proj)

        file_menu.addSeparator()

        act_export_graph = QAction("Export &Graph (PNG/SVG/PDF)...", self)
        act_export_graph.triggered.connect(self.prompt_export_graph)
        file_menu.addAction(act_export_graph)

        act_export_report = QAction("Generate &PDF Report...", self)
        act_export_report.setShortcut(QKeySequence("Ctrl+R"))
        act_export_report.triggered.connect(self.prompt_export_report)
        file_menu.addAction(act_export_report)

        act_export_excel = QAction("Export Results to &Excel...", self)
        act_export_excel.triggered.connect(self.prompt_export_excel)
        file_menu.addAction(act_export_excel)

        file_menu.addSeparator()

        act_exit = QAction("E&xit", self)
        act_exit.setShortcut(QKeySequence("Ctrl+Q"))
        act_exit.triggered.connect(self.close)
        file_menu.addAction(act_exit)

        # Edit Menu
        edit_menu = menubar.addMenu("&Edit")
        act_prefs = QAction("&Settings / Preferences...", self)
        act_prefs.triggered.connect(self.prompt_settings)
        edit_menu.addAction(act_prefs)

        # View Menu
        view_menu = menubar.addMenu("&View")
        act_theme = QAction("Toggle &Dark/Light Theme", self)
        act_theme.triggered.connect(self.toggle_theme)
        view_menu.addAction(act_theme)

        # Help Menu
        help_menu = menubar.addMenu("&Help")
        act_samples = QAction("Load Sample &DGS vs Without DGS Filters", self)
        act_samples.triggered.connect(self.load_sample_dgs_pair)
        help_menu.addAction(act_samples)

        help_menu.addSeparator()
        act_about = QAction("&About VNA Filter Analyzer", self)
        act_about.triggered.connect(self.show_about_dialog)
        help_menu.addAction(act_about)

    def _create_tool_bar(self):
        toolbar = QToolBar("Main Toolbar")
        toolbar.setMovable(False)
        self.addToolBar(toolbar)

        btn_add = QToolButton()
        btn_add.setText("📂 Add Measurement Files")
        btn_add.clicked.connect(self.prompt_add_files)
        toolbar.addWidget(btn_add)

        btn_rvitm = QToolButton()
        btn_rvitm.setText("📁 Import RVITM Folder")
        btn_rvitm.setToolTip("Import full RVITM folder (auto-merges DGS and Without DGS S-parameters)")
        btn_rvitm.clicked.connect(self.prompt_import_rvitm_folder)
        toolbar.addWidget(btn_rvitm)

        btn_samples = QToolButton()
        btn_samples.setText("⚡ Load Sample")
        btn_samples.setToolTip("Quick load 5th-order DGS vs Non-DGS sample measurements")
        btn_samples.clicked.connect(self.load_sample_dgs_pair)
        toolbar.addWidget(btn_samples)

        toolbar.addSeparator()

        toolbar.addWidget(QLabel(" Parameter: "))
        self.combo_sparam = QComboBox()
        self.combo_sparam.addItems(["S21", "S11", "S12", "S22"])
        self.combo_sparam.currentTextChanged.connect(self._on_sparam_changed)
        toolbar.addWidget(self.combo_sparam)

        toolbar.addSeparator()

        btn_save = QToolButton()
        btn_save.setText("💾 Save Project")
        btn_save.clicked.connect(self.prompt_save_project)
        toolbar.addWidget(btn_save)

        btn_open = QToolButton()
        btn_open.setText("📂 Open Project")
        btn_open.clicked.connect(self.prompt_open_project)
        toolbar.addWidget(btn_open)

        toolbar.addSeparator()

        btn_report = QToolButton()
        btn_report.setText("📄 PDF Report")
        btn_report.clicked.connect(self.prompt_export_report)
        toolbar.addWidget(btn_report)

        btn_export = QToolButton()
        btn_export.setText("📊 Export Graph")
        btn_export.clicked.connect(self.prompt_export_graph)
        toolbar.addWidget(btn_export)

        toolbar.addSeparator()

        self.btn_theme = QToolButton()
        self.btn_theme.setText("🌓 Theme")
        self.btn_theme.clicked.connect(self.toggle_theme)
        toolbar.addWidget(self.btn_theme)

    def _apply_theme(self):
        self.setStyleSheet(DARK_THEME if self.is_dark else LIGHT_THEME)
        self.plot_widget.set_dark_mode(self.is_dark)

    def toggle_theme(self):
        self.is_dark = not self.is_dark
        self._apply_theme()

    def prompt_add_files(self):
        if len(self.measurements) >= 4:
            QMessageBox.warning(self, "Maximum Limit Reached", "Maximum 4 measurements can be loaded simultaneously.")
            return

        files, _ = QFileDialog.getOpenFileNames(
            self,
            "Select VNA / RVITM / CST Measurement Files (1–4)",
            "",
            "All Measurement Files (*.csv *.txt *.dat *.s2p *.s1p *DGS* *S*);;RVITM Files (*DGS* *S*);;CSV Files (*.csv);;CST / Touchstone Files (*.s2p *.s1p *.txt *.sig);;All Files (*.*)",
        )
        if files:
            self.load_files(files)

    def prompt_import_rvitm_folder(self):
        """Prompt user to select an RVITM data folder and load measurements."""
        folder = QFileDialog.getExistingDirectory(
            self, "Select RVITM Directory", "", QFileDialog.ShowDirsOnly
        )
        if folder:
            self.import_rvitm_folder(folder)

    def import_rvitm_folder(self, folder_path: str):
        """Import all measurements from an RVITM directory (DGS and Without DGS)."""
        from .csv_parser import parse_rvitm_directory
        results = parse_rvitm_directory(folder_path)
        if not results:
            QMessageBox.warning(
                self, "RVITM Import",
                f"No matching RVITM S-parameter files found in:\n{folder_path}"
            )
            return

        loaded_names = [m.name for m in self.measurements]
        for res in results:
            if len(self.measurements) >= 4:
                break
            name = res.measurement_name or "RVITM Measurement"
            if name in loaded_names:
                continue

            clean_f, clean_s, q_report = check_data_quality(res.freq_hz, res.s_params)
            m = MeasurementData(
                file_path=res.file_path,
                name=name,
                raw_freq_hz=clean_f,
                raw_s_params=clean_s,
                metadata=res.metadata,
                index=len(self.measurements),
            )
            m.quality_warnings = q_report.warnings

            s21 = m.clean_s_params.get("S21", next(iter(m.clean_s_params.values())))
            s11 = m.clean_s_params.get("S11")
            m.metrics = calculate_filter_metrics(m.clean_freq_hz, s21, s11_db=s11, threshold_db=3.0)

            self.measurements.append(m)
            loaded_names.append(name)

        self._refresh_all_views()
        self.status_bar.showMessage(f"Successfully imported RVITM data from: {os.path.basename(folder_path)}", 5000)

    def load_files(self, file_paths: List[str], show_preview: bool = True):
        """Load and parse measurement files (with optional import preview)."""
        available_slots = 4 - len(self.measurements)

        # Check for directory drops
        for path in file_paths:
            if os.path.isdir(path):
                self.import_rvitm_folder(path)
                return

        paths_to_load = file_paths[:available_slots]
        loaded_conditions = set(m.name for m in self.measurements)

        for path in paths_to_load:
            if len(self.measurements) >= 4:
                break
            try:
                ext = os.path.splitext(path)[1].lower()
                # If standard CSV with headers and show_preview is True, show preview
                if show_preview and ext in (".csv", ".txt", ".dat") and not re.search(r"S\d\d_", os.path.basename(path)):
                    dialog = ImportPreviewDialog(path, self)
                    if dialog.exec() != QDialog.Accepted:
                        continue
                    mapping = dialog.get_selected_mapping()
                    result = parse_vna_file(
                        path,
                        freq_col=mapping["freq_col"],
                        freq_unit_mult=mapping["freq_unit_mult"],
                        s21_col=mapping["s21_col"],
                        s11_col=mapping["s11_col"],
                        s12_col=mapping["s12_col"],
                        s22_col=mapping["s22_col"],
                    )
                else:
                    result = parse_vna_file(path)

                # Avoid duplicate measurements if multiple sibling S-param files were selected together
                meas_name = result.measurement_name
                if not meas_name:
                    base_name = os.path.splitext(os.path.basename(path))[0]
                    if "dgs" in base_name.lower() and "without" not in base_name.lower():
                        meas_name = "DGS"
                    elif "without" in base_name.lower() or "wodgs" in base_name.lower():
                        meas_name = "Without DGS"
                    else:
                        meas_name = base_name

                if meas_name in loaded_conditions:
                    # Update existing measurement with any newly found S-parameters
                    for existing_m in self.measurements:
                        if existing_m.name == meas_name:
                            for sp, svals in result.s_params.items():
                                if sp not in existing_m.clean_s_params:
                                    existing_m.clean_s_params[sp] = svals
                                    existing_m.raw_s_params[sp] = svals
                    continue

                clean_f, clean_s, q_report = check_data_quality(result.freq_hz, result.s_params)
                if not q_report.is_valid:
                    QMessageBox.warning(
                        self, "Data Quality Issue",
                        f"Could not load '{os.path.basename(path)}':\n" + "\n".join(q_report.warnings)
                    )
                    continue

                idx = len(self.measurements)
                m = MeasurementData(
                    file_path=path,
                    name=meas_name,
                    raw_freq_hz=clean_f,
                    raw_s_params=clean_s,
                    metadata=result.metadata,
                    index=idx,
                )
                m.quality_warnings = q_report.warnings

                s21 = m.clean_s_params.get("S21", next(iter(m.clean_s_params.values())))
                s11 = m.clean_s_params.get("S11")
                m.metrics = calculate_filter_metrics(m.clean_freq_hz, s21, s11_db=s11, threshold_db=3.0)

                self.measurements.append(m)
                loaded_conditions.add(meas_name)

            except Exception as e:
                QMessageBox.critical(
                    self, "Import Error",
                    f"Failed to import '{os.path.basename(path)}':\n{str(e)}"
                )

        self._refresh_all_views()

    def load_sample_dgs_pair(self):
        """Quick load the included sample 5th-order DGS vs Non-DGS measurements."""
        base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "sample_data"))
        dgs_csv = os.path.join(base_dir, "dgs_filter_5th_order.csv")
        wodgs_csv = os.path.join(base_dir, "without_dgs_filter_5th_order.csv")

        if os.path.exists(dgs_csv) and os.path.exists(wodgs_csv):
            self.measurements.clear()
            self.load_files([dgs_csv, wodgs_csv], show_preview=False)
            self.status_bar.showMessage("Loaded 5th-Order Bandpass Filter sample files (DGS vs Without DGS)", 5000)
        else:
            QMessageBox.warning(self, "Sample Data", f"Sample files not found at {base_dir}.")

    def _refresh_all_views(self):
        self.filter_list.set_measurements(self.measurements)

        primary_m = None
        if self.measurements and 0 <= self.active_index < len(self.measurements):
            primary_m = self.measurements[self.active_index]
        elif self.measurements:
            self.active_index = 0
            primary_m = self.measurements[0]

        self.analysis_panel.set_measurement(primary_m)
        self.comparison_panel.set_measurements(self.measurements)
        self.raw_data_panel.set_measurements(self.measurements)
        self.plot_widget.set_data(self.measurements, active_param=self.active_param, primary_idx=self.active_index)
        self._update_status()

    def _on_filter_selection_changed(self, idx: int):
        if 0 <= idx < len(self.measurements):
            self.active_index = idx
            self.analysis_panel.set_measurement(self.measurements[idx])
            self.plot_widget.set_data(self.measurements, active_param=self.active_param, primary_idx=self.active_index)
            self._update_status()

    def _on_filter_data_changed(self):
        self._refresh_all_views()

    def _on_analysis_changed(self):
        self.plot_widget.set_data(self.measurements, active_param=self.active_param, primary_idx=self.active_index)
        self.comparison_panel.set_measurements(self.measurements)

    def _on_sparam_changed(self, text: str):
        self.active_param = text
        self.plot_widget.set_data(self.measurements, active_param=self.active_param, primary_idx=self.active_index)
        if self.measurements and 0 <= self.active_index < len(self.measurements):
            self.measurements[self.active_index].active_s_param = text
            self.analysis_panel.set_measurement(self.measurements[self.active_index])

    def _update_status(self):
        if not self.measurements:
            self.status_bar.showMessage("Ready. Add 1 to 4 VNA CSV measurement files to begin analysis.")
            return

        m = self.measurements[self.active_index] if 0 <= self.active_index < len(self.measurements) else None
        if m and m.metrics:
            pts_str = f"Points: {m.num_points}"
            fc_str = f"Fc: {m.metrics.center_freq_hz/1e9:.3f} GHz"
            bw_str = f"BW: {m.metrics.bandwidth_hz/1e6:.1f} MHz"
            il_str = f"IL: {m.metrics.insertion_loss_db:.2f} dB"
            self.status_bar.showMessage(f"Active Filter: '{m.name}' | {pts_str} | {fc_str} | {bw_str} | {il_str}")
        else:
            self.status_bar.showMessage(f"{len(self.measurements)} measurement(s) loaded.")

    def prompt_save_project(self):
        if not self.measurements:
            QMessageBox.warning(self, "Save Project", "No measurement files loaded to save.")
            return
        path, _ = QFileDialog.getSaveFileName(self, "Save Analysis Project", "filter_analysis.vna", "VNA Project (*.vna)")
        if path:
            save_project(
                path,
                self.measurements,
                active_index=self.active_index,
                normalized=self.plot_widget.normalized,
                notes=self.engineering_notes,
            )
            QMessageBox.information(self, "Project Saved", f"Analysis project successfully saved to:\n{path}")

    def prompt_open_project(self):
        path, _ = QFileDialog.getOpenFileName(self, "Open Analysis Project", "", "VNA Project (*.vna)")
        if path:
            try:
                measurements, active_idx, normalized, notes = load_project(path)
                self.measurements = measurements
                self.active_index = active_idx
                self.engineering_notes = notes
                self.plot_widget.btn_normalize.setChecked(normalized)
                self.plot_widget.normalized = normalized
                self._refresh_all_views()
                QMessageBox.information(self, "Project Loaded", f"Loaded project session with {len(measurements)} filter(s).")
            except Exception as e:
                QMessageBox.critical(self, "Open Project Error", f"Failed to open project file:\n{str(e)}")

    def prompt_export_graph(self):
        if not self.measurements:
            QMessageBox.warning(self, "Export Graph", "No measurements loaded to export.")
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Export Graph Figure", "filter_plot.png",
            "PNG Image (*.png);;SVG Vector (*.svg);;PDF Document (*.pdf)"
        )
        if path:
            export_figure(
                measurements=self.measurements,
                file_path=path,
                active_param=self.active_param,
                normalized=self.plot_widget.normalized,
                show_markers=self.plot_widget.show_markers,
                primary_idx=self.active_index,
                dpi=300,
            )
            QMessageBox.information(self, "Graph Exported", f"Saved high-resolution plot to:\n{path}")

    def prompt_export_report(self):
        if not self.measurements:
            QMessageBox.warning(self, "Export PDF Report", "No measurements loaded to generate a report.")
            return
        path, _ = QFileDialog.getSaveFileName(self, "Generate PDF Engineering Report", "vna_filter_report.pdf", "PDF Report (*.pdf)")
        if path:
            generate_pdf_report(
                measurements=self.measurements,
                file_path=path,
                active_param=self.active_param,
                notes=self.engineering_notes,
            )
            QMessageBox.information(self, "Report Generated", f"PDF engineering report generated at:\n{path}")

    def prompt_export_excel(self):
        if not self.measurements:
            QMessageBox.warning(self, "Export Excel", "No measurements loaded to export.")
            return
        path, _ = QFileDialog.getSaveFileName(self, "Export Analysis to Excel", "filter_metrics.xlsx", "Excel Files (*.xlsx)")
        if path:
            export_results_to_excel(self.measurements, path)
            QMessageBox.information(self, "Excel Exported", f"Excel report generated at:\n{path}")

    def prompt_settings(self):
        dialog = SettingsDialog(self, is_dark=self.is_dark)
        if dialog.exec() == QDialog.Accepted:
            cfg = dialog.get_settings()
            if cfg["dark_theme"] != self.is_dark:
                self.is_dark = cfg["dark_theme"]
                self._apply_theme()
            # Update smoothing defaults
            for m in self.measurements:
                m.smoothing_method = cfg["smoothing_algo"]
                m.smoothing_window = cfg["smoothing_window"]
            self._refresh_all_views()

    def show_about_dialog(self):
        QMessageBox.about(
            self,
            "About VNA Filter Analyzer",
            "<b>Rohde & Schwarz VNA Filter Analyzer</b><br/>"
            "Version 1.0.0<br/><br/>"
            "A high-precision desktop engineering application for Vector Network Analyzer "
            "filter characterization and multi-measurement comparison.<br/><br/>"
            "<b>Key Features:</b><br/>"
            "• 1 to 4 CSV/Touchstone measurement files simultaneously<br/>"
            "• High-precision interpolated -3 dB bandwidth & cutoff frequencies<br/>"
            "• Insertion loss, return loss, VSWR, loaded Q, passband ripple<br/>"
            "• DGS vs. Non-DGS comparative analysis<br/>"
            "• Interactive Plotly graphics & PDF report generation<br/><br/>"
            "<i>Designed for Ubuntu Linux RF/Microwave Engineering.</i>"
        )

    # Drag and Drop Support
    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent):
        urls = event.mimeData().urls()
        file_paths = [u.toLocalFile() for u in urls if os.path.exists(u.toLocalFile())]
        if file_paths:
            self.load_files(file_paths)
