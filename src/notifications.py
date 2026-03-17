from __future__ import annotations

import os
from collections import deque
from typing import Any, Deque, Dict, Optional

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QApplication, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

NOTIFICATION_DURATION_MS = 4000

EVENT_START = "start"
EVENT_FINISHED_EXITED = "finished_exited"
EVENT_FINISHED_KILLED = "finished_killed"
EVENT_ERROR = "error"


_queue: Deque[Dict[str, Any]] = deque()
_current_toast: Optional["_NotificationToast"] = None
_current_palette: Optional[dict] = None


class _NotificationToast(QWidget):
    def __init__(self, payload: Dict[str, Any], palette: dict, on_closed: callable):
        super().__init__(None, Qt.Tool | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setObjectName("notificationToast")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self._payload = payload
        self._palette = palette
        self._on_closed = on_closed

        self._build_ui()
        self._apply_palette()
        self._position_on_screen()

        QTimer.singleShot(NOTIFICATION_DURATION_MS, self._handle_timeout)

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(6)

        header_row = QHBoxLayout()
        header_row.setContentsMargins(0, 0, 0, 0)
        header_row.setSpacing(6)

        self._title_label = QLabel(self._build_title())
        self._title_label.setObjectName("notificationTitle")
        header_row.addWidget(self._title_label)
        header_row.addStretch()

        close_btn = QPushButton("×")
        close_btn.setObjectName("notificationCloseBtn")
        close_btn.setFixedSize(18, 18)
        close_btn.clicked.connect(self._handle_close_clicked)
        header_row.addWidget(close_btn)

        layout.addLayout(header_row)

        # Main body
        schedule_name = self._payload.get("schedule_name", "—")
        script_name = self._payload.get("script_name", "—")
        rule_type = self._payload.get("rule_type", "—")
        next_run = self._payload.get("next_run", "—")
        error_message = self._payload.get("error_message")

        body_label = QLabel(
            f"Schedule: {schedule_name}\n"
            f"Script: {script_name}\n"
            f"Rule: {rule_type}\n"
            f"Next run: {next_run}"
        )
        body_label.setObjectName("notificationBody")
        body_label.setWordWrap(True)
        layout.addWidget(body_label)

        if self._payload.get("event_type") == EVENT_ERROR and error_message:
            error_label = QLabel(str(error_message))
            error_label.setObjectName("notificationError")
            error_label.setWordWrap(True)
            layout.addWidget(error_label)

        self.setMinimumWidth(260)
        self.adjustSize()

    def _build_title(self) -> str:
        event_type = self._payload.get("event_type")
        if event_type == EVENT_START:
            return "Scheduled run started"
        if event_type == EVENT_FINISHED_EXITED:
            return "Scheduled run finished"
        if event_type == EVENT_FINISHED_KILLED:
            return "Scheduled run killed"
        if event_type == EVENT_ERROR:
            return "Scheduled run error"
        return "Scheduled run"

    def _apply_palette(self) -> None:
        # The main styling is done via QSS (theme.py) using objectName.
        # This method exists so we can trigger a refresh when palette changes.
        self.style().unpolish(self)
        self.style().polish(self)
        self.update()

    def update_palette(self, palette: dict) -> None:
        self._palette = palette
        self._apply_palette()

    def _position_on_screen(self) -> None:
        app = QApplication.instance()
        if app is None:
            return

        # Determine screen: prefer the active window's screen, fallback to primary.
        screen = None
        active_window = app.activeWindow()
        if active_window and active_window.windowHandle():
            screen = active_window.windowHandle().screen()
        if screen is None:
            screen = QGuiApplication.primaryScreen()
        if screen is None:
            return

        geom = screen.availableGeometry()
        self.adjustSize()
        x = geom.right() - self.width() - 16
        y = geom.bottom() - self.height() - 16
        self.move(x, y)

    def _handle_timeout(self) -> None:
        self._finalize_close()

    def _handle_close_clicked(self) -> None:
        self._finalize_close()

    def _finalize_close(self) -> None:
        try:
            self.close()
        finally:
            if self._on_closed:
                self._on_closed()


def _show_next_from_queue() -> None:
    global _current_toast
    if _current_toast is not None:
        return
    if not _queue:
        return

    payload = _queue.popleft()

    def _on_closed() -> None:
        global _current_toast
        _current_toast = None
        # Show next notification in queue, if any.
        if _queue:
            QTimer.singleShot(50, _show_next_from_queue)

    palette = _current_palette or {}
    _current_toast = _NotificationToast(payload, palette, _on_closed)
    _current_toast.show()


def show_notification(
    event_type: str,
    schedule_name: str,
    script_name: str,
    rule_type: str,
    next_run: str,
    palette: dict,
    error_message: Optional[str] = None,
) -> None:
    """Queue a system notification for scheduler-related events.

    All text is preformatted by gui.py; this module only displays it.
    """
    # Optional no-op on non-Windows platforms (spec allows degrade).
    if os.name != "nt":
        return

    global _current_palette
    _current_palette = palette

    payload = {
        "event_type": event_type,
        "schedule_name": schedule_name,
        "script_name": script_name,
        "rule_type": rule_type,
        "next_run": next_run,
        "error_message": error_message,
    }
    _queue.append(payload)
    if _current_toast is None:
        _show_next_from_queue()


def update_notification_theme(palette: dict) -> None:
    """Update palette for currently visible notification and future ones."""
    global _current_palette
    _current_palette = palette
    if _current_toast is not None:
        _current_toast.update_palette(palette)
