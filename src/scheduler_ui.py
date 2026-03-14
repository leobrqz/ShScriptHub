"""
Scheduler UI — SchedulerContentWidget (schedules + history views) and ScheduleDialog.
Separated from gui.py to keep modules focused.
"""
import os
from datetime import datetime

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QRadioButton,
    QScrollArea,
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
from scheduler_engine import format_next_run
from scheduler_storage import load_history, load_schedules, save_schedules

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

        new_btn = QPushButton("+ New Schedule")
        new_btn.setObjectName("newScheduleBtn")
        new_btn.clicked.connect(self._on_new_schedule)
        top_row = QHBoxLayout()
        top_row.addWidget(new_btn)
        top_row.addStretch()
        layout.addLayout(top_row)

        header = QWidget()
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(12, 4, 12, 4)
        header_layout.setSpacing(8)
        for text, stretch in [("Name", 3), ("Script", 3), ("Next Run", 2), ("Enabled", 1), ("", 1)]:
            lbl = QLabel(text)
            lbl.setObjectName("scheduleHeaderLabel")
            header_layout.addWidget(lbl, stretch)
        layout.addWidget(header)

        self._schedules_scroll = QScrollArea()
        self._schedules_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._schedules_scroll.setWidgetResizable(True)
        self._schedules_scroll.viewport().setAttribute(Qt.WA_StyledBackground, True)
        self._schedules_container = QWidget()
        self._schedules_layout = QVBoxLayout(self._schedules_container)
        self._schedules_layout.setContentsMargins(0, 0, 0, 0)
        self._schedules_layout.setSpacing(4)
        self._schedules_layout.addStretch()
        self._schedules_scroll.setWidget(self._schedules_container)
        layout.addWidget(self._schedules_scroll, 1)

        self._schedules_empty = QLabel("No schedules. Click + New Schedule to create one.")
        self._schedules_empty.setObjectName("emptyStateLabel")
        self._schedules_empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._schedules_empty, 1)

        return view

    def _build_history_view(self):
        view = QWidget()
        layout = QVBoxLayout(view)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        filter_row = QHBoxLayout()
        filter_row.addWidget(QLabel("Filter:"))
        self._history_filter = QComboBox()
        self._history_filter.addItems(HISTORY_FILTER_OPTIONS)
        self._history_filter.currentTextChanged.connect(lambda _: self.refresh_history())
        filter_row.addWidget(self._history_filter)
        filter_row.addStretch()
        layout.addLayout(filter_row)

        header = QWidget()
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(12, 4, 12, 4)
        header_layout.setSpacing(8)
        for text, stretch in [("Time", 2), ("Schedule", 2), ("Script", 2), ("Status", 1)]:
            lbl = QLabel(text)
            lbl.setObjectName("scheduleHeaderLabel")
            header_layout.addWidget(lbl, stretch)
        layout.addWidget(header)

        self._history_scroll = QScrollArea()
        self._history_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._history_scroll.setWidgetResizable(True)
        self._history_scroll.viewport().setAttribute(Qt.WA_StyledBackground, True)
        self._history_container = QWidget()
        self._history_layout = QVBoxLayout(self._history_container)
        self._history_layout.setContentsMargins(0, 0, 0, 0)
        self._history_layout.setSpacing(4)
        self._history_layout.addStretch()
        self._history_scroll.setWidget(self._history_container)
        layout.addWidget(self._history_scroll, 1)

        self._history_empty = QLabel("No history entries.")
        self._history_empty.setObjectName("emptyStateLabel")
        self._history_empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._history_empty, 1)

        return view

    # ------------------------------------------------------------------
    # Refresh
    # ------------------------------------------------------------------

    def refresh_schedules(self):
        while self._schedules_layout.count():
            item = self._schedules_layout.takeAt(0)
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
            self._schedules_layout.addWidget(row_w)
        self._schedules_layout.addStretch()

    def refresh_history(self):
        while self._history_layout.count():
            item = self._history_layout.takeAt(0)
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
            self._history_layout.addWidget(row_w)
        self._history_layout.addStretch()

    def refresh_current_view(self):
        if self._tab_stack.currentIndex() == 0:
            self.refresh_schedules()
        else:
            self.refresh_history()

    # ------------------------------------------------------------------
    # Schedule rows
    # ------------------------------------------------------------------

    def _make_schedule_row(self, schedule):
        row = QWidget()
        row.setObjectName("scheduleRow")
        row.setCursor(Qt.CursorShape.PointingHandCursor)
        layout = QHBoxLayout(row)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(8)

        name_lbl = QLabel(schedule["name"])
        name_lbl.setObjectName("scheduleNameLabel")
        layout.addWidget(name_lbl, 3)

        script_path = schedule.get("script_path", "")
        rel = self._relative_script_path(script_path)
        script_lbl = QLabel(rel)
        layout.addWidget(script_lbl, 3)

        next_run_text = format_next_run(schedule)
        next_lbl = QLabel(next_run_text)
        layout.addWidget(next_lbl, 2)

        enabled = schedule.get("enabled", False)
        toggle = QPushButton("ON" if enabled else "OFF")
        toggle.setObjectName("enableToggleBtn")
        toggle.setProperty("enabled_state", "true" if enabled else "false")
        toggle.setFixedWidth(44)
        schedule_id = schedule["id"]
        toggle.clicked.connect(lambda _=False, sid=schedule_id: self._on_toggle_enabled(sid))
        layout.addWidget(toggle, 1)

        delete_btn = QPushButton("×")
        delete_btn.setObjectName("scheduleDeleteBtn")
        delete_btn.setFixedWidth(28)
        delete_btn.clicked.connect(lambda _=False, s=dict(schedule): self._on_delete_schedule(s))
        layout.addWidget(delete_btn, 0)

        row.mousePressEvent = lambda event, s=dict(schedule): self._on_edit_schedule(s)
        return row

    def _make_history_row(self, run):
        row = QWidget()
        row.setObjectName("scheduleRow")
        main_layout = QVBoxLayout(row)
        main_layout.setContentsMargins(12, 6, 12, 6)
        main_layout.setSpacing(2)

        top_row = QHBoxLayout()
        top_row.setSpacing(8)

        triggered = run.get("triggered_at", "")
        try:
            dt = datetime.fromisoformat(triggered)
            time_str = dt.strftime("%Y-%m-%d %H:%M")
        except (ValueError, TypeError):
            time_str = triggered[:16] if triggered else "—"
        time_lbl = QLabel(time_str)
        top_row.addWidget(time_lbl, 2)

        name_lbl = QLabel(run.get("schedule_name", "—"))
        top_row.addWidget(name_lbl, 2)

        script_path = run.get("script_path", "")
        rel = self._relative_script_path(script_path)
        script_lbl = QLabel(rel)
        top_row.addWidget(script_lbl, 2)

        status = run.get("status", "—")
        status_display = STATUS_DISPLAY.get(status, status.upper())
        status_lbl = QLabel(status_display)
        status_lbl.setObjectName("historyStatusLabel")
        status_lbl.setProperty("status_type", status)
        top_row.addWidget(status_lbl, 1)

        main_layout.addLayout(top_row)

        sub_text = None
        if status == "failed":
            sub_text = run.get("error_message", "Unknown error")
        elif status == "exited":
            finished = run.get("finished_at", "")
            if finished:
                try:
                    dt = datetime.fromisoformat(finished)
                    sub_text = f"finished: {dt.strftime('%Y-%m-%d %H:%M:%S')}"
                except (ValueError, TypeError):
                    sub_text = f"finished: {finished}"
        elif status == "killed":
            sub_text = "previous instance terminated by scheduler"

        if sub_text:
            sub_lbl = QLabel(sub_text)
            sub_lbl.setObjectName("historySubLabel")
            main_layout.addWidget(sub_lbl)

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
                s["enabled"] = not s.get("enabled", False)
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
