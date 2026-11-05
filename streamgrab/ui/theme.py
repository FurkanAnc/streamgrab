"""Karanlik tema: anlamsal renk token'lari + QSS.

Kod ve QSS ham renk yerine buradaki token'lari kullanir. Metin renkleri
SURFACE uzerinde en az 4.5:1 kontrast verecek sekilde secildi.
"""

from ..paths import assets_dir

BG = "#0f1115"
SIDEBAR = "#0b0d11"
SURFACE = "#171a21"
RAISED = "#1f232c"
HOVER = "#272c37"
BORDER = "#2a2f3a"
BORDER_STRONG = "#566074"

TEXT = "#eef0f4"
TEXT_MUTED = "#a2abba"
TEXT_FAINT = "#8590a2"

ACCENT = "#5b8cff"
ACCENT_HOVER = "#7aa2ff"
ACCENT_SOFT = "#1d2a47"
ON_ACCENT = "#07101f"

SUCCESS = "#4ade80"
SUCCESS_SOFT = "#12301f"
WARNING = "#fbbf24"
WARNING_SOFT = "#33280f"
DANGER = "#fb7185"
DANGER_SOFT = "#3a1a22"

_ASSETS = assets_dir().as_posix()

STYLE = f"""
* {{ font-size: 10pt; outline: 0; }}

QWidget#Root, QMainWindow, QDialog {{ background: {BG}; color: {TEXT}; }}
QStackedWidget {{ background: {BG}; }}

QLabel {{ color: {TEXT}; background: transparent; }}
QLabel#Brand {{ font-size: 13pt; font-weight: 700; }}
QLabel#Title {{ font-size: 20pt; font-weight: 700; }}
QLabel#Section {{ font-size: 10pt; font-weight: 600; color: {TEXT}; }}
QLabel#H1 {{ font-size: 11pt; font-weight: 600; }}
QLabel#Muted {{ color: {TEXT_MUTED}; font-size: 9pt; }}
QLabel#Subtitle {{ color: {TEXT_MUTED}; font-size: 10pt; }}
QLabel#EmptyTitle {{ font-size: 13pt; font-weight: 600; }}
QLabel#EmptyText {{ color: {TEXT_MUTED}; }}
QLabel#Chip {{ color: {TEXT_FAINT}; font-size: 9pt; padding: 0 12px; }}
QLabel#Badge {{
    background: {ACCENT}; color: {ON_ACCENT}; border-radius: 9px;
    font-size: 8pt; font-weight: 700; padding: 1px 7px;
}}
QLabel#Error {{
    background: {DANGER_SOFT}; border: 1px solid #6b2c3a; border-radius: 10px;
    padding: 10px 14px; color: #fecdd3;
}}
QLabel#Thumb {{ background: {RAISED}; border-radius: 10px; color: {TEXT_FAINT}; }}

QLabel#Pill {{
    border-radius: 10px; padding: 3px 10px; font-size: 9pt; font-weight: 600;
    background: {RAISED}; color: {TEXT_MUTED};
}}
QLabel#Pill[tone="active"] {{ background: {ACCENT_SOFT}; color: #bcd0ff; }}
QLabel#Pill[tone="warn"] {{ background: {WARNING_SOFT}; color: {WARNING}; }}
QLabel#Pill[tone="ok"] {{ background: {SUCCESS_SOFT}; color: {SUCCESS}; }}
QLabel#Pill[tone="bad"] {{ background: {DANGER_SOFT}; color: {DANGER}; }}

QFrame#Sidebar {{ background: {SIDEBAR}; border-right: 1px solid {BORDER}; }}
QFrame#Card, QFrame#Hero {{
    background: {SURFACE}; border: 1px solid {BORDER}; border-radius: 14px;
}}
QFrame#Job {{ background: {SURFACE}; border: 1px solid {BORDER}; border-radius: 12px; }}
QFrame#Job:hover {{ border-color: {BORDER_STRONG}; }}

QLineEdit, QComboBox, QSpinBox {{
    background: {RAISED}; border: 1px solid {BORDER}; border-radius: 9px;
    padding: 9px 12px; color: {TEXT}; selection-background-color: {ACCENT};
    selection-color: {ON_ACCENT};
}}
QFrame#Hero QLineEdit {{
    background: transparent; border: none; font-size: 11pt; padding: 8px 6px;
}}
QLineEdit:hover, QComboBox:hover, QSpinBox:hover {{ border-color: {BORDER_STRONG}; }}
QLineEdit:focus, QComboBox:focus, QSpinBox:focus {{ border-color: {ACCENT}; }}
QLineEdit:disabled {{ color: {TEXT_FAINT}; }}
QSpinBox QLineEdit {{ background: transparent; border: none; padding: 0 0 0 10px; }}

QComboBox::drop-down {{ border: none; width: 28px; }}
QComboBox::down-arrow {{ image: url({_ASSETS}/chevron-down.svg); width: 14px; height: 14px; }}
QComboBox QAbstractItemView {{
    background: {RAISED}; border: 1px solid {BORDER}; color: {TEXT};
    selection-background-color: {ACCENT_SOFT}; selection-color: {TEXT}; padding: 4px;
}}
QSpinBox::up-button, QSpinBox::down-button {{
    width: 24px; background: transparent; border: none;
}}
QSpinBox::up-arrow {{ image: url({_ASSETS}/chevron-up.svg); width: 12px; height: 12px; }}
QSpinBox::down-arrow {{ image: url({_ASSETS}/chevron-down.svg); width: 12px; height: 12px; }}

QPushButton {{
    background: {RAISED}; color: {TEXT}; border: 1px solid {BORDER};
    border-radius: 9px; padding: 9px 16px;
}}
QPushButton:hover {{ background: {HOVER}; border-color: {BORDER_STRONG}; }}
QPushButton:pressed {{ background: {SURFACE}; }}
QPushButton:focus {{ border-color: {ACCENT}; }}
QPushButton:disabled {{ color: {TEXT_FAINT}; background: {SURFACE}; border-color: {BORDER}; }}

QPushButton#Primary {{
    background: {ACCENT}; border-color: {ACCENT}; color: {ON_ACCENT}; font-weight: 700;
}}
QPushButton#Primary:hover {{ background: {ACCENT_HOVER}; border-color: {ACCENT_HOVER}; }}
QPushButton#Primary:disabled {{
    background: {ACCENT_SOFT}; border-color: {ACCENT_SOFT}; color: {TEXT_FAINT};
}}

QPushButton#Ghost {{
    background: transparent; border: 1px solid transparent; color: {TEXT_MUTED};
    padding: 7px 10px;
}}
QPushButton#Ghost:hover {{ color: {TEXT}; background: {RAISED}; }}

QPushButton#Icon {{
    background: transparent; border: none; border-radius: 8px; padding: 6px;
}}
QPushButton#Icon:hover {{ background: {HOVER}; }}

QPushButton#Nav {{
    background: transparent; border: none; border-radius: 9px; color: {TEXT_MUTED};
    padding: 10px 12px; text-align: left; font-weight: 600;
}}
QPushButton#Nav:hover {{ background: {RAISED}; color: {TEXT}; }}
QPushButton#Nav:checked {{ background: {ACCENT_SOFT}; color: {TEXT}; }}

QPushButton#Filter {{
    background: transparent; border: 1px solid {BORDER}; border-radius: 15px;
    color: {TEXT_MUTED}; padding: 5px 14px;
}}
QPushButton#Filter:hover {{ color: {TEXT}; border-color: {BORDER_STRONG}; }}
QPushButton#Filter:checked {{
    background: {ACCENT_SOFT}; border-color: {ACCENT}; color: {TEXT}; font-weight: 600;
}}

QTableWidget {{
    background: {SURFACE}; alternate-background-color: #1a1e26; color: {TEXT};
    border: 1px solid {BORDER}; border-radius: 12px; gridline-color: transparent;
    selection-background-color: {ACCENT_SOFT}; selection-color: {TEXT};
}}
QTableWidget::item {{ padding: 6px 8px; border: none; }}
QHeaderView {{ background: transparent; }}
QHeaderView::section {{
    background: {SURFACE}; color: {TEXT_FAINT}; border: none;
    border-bottom: 1px solid {BORDER}; padding: 9px 8px; font-size: 9pt; font-weight: 600;
}}
QTableCornerButton::section {{ background: {SURFACE}; border: none; }}

QCheckBox {{ color: {TEXT}; spacing: 8px; }}
QCheckBox::indicator, QTableWidget::indicator {{
    width: 15px; height: 15px; border: 1px solid {BORDER_STRONG}; border-radius: 4px;
    background: {RAISED};
}}
QCheckBox::indicator:hover, QTableWidget::indicator:hover {{ border-color: {ACCENT}; }}
QCheckBox::indicator:checked, QTableWidget::indicator:checked {{
    background: {ACCENT}; border-color: {ACCENT}; image: url({_ASSETS}/check.svg);
}}

QProgressBar {{
    background: {RAISED}; border: none; border-radius: 3px;
    min-height: 6px; max-height: 6px; color: transparent;
}}
QProgressBar::chunk {{ background: {ACCENT}; border-radius: 3px; }}
QProgressBar[tone="ok"]::chunk {{ background: {SUCCESS}; }}
QProgressBar[tone="warn"]::chunk {{ background: {WARNING}; }}
QProgressBar[tone="bad"]::chunk {{ background: {DANGER}; }}
QProgressBar#Busy {{ min-height: 3px; max-height: 3px; }}

QScrollArea {{ background: transparent; border: none; }}
QScrollBar:vertical {{ background: transparent; width: 10px; margin: 2px; }}
QScrollBar::handle:vertical {{ background: {HOVER}; border-radius: 3px; min-height: 30px; }}
QScrollBar::handle:vertical:hover {{ background: {BORDER_STRONG}; }}
QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; width: 0; }}
QScrollBar:horizontal {{ background: transparent; height: 10px; margin: 2px; }}
QScrollBar::handle:horizontal {{ background: {HOVER}; border-radius: 3px; }}
QScrollBar::add-page, QScrollBar::sub-page {{ background: transparent; }}

QStatusBar {{ background: {SIDEBAR}; color: {TEXT_FAINT}; border-top: 1px solid {BORDER}; }}
QStatusBar::item {{ border: none; }}
QSplitter::handle {{ background: transparent; height: 10px; }}
QToolTip {{
    background: {RAISED}; color: {TEXT}; border: 1px solid {BORDER_STRONG};
    border-radius: 6px; padding: 6px;
}}
QMessageBox {{ background: {SURFACE}; }}
"""
