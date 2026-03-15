"""
Scheduler UI — SchedulerContentWidget (schedules + history views) and ScheduleDialog.
Separated from gui.py to keep modules focused.
"""
import os
from datetime import datetime

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QFont, QIcon
from PySide6.QtWidgets import (
    QStyle,
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QRadioButton,
    QScrollArea,
    QSizePolicy,
    QSplitter,
    QSpinBox,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from scheduler_data import (
    DAY_NAMES,
    MAX_INTERVAL_HOURS,
    MAX_NAME_LENGTH,
    create_schedule,
    now_iso,
    validate_schedule,
)
from scheduler_engine import format_next_run_countdown, format_rule_display
from scheduler_storage import load_history, load_log, load_schedules, save_schedules
import utils

HISTORY_FILTER_OPTIONS = ("All", "started", "killed", "exited", "failed")
STATUS_DISPLAY = {
    "started": "STARTED",
    "killed": "KILLED",
    "exited": "EXITED",
    "failed": "FAILED",
}


class SchedulerContentWidget(QWidget):
    """Main scheduler content area with Schedules and History sub-views."""

    def __init__(self, main_window, parent=None):
        super().__init__(parent)
        self.setObjectName("schedulerContent")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self._main = main_window
        self._schedule_row_map: dict[str, "QLabel"] = {}
        self._schedule_status_map: dict[str, "QLabel"] = {}
        self._countdown_timer = QTimer(self)
        self._countdown_timer.timeout.connect(self._countdown_tick)
        self._countdown_timer.start(1000)
        self._build_ui()

    @property
    def _palette(self):
        return self._main._palette

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 16, 24, 16)
        layout.setSpacing(12)

        title = QLabel("Scheduler")
        title.setObjectName("detailTitle")
        layout.addWidget(title)

        tabs_row = QHBoxLayout()
        tabs_row.setSpacing(4)
        self._schedules_btn = QPushButton("Schedules")
        self._schedules_btn.setObjectName("schedulerTabBtn")
        self._schedules_btn.clicked.connect(lambda: self._switch_tab(0))
        self._history_btn = QPushButton("History")
        self._history_btn.setObjectName("schedulerTabBtn")
        self._history_btn.clicked.connect(lambda: self._switch_tab(1))
        tabs_row.addWidget(self._schedules_btn)
        tabs_row.addWidget(self._history_btn)
        tabs_row.addStretch()
        layout.addLayout(tabs_row)

        self._tab_stack = QStackedWidget()
        self._schedules_view = self._build_schedules_view()
        self._history_view = self._build_history_view()
        self._tab_stack.addWidget(self._schedules_view)
        self._tab_stack.addWidget(self._history_view)
        layout.addWidget(self._tab_stack, 1)

        self._switch_tab(0)

    def _switch_tab(self, index):
        self._tab_stack.setCurrentIndex(index)
        self._schedules_btn.setProperty("active", "true" if index == 0 else "false")
        self._history_btn.setProperty("active", "true" if index == 1 else "false")
        for btn in (self._schedules_btn, self._history_btn):
            btn.style().unpolish(btn)
            btn.style().polish(btn)
        if index == 0:
            self.refresh_schedules()
        else:
            self.refresh_history()

    # ------------------------------------------------------------------
    # Schedules view
    # ------------------------------------------------------------------

    def _build_schedules_view(self):
        view = QWidget()
        layout = QVBoxLayout(view)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        new_btn = QPushButton("New Schedule")
        new_btn.setObjectName("newScheduleBtn")
        new_btn.clicked.connect(self._on_new_schedule)
        top_row = QHBoxLayout()
        top_row.addWidget(new_btn)
        top_row.addStretch()
        layout.addLayout(top_row)

        self._schedules_scroll = QScrollArea()
        self._schedules_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._schedules_scroll.setWidgetResizable(True)
        self._schedules_scroll.viewport().setAttribute(Qt.WA_StyledBackground, True)
        self._schedules_container = QWidget()
        self._schedules_layout = QVBoxLayout(self._schedules_container)
        self._schedules_layout.setContentsMargins(0, 0, 0, 0)
        self._schedules_layout.setSpacing(4)

        self._schedules_header = self._make_schedules_header_row()
        self._schedules_layout.addWidget(self._schedules_header)

        self._schedules_layout.addStretch()
        self._schedules_scroll.setWidget(self._schedules_container)
        layout.addWidget(self._schedules_scroll, 1)

        self._schedules_empty = QLabel("No schedules. Click New Schedule to create one.")
        self._schedules_empty.setObjectName("emptyStateLabel")
        self._schedules_empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._schedules_empty, 1)

        return view

    def _build_history_view(self):
        view = QWidget()
        splitter = QSplitter(Qt.Orientation.Vertical)

        self._selected_history_run_id = None
        self._history_row_map = {}

        list_widget = QWidget()
        list_layout = QVBoxLayout(list_widget)
        list_layout.setContentsMargins(0, 0, 0, 0)
        list_layout.setSpacing(8)

        filter_row = QHBoxLayout()
        filter_row.addWidget(QLabel("Filter:"))
        self._history_filter = QComboBox()
        self._history_filter.addItems(HISTORY_FILTER_OPTIONS)
        self._history_filter.currentTextChanged.connect(lambda _: self.refresh_history())
        filter_row.addWidget(self._history_filter)
        filter_row.addStretch()
        list_layout.addLayout(filter_row)

        self._history_scroll = QScrollArea()
        self._history_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._history_scroll.setWidgetResizable(True)
        self._history_scroll.viewport().setAttribute(Qt.WA_StyledBackground, True)
        self._history_container = QWidget()
        self._history_layout = QVBoxLayout(self._history_container)
        self._history_layout.setContentsMargins(0, 0, 0, 0)
        self._history_layout.setSpacing(4)

        self._history_header = self._make_history_header_row()
        self._history_layout.addWidget(self._history_header)

        self._history_layout.addStretch()
        self._history_scroll.setWidget(self._history_container)
        list_layout.addWidget(self._history_scroll, 1)

        self._history_empty = QLabel("No history entries.")
        self._history_empty.setObjectName("emptyStateLabel")
        self._history_empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        list_layout.addWidget(self._history_empty, 1)

        list_widget.setMinimumHeight(120)
        splitter.addWidget(list_widget)

        self._history_log_viewer_panel = QFrame()
        self._history_log_viewer_panel.setObjectName("scriptViewer")
        self._history_log_viewer_panel.setAttribute(Qt.WA_StyledBackground, True)
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
        log_layout.addWidget(self._history_log_edit, 1)

        splitter.addWidget(self._history_log_viewer_panel)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([300, 320])

        main_layout = QVBoxLayout(view)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.addWidget(splitter)
        return view

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

    # ------------------------------------------------------------------
    # Refresh
    # ------------------------------------------------------------------

    def refresh_schedules(self):
        self._schedule_row_map.clear()
        self._schedule_status_map.clear()
        while self._schedules_layout.count() > 2:
            item = self._schedules_layout.takeAt(1)
            w = item.widget()
            if w:
                w.hide()
                w.setParent(None)

        schedules = load_schedules()
        has_rows = bool(schedules)
        self._schedules_scroll.setVisible(has_rows)
        self._schedules_empty.setVisible(not has_rows)

        for schedule in schedules:
            row_w = self._make_schedule_row(schedule)
            self._schedules_layout.insertWidget(self._schedules_layout.count() - 1, row_w)

    def refresh_history(self):
        self._history_row_map.clear()
        while self._history_layout.count() > 2:
            item = self._history_layout.takeAt(1)
            w = item.widget()
            if w:
                w.hide()
                w.setParent(None)

        runs = load_history()
        filter_status = self._history_filter.currentText()
        if filter_status != "All":
            runs = [r for r in runs if r.get("status") == filter_status]

        runs.sort(key=lambda r: r.get("triggered_at", ""), reverse=True)

        has_rows = bool(runs)
        self._history_scroll.setVisible(has_rows)
        self._history_empty.setVisible(not has_rows)

        for run in runs:
            row_w = self._make_history_row(run)
            self._history_layout.insertWidget(self._history_layout.count() - 1, row_w)

    def refresh_current_view(self):
        if self._tab_stack.currentIndex() == 0:
            self.refresh_schedules()
        else:
            self.refresh_history()

    def _countdown_tick(self):
        if not self.isVisible() or self._tab_stack.currentIndex() != 0:
            return
        schedules = load_schedules()
        for schedule in schedules:
            sid = schedule.get("id")
            next_lbl = self._schedule_row_map.get(sid)
            if next_lbl is not None:
                next_lbl.setText(format_next_run_countdown(schedule))
            status_lbl = self._schedule_status_map.get(sid)
            if status_lbl is not None:
                script_path = schedule.get("script_path", "")
                script_row = self._main._get_row(script_path) if script_path else None
                running = self._main._is_row_running(script_row) if script_row is not None else False
                status_lbl.setText("Running" if running else "—")

    # ------------------------------------------------------------------
    # Schedule rows (shared column widths via fixed-size button wrappers)
    # ------------------------------------------------------------------

    SCHEDULE_COLUMN_STRETCH = (3, 3, 2, 2, 1, 0, 0, 0)
    SCHEDULE_COL_MIN_WIDTHS = (0, 0, 0, 0, 0, 56, 24, 52)
    ENABLED_COL_WIDTH = 64
    SPACER_WIDTH = 24
    ACTION_COL_WIDTH = 32

    def _make_schedule_grid_row(self, contents_margins: tuple[int, int, int, int]):
        row = QWidget()
        grid = QGridLayout(row)
        grid.setContentsMargins(*contents_margins)
        grid.setHorizontalSpacing(8)
        for col, stretch in enumerate(self.SCHEDULE_COLUMN_STRETCH):
            grid.setColumnStretch(col, stretch)
        for col, min_w in enumerate(self.SCHEDULE_COL_MIN_WIDTHS):
            if min_w > 0:
                grid.setColumnMinimumWidth(col, min_w)
        return row, grid

    def _make_schedules_header_row(self):
        row, grid = self._make_schedule_grid_row((12, 4, 12, 4))
        header_cols = [
            ("Name", 0, False),
            ("Script", 1, False),
            ("Rule", 2, False),
            ("Next Run", 3, False),
            ("Status", 4, False),
            ("Enabled", 5, self.ENABLED_COL_WIDTH),
            ("", 6, self.SPACER_WIDTH),
            ("Action", 7, self.ACTION_COL_WIDTH),
        ]
        for text, col, cell_width in header_cols:
            lbl = QLabel(text)
            lbl.setObjectName("scheduleHeaderLabel")
            if cell_width:
                cell = QWidget()
                cell.setFixedWidth(cell_width)
                cell_layout = QHBoxLayout(cell)
                cell_layout.setContentsMargins(0, 0, 0, 0)
                cell_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
                cell_layout.addWidget(lbl)
                grid.addWidget(cell, 0, col)
            else:
                grid.addWidget(lbl, 0, col)
        return row

    def _make_schedule_row(self, schedule):
        row, grid = self._make_schedule_grid_row((12, 6, 12, 6))
        row.setObjectName("scheduleRow")
        row.setCursor(Qt.CursorShape.PointingHandCursor)

        name_lbl = QLabel(schedule["name"])
        name_lbl.setObjectName("scheduleNameLabel")
        grid.addWidget(name_lbl, 0, 0)

        script_path = schedule.get("script_path", "")
        rel = self._relative_script_path(script_path)
        script_lbl = QLabel(rel)
        grid.addWidget(script_lbl, 0, 1)

        rule_lbl = QLabel(format_rule_display(schedule))
        grid.addWidget(rule_lbl, 0, 2)

        next_run_text = format_next_run_countdown(schedule)
        next_lbl = QLabel(next_run_text)
        self._schedule_row_map[schedule["id"]] = next_lbl
        grid.addWidget(next_lbl, 0, 3)

        script_path = schedule.get("script_path", "")
        script_row = self._main._get_row(script_path) if script_path else None
        running = self._main._is_row_running(script_row) if script_row is not None else False
        status_lbl = QLabel("Running" if running else "—")
        self._schedule_status_map[schedule["id"]] = status_lbl
        grid.addWidget(status_lbl, 0, 4)

        enabled = schedule.get("enabled", False)
        toggle = QPushButton("ON" if enabled else "OFF")
        toggle.setObjectName("enableToggleBtn")
        toggle.setProperty("enabled_state", "true" if enabled else "false")
        toggle.setFixedSize(40, 22)
        toggle.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        toggle.clicked.connect(lambda _=False, sid=schedule["id"]: self._on_toggle_enabled(sid))
        toggle_cell = QWidget()
        toggle_cell.setFixedWidth(self.ENABLED_COL_WIDTH)
        toggle_layout = QHBoxLayout(toggle_cell)
        toggle_layout.setContentsMargins(0, 0, 0, 0)
        toggle_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        toggle_layout.addWidget(toggle)
        grid.addWidget(toggle_cell, 0, 5)

        spacer = QWidget()
        spacer.setFixedWidth(self.SPACER_WIDTH)
        grid.addWidget(spacer, 0, 6)

        delete_btn = QPushButton()
        delete_btn.setObjectName("scheduleDeleteBtn")
        trash_path = utils.get_resource_path("assets/trash.svg")
        delete_btn.setIcon(
            QIcon(trash_path) if os.path.isfile(trash_path) else self.style().standardIcon(QStyle.StandardPixmap.SP_TrashIcon)
        )
        delete_btn.setFixedSize(28, 22)
        delete_btn.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        delete_btn.setToolTip("Delete schedule")
        delete_btn.clicked.connect(lambda _=False, s=dict(schedule): self._on_delete_schedule(s))
        delete_cell = QWidget()
        delete_cell.setFixedWidth(self.ACTION_COL_WIDTH)
        delete_layout = QHBoxLayout(delete_cell)
        delete_layout.setContentsMargins(0, 0, 0, 0)
        delete_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        delete_layout.addWidget(delete_btn)
        grid.addWidget(delete_cell, 0, 7)

        def _on_row_click(event, s=dict(schedule)):
            self._on_edit_schedule(s)
        row.mousePressEvent = _on_row_click
        for w in (name_lbl, script_lbl, rule_lbl, next_lbl, status_lbl):
            w.mousePressEvent = _on_row_click
        return row

    HISTORY_COLUMN_STRETCH = (2, 2, 2, 1)

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
        for col, text in enumerate(["Schedule", "Script", "Time", "Status"]):
            lbl = QLabel(text)
            lbl.setObjectName("scheduleHeaderLabel")
            grid.addWidget(lbl, 0, col)
        return row

    def _make_history_row(self, run):
        row, grid = self._make_history_grid_row((12, 6, 12, 6))
        row.setObjectName("scheduleRow")

        name_lbl = QLabel(run.get("schedule_name", "—"))
        grid.addWidget(name_lbl, 0, 0)

        script_path = run.get("script_path", "")
        rel = self._relative_script_path(script_path)
        script_lbl = QLabel(rel)
        grid.addWidget(script_lbl, 0, 1)

        triggered = run.get("triggered_at", "")
        try:
            dt = datetime.fromisoformat(triggered)
            time_str = dt.strftime("%Y-%m-%d %H:%M")
        except (ValueError, TypeError):
            time_str = triggered[:16] if triggered else "—"
        time_lbl = QLabel(time_str)
        grid.addWidget(time_lbl, 0, 2)

        status = run.get("status", "—")
        status_display = STATUS_DISPLAY.get(status, status.upper())
        status_lbl = QLabel(status_display)
        status_lbl.setObjectName("historyStatusLabel")
        status_lbl.setProperty("status_type", status)
        grid.addWidget(status_lbl, 0, 3)

        def _fmt_started(s):
            if not s:
                return None
            try:
                dt = datetime.fromisoformat(s)
                return dt.strftime("%Y-%m-%d %H:%M:%S")
            except (ValueError, TypeError):
                return s[:19] if s else None

        sub_text = None
        started_str = _fmt_started(run.get("started_at"))
        if status == "failed":
            sub_text = run.get("error_message", "Unknown error")
            if started_str:
                sub_text = f"Started: {started_str}\n{sub_text}"
        elif status == "exited":
            parts = []
            if started_str:
                parts.append(f"Started: {started_str}")
            finished = run.get("finished_at", "")
            if finished:
                try:
                    dt = datetime.fromisoformat(finished)
                    parts.append(f"Finished: {dt.strftime('%Y-%m-%d %H:%M:%S')}")
                except (ValueError, TypeError):
                    parts.append(f"Finished: {finished}")
            sub_text = "\n".join(parts) if parts else None
        elif status == "killed":
            sub_text = "Previous instance terminated by scheduler"
            if started_str:
                sub_text = f"Started: {started_str}\n{sub_text}"
        elif status == "started" and started_str:
            sub_text = f"Started: {started_str}"

        sub_lbl = None
        if sub_text:
            sub_lbl = QLabel(sub_text)
            sub_lbl.setObjectName("historySubLabel")
            grid.addWidget(sub_lbl, 1, 0, 1, 4)

        run_id = run.get("id")
        row.setProperty("selected", run_id == self._selected_history_run_id)
        row.setCursor(Qt.CursorShape.PointingHandCursor)
        self._history_row_map[run_id] = row

        def _on_click(event, r=dict(run)):
            self._on_history_row_clicked(r)
        row.mousePressEvent = _on_click
        for w in (name_lbl, script_lbl, time_lbl, status_lbl):
            w.mousePressEvent = _on_click
        if sub_lbl is not None:
            sub_lbl.mousePressEvent = _on_click

        return row

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def _on_new_schedule(self):
        scripts = self._main.scripts if self._main.scripts else []
        dialog = ScheduleDialog(scripts, self._main.project_path, parent=self._main)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            data = dialog.get_schedule_data()
            schedule = create_schedule(
                name=data["name"],
                script_path=data["script_path"],
                rule_type=data["rule_type"],
                rule=data["rule"],
                enabled=data["enabled"],
            )
            schedules = load_schedules()
            schedules.append(schedule)
            save_schedules(schedules)
            self.refresh_schedules()

    def _on_edit_schedule(self, schedule):
        scripts = self._main.scripts if self._main.scripts else []
        dialog = ScheduleDialog(
            scripts, self._main.project_path, schedule=schedule, parent=self._main,
        )
        if dialog.exec() == QDialog.DialogCode.Accepted:
            data = dialog.get_schedule_data()
            schedules = load_schedules()
            for s in schedules:
                if s["id"] == schedule["id"]:
                    old_rule_type = s.get("rule_type")
                    old_rule = s.get("rule")
                    s["name"] = data["name"]
                    s["script_path"] = data["script_path"]
                    s["rule_type"] = data["rule_type"]
                    s["rule"] = data["rule"]
                    s["enabled"] = data["enabled"]
                    rule_changed = old_rule_type != data["rule_type"] or old_rule != data["rule"]
                    if data["rule_type"] == "interval" and rule_changed:
                        s["interval_base_at"] = now_iso()
                    if data["rule_type"] != "interval":
                        s.pop("interval_base_at", None)
                    if rule_changed:
                        s.pop("last_triggered_at", None)
                    break
            save_schedules(schedules)
            self.refresh_schedules()

    def _on_toggle_enabled(self, schedule_id):
        schedules = load_schedules()
        for s in schedules:
            if s["id"] == schedule_id:
                was_enabled = s.get("enabled", False)
                s["enabled"] = not was_enabled
                if s["enabled"] and s.get("rule_type") == "interval":
                    s["interval_base_at"] = now_iso()
                break
        save_schedules(schedules)
        self.refresh_schedules()

    def _on_delete_schedule(self, schedule):
        reply = QMessageBox.question(
            self._main,
            "Delete Schedule",
            f"Delete schedule '{schedule['name']}'?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            schedules = load_schedules()
            schedules = [s for s in schedules if s["id"] != schedule["id"]]
            save_schedules(schedules)
            self.refresh_schedules()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _relative_script_path(self, script_path: str) -> str:
        if not script_path:
            return "—"
        if self._main.project_path:
            try:
                return os.path.relpath(script_path, self._main.project_path).replace("\\", "/")
            except ValueError:
                pass
        return os.path.basename(script_path)


class ScheduleDialog(QDialog):
    """Dialog for creating or editing a schedule."""

    def __init__(self, scripts, project_path, schedule=None, parent=None):
        super().__init__(parent)
        self.setObjectName("scheduleDialog")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self._scripts = scripts
        self._project_path = project_path
        self._schedule = schedule
        self._is_edit = schedule is not None
        self.setWindowTitle("Edit Schedule" if self._is_edit else "New Schedule")
        self.setMinimumWidth(500)
        self._script_paths: dict[str, str] = {}
        self._build_form()
        if self._is_edit:
            self._populate_from_schedule()

    def _build_form(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(20, 16, 20, 16)

        layout.addWidget(QLabel("Name"))
        self._name_edit = QLineEdit()
        self._name_edit.setMaxLength(MAX_NAME_LENGTH)
        self._name_edit.setPlaceholderText("Schedule name")
        layout.addWidget(self._name_edit)

        layout.addWidget(QLabel("Script"))
        script_row = QHBoxLayout()
        self._script_combo = QComboBox()
        self._script_combo.setEditable(False)
        if self._scripts and self._project_path:
            for s in sorted(self._scripts, key=lambda x: x["path"].lower()):
                try:
                    rel = os.path.relpath(s["path"], self._project_path).replace("\\", "/")
                except ValueError:
                    rel = s["name"]
                self._script_combo.addItem(rel)
                self._script_paths[rel] = s["path"]
        script_row.addWidget(self._script_combo, 1)
        browse_btn = QPushButton("Browse")
        browse_btn.clicked.connect(self._on_browse)
        script_row.addWidget(browse_btn)
        layout.addLayout(script_row)

        layout.addWidget(QLabel("Rule Type"))
        self._time_radio = QRadioButton("Time-based (specific hour:minute)")
        self._interval_radio = QRadioButton("Interval-based (every N minutes/hours)")
        self._rule_type_group = QButtonGroup(self)
        self._rule_type_group.addButton(self._time_radio, 0)
        self._rule_type_group.addButton(self._interval_radio, 1)
        self._time_radio.setChecked(True)
        layout.addWidget(self._time_radio)
        layout.addWidget(self._interval_radio)

        # Time rule section
        self._time_section = QWidget()
        time_layout = QVBoxLayout(self._time_section)
        time_layout.setContentsMargins(0, 4, 0, 4)
        time_layout.setSpacing(8)

        hm_row = QHBoxLayout()
        hm_row.addWidget(QLabel("Hour"))
        self._hour_spin = QSpinBox()
        self._hour_spin.setRange(0, 23)
        self._hour_spin.setValue(9)
        hm_row.addWidget(self._hour_spin)
        hm_row.addSpacing(16)
        hm_row.addWidget(QLabel("Minute"))
        self._minute_spin = QSpinBox()
        self._minute_spin.setRange(0, 59)
        self._minute_spin.setValue(0)
        hm_row.addWidget(self._minute_spin)
        hm_row.addStretch()
        time_layout.addLayout(hm_row)

        time_layout.addWidget(QLabel("Days (optional — leave all unchecked = every day)"))
        days_row = QHBoxLayout()
        self._day_checks: list[QCheckBox] = []
        for name in DAY_NAMES:
            cb = QCheckBox(name)
            self._day_checks.append(cb)
            days_row.addWidget(cb)
        days_row.addStretch()
        time_layout.addLayout(days_row)
        layout.addWidget(self._time_section)

        # Interval rule section
        self._interval_section = QWidget()
        interval_layout = QVBoxLayout(self._interval_section)
        interval_layout.setContentsMargins(0, 4, 0, 4)
        interval_layout.setSpacing(8)

        interval_row = QHBoxLayout()
        interval_row.addWidget(QLabel("Run every"))
        self._interval_value_spin = QSpinBox()
        self._interval_value_spin.setRange(1, 9999)
        self._interval_value_spin.setValue(5)
        interval_row.addWidget(self._interval_value_spin)
        self._interval_unit_combo = QComboBox()
        self._interval_unit_combo.addItems(["minutes", "hours"])
        self._interval_unit_combo.currentTextChanged.connect(self._on_interval_unit_changed)
        interval_row.addWidget(self._interval_unit_combo)
        interval_row.addStretch()
        interval_layout.addLayout(interval_row)
        layout.addWidget(self._interval_section)

        self._time_radio.toggled.connect(self._on_rule_type_changed)
        self._on_rule_type_changed()

        divider = QFrame()
        divider.setFrameShape(QFrame.Shape.HLine)
        divider.setObjectName("divider")
        layout.addWidget(divider)

        self._enabled_check = QCheckBox("Schedule active immediately")
        self._enabled_check.setChecked(True)
        layout.addWidget(self._enabled_check)

        divider2 = QFrame()
        divider2.setFrameShape(QFrame.Shape.HLine)
        divider2.setObjectName("divider")
        layout.addWidget(divider2)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(cancel_btn)
        save_btn = QPushButton("Save Schedule")
        save_btn.setObjectName("runBtn")
        save_btn.clicked.connect(self._on_save)
        btn_row.addWidget(save_btn)
        layout.addLayout(btn_row)

    def _on_rule_type_changed(self):
        is_time = self._time_radio.isChecked()
        self._time_section.setVisible(is_time)
        self._interval_section.setVisible(not is_time)

    def _on_interval_unit_changed(self, unit):
        if unit == "hours":
            self._interval_value_spin.setMaximum(MAX_INTERVAL_HOURS)
            if self._interval_value_spin.value() > MAX_INTERVAL_HOURS:
                self._interval_value_spin.setValue(MAX_INTERVAL_HOURS)
        else:
            self._interval_value_spin.setMaximum(9999)

    def _on_browse(self):
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Select script",
            self._project_path or "",
            "Shell scripts (*.sh);;All files (*.*)",
        )
        if path and os.path.isfile(path):
            if self._project_path:
                try:
                    rel = os.path.relpath(path, self._project_path).replace("\\", "/")
                except ValueError:
                    rel = os.path.basename(path)
            else:
                rel = os.path.basename(path)
            idx = self._script_combo.findText(rel)
            if idx < 0:
                self._script_combo.addItem(rel)
                self._script_paths[rel] = path
                idx = self._script_combo.count() - 1
            self._script_combo.setCurrentIndex(idx)

    def _populate_from_schedule(self):
        s = self._schedule
        self._name_edit.setText(s.get("name", ""))

        script_path = s.get("script_path", "")
        if script_path:
            if self._project_path:
                try:
                    rel = os.path.relpath(script_path, self._project_path).replace("\\", "/")
                except ValueError:
                    rel = os.path.basename(script_path)
            else:
                rel = os.path.basename(script_path)
            idx = self._script_combo.findText(rel)
            if idx < 0:
                self._script_combo.addItem(rel)
                self._script_paths[rel] = script_path
                idx = self._script_combo.count() - 1
            self._script_combo.setCurrentIndex(idx)

        rule_type = s.get("rule_type", "time")
        if rule_type == "interval":
            self._interval_radio.setChecked(True)
        else:
            self._time_radio.setChecked(True)

        rule = s.get("rule", {})
        if rule_type == "time":
            self._hour_spin.setValue(rule.get("hour", 0))
            self._minute_spin.setValue(rule.get("minute", 0))
            days = rule.get("days")
            for cb in self._day_checks:
                cb.setChecked(False)
            if days and isinstance(days, list):
                for d in days:
                    if 0 <= d <= 6:
                        self._day_checks[d].setChecked(True)
        elif rule_type == "interval":
            self._interval_value_spin.setValue(rule.get("value", 5))
            unit = rule.get("unit", "minutes")
            idx = self._interval_unit_combo.findText(unit)
            if idx >= 0:
                self._interval_unit_combo.setCurrentIndex(idx)

        self._enabled_check.setChecked(s.get("enabled", True))

    def _on_save(self):
        data = self.get_schedule_data()
        errors = validate_schedule(data)
        if errors:
            QMessageBox.critical(self, "Validation Error", "\n".join(errors))
            return
        if not os.path.isfile(data["script_path"]):
            QMessageBox.critical(
                self, "Validation Error", f"Script file not found: {data['script_path']}",
            )
            return
        self.accept()

    def get_schedule_data(self) -> dict:
        name = self._name_edit.text().strip()

        script_display = self._script_combo.currentText()
        script_path = self._script_paths.get(script_display, "")
        if not script_path and self._project_path:
            candidate = os.path.join(self._project_path, script_display.replace("/", os.sep))
            if os.path.isfile(candidate):
                script_path = candidate

        rule_type = "time" if self._time_radio.isChecked() else "interval"

        if rule_type == "time":
            days = [i for i, cb in enumerate(self._day_checks) if cb.isChecked()]
            rule: dict = {
                "hour": self._hour_spin.value(),
                "minute": self._minute_spin.value(),
            }
            if days:
                rule["days"] = days
        else:
            rule = {
                "value": self._interval_value_spin.value(),
                "unit": self._interval_unit_combo.currentText(),
            }

        return {
            "name": name,
            "script_path": script_path,
            "rule_type": rule_type,
            "rule": rule,
            "enabled": self._enabled_check.isChecked(),
        }
