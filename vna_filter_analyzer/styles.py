"""Modern engineering UI stylesheets for VNA Filter Analyzer."""

DARK_THEME = """
QWidget {
    background-color: #1a1d24;
    color: #e2e8f0;
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
    font-size: 12px;
}

QMainWindow {
    background-color: #14171d;
}

QMenuBar {
    background-color: #181b22;
    color: #cbd5e1;
    border-bottom: 1px solid #2d3748;
    padding: 2px;
}

QMenuBar::item {
    background: transparent;
    padding: 4px 10px;
    border-radius: 4px;
}

QMenuBar::item:selected {
    background-color: #2b3548;
    color: #ffffff;
}

QMenu {
    background-color: #1e2430;
    color: #e2e8f0;
    border: 1px solid #3b465c;
    border-radius: 6px;
    padding: 4px;
}

QMenu::item {
    padding: 6px 24px;
    border-radius: 4px;
}

QMenu::item:selected {
    background-color: #0284c7;
    color: #ffffff;
}

QToolBar {
    background-color: #181b22;
    border-bottom: 1px solid #2d3748;
    spacing: 6px;
    padding: 4px 8px;
}

QToolButton {
    background-color: #242c3d;
    color: #e2e8f0;
    border: 1px solid #3b465c;
    border-radius: 4px;
    padding: 5px 12px;
    font-weight: 500;
}

QToolButton:hover {
    background-color: #2e3a52;
    border-color: #0284c7;
}

QToolButton:pressed {
    background-color: #0284c7;
    color: #ffffff;
}

QToolButton:checked {
    background-color: #0369a1;
    border-color: #38bdf8;
    color: #ffffff;
}

QTabWidget::pane {
    border: 1px solid #2d3748;
    background-color: #1a1d24;
    border-radius: 6px;
    top: -1px;
}

QTabBar::tab {
    background-color: #202634;
    color: #94a3b8;
    padding: 8px 18px;
    border-top-left-radius: 6px;
    border-top-right-radius: 6px;
    margin-right: 3px;
    font-weight: 600;
}

QTabBar::tab:hover {
    background-color: #273042;
    color: #f1f5f9;
}

QTabBar::tab:selected {
    background-color: #1a1d24;
    color: #38bdf8;
    border-top: 2px solid #38bdf8;
}

QPushButton {
    background-color: #0284c7;
    color: #ffffff;
    border: none;
    border-radius: 4px;
    padding: 6px 14px;
    font-weight: 600;
}

QPushButton:hover {
    background-color: #0369a1;
}

QPushButton:pressed {
    background-color: #075985;
}

QPushButton:disabled {
    background-color: #2d3748;
    color: #64748b;
}

QPushButton#SecondaryBtn {
    background-color: #242c3d;
    color: #e2e8f0;
    border: 1px solid #3b465c;
}

QPushButton#SecondaryBtn:hover {
    background-color: #2f3a50;
    border-color: #60a5fa;
}

QPushButton#DangerBtn {
    background-color: #dc2626;
    color: #ffffff;
}

QPushButton#DangerBtn:hover {
    background-color: #b91c1c;
}

QGroupBox {
    border: 1px solid #2d3748;
    border-radius: 6px;
    margin-top: 18px;
    padding-top: 14px;
    font-weight: 600;
}

QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    padding: 0 6px;
    color: #38bdf8;
}

QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox {
    background-color: #12151c;
    color: #f1f5f9;
    border: 1px solid #334155;
    border-radius: 4px;
    padding: 5px 8px;
}

QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus {
    border: 1px solid #38bdf8;
}

QComboBox::drop-down {
    border: none;
    width: 20px;
}

QTableWidget, QTableView {
    background-color: #161922;
    color: #f1f5f9;
    gridline-color: #273042;
    border: 1px solid #2d3748;
    border-radius: 4px;
    selection-background-color: #0369a1;
    selection-color: #ffffff;
}

QHeaderView::section {
    background-color: #1e2433;
    color: #94a3b8;
    font-weight: 600;
    padding: 6px;
    border: none;
    border-right: 1px solid #273042;
    border-bottom: 1px solid #273042;
}

QScrollBar:vertical {
    background: #14171d;
    width: 10px;
    margin: 0;
}

QScrollBar::handle:vertical {
    background: #334155;
    min-height: 20px;
    border-radius: 5px;
}

QScrollBar::handle:vertical:hover {
    background: #475569;
}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0;
}

QStatusBar {
    background-color: #14171d;
    color: #94a3b8;
    border-top: 1px solid #242c3d;
}

QCheckBox {
    spacing: 6px;
}

QCheckBox::indicator {
    width: 16px;
    height: 16px;
    border-radius: 3px;
    border: 1px solid #475569;
    background-color: #12151c;
}

QCheckBox::indicator:checked {
    background-color: #0284c7;
    border-color: #38bdf8;
}
"""

LIGHT_THEME = """
QWidget {
    background-color: #f8fafc;
    color: #1e293b;
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
    font-size: 12px;
}

QMainWindow {
    background-color: #f1f5f9;
}

QMenuBar {
    background-color: #ffffff;
    color: #334155;
    border-bottom: 1px solid #e2e8f0;
    padding: 2px;
}

QMenuBar::item:selected {
    background-color: #e2e8f0;
    color: #0f172a;
}

QMenu {
    background-color: #ffffff;
    color: #1e293b;
    border: 1px solid #cbd5e1;
    border-radius: 6px;
    padding: 4px;
}

QMenu::item:selected {
    background-color: #0284c7;
    color: #ffffff;
}

QToolBar {
    background-color: #ffffff;
    border-bottom: 1px solid #e2e8f0;
    spacing: 6px;
    padding: 4px 8px;
}

QToolButton {
    background-color: #f8fafc;
    color: #334155;
    border: 1px solid #cbd5e1;
    border-radius: 4px;
    padding: 5px 12px;
    font-weight: 500;
}

QToolButton:hover {
    background-color: #e2e8f0;
    border-color: #0284c7;
}

QToolButton:checked {
    background-color: #e0f2fe;
    border-color: #0284c7;
    color: #0369a1;
}

QTabWidget::pane {
    border: 1px solid #cbd5e1;
    background-color: #ffffff;
    border-radius: 6px;
}

QTabBar::tab {
    background-color: #e2e8f0;
    color: #64748b;
    padding: 8px 18px;
    border-top-left-radius: 6px;
    border-top-right-radius: 6px;
    margin-right: 3px;
    font-weight: 600;
}

QTabBar::tab:selected {
    background-color: #ffffff;
    color: #0284c7;
    border-top: 2px solid #0284c7;
}

QPushButton {
    background-color: #0284c7;
    color: #ffffff;
    border: none;
    border-radius: 4px;
    padding: 6px 14px;
    font-weight: 600;
}

QPushButton:hover {
    background-color: #0369a1;
}

QGroupBox {
    border: 1px solid #cbd5e1;
    border-radius: 6px;
    margin-top: 18px;
    padding-top: 14px;
    font-weight: 600;
}

QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    padding: 0 6px;
    color: #0369a1;
}

QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox {
    background-color: #ffffff;
    color: #1e293b;
    border: 1px solid #cbd5e1;
    border-radius: 4px;
    padding: 5px 8px;
}

QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus {
    border: 1px solid #0284c7;
}

QTableWidget, QTableView {
    background-color: #ffffff;
    color: #1e293b;
    gridline-color: #e2e8f0;
    border: 1px solid #cbd5e1;
    border-radius: 4px;
    selection-background-color: #e0f2fe;
    selection-color: #0369a1;
}

QHeaderView::section {
    background-color: #f1f5f9;
    color: #475569;
    font-weight: 600;
    padding: 6px;
    border: none;
    border-right: 1px solid #e2e8f0;
    border-bottom: 1px solid #e2e8f0;
}
"""
