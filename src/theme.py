"""
Centralized palette and application stylesheet.
"""

DARK_PALETTE = {
    "bg_main": "#0d0f11",
    "bg_sidebar": "#0d0f11",
    "bg_detail": "#0d0f11",
    "bg_card": "#141618",
    "border": "#2a2d31",
    "text_primary": "#e5e7eb",
    "text_secondary": "#9ca3af",
    "text_title": "#f9fafb",
    "text_muted": "#9ca3af",
    "accent": "#2563eb",
    "sidebar_selected_bg": "#1e2a3a",
    "sidebar_selected_border": "#2563eb",
    "dot_running": "#22c55e",
    "dot_stopped": "#4b5563",
    "menu_bg": "#1a1d21",
    "menu_item_hover": "#23272e",
    "top_bar_bg": "#0d0f11",
    "run_btn_bg": "#15803d",
    "run_btn_hover": "#166534",
    "run_btn_pressed": "#14532d",
    "kill_btn_bg": "#b91c1c",
    "kill_btn_hover": "#991b1b",
    "kill_btn_pressed": "#7f1d1d",
    "btn_text": "#ffffff",
    "fav_btn": "#d97706",
    "fav_btn_hover": "#f59e0b",
    "status_running": "#22c55e",
    "status_stopped": "#6b7280",
    "status_placeholder": "#4b5563",
    "scrollbar_handle": "#2a2d31",
    "scrollbar_handle_hover": "#3f4349",
    "graphs_box_bg": "#0a0c0e",
    "input_bg": "#1a1d21",
    "sh_bg": "#0a0c0e",
    "sh_text": "#e5e7eb",
    "sh_comment": "#6b7280",
    "sh_keyword": "#60a5fa",
    "sh_string": "#86efac",
    "sh_variable": "#fbbf24",
    "sh_shebang": "#a78bfa",
    "sh_number": "#f9a8d4",
}

LIGHT_PALETTE = {
    "bg_main": "#f0f2f5",
    "bg_sidebar": "#f0f2f5",
    "bg_detail": "#f0f2f5",
    "bg_card": "#ffffff",
    "border": "#e5e7eb",
    "text_primary": "#1f2937",
    "text_secondary": "#374151",
    "text_title": "#111827",
    "text_muted": "#6b7280",
    "accent": "#2563eb",
    "sidebar_selected_bg": "#e5e7eb",
    "sidebar_selected_border": "#2563eb",
    "dot_running": "#15803d",
    "dot_stopped": "#9ca3af",
    "menu_bg": "#ffffff",
    "menu_item_hover": "#e5e7eb",
    "top_bar_bg": "#f0f2f5",
    "run_btn_bg": "#15803d",
    "run_btn_hover": "#166534",
    "run_btn_pressed": "#14532d",
    "kill_btn_bg": "#b91c1c",
    "kill_btn_hover": "#991b1b",
    "kill_btn_pressed": "#7f1d1d",
    "btn_text": "#ffffff",
    "fav_btn": "#d97706",
    "fav_btn_hover": "#b45309",
    "status_running": "#15803d",
    "status_stopped": "#64748b",
    "status_placeholder": "#6b7280",
    "scrollbar_handle": "#9ca3af",
    "scrollbar_handle_hover": "#6b7280",
    "graphs_box_bg": "#ffffff",
    "input_bg": "#ffffff",
    "sh_bg": "#f8f9fa",
    "sh_text": "#1f2937",
    "sh_comment": "#9ca3af",
    "sh_keyword": "#1d4ed8",
    "sh_string": "#15803d",
    "sh_variable": "#b45309",
    "sh_shebang": "#7c3aed",
    "sh_number": "#db2777",
}


def get_stylesheet(theme: str = "dark") -> str:
    p = DARK_PALETTE if theme == "dark" else LIGHT_PALETTE
    return f"""
QApplication, QMainWindow, QWidget {{
    font-family: "Segoe UI", sans-serif;
    font-size: 9pt;
    color: {p["text_primary"]};
}}
QMainWindow {{
    background-color: {p["bg_main"]};
}}
QWidget {{
    background-color: transparent;
}}
QLabel {{
    color: {p["text_secondary"]};
}}
QWidget#topBar {{
    background-color: {p["top_bar_bg"]};
    border-bottom: 1px solid {p["border"]};
}}
QWidget#pathsRow {{
    background-color: {p["bg_main"]};
    border-bottom: 1px solid {p["border"]};
}}
QFrame#sidebarPanel {{
    background-color: {p["bg_sidebar"]};
    border-right: 1px solid {p["border"]};
}}
QWidget#favoritesSection, QWidget#treeSection {{
    background-color: transparent;
}}
QLabel#sectionHeader {{
    color: {p["text_muted"]};
    font-size: 8pt;
    font-weight: 700;
    letter-spacing: 0.8px;
}}
QLabel#folderLabel {{
    color: {p["text_muted"]};
    font-weight: 600;
}}
QWidget#sidebarRow {{
    border-radius: 4px;
    border-left: 2px solid transparent;
}}
QWidget#sidebarRow:hover {{
    background-color: {p["menu_item_hover"]};
}}
QWidget#sidebarRow[selected="true"] {{
    background-color: {p["sidebar_selected_bg"]};
    border-left: 2px solid {p["sidebar_selected_border"]};
}}
QLabel#dotLabel[running="true"] {{
    color: {p["dot_running"]};
    font-weight: 700;
}}
QLabel#dotLabel[running="false"] {{
    color: {p["dot_stopped"]};
    font-weight: 700;
}}
QWidget#detailPanel {{
    background-color: {p["bg_detail"]};
}}
QLabel#detailTitle {{
    color: {p["text_title"]};
    font-size: 12pt;
    font-weight: 700;
}}
QLabel#detailSectionHeader {{
    color: {p["text_title"]};
    font-weight: 700;
}}
QFrame#graphsBox {{
    background-color: {p["graphs_box_bg"]};
    border: 1px solid {p["border"]};
    border-radius: 6px;
}}
QPushButton {{
    min-width: 56px;
    padding: 8px 14px;
    border-radius: 6px;
    font-weight: 500;
    border: none;
}}
QPushButton#topBarBtn {{
    background-color: transparent;
    color: {p["text_primary"]};
    border-radius: 3px;
    min-width: 0;
    padding: 2px 8px;
    font-size: 12px;
}}
QPushButton#topBarBtn:hover {{
    background-color: {p["menu_item_hover"]};
}}
QPushButton#folderToggleBtn {{
    background-color: transparent;
    color: {p["text_secondary"]};
    min-width: 0;
    max-width: 22px;
    padding: 0;
    border-radius: 3px;
    font-size: 8pt;
}}
QPushButton#folderToggleBtn:hover {{
    background-color: {p["menu_item_hover"]};
}}
QPushButton#runBtn {{
    background-color: {p["run_btn_bg"]};
    color: {p["btn_text"]};
}}
QPushButton#runBtn:hover {{
    background-color: {p["run_btn_hover"]};
}}
QPushButton#runBtn:pressed {{
    background-color: {p["run_btn_pressed"]};
}}
QPushButton#killBtn {{
    background-color: {p["kill_btn_bg"]};
    color: {p["btn_text"]};
}}
QPushButton#killBtn:hover {{
    background-color: {p["kill_btn_hover"]};
}}
QPushButton#killBtn:pressed {{
    background-color: {p["kill_btn_pressed"]};
}}
QPushButton#favBtn {{
    font-size: 14pt;
    min-width: 32px;
    background-color: transparent;
    color: {p["fav_btn"]};
    padding: 4px 8px;
}}
QPushButton#favBtn:hover {{
    color: {p["fav_btn_hover"]};
}}
QLineEdit#searchEdit, QComboBox#categoryCombo, QComboBox#detailCategoryCombo {{
    background-color: {p["input_bg"]};
    color: {p["text_primary"]};
    border: 1px solid {p["border"]};
    border-radius: 6px;
    padding: 6px 10px;
}}
QComboBox::drop-down {{
    border: none;
    width: 18px;
}}
QComboBox QAbstractItemView {{
    background-color: {p["menu_bg"]};
    border: 1px solid {p["border"]};
    color: {p["text_primary"]};
    selection-background-color: {p["menu_item_hover"]};
}}
QMenu {{
    background-color: {p["menu_bg"]};
    border: 1px solid {p["border"]};
    border-radius: 6px;
    padding: 4px 0;
}}
QMenu::item {{
    color: {p["text_primary"]};
    padding: 6px 12px;
}}
QMenu::item:selected {{
    background-color: {p["menu_item_hover"]};
}}
QScrollArea {{
    border: none;
    background-color: transparent;
}}
QSplitter::handle {{
    background-color: {p["border"]};
    width: 1px;
}}
QFrame#divider {{
    max-height: 1px;
    background-color: {p["border"]};
}}
QFrame#scriptViewer {{
    background-color: {p["sh_bg"]};
    border: 1px solid {p["border"]};
    border-radius: 6px;
}}
QFrame#scriptViewer QPlainTextEdit {{
    background-color: {p["sh_bg"]};
    color: {p["sh_text"]};
    border: none;
    padding: 4px 8px;
    selection-background-color: {p["accent"]};
}}
QScrollBar:vertical {{
    background: transparent;
    width: 10px;
    margin: 2px 0;
}}
QScrollBar::handle:vertical {{
    background: {p["scrollbar_handle"]};
    border-radius: 5px;
    min-height: 24px;
}}
QScrollBar::handle:vertical:hover {{
    background: {p["scrollbar_handle_hover"]};
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0;
}}
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
    background: transparent;
}}
QScrollBar:horizontal {{
    background: transparent;
    height: 10px;
    margin: 0 2px;
}}
QScrollBar::handle:horizontal {{
    background: {p["scrollbar_handle"]};
    border-radius: 5px;
    min-width: 24px;
}}
QScrollBar::handle:horizontal:hover {{
    background: {p["scrollbar_handle_hover"]};
}}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
    width: 0;
}}
QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {{
    background: transparent;
}}
"""
