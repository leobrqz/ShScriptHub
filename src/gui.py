import os
import time
from typing import Callable, Optional

from PySide6.QtCore import QRect, QRegularExpression, QSize, Qt, QTimer
from PySide6.QtGui import QAction, QColor, QFont, QPainter, QSyntaxHighlighter, QTextCharFormat, QTextCursor, QWheelEvent
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QSplitter,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

import utils
from config import (
    load_favorites,
    load_project_path,
    load_script_categories,
    load_terminal_path,
    load_theme,
    load_venv_activate_path,
    save_project_path,
    save_script_category,
    save_terminal_path,
    save_theme,
    save_venv_activate_path,
    toggle_favorite,
)
from metrics import PLACEHOLDER, collect_metrics, format_cpu_time, format_elapsed
from script_manager import ScriptManager
from theme import DARK_PALETTE, LIGHT_PALETTE, get_stylesheet
from utils import get_process_tree_after_spawn, kill_script_process, run_script_in_gitbash

from scheduler_data import create_history_entry, now_iso
from scheduler_engine import get_due_schedules, validate_trigger
from scheduler_storage import (
    append_history_entry,
    load_schedules,
    save_schedules,
    update_history_entry,
)
from scheduler_ui import SchedulerContentWidget

CATEGORY_OPTIONS = ("None", "backend", "frontend")
CATEGORY_FILTER_OPTIONS = ("All", "Backend", "Frontend", "Running")
SIDEBAR_WIDTH = 220


class NoWheelComboBox(QComboBox):
    """QComboBox that ignores mouse wheel to avoid accidental option change."""

    def wheelEvent(self, event: QWheelEvent) -> None:
        event.ignore()


class LineNumberGutter(QWidget):
    """Paints line numbers alongside a QPlainTextEdit."""

    PADDING = 8  # px on each side of the number

    def __init__(self, editor: "QPlainTextEdit", palette: dict):
        super().__init__(editor.parent())
        self._editor = editor
        self._update_colors(palette)

        editor.blockCountChanged.connect(self._update_width)
        editor.updateRequest.connect(self._on_update_request)
        self._update_width()

    def _update_colors(self, palette: dict) -> None:
        self._bg_color = QColor(palette.get("sh_bg", "#1a1a1a"))
        self._fg_color = QColor(palette["text_muted"])

    def update_palette(self, palette: dict) -> None:
        self._update_colors(palette)
        self.update()

    def gutter_width(self) -> int:
        digits = max(len(str(self._editor.blockCount())), 2)
        return self.PADDING + self._editor.fontMetrics().horizontalAdvance("9") * digits + self.PADDING

    def _update_width(self) -> None:
        self._editor.setViewportMargins(self.gutter_width(), 0, 0, 0)
        self._reposition()

    def _reposition(self) -> None:
        cr = self._editor.contentsRect()
        self.setGeometry(QRect(cr.left(), cr.top(), self.gutter_width(), cr.height()))

    def _on_update_request(self, rect: QRect, dy: int) -> None:
        if dy:
            self.scroll(0, dy)
        else:
            self.update(0, rect.y(), self.width(), rect.height())
        if rect.contains(self._editor.viewport().rect()):
            self._update_width()

    def sizeHint(self) -> QSize:
        return QSize(self.gutter_width(), 0)

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.fillRect(event.rect(), self._bg_color)

        block = self._editor.firstVisibleBlock()
        block_number = block.blockNumber()
        offset = self._editor.contentOffset()
        top = self._editor.blockBoundingGeometry(block).translated(offset).top()
        bottom = top + self._editor.blockBoundingRect(block).height()

        font = self._editor.font()
        painter.setFont(font)

        while block.isValid() and top <= event.rect().bottom():
            if block.isVisible() and bottom >= event.rect().top():
                painter.setPen(self._fg_color)
                painter.drawText(
                    0,
                    int(top),
                    self.width() - self.PADDING,
                    self._editor.fontMetrics().height(),
                    Qt.AlignRight | Qt.AlignVCenter,
                    str(block_number + 1),
                )
            block = block.next()
            block_number += 1
            top = bottom
            bottom = top + self._editor.blockBoundingRect(block).height()


class ShellHighlighter(QSyntaxHighlighter):
    """Read-only syntax highlighter for .sh scripts."""

    def __init__(self, parent, palette: dict):
        super().__init__(parent)
        self._rules: list[tuple[QRegularExpression, QTextCharFormat]] = []
        self._build_rules(palette)

    def _fmt(self, color: str, bold: bool = False) -> QTextCharFormat:
        fmt = QTextCharFormat()
        fmt.setForeground(QColor(color))
        if bold:
            fmt.setFontWeight(QFont.Bold)
        return fmt

    def _build_rules(self, palette: dict) -> None:
        self._rules = []

        # Shebang line (#!...)
        self._rules.append((
            QRegularExpression(r"^#!.*$"),
            self._fmt(palette["sh_shebang"], bold=True),
        ))
        # Comments (# not shebang)
        self._rules.append((
            QRegularExpression(r"(?<!#!)#[^\n]*"),
            self._fmt(palette["sh_comment"]),
        ))
        # Double-quoted strings
        self._rules.append((
            QRegularExpression(r'"[^"\\]*(?:\\.[^"\\]*)*"'),
            self._fmt(palette["sh_string"]),
        ))
        # Single-quoted strings
        self._rules.append((
            QRegularExpression(r"'[^']*'"),
            self._fmt(palette["sh_string"]),
        ))
        # Variables: $VAR, ${VAR}, $1 etc.
        self._rules.append((
            QRegularExpression(r"\$\{?[A-Za-z_][A-Za-z0-9_]*\}?|\$[0-9@#\*\?]"),
            self._fmt(palette["sh_variable"]),
        ))
        # Keywords
        keywords = (
            r"\b(if|then|else|elif|fi|for|while|do|done|case|esac|in|"
            r"function|return|exit|export|local|declare|readonly|shift|"
            r"source|echo|printf|cd|mkdir|rm|cp|mv|chmod|chown|grep|"
            r"sed|awk|cat|ls|pwd|set|unset|true|false|test|exec)\b"
        )
        self._rules.append((
            QRegularExpression(keywords),
            self._fmt(palette["sh_keyword"], bold=True),
        ))
        # Numbers
        self._rules.append((
            QRegularExpression(r"\b[0-9]+\b"),
            self._fmt(palette["sh_number"]),
        ))

    def update_palette(self, palette: dict) -> None:
        self._build_rules(palette)
        self.rehighlight()

    def highlightBlock(self, text: str) -> None:
        for pattern, fmt in self._rules:
            it = pattern.globalMatch(text)
            while it.hasNext():
                match = it.next()
                self.setFormat(match.capturedStart(), match.capturedLength(), fmt)


class ShScriptHubApp(QMainWindow):
    def __init__(self):
        super().__init__()

        self.script_manager = None
        self.scripts = []
        self.script_rows = []
        self.script_categories = {}
        self.terminal_path = load_terminal_path()
        self.venv_activate_path = load_venv_activate_path()
        self.project_path = None
        self._theme: str = load_theme()
        self._selected_script_path: Optional[str] = None
        self._folder_expanded: dict[str, bool] = {}
        # Permanent tree widget references — built once, filtered via setVisible
        self._tree_script_rows: dict[str, QWidget] = {}   # path -> row widget
        self._tree_script_dots: dict[str, QLabel] = {}    # path -> dot label
        self._tree_folder_headers: dict[str, QWidget] = {}
        self._tree_children_widgets: dict[str, QWidget] = {}

        self._update_title()
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.top_bar = self._build_top_bar()
        layout.addWidget(self.top_bar)

        self.paths_row = self._build_paths_row()
        layout.addWidget(self.paths_row)

        self.page_selector = self._build_page_selector()
        layout.addWidget(self.page_selector)

        self.body_splitter = QSplitter(Qt.Horizontal)
        self.sidebar_panel = self._build_sidebar()
        self.detail_panel = self._build_detail_panel()
        self._scheduler_widget = SchedulerContentWidget(self)
        self._content_stack = QStackedWidget()
        self._content_stack.addWidget(self.detail_panel)
        self._content_stack.addWidget(self._scheduler_widget)
        self.body_splitter.addWidget(self.sidebar_panel)
        self.body_splitter.addWidget(self._content_stack)
        self.body_splitter.setStretchFactor(0, 0)
        self.body_splitter.setStretchFactor(1, 1)
        self.body_splitter.setSizes([SIDEBAR_WIDTH, 900])
        layout.addWidget(self.body_splitter, 1)

        self._update_path_labels()
        saved = load_project_path()
        if saved and os.path.isdir(saved):
            self.project_path = saved
            self._update_title()
            self.load_scripts()
        self._update_path_labels()
        self._render_detail_panel()

        self._tick_timer = QTimer(self)
        self._tick_timer.timeout.connect(self._tick_process_check)
        self._tick_timer.start(1000)
        QTimer.singleShot(100, self._ensure_terminal_path)

        self._scheduler_timer = QTimer(self)
        self._scheduler_timer.timeout.connect(self._scheduler_tick)
        self._scheduler_timer.start(15000)

    @property
    def _palette(self) -> dict:
        return DARK_PALETTE if self._theme == "dark" else LIGHT_PALETTE

    def _build_top_bar(self) -> QWidget:
        bar = QWidget()
        bar.setObjectName("topBar")
        bar.setFixedHeight(32)

        row = QHBoxLayout(bar)
        row.setContentsMargins(12, 0, 12, 0)
        row.setSpacing(4)

        project_btn = QPushButton("Project")
        project_btn.setObjectName("topBarBtn")
        project_btn.clicked.connect(
            lambda: self._show_button_menu(
                project_btn,
                [
                    ("Set project path", self.select_project),
                    ("Refresh", self._refresh_scripts),
                ],
            )
        )
        row.addWidget(project_btn)

        terminal_btn = QPushButton("Terminal")
        terminal_btn.setObjectName("topBarBtn")
        terminal_btn.clicked.connect(
            lambda: self._show_button_menu(
                terminal_btn,
                [("Set terminal path", self._choose_terminal_path)],
            )
        )
        row.addWidget(terminal_btn)

        venv_btn = QPushButton("Venv")
        venv_btn.setObjectName("topBarBtn")
        venv_btn.clicked.connect(
            lambda: self._show_button_menu(
                venv_btn,
                [
                    ("Set venv activate path", self._choose_venv_activate_path),
                    ("Clear venv path", self._clear_venv_activate_path),
                ],
            )
        )
        row.addWidget(venv_btn)

        row.addStretch()

        theme_label = "☀ Light" if self._theme == "dark" else "🌙 Dark"
        self._theme_btn = QPushButton(theme_label)
        self._theme_btn.setObjectName("topBarBtn")
        self._theme_btn.clicked.connect(self._toggle_theme)
        row.addWidget(self._theme_btn)

        return bar

    def _toggle_theme(self) -> None:
        self._theme = "light" if self._theme == "dark" else "dark"
        save_theme(self._theme)
        QApplication.instance().setStyleSheet(get_stylesheet(self._theme))
        self._theme_btn.setText("☀ Light" if self._theme == "dark" else "🌙 Dark")
        self._sh_highlighter.update_palette(self._palette)
        self._line_gutter.update_palette(self._palette)
        if hasattr(self, "_scheduler_widget"):
            self._scheduler_widget.refresh_current_view()

    def _build_paths_row(self) -> QWidget:
        row_widget = QWidget()
        row_widget.setObjectName("pathsRow")
        row_widget.setFixedHeight(32)
        row = QHBoxLayout(row_widget)
        row.setContentsMargins(12, 0, 12, 0)
        row.setSpacing(8)

        self.terminal_label = QLabel("Terminal path: —")
        self.project_label = QLabel("Project path: —")
        self.venv_label = QLabel("Venv activate: Auto")

        sep1 = QLabel("|")
        sep2 = QLabel("|")
        sep1.setStyleSheet(f"color: {self._palette['text_muted']};")
        sep2.setStyleSheet(f"color: {self._palette['text_muted']};")

        row.addWidget(self.terminal_label)
        row.addWidget(sep1)
        row.addWidget(self.project_label)
        row.addWidget(sep2)
        row.addWidget(self.venv_label)
        row.addStretch()

        return row_widget

    def _build_sidebar(self) -> QFrame:
        panel = QFrame()
        panel.setObjectName("sidebarPanel")
        panel.setMinimumWidth(SIDEBAR_WIDTH)

        layout = QVBoxLayout(panel)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(8)

        favorites_header = QLabel("FAVORITES")
        favorites_header.setObjectName("sectionHeader")
        layout.addWidget(favorites_header)

        favorites_section = QWidget()
        favorites_section.setObjectName("favoritesSection")
        self.favorites_layout = QVBoxLayout(favorites_section)
        self.favorites_layout.setContentsMargins(0, 0, 0, 0)
        self.favorites_layout.setSpacing(2)
        layout.addWidget(favorites_section)

        layout.addWidget(self._build_divider())

        filter_row = QHBoxLayout()
        filter_row.setContentsMargins(0, 0, 0, 0)
        filter_row.setSpacing(6)
        filter_row.addWidget(QLabel("Filter"))
        self.category_combo = NoWheelComboBox()
        self.category_combo.setObjectName("categoryCombo")
        self.category_combo.addItems(CATEGORY_FILTER_OPTIONS)
        filter_row.addWidget(self.category_combo, 1)
        layout.addLayout(filter_row)

        self.search_edit = QLineEdit()
        self.search_edit.setObjectName("searchEdit")
        self.search_edit.setPlaceholderText("Search...")
        self.search_edit.setClearButtonEnabled(True)
        layout.addWidget(self.search_edit)

        layout.addWidget(self._build_divider())

        project_header = QLabel("PROJECT")
        project_header.setObjectName("sectionHeader")
        layout.addWidget(project_header)

        self.tree_scroll = QScrollArea()
        self.tree_scroll.setFrameShape(QFrame.NoFrame)
        self.tree_scroll.setWidgetResizable(True)
        self.tree_container = QWidget()
        self.tree_container.setObjectName("treeSection")
        self.tree_layout = QVBoxLayout(self.tree_container)
        self.tree_layout.setContentsMargins(0, 0, 0, 0)
        self.tree_layout.setSpacing(2)
        self.tree_scroll.setWidget(self.tree_container)
        layout.addWidget(self.tree_scroll, 1)

        self._search_debounce_timer = QTimer(self)
        self._search_debounce_timer.setSingleShot(True)
        self._search_debounce_timer.setInterval(180)
        self._search_debounce_timer.timeout.connect(self._on_filter_changed)

        self.category_combo.currentTextChanged.connect(self._on_filter_changed)
        self.search_edit.textChanged.connect(self._search_debounce_timer.start)

        return panel

    def _build_detail_panel(self) -> QWidget:
        panel = QWidget()
        panel.setObjectName("detailPanel")
        root = QVBoxLayout(panel)
        root.setContentsMargins(24, 16, 24, 16)
        root.setSpacing(12)

        self._detail_placeholder = QWidget()
        placeholder_layout = QVBoxLayout(self._detail_placeholder)
        placeholder_layout.setContentsMargins(0, 0, 0, 0)
        placeholder_layout.addStretch()
        placeholder_lbl = QLabel("Select a script")
        placeholder_lbl.setAlignment(Qt.AlignCenter)
        placeholder_layout.addWidget(placeholder_lbl)
        placeholder_layout.addStretch()
        root.addWidget(self._detail_placeholder, 1)

        self._detail_content = QWidget()
        content = QVBoxLayout(self._detail_content)
        content.setContentsMargins(0, 0, 0, 0)
        content.setSpacing(8)
        root.addWidget(self._detail_content, 1)

        self.detail_title = QLabel("")
        self.detail_title.setObjectName("detailTitle")
        content.addWidget(self.detail_title)

        detail_row = QHBoxLayout()
        detail_row.setSpacing(8)
        detail_row.addWidget(QLabel("Category:"))
        self.detail_category_combo = NoWheelComboBox()
        self.detail_category_combo.setObjectName("detailCategoryCombo")
        self.detail_category_combo.addItems(CATEGORY_OPTIONS)
        detail_row.addWidget(self.detail_category_combo)
        detail_row.addSpacing(8)
        detail_row.addWidget(QLabel("Env:"))
        self.detail_env_label = QLabel(PLACEHOLDER)
        detail_row.addWidget(self.detail_env_label)
        detail_row.addSpacing(8)
        detail_row.addWidget(QLabel("Status:"))
        self.detail_status_label = QLabel(PLACEHOLDER)
        detail_row.addWidget(self.detail_status_label)
        detail_row.addSpacing(8)
        detail_row.addWidget(QLabel("PID:"))
        self.detail_pid_label = QLabel(PLACEHOLDER)
        detail_row.addWidget(self.detail_pid_label)
        detail_row.addStretch()
        self.detail_fav_btn = QPushButton("☆")
        self.detail_fav_btn.setObjectName("favBtn")
        detail_row.addWidget(self.detail_fav_btn)
        content.addLayout(detail_row)

        action_row = QHBoxLayout()
        action_row.setSpacing(8)
        self.detail_run_btn = QPushButton("Run")
        self.detail_run_btn.setObjectName("runBtn")
        self.detail_kill_btn = QPushButton("Kill")
        self.detail_kill_btn.setObjectName("killBtn")
        self.detail_kill_btn.setVisible(False)
        action_row.addWidget(self.detail_run_btn)
        action_row.addWidget(self.detail_kill_btn)
        action_row.addStretch()
        content.addLayout(action_row)

        metrics_header = QLabel("Metrics")
        metrics_header.setObjectName("detailSectionHeader")
        content.addWidget(metrics_header)

        metrics_grid = QGridLayout()
        metrics_grid.setVerticalSpacing(2)
        metrics_grid.setHorizontalSpacing(8)
        metric_specs = [
            ("CPU %", "detail_cpu_pct_label"),
            ("RAM (RSS)", "detail_ram_rss_label"),
            ("RAM %", "detail_ram_pct_label"),
            ("Elapsed", "detail_elapsed_label"),
            ("Peak memory", "detail_peak_mem_label"),
            ("CPU time", "detail_cpu_time_label"),
            ("Threads", "detail_threads_label"),
        ]
        for idx, (title, attr_name) in enumerate(metric_specs):
            r, c = idx // 2, (idx % 2) * 2
            metrics_grid.addWidget(QLabel(f"{title}:"), r, c)
            value = QLabel(PLACEHOLDER)
            setattr(self, attr_name, value)
            metrics_grid.addWidget(value, r, c + 1)
        content.addLayout(metrics_grid)

        script_header = QLabel("Script")
        script_header.setObjectName("detailSectionHeader")
        content.addWidget(script_header)

        # Container gives the gutter a shared parent with the editor
        viewer_container = QFrame()
        viewer_container.setObjectName("scriptViewer")
        viewer_container_layout = QVBoxLayout(viewer_container)
        viewer_container_layout.setContentsMargins(0, 0, 0, 0)
        viewer_container_layout.setSpacing(0)

        self.script_viewer = QPlainTextEdit(viewer_container)
        self.script_viewer.setReadOnly(True)
        viewer_font = QFont("Consolas")
        viewer_font.setStyleHint(QFont.Monospace)
        viewer_font.setPointSize(9)
        self.script_viewer.setFont(viewer_font)
        self.script_viewer.setLineWrapMode(QPlainTextEdit.NoWrap)
        # Remove the editor's own frame — the container provides it
        self.script_viewer.setFrameShape(QFrame.NoFrame)
        viewer_container_layout.addWidget(self.script_viewer)
        content.addWidget(viewer_container, 1)

        self._sh_highlighter = ShellHighlighter(self.script_viewer.document(), self._palette)
        self._line_gutter = LineNumberGutter(self.script_viewer, self._palette)

        self.detail_run_btn.clicked.connect(self._run_selected_script)
        self.detail_kill_btn.clicked.connect(self._kill_selected_script)
        self.detail_fav_btn.clicked.connect(self._toggle_selected_favorite)
        self.detail_category_combo.currentTextChanged.connect(self._on_detail_category_changed)

        self._detail_content.setVisible(False)
        self._detail_placeholder.setVisible(True)
        return panel

    def _build_divider(self) -> QFrame:
        divider = QFrame()
        divider.setObjectName("divider")
        divider.setFrameShape(QFrame.HLine)
        return divider

    def _show_button_menu(self, button: QPushButton, action_specs: list[tuple[str, Callable]]) -> None:
        menu = QMenu(self)
        for text, callback in action_specs:
            action = QAction(text, self)
            action.triggered.connect(callback)
            menu.addAction(action)
        menu.exec(button.mapToGlobal(button.rect().bottomLeft()))

    def _update_path_labels(self) -> None:
        self.terminal_label.setText(f"Terminal path: {self.terminal_path or '—'}")
        self.venv_label.setText(f"Venv activate: {self.venv_activate_path or 'Auto'}")
        self.project_label.setText(f"Project path: {self.project_path or '—'}")

    def _choose_terminal_path(self) -> None:
        QMessageBox.information(
            self,
            "ShScriptHub",
            "Select the terminal executable (.exe), e.g. Git Bash.",
        )
        title = "Select terminal executable"
        if os.name == "nt":
            path, _ = QFileDialog.getOpenFileName(
                self,
                title,
                os.environ.get("ProgramFiles", "/"),
                "Executable (*.exe);;All files (*.*)",
            )
        else:
            path, _ = QFileDialog.getOpenFileName(self, title)
        if path and os.path.isfile(path):
            save_terminal_path(path)
            self.terminal_path = path
            self._update_path_labels()
            QMessageBox.information(self, "ShScriptHub", "Terminal path saved.")

    def _choose_venv_activate_path(self) -> None:
        QMessageBox.information(
            self,
            "ShScriptHub",
            "Select the venv activate script (e.g. backend\\.venv\\Scripts\\activate). Used for backend scripts; overrides auto-detect.",
        )
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Select venv activate script",
            self.project_path or os.path.expanduser("~"),
            "All files (*.*)",
        )
        if path and os.path.isfile(path):
            save_venv_activate_path(path)
            self.venv_activate_path = path
            self._update_path_labels()
            QMessageBox.information(self, "ShScriptHub", "Venv activate path saved.")

    def _refresh_scripts(self) -> None:
        if not self.project_path:
            QMessageBox.information(self, "ShScriptHub", "Select project path first.")
            return
        self.load_scripts()

    def _clear_venv_activate_path(self) -> None:
        save_venv_activate_path("")
        self.venv_activate_path = None
        self._update_path_labels()
        if self.project_path:
            self.load_scripts()
        QMessageBox.information(
            self, "ShScriptHub", "Venv path cleared. Backend scripts will use auto-detect."
        )

    def _ensure_terminal_path(self) -> None:
        if self.terminal_path and os.path.isfile(self.terminal_path):
            return
        self._choose_terminal_path()

    def _get_default_category(self, script_path: str) -> str:
        rel = os.path.relpath(script_path, self.project_path)
        parts = os.path.normpath(rel).split(os.sep)
        if parts and parts[0].lower() == "backend":
            return "backend"
        if parts and parts[0].lower() == "frontend":
            return "frontend"
        return "none"

    def _get_category_for_script(self, script_path: str) -> str:
        return self.script_categories.get(script_path) or self._get_default_category(script_path)

    def _get_env_display(self, script: dict, category: str) -> str:
        cwd = os.path.dirname(script["path"])
        if not os.path.isdir(cwd):
            return "—"
        if category == "backend" and self.venv_activate_path and os.path.isfile(self.venv_activate_path):
            activate_dir = os.path.dirname(self.venv_activate_path)
            venv_dir = os.path.dirname(activate_dir)
            return os.path.basename(venv_dir) if venv_dir else "—"
        search_roots = [cwd]
        if self.project_path and os.path.isdir(self.project_path) and self.project_path != cwd:
            search_roots.append(self.project_path)
        for root in search_roots:
            for path, name in [
                (os.path.join(root, ".venv", "Scripts", "activate"), ".venv"),
                (os.path.join(root, ".venv", "bin", "activate"), ".venv"),
                (os.path.join(root, "venv", "Scripts", "activate"), "venv"),
                (os.path.join(root, "venv", "bin", "activate"), "venv"),
            ]:
                if os.path.isfile(path):
                    return name
        if os.path.isdir(os.path.join(cwd, "node_modules")):
            return "node_modules"
        return "—"

    def _update_title(self) -> None:
        if getattr(self, "project_path", None):
            self.setWindowTitle(f"ShScriptHub - {os.path.basename(self.project_path)}")
        else:
            self.setWindowTitle("ShScriptHub")

    def select_project(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "Select the root of the project")
        if not folder:
            return
        self.project_path = folder
        self._update_path_labels()
        self._update_title()
        save_project_path(self.project_path)
        self.load_scripts()

    def _matches_search(self, script: dict, search_text: str) -> bool:
        if not search_text or not search_text.strip():
            return True
        q = search_text.strip().lower()
        rel = os.path.relpath(script["path"], self.project_path).replace("\\", "/").lower()
        name = script["name"].lower()
        folder = os.path.basename(os.path.dirname(script["path"])).lower()
        return q in rel or q in name or q in folder

    def _script_folder(self, script: dict) -> str:
        rel = os.path.relpath(script["path"], self.project_path)
        parts = os.path.normpath(rel).split(os.sep)
        if len(parts) <= 1:
            return "root"
        return parts[0]

    def _get_row(self, path: Optional[str]) -> Optional[dict]:
        if not path:
            return None
        for row in self.script_rows:
            if row["script"]["path"] == path:
                return row
        return None

    def _is_row_running(self, row: Optional[dict]) -> bool:
        if row is None:
            return False
        proc = row.get("process")
        return proc is not None and proc.poll() is None

    def _set_detail_status(self, text: str) -> None:
        self.detail_status_label.setText(text)
        color = {
            "—": self._palette["status_placeholder"],
            "Running": self._palette["status_running"],
            "Stopped": self._palette["status_stopped"],
        }.get(text, self._palette["status_placeholder"])
        self.detail_status_label.setStyleSheet(f"color: {color};")

    def _run_selected_script(self) -> None:
        row = self._get_row(self._selected_script_path)
        if row:
            self._run_script_row(row)

    def _kill_selected_script(self) -> None:
        row = self._get_row(self._selected_script_path)
        if row:
            self._kill_script_row(row)

    def _toggle_selected_favorite(self) -> None:
        path = self._selected_script_path
        if not path:
            return
        now_fav = toggle_favorite(path)
        self.detail_fav_btn.setText("★" if now_fav else "☆")
        self._rebuild_favorites()
        self._refresh_sidebar_selection()

    def _on_detail_category_changed(self, text: str) -> None:
        path = self._selected_script_path
        if not path:
            return
        stored = "none" if text == "None" else text
        save_script_category(path, stored)
        self.script_categories[path] = stored
        row = self._get_row(path)
        if row:
            self.detail_env_label.setText(self._get_env_display(row["script"], stored))
        self._apply_tree_filter()

    def _select_script(self, path: str) -> None:
        self._selected_script_path = path
        self._switch_page("home")
        self._render_detail_panel()
        self._refresh_sidebar_selection()

    def _render_detail_panel(self) -> None:
        row = self._get_row(self._selected_script_path)
        if row is None:
            self._detail_placeholder.setVisible(True)
            self._detail_content.setVisible(False)
            return

        self._detail_placeholder.setVisible(False)
        self._detail_content.setVisible(True)

        path = row["script"]["path"]
        rel = os.path.relpath(path, self.project_path).replace("\\", "/")
        category = self._get_category_for_script(path)
        running = self._is_row_running(row)

        self.detail_title.setText(rel)
        self.detail_category_combo.blockSignals(True)
        self.detail_category_combo.setCurrentText("None" if category == "none" else category)
        self.detail_category_combo.blockSignals(False)
        self.detail_env_label.setText(self._get_env_display(row["script"], category))

        self._set_detail_status("Running" if running else "Stopped")
        proc = row.get("process")
        self.detail_pid_label.setText(str(proc.pid) if running and proc is not None else PLACEHOLDER)
        self.detail_fav_btn.setText("★" if path in load_favorites() else "☆")
        self.detail_kill_btn.setVisible(running)

        if running:
            self._update_row_metrics(row)
        else:
            for lbl in (
                self.detail_cpu_pct_label,
                self.detail_ram_rss_label,
                self.detail_ram_pct_label,
                self.detail_elapsed_label,
                self.detail_peak_mem_label,
                self.detail_cpu_time_label,
                self.detail_threads_label,
            ):
                lbl.setText(PLACEHOLDER)

        self._load_script_viewer(path)

    def _load_script_viewer(self, path: str) -> None:
        try:
            with open(path, encoding="utf-8", errors="replace") as f:
                content = f.read()
        except OSError:
            content = f"# Could not read file: {path}"
        self.script_viewer.setPlainText(content)
        self.script_viewer.moveCursor(QTextCursor.MoveOperation.Start)

    # ------------------------------------------------------------------
    # Sidebar – favorites (rebuilt on load/favorite-toggle only)
    # ------------------------------------------------------------------

    def _rebuild_favorites(self) -> None:
        """Tear down and recreate only the favorites section. Called on load and favorite toggle."""
        while self.favorites_layout.count():
            item = self.favorites_layout.takeAt(0)
            w = item.widget()
            if w:
                w.hide()
                w.setParent(None)

        # Favorites sidebar refs are separate from tree refs
        self._fav_row_refs: list[tuple[str, QWidget, QLabel]] = []

        favorites = sorted(load_favorites())
        favorites = [p for p in favorites if self._get_row(p) is not None]
        if not favorites:
            empty = QLabel("No favorites")
            empty.setStyleSheet(f"color: {self._palette['text_muted']};")
            self.favorites_layout.addWidget(empty)
            return
        for script_path in favorites:
            row_w, dot = self._make_sidebar_row_widget(script_path, show_star=True)
            self.favorites_layout.addWidget(row_w)
            self._fav_row_refs.append((script_path, row_w, dot))

    # ------------------------------------------------------------------
    # Sidebar – tree (built ONCE on load_scripts, filtered via setVisible)
    # ------------------------------------------------------------------

    def _build_tree(self) -> None:
        """Build the full tree from scratch. Called only from load_scripts."""
        # Clear any previous tree widgets
        while self.tree_layout.count():
            item = self.tree_layout.takeAt(0)
            w = item.widget()
            if w:
                w.hide()
                w.setParent(None)

        self._tree_script_rows.clear()
        self._tree_script_dots.clear()
        self._tree_folder_headers.clear()
        self._tree_children_widgets.clear()

        # Group ALL scripts by folder (no filtering here)
        grouped: dict[str, list[dict]] = {}
        for row in self.script_rows:
            folder = self._script_folder(row["script"])
            grouped.setdefault(folder, []).append(row)

        folders = sorted(f for f in grouped if f != "root")
        if "root" in grouped:
            folders.append("root")

        for folder in folders:
            expanded = self._folder_expanded.get(folder, True)

            folder_header = QWidget()
            header_layout = QHBoxLayout(folder_header)
            header_layout.setContentsMargins(6, 4, 6, 2)
            header_layout.setSpacing(6)
            toggle_btn = QPushButton("▼" if expanded else "►")
            toggle_btn.setObjectName("folderToggleBtn")
            toggle_btn.setFixedSize(22, 22)
            folder_lbl = QLabel(folder)
            folder_lbl.setObjectName("folderLabel")
            header_layout.addWidget(toggle_btn, 0)
            header_layout.addWidget(folder_lbl, 1)
            self.tree_layout.addWidget(folder_header)
            self._tree_folder_headers[folder] = folder_header

            children_widget = QWidget()
            children_layout = QVBoxLayout(children_widget)
            children_layout.setContentsMargins(18, 0, 0, 4)
            children_layout.setSpacing(2)

            for row in sorted(grouped[folder], key=lambda r: r["script"]["path"].lower()):
                script = row["script"]
                row_w, dot = self._make_sidebar_row_widget(script["path"], display_text=script["name"])
                children_layout.addWidget(row_w)
                self._tree_script_rows[script["path"]] = row_w
                self._tree_script_dots[script["path"]] = dot

            children_widget.setVisible(expanded)
            self.tree_layout.addWidget(children_widget)
            self._tree_children_widgets[folder] = children_widget

            toggle_btn.clicked.connect(
                lambda checked=False, f=folder, w=children_widget, b=toggle_btn: self._toggle_folder(f, w, b)
            )

        self.tree_layout.addStretch()

    def _apply_tree_filter(self) -> None:
        """Show/hide existing tree widgets based on current filter and search. No widget creation."""
        filter_text = self.category_combo.currentText()
        query = self.search_edit.text().strip().lower()

        for row in self.script_rows:
            script = row["script"]
            path = script["path"]
            row_w = self._tree_script_rows.get(path)
            if row_w is None:
                continue

            visible = True
            if query and not self._matches_search(script, query):
                visible = False
            if visible and filter_text == "Backend":
                visible = self._get_category_for_script(path) == "backend"
            if visible and filter_text == "Frontend":
                visible = self._get_category_for_script(path) == "frontend"
            if visible and filter_text == "Running":
                visible = self._is_row_running(row)

            row_w.setVisible(visible)

        # Show/hide folder headers: visible if at least one child is not explicitly hidden.
        # isVisible() must NOT be used here — when children_widget is hidden (from a prior
        # filter pass) all children also return isVisible()==False, breaking subsequent passes.
        # isHidden() checks only the widget's own flag, independent of ancestor visibility.
        for folder, children_widget in self._tree_children_widgets.items():
            expanded = self._folder_expanded.get(folder, True)
            children_layout = children_widget.layout()
            folder_has_visible = any(
                children_layout.itemAt(i).widget() is not None
                and not children_layout.itemAt(i).widget().isHidden()
                for i in range(children_layout.count())
            )
            header = self._tree_folder_headers.get(folder)
            if header:
                header.setVisible(folder_has_visible)
            children_widget.setVisible(folder_has_visible and expanded)

    def _toggle_folder(self, folder: str, widget: QWidget, toggle_btn: QPushButton) -> None:
        current = self._folder_expanded.get(folder, True)
        new_state = not current
        self._folder_expanded[folder] = new_state
        widget.setVisible(new_state)
        toggle_btn.setText("▼" if new_state else "►")

    def _make_sidebar_row_widget(
        self, script_path: str, show_star: bool = False, display_text: Optional[str] = None
    ) -> tuple[QWidget, QLabel]:
        """Create a sidebar row widget. Returns (row_widget, dot_label)."""
        row = QWidget()
        row.setObjectName("sidebarRow")
        row.setProperty("selected", script_path == self._selected_script_path)
        row.setCursor(Qt.PointingHandCursor)
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(8, 3, 8, 3)
        row_layout.setSpacing(6)

        running = self._is_row_running(self._get_row(script_path))
        dot = QLabel("•" if running else "o")
        dot.setObjectName("dotLabel")
        dot.setProperty("running", "true" if running else "false")
        row_layout.addWidget(dot)

        if display_text is None:
            display_text = os.path.relpath(script_path, self.project_path).replace("\\", "/")
        name_lbl = QLabel(display_text)
        name_lbl.setToolTip(os.path.relpath(script_path, self.project_path).replace("\\", "/"))
        row_layout.addWidget(name_lbl, 1)

        if show_star or script_path in load_favorites():
            star = QLabel("★")
            star.setStyleSheet(f"color: {self._palette['fav_btn']};")
            row_layout.addWidget(star)

        row.mousePressEvent = lambda event, p=script_path: self._select_script(p)
        return row, dot

    def _refresh_sidebar(self) -> None:
        """Full sidebar refresh — called on load and favorite toggle."""
        self._rebuild_favorites()
        self._build_tree()
        self._refresh_sidebar_selection()

    def _refresh_sidebar_dots(self) -> None:
        """Update dot state on all visible sidebar rows without any widget creation."""
        all_refs = list(self._tree_script_dots.items())
        fav_refs = getattr(self, "_fav_row_refs", [])

        for path, dot in all_refs:
            running = self._is_row_running(self._get_row(path))
            dot.setText("•" if running else "o")
            dot.setProperty("running", "true" if running else "false")
            dot.style().unpolish(dot)
            dot.style().polish(dot)

        for path, _row_w, dot in fav_refs:
            running = self._is_row_running(self._get_row(path))
            dot.setText("•" if running else "o")
            dot.setProperty("running", "true" if running else "false")
            dot.style().unpolish(dot)
            dot.style().polish(dot)

        self._refresh_sidebar_selection()

    def _refresh_sidebar_selection(self) -> None:
        """Update selected highlight on all sidebar rows."""
        all_rows: list[tuple[str, QWidget]] = list(self._tree_script_rows.items())
        all_rows += [(p, w) for p, w, _d in getattr(self, "_fav_row_refs", [])]
        for path, widget in all_rows:
            widget.setProperty("selected", path == self._selected_script_path)
            widget.style().unpolish(widget)
            widget.style().polish(widget)

    def _on_filter_changed(self, _value=None) -> None:
        self._apply_tree_filter()
        self._refresh_sidebar_selection()

    def load_scripts(self) -> None:
        try:
            self.script_rows = []
            self.script_manager = ScriptManager(self.project_path)
            self.scripts = self.script_manager.get_scripts()
        except Exception as exc:
            QMessageBox.critical(self, "ShScriptHub - Error", f"Failed to load scripts: {str(exc)}")
            return

        self.script_categories = load_script_categories()
        self.scripts.sort(key=lambda s: s["path"].lower())
        for script in self.scripts:
            row = {
                "script": script,
                "process": None,
                "kill_pids": None,
                "start_time": None,
                "peak_rss": 0.0,
                "cpu_primed_pids": None,
                "scheduler_history_id": None,
            }
            self.script_rows.append(row)

        self._refresh_sidebar()
        if self.scripts:
            paths = {s["path"] for s in self.scripts}
            if self._selected_script_path not in paths:
                self._select_script(self.scripts[0]["path"])
            else:
                self._render_detail_panel()
        else:
            self._selected_script_path = None
            self._render_detail_panel()

    def _run_script_row(self, row: dict) -> None:
        try:
            category = self._get_category_for_script(row["script"]["path"])
            proc = run_script_in_gitbash(
                row["script"]["path"],
                category,
                self.project_path,
                terminal_path=self.terminal_path,
                venv_activate_path=self.venv_activate_path,
            )
            row["process"] = proc
            row["kill_pids"] = None
            row["start_time"] = time.monotonic()
            row["peak_rss"] = 0.0
            row["cpu_primed_pids"] = set()
            delay_ms = int(utils.TREE_CAPTURE_DELAY_SEC * 1000)
            QTimer.singleShot(delay_ms, lambda: self._capture_kill_pids(row))
            if row["script"]["path"] == self._selected_script_path:
                self._render_detail_panel()
            self._refresh_sidebar_dots()
            QMessageBox.information(self, "ShScriptHub", f"Script '{row['script']['name']}' started.")
        except Exception as exc:
            QMessageBox.critical(self, "ShScriptHub - Error", str(exc))

    def _capture_kill_pids(self, row: dict) -> None:
        proc = row.get("process")
        if proc is None or proc.poll() is not None:
            return
        row["kill_pids"] = get_process_tree_after_spawn(proc)

    def _kill_script_row(self, row: dict) -> None:
        proc = row.get("process")
        if proc is None:
            return
        kill_pids = row.get("kill_pids")
        if not kill_pids and proc.poll() is None:
            kill_pids = [proc.pid]
        kill_script_process(proc, kill_pids=kill_pids)
        row["process"] = None
        row["kill_pids"] = None
        row["start_time"] = None
        row["peak_rss"] = 0.0
        row["cpu_primed_pids"] = None
        if row["script"]["path"] == self._selected_script_path:
            self._render_detail_panel()
        self._refresh_sidebar_dots()

    def check_processes(self) -> None:
        changed = False
        for row in self.script_rows:
            proc = row.get("process")
            if proc is None:
                continue
            if proc.poll() is None:
                continue
            history_id = row.get("scheduler_history_id")
            if history_id:
                update_history_entry(history_id, {
                    "status": "exited",
                    "finished_at": now_iso(),
                })
                row["scheduler_history_id"] = None
            row["process"] = None
            row["kill_pids"] = None
            row["start_time"] = None
            row["peak_rss"] = 0.0
            row["cpu_primed_pids"] = None
            changed = True
            if row["script"]["path"] == self._selected_script_path:
                self._render_detail_panel()
        if changed:
            self._refresh_sidebar_dots()

    def _update_row_metrics(self, row: dict) -> None:
        if row["script"]["path"] != self._selected_script_path:
            return
        proc = row.get("process")
        if proc is None or proc.poll() is not None:
            return
        pids = row.get("kill_pids") or [proc.pid]
        start_time = row.get("start_time") or 0
        peak_rss = row.get("peak_rss") or 0.0
        cpu_primed_pids = row.get("cpu_primed_pids")
        if cpu_primed_pids is None:
            cpu_primed_pids = set()
            row["cpu_primed_pids"] = cpu_primed_pids
        try:
            metrics = collect_metrics(pids, start_time, peak_rss, cpu_primed_pids)
        except Exception:
            return
        row["peak_rss"] = metrics["peak_rss_bytes"]
        self.detail_cpu_pct_label.setText(f"{metrics['cpu_percent']:.1f}%")
        self.detail_ram_rss_label.setText(f"{metrics['rss_mb']:.2f} MB")
        self.detail_ram_pct_label.setText(f"{metrics['ram_percent']:.1f}%")
        self.detail_elapsed_label.setText(format_elapsed(metrics["elapsed_sec"]))
        self.detail_peak_mem_label.setText(f"{metrics['peak_rss_mb']:.2f} MB")
        self.detail_cpu_time_label.setText(format_cpu_time(metrics["cpu_time_sec"]))
        self.detail_threads_label.setText(str(metrics["num_threads"]))

    def _tick_process_check(self) -> None:
        self.check_processes()
        row = self._get_row(self._selected_script_path)
        if row and self._is_row_running(row):
            self._update_row_metrics(row)

    # ------------------------------------------------------------------
    # Page selector
    # ------------------------------------------------------------------

    def _build_page_selector(self) -> QWidget:
        selector = QWidget()
        selector.setObjectName("pageSelector")
        selector.setFixedHeight(32)
        row = QHBoxLayout(selector)
        row.setContentsMargins(12, 0, 12, 0)
        row.setSpacing(4)

        self._home_page_btn = QPushButton("Home")
        self._home_page_btn.setObjectName("pageSelectorBtn")
        self._home_page_btn.clicked.connect(lambda: self._switch_page("home"))
        row.addWidget(self._home_page_btn)

        self._scheduler_page_btn = QPushButton("Scheduler")
        self._scheduler_page_btn.setObjectName("pageSelectorBtn")
        self._scheduler_page_btn.clicked.connect(lambda: self._switch_page("scheduler"))
        row.addWidget(self._scheduler_page_btn)

        row.addStretch()

        self._current_page = "home"
        self._update_page_selector_styles()
        return selector

    def _switch_page(self, page: str) -> None:
        self._current_page = page
        if page == "home":
            self._content_stack.setCurrentIndex(0)
        else:
            self._content_stack.setCurrentIndex(1)
            self._scheduler_widget.refresh_schedules()
        self._update_page_selector_styles()

    def _update_page_selector_styles(self) -> None:
        self._home_page_btn.setProperty("active", "true" if self._current_page == "home" else "false")
        self._scheduler_page_btn.setProperty("active", "true" if self._current_page == "scheduler" else "false")
        for btn in (self._home_page_btn, self._scheduler_page_btn):
            btn.style().unpolish(btn)
            btn.style().polish(btn)

    # ------------------------------------------------------------------
    # Scheduler engine integration
    # ------------------------------------------------------------------

    def _scheduler_tick(self) -> None:
        if not self.project_path:
            return
        schedules = load_schedules()
        due = get_due_schedules(schedules)
        if not due:
            return
        for schedule in due:
            self._execute_scheduled_run(schedule)
        save_schedules(schedules)
        self._refresh_sidebar_dots()

    def _execute_scheduled_run(self, schedule: dict) -> None:
        script_path = schedule["script_path"]
        triggered_at = now_iso()

        error = validate_trigger(script_path, self.project_path)
        if error:
            entry = create_history_entry(
                schedule_id=schedule["id"],
                schedule_name=schedule["name"],
                script_path=script_path,
                triggered_at=triggered_at,
                started_at=None,
                status="failed",
                error_message=error,
            )
            append_history_entry(entry)
            self._mark_schedule_triggered(schedule)
            return

        row = self._get_row(script_path)

        if row and self._is_row_running(row):
            history_id = row.get("scheduler_history_id")
            if history_id:
                update_history_entry(history_id, {
                    "status": "killed",
                    "finished_at": now_iso(),
                })
                row["scheduler_history_id"] = None
            kill_script_process(row.get("process"), kill_pids=row.get("kill_pids"))
            try:
                proc = row.get("process")
                if proc:
                    proc.wait(timeout=3)
            except Exception:
                pass
            row["process"] = None
            row["kill_pids"] = None
            row["start_time"] = None
            row["peak_rss"] = 0.0
            row["cpu_primed_pids"] = None

        try:
            category = self._get_category_for_script(script_path)
            proc = run_script_in_gitbash(
                script_path,
                category,
                self.project_path,
                terminal_path=self.terminal_path,
                venv_activate_path=self.venv_activate_path,
            )
            started_at = now_iso()

            if row:
                row["process"] = proc
                row["kill_pids"] = None
                row["start_time"] = time.monotonic()
                row["peak_rss"] = 0.0
                row["cpu_primed_pids"] = set()
                delay_ms = int(utils.TREE_CAPTURE_DELAY_SEC * 1000)
                QTimer.singleShot(delay_ms, lambda r=row: self._capture_kill_pids(r))

            entry = create_history_entry(
                schedule_id=schedule["id"],
                schedule_name=schedule["name"],
                script_path=script_path,
                triggered_at=triggered_at,
                started_at=started_at,
                status="started",
            )
            append_history_entry(entry)

            if row:
                row["scheduler_history_id"] = entry["id"]

            self._mark_schedule_triggered(schedule)

            if script_path == self._selected_script_path:
                self._render_detail_panel()
        except Exception as exc:
            entry = create_history_entry(
                schedule_id=schedule["id"],
                schedule_name=schedule["name"],
                script_path=script_path,
                triggered_at=triggered_at,
                started_at=None,
                status="failed",
                error_message=str(exc),
            )
            append_history_entry(entry)
            self._mark_schedule_triggered(schedule)

    def _mark_schedule_triggered(self, schedule: dict) -> None:
        schedule["last_triggered_at"] = now_iso()
        if schedule["rule_type"] == "interval":
            schedule["interval_base_at"] = now_iso()
