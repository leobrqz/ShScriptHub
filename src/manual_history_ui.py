import os
from datetime import datetime

from PySide6.QtCore import Qt, QStringListModel
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QComboBox,
    QCompleter,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from highlighter import ShellHighlighter
from scheduler_storage import load_history, load_log
from scheduler_ui import STATUS_DISPLAY, HISTORY_FILTER_OPTIONS

class ManualHistoryWidget(QWidget):
    def __init__(self, main_window):
        super().__init__(main_window)
        self._main = main_window
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setObjectName("manualHistoryWidget")

        self._selected_history_run_id = None
        self._history_row_map = {}

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        splitter = QSplitter(Qt.Orientation.Vertical)

        list_widget = QWidget()
        list_layout = QVBoxLayout(list_widget)
        list_layout.setContentsMargins(0, 0, 0, 0)
        list_layout.setSpacing(8)

        # Filters
        filter_row = QHBoxLayout()
        filter_row.setSpacing(8)
        
        filter_row.addWidget(QLabel("Script:"))
        self._history_script_combo = QComboBox()
        self._history_script_combo.setMinimumWidth(180)
        self._history_script_combo.currentTextChanged.connect(lambda _: self.refresh_history())
        filter_row.addWidget(self._history_script_combo, 1)
        
        filter_row.addWidget(QLabel("Status:"))
        self._history_filter = QComboBox()
        self._history_filter.addItems(HISTORY_FILTER_OPTIONS)
        self._history_filter.currentTextChanged.connect(lambda _: self.refresh_history())
        filter_row.addWidget(self._history_filter)
        filter_row.addStretch()
        list_layout.addLayout(filter_row)

        # Scroll Area
        self._history_scroll = QScrollArea()
        self._history_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._history_scroll.setWidgetResizable(True)
        self._history_scroll.viewport().setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self._history_container = QWidget()
        self._history_layout = QVBoxLayout(self._history_container)
        self._history_layout.setContentsMargins(0, 0, 0, 0)
        self._history_layout.setSpacing(4)

        # Header
        self._history_header = self._make_history_header_row()
        self._history_layout.addWidget(self._history_header)

        self._history_layout.addStretch()
        self._history_scroll.setWidget(self._history_container)
        list_layout.addWidget(self._history_scroll, 1)

        self._history_empty = QLabel("No manual script runs yet.")
        self._history_empty.setObjectName("emptyStateLabel")
        self._history_empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        list_layout.addWidget(self._history_empty, 1)

        list_widget.setMinimumHeight(120)
        splitter.addWidget(list_widget)

        # Log Viewer Panel
        self._history_log_viewer_panel = QFrame()
        self._history_log_viewer_panel.setObjectName("scriptViewer")
        self._history_log_viewer_panel.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        log_layout = QVBoxLayout(self._history_log_viewer_panel)
        log_layout.setContentsMargins(12, 8, 12, 12)
        log_layout.setSpacing(8)

        log_header = QHBoxLayout()
        log_title = QLabel("Run log")
        log_title.setObjectName("detailSectionHeader")
        log_header.addWidget(log_title)
        log_header.addStretch()
        close_btn = QPushButton("×")
        close_btn.setObjectName("historyLogCloseBtn")
        close_btn.setFixedSize(24, 22)
        close_font = QFont()
        close_font.setPointSize(10)
        close_font.setWeight(QFont.Weight.DemiBold)
        close_btn.setFont(close_font)
        close_btn.setToolTip("Close log viewer")
        close_btn.clicked.connect(self._on_close_log_viewer)
        log_header.addWidget(close_btn)
        log_layout.addLayout(log_header)

        self._history_log_edit = QPlainTextEdit()
        self._history_log_edit.setReadOnly(True)
        self._history_log_edit.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        log_font = QFont("Consolas")
        log_font.setStyleHint(QFont.StyleHint.Monospace)
        log_font.setPointSize(9)
        self._history_log_edit.setFont(log_font)
        self._history_log_edit.setPlaceholderText("Select a history entry to view its log.")
        self._history_log_highlighter = ShellHighlighter(
            self._history_log_edit.document(), self._main._palette
        )
        log_layout.addWidget(self._history_log_edit, 1)

        splitter.addWidget(self._history_log_viewer_panel)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([300, 320])

        layout.addWidget(splitter)
        self._history_log_viewer_panel.setVisible(False)

    def _relative_script_path(self, script_path: str) -> str:
        if not script_path:
            return "—"
        if self._main.project_path:
            try:
                return os.path.relpath(script_path, self._main.project_path).replace("\\", "/")
            except ValueError:
                pass
        return os.path.basename(script_path)

    def update_log_highlighter_palette(self, palette: dict) -> None:
        if hasattr(self, "_history_log_highlighter"):
            self._history_log_highlighter.update_palette(palette)

    def _on_close_log_viewer(self):
        self._history_log_viewer_panel.setVisible(False)

    def _on_history_row_clicked(self, run):
        self._selected_history_run_id = run.get("id")
        for rid, row_w in self._history_row_map.items():
            row_w.setProperty("selected", rid == self._selected_history_run_id)
            row_w.style().unpolish(row_w)
            row_w.style().polish(row_w)
        log_text = load_log(run["id"]) if run.get("id") else ""
        self._history_log_edit.setPlaceholderText("")
        self._history_log_edit.setPlainText(log_text if log_text else "No log recorded.")
        self._history_log_viewer_panel.setVisible(True)

    def refresh_history(self):
        self._history_row_map.clear()
        while self._history_layout.count() > 2:
            item = self._history_layout.takeAt(1)
            w = item.widget()
            if w:
                w.hide()
                w.setParent(None)

        runs = load_history()
        # Filter for manual runs only
        runs = [r for r in runs if not r.get("schedule_id")]

        distinct_script_rel = []
        if self._main.project_path:
            seen = set()
            for r in runs:
                path = r.get("script_path", "")
                if not path or path in seen:
                    continue
                seen.add(path)
                try:
                    rel = os.path.relpath(path, self._main.project_path).replace("\\", "/")
                    distinct_script_rel.append(rel)
                except ValueError:
                    distinct_script_rel.append(os.path.basename(path))
        distinct_script_rel.sort(key=str.lower)

        prev_script = self._history_script_combo.currentText()
        self._history_script_combo.blockSignals(True)
        self._history_script_combo.clear()
        self._history_script_combo.addItem("All scripts")
        self._history_script_combo.addItems(distinct_script_rel)
        if prev_script and prev_script in ["All scripts"] + distinct_script_rel:
            self._history_script_combo.setCurrentText(prev_script)
        self._history_script_combo.blockSignals(False)

        filter_status = self._history_filter.currentText()
        if filter_status != "All":
            runs = [r for r in runs if r.get("status") == filter_status]

        script_combo_text = self._history_script_combo.currentText().strip()
        if script_combo_text and script_combo_text != "All scripts":
            def _run_script_rel(run):
                p = run.get("script_path", "")
                if not p or not self._main.project_path:
                    return os.path.basename(p)
                try:
                    return os.path.relpath(p, self._main.project_path).replace("\\", "/")
                except ValueError:
                    return os.path.basename(p)
            runs = [r for r in runs if _run_script_rel(r) == script_combo_text]

        runs.sort(key=lambda r: r.get("triggered_at", ""), reverse=True)

        has_rows = bool(runs)
        self._history_scroll.setVisible(has_rows)
        self._history_empty.setVisible(not has_rows)

        for run in runs:
            row_w = self._make_history_row(run)
            self._history_layout.insertWidget(self._history_layout.count() - 1, row_w)

    HISTORY_COLUMN_STRETCH = (3, 2, 1)

    def _make_history_grid_row(self, contents_margins: tuple[int, int, int, int] = (0, 0, 0, 0)):
        row = QWidget()
        grid = QGridLayout(row)
        grid.setContentsMargins(*contents_margins)
        grid.setHorizontalSpacing(8)
        grid.setVerticalSpacing(2)
        for col, stretch in enumerate(self.HISTORY_COLUMN_STRETCH):
            grid.setColumnStretch(col, stretch)
        return row, grid

    def _make_history_header_row(self):
        row, grid = self._make_history_grid_row((12, 4, 12, 4))
        for col, text in enumerate(["Script", "Time", "Status"]):
            lbl = QLabel(text)
            lbl.setObjectName("scheduleHeaderLabel")
            grid.addWidget(lbl, 0, col)
        return row

    def _make_history_row(self, run):
        row, grid = self._make_history_grid_row((12, 6, 12, 6))
        row.setObjectName("scheduleRow")

        script_path = run.get("script_path", "")
        rel = self._relative_script_path(script_path)
        script_lbl = QLabel(rel)
        script_lbl.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        grid.addWidget(script_lbl, 0, 0)

        def _fmt_ts(s):
            if not s:
                return None
            try:
                dt = datetime.fromisoformat(s)
                return dt.strftime("%Y-%m-%d %H:%M:%S")
            except (ValueError, TypeError):
                return s[:19] if s else None

        started_str = _fmt_ts(run.get("started_at"))
        finished_str = _fmt_ts(run.get("finished_at"))
        time_parts = []
        if started_str:
            time_parts.append(f"Started: {started_str}")
        if finished_str:
            time_parts.append(f"Finished: {finished_str}")
        time_column_text = "\n".join(time_parts) if time_parts else "—"
        time_lbl = QLabel(time_column_text)
        time_lbl.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        grid.addWidget(time_lbl, 0, 1)

        status = run.get("status", "—")
        status_display = STATUS_DISPLAY.get(status, status.upper())
        status_lbl = QLabel(status_display)
        status_lbl.setObjectName("historyStatusLabel")
        status_lbl.setProperty("status_type", status)
        status_lbl.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        grid.addWidget(status_lbl, 0, 2)

        sub_text = None
        if status == "failed":
            sub_text = run.get("error_message", "Unknown error")

        sub_lbl = None
        if sub_text:
            sub_lbl = QLabel(sub_text)
            sub_lbl.setObjectName("historySubLabel")
            grid.addWidget(sub_lbl, 1, 0, 1, 3)

        run_id = run.get("id")
        row.setProperty("selected", run_id == self._selected_history_run_id)
        row.setCursor(Qt.CursorShape.PointingHandCursor)
        self._history_row_map[run_id] = row

        def _on_click(event, r=dict(run)):
            self._on_history_row_clicked(r)
        row.mousePressEvent = _on_click
        for w in (script_lbl, time_lbl, status_lbl):
            w.mousePressEvent = _on_click
        if sub_lbl is not None:
            sub_lbl.mousePressEvent = _on_click

        return row
