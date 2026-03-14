"""
Scheduler engine — next-run calculation, due-schedule detection, trigger validation.
Pure logic module with no UI dependencies.
"""
import math
import os
from datetime import datetime, time as dt_time, timedelta, timezone

TRIGGER_TOLERANCE_SEC = 90


def _parse_iso(iso_str: str) -> datetime:
    return datetime.fromisoformat(iso_str)


def _now_local() -> datetime:
    return datetime.now(timezone.utc).astimezone()


def _next_run_time_based(schedule: dict) -> datetime | None:
    rule = schedule["rule"]
    hour = rule["hour"]
    minute = rule["minute"]
    days = rule.get("days")

    last_triggered = schedule.get("last_triggered_at")
    last_dt = _parse_iso(last_triggered) if last_triggered else None

    now = _now_local()
    today = now.date()

    for offset in range(8):
        candidate_date = today + timedelta(days=offset)
        weekday = candidate_date.weekday()

        if days is not None and len(days) > 0 and weekday not in days:
            continue

        candidate = datetime.combine(
            candidate_date, dt_time(hour, minute), tzinfo=now.tzinfo,
        )

        if last_dt and candidate <= last_dt:
            continue

        return candidate

    return None


def _next_run_interval_based(schedule: dict) -> datetime | None:
    rule = schedule["rule"]
    value = rule["value"]
    unit = rule["unit"]

    base_str = schedule.get("interval_base_at") or schedule.get("created_at")
    if not base_str:
        return None

    base = _parse_iso(base_str)
    now = _now_local()
    delta = timedelta(minutes=value) if unit == "minutes" else timedelta(hours=value)
    delta_seconds = delta.total_seconds()

    if delta_seconds <= 0:
        return None

    elapsed = (now - base).total_seconds()

    if elapsed <= 0:
        return base + delta

    n = max(1, math.floor(elapsed / delta_seconds))
    candidate = base + n * delta
    seconds_past = (now - candidate).total_seconds()

    if seconds_past >= 0 and seconds_past <= TRIGGER_TOLERANCE_SEC:
        return candidate

    if seconds_past > TRIGGER_TOLERANCE_SEC:
        return base + (n + 1) * delta

    return candidate


def get_next_run(schedule: dict) -> datetime | None:
    if not schedule.get("enabled", False):
        return None
    rule_type = schedule.get("rule_type")
    if rule_type == "time":
        return _next_run_time_based(schedule)
    if rule_type == "interval":
        return _next_run_interval_based(schedule)
    return None


def format_next_run(schedule: dict) -> str:
    if not schedule.get("enabled", False):
        return "Disabled"

    next_run = get_next_run(schedule)
    if next_run is None:
        return "—"

    now = _now_local()
    delta = next_run - now
    total_seconds = delta.total_seconds()

    if total_seconds <= 0:
        return "Now"

    total_minutes = int(total_seconds / 60)

    if total_minutes < 1:
        return "< 1 min"
    if total_minutes < 60:
        return f"In {total_minutes} min"
    if total_minutes < 120:
        hours = total_minutes // 60
        mins = total_minutes % 60
        if mins:
            return f"In {hours}h {mins}m"
        return f"In {hours} hour"

    if next_run.date() == now.date():
        return f"Today {next_run.strftime('%H:%M')}"
    if next_run.date() == (now + timedelta(days=1)).date():
        return f"Tomorrow {next_run.strftime('%H:%M')}"
    return next_run.strftime("%a %H:%M")


def format_next_run_countdown(schedule: dict) -> str:
    """Second-precision countdown for live display. Returns 'Disabled' when disabled."""
    if not schedule.get("enabled", False):
        return "Disabled"

    next_run = get_next_run(schedule)
    if next_run is None:
        return "—"

    now = _now_local()
    delta = next_run - now
    total_seconds = int(delta.total_seconds())

    if total_seconds <= 0:
        return "Now"

    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    seconds = total_seconds % 60

    if hours > 0:
        return f"{hours}h {minutes}m {seconds}s"
    if minutes > 0:
        return f"{minutes}m {seconds}s"
    return f"{seconds}s"


def format_rule_display(schedule: dict) -> str:
    """Human-readable rule type and value for table display."""
    rule_type = schedule.get("rule_type")
    rule = schedule.get("rule") or {}
    if rule_type == "interval":
        value = rule.get("value", 0)
        unit = rule.get("unit", "minutes")
        suffix = "min" if unit == "minutes" else "h"
        return f"Interval: {value}{suffix}"
    if rule_type == "time":
        hour = rule.get("hour", 0)
        minute = rule.get("minute", 0)
        return f"Time: {hour:02d}:{minute:02d}"
    return "—"


def get_due_schedules(schedules: list[dict]) -> list[dict]:
    now = _now_local()
    due = []
    for schedule in schedules:
        if not schedule.get("enabled", False):
            continue
        next_run = get_next_run(schedule)
        if next_run is not None and next_run <= now:
            due.append(schedule)
    due.sort(key=lambda s: s.get("id", ""))
    return due


def validate_trigger(script_path: str, project_path: str | None) -> str | None:
    if not project_path:
        return "Project path is not set."
    if not os.path.isfile(script_path):
        return f"Script not found: {script_path}"
    norm_script = os.path.normcase(os.path.normpath(os.path.abspath(script_path)))
    norm_project = os.path.normcase(os.path.normpath(os.path.abspath(project_path)))
    if not norm_script.startswith(norm_project + os.sep):
        return "Script is not under the project path."
    return None
