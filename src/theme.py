"""
Centralized palette and application stylesheet.
A future theme swap (e.g. dark) replaces PALETTE and reapplies the stylesheet.
"""

# (light theme).
PALETTE = {
    "bg_main": "#f0f2f5",
    "bg_card": "#ffffff",
    "border": "#e5e7eb",
    "text_primary": "#1f2937",
    "text_secondary": "#374151",
    "text_title": "#111827",
    "text_muted": "#6b7280",
    "menu_item_selected": "#e5e7eb",
    "menu_item_selected_sub": "#f3f4f6",
    "combo_hover": "#9ca3af",
    "scrollbar_handle": "#9ca3af",
    "scrollbar_handle_hover": "#6b7280",
    "run_btn_bg": "#15803d",
    "run_btn_hover": "#166534",
    "run_btn_pressed": "#14532d",
    "kill_btn_bg": "#b91c1c",
    "kill_btn_hover": "#991b1b",
    "kill_btn_pressed": "#7f1d1d",
    "btn_text": "#ffffff",
    "fav_btn": "#d97706",
    "fav_btn_hover": "#b45309",
    "status_placeholder": "#6b7280",
    "status_running": "#15803d",
    "status_stopped": "#64748b",
}


def get_stylesheet() -> str:
    """Build the full application QSS from PALETTE. No hardcoded colors."""
    p = PALETTE
    return f"""
QApplication, QMainWindow, QWidget, QScrollArea {{
    font-family: "Segoe UI", sans-serif;
    font-size: 9pt;
    background-color: {p["bg_main"]};
    color: {p["text_primary"]};
}}
QMenuBar {{
    background-color: {p["bg_main"]};
    padding: 4px 0;
    border-bottom: 1px solid {p["border"]};
}}
QMenuBar::item {{
    padding: 8px 14px;
    background-color: transparent;
    border-radius: 4px;
}}
QMenuBar::item:selected {{
    background-color: {p["menu_item_selected"]};
}}
QMenu {{
    background-color: {p["bg_card"]};
    padding: 3px 0;
    border: 1px solid {p["border"]};
    border-radius: 6px;
}}
QMenu::item {{
    padding: 5px 12px;
}}
QMenu::item:selected {{
    background-color: {p["menu_item_selected_sub"]};
}}
QLabel {{
    color: {p["text_secondary"]};
}}
QPushButton {{
    min-width: 56px;
    padding: 8px 14px;
    border-radius: 6px;
    font-weight: 500;
}}
QPushButton#runBtn, QFrame#scriptCard QPushButton#runBtn {{
    background-color: {p["run_btn_bg"]};
    color: {p["btn_text"]};
    border: none;
}}
QPushButton#runBtn:hover, QFrame#scriptCard QPushButton#runBtn:hover {{
    background-color: {p["run_btn_hover"]};
    color: {p["btn_text"]};
}}
QPushButton#runBtn:pressed, QFrame#scriptCard QPushButton#runBtn:pressed {{
    background-color: {p["run_btn_pressed"]};
    color: {p["btn_text"]};
}}
QPushButton#killBtn, QFrame#scriptCard QPushButton#killBtn {{
    background-color: {p["kill_btn_bg"]};
    color: {p["btn_text"]};
    border: none;
}}
QPushButton#killBtn:hover, QFrame#scriptCard QPushButton#killBtn:hover {{
    background-color: {p["kill_btn_hover"]};
    color: {p["btn_text"]};
}}
QPushButton#killBtn:pressed, QFrame#scriptCard QPushButton#killBtn:pressed {{
    background-color: {p["kill_btn_pressed"]};
    color: {p["btn_text"]};
}}
QPushButton#favBtn, QFrame#scriptCard QPushButton#favBtn {{
    font-size: 14pt;
    border: none;
    background: transparent;
    color: {p["fav_btn"]};
}}
QPushButton#favBtn:hover, QFrame#scriptCard QPushButton#favBtn:hover {{
    color: {p["fav_btn_hover"]};
}}
QComboBox {{
    min-width: 100px;
    padding: 6px 10px;
    border: 1px solid {p["border"]};
    border-radius: 6px;
    background-color: {p["bg_card"]};
}}
QComboBox:hover {{
    border-color: {p["combo_hover"]};
}}
QComboBox::drop-down {{
    border: none;
    width: 20px;
}}
QLineEdit#searchEdit {{
    padding: 10px 14px;
    border: 1px solid {p["border"]};
    border-radius: 8px;
    background-color: {p["bg_card"]};
    min-height: 20px;
}}
QComboBox#folderCombo {{
    padding: 8px 12px;
    border: 1px solid {p["border"]};
    border-radius: 8px;
    background-color: {p["bg_card"]};
}}
QFrame#separator {{
    background-color: {p["border"]};
    max-height: 1px;
}}
QScrollArea {{
    border: none;
}}
QWidget#scrollViewport, QWidget#scriptsContainer {{
    background-color: {p["bg_main"]};
}}
QScrollBar:vertical {{
    background: {p["bg_main"]};
    width: 10px;
    border-radius: 5px;
    margin: 0;
}}
QScrollBar::handle:vertical {{
    background: {p["scrollbar_handle"]};
    border-radius: 5px;
    min-height: 30px;
}}
QScrollBar::handle:vertical:hover {{
    background: {p["scrollbar_handle_hover"]};
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0;
    background: {p["bg_main"]};
}}
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
    background: {p["bg_main"]};
}}
QScrollBar:horizontal {{
    background: {p["bg_main"]};
    height: 10px;
    border-radius: 5px;
    margin: 0;
}}
QScrollBar::handle:horizontal {{
    background: {p["scrollbar_handle"]};
    border-radius: 5px;
    min-width: 30px;
}}
QScrollBar::handle:horizontal:hover {{
    background: {p["scrollbar_handle_hover"]};
}}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
    width: 0;
}}
QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {{
    background: {p["bg_main"]};
}}
QFrame#scriptCard {{
    background-color: {p["bg_card"]};
    border: 1px solid {p["border"]};
    border-radius: 10px;
}}
QFrame#scriptCard QLabel, QFrame#scriptCard QComboBox {{
    background-color: transparent;
}}
QFrame#scriptCard QLabel {{
    color: {p["text_muted"]};
}}
QFrame#scriptCard QLabel#cardTitleLabel {{
    font-weight: 600;
    font-size: 11pt;
    color: {p["text_title"]};
}}
QFrame#scriptCard QLabel#metricValueLabel {{
    color: {p["text_secondary"]};
}}
"""

APP_STYLESHEET = get_stylesheet()
