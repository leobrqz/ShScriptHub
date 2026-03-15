"""
Schedule and history entity definitions, validation, and factory functions.
"""
import uuid
from datetime import datetime, timezone

VALID_RULE_TYPES = ("time", "interval")
VALID_STATUSES = ("started", "killed", "exited", "failed")
MAX_NAME_LENGTH = 128
HISTORY_RETENTION = 1000
MAX_INTERVAL_HOURS = 24
DAY_NAMES = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")


def now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat()


def generate_id() -> str:
    return uuid.uuid4().hex


def validate_name(name: str) -> list[str]:
    errors = []
    if not name or not name.strip():
        errors.append("Name is required.")
    elif len(name.strip()) > MAX_NAME_LENGTH:
        errors.append(f"Name must be at most {MAX_NAME_LENGTH} characters.")
    return errors


def validate_time_rule(rule: dict) -> list[str]:
    errors = []
    hour = rule.get("hour")
    minute = rule.get("minute")
    days = rule.get("days")

    if not isinstance(hour, int) or hour < 0 or hour > 23:
        errors.append("Hour must be an integer between 0 and 23.")
    if not isinstance(minute, int) or minute < 0 or minute > 59:
        errors.append("Minute must be an integer between 0 and 59.")
    if days is not None:
        if not isinstance(days, list):
            errors.append("Days must be a list of integers (0–6) or null.")
        else:
            for d in days:
                if not isinstance(d, int) or d < 0 or d > 6:
                    errors.append(f"Invalid day value: {d}. Must be 0 (Mon) through 6 (Sun).")
                    break
    return errors


def validate_interval_rule(rule: dict) -> list[str]:
    errors = []
    minutes = rule.get("minutes", 0)
    hours = rule.get("hours", 0)

    if not isinstance(minutes, int) or minutes < 0:
        errors.append("Interval minutes must be a non-negative integer.")
    if not isinstance(hours, int) or hours < 0:
        errors.append("Interval hours must be a non-negative integer.")
    if isinstance(minutes, int) and isinstance(hours, int):
        if minutes > 9999:
            errors.append("Interval minutes must be at most 9999.")
        if hours > MAX_INTERVAL_HOURS:
            errors.append(f"Interval hours must be at most {MAX_INTERVAL_HOURS}.")
        if minutes == 0 and hours == 0:
            errors.append("Set at least one of minutes or hours to a value greater than 0.")
    return errors


def validate_schedule(data: dict) -> list[str]:
    errors = []
    errors.extend(validate_name(data.get("name", "")))

    script_path = data.get("script_path", "")
    if not script_path or not script_path.strip():
        errors.append("Script path is required.")

    rule_type = data.get("rule_type")
    if rule_type not in VALID_RULE_TYPES:
        errors.append(f"Rule type must be one of: {', '.join(VALID_RULE_TYPES)}.")

    rule = data.get("rule")
    if not isinstance(rule, dict):
        errors.append("Rule must be a valid object.")
    elif rule_type == "time":
        errors.extend(validate_time_rule(rule))
    elif rule_type == "interval":
        errors.extend(validate_interval_rule(rule))

    return errors


def create_schedule(
    name: str,
    script_path: str,
    rule_type: str,
    rule: dict,
    enabled: bool = True,
) -> dict:
    now = now_iso()
    schedule = {
        "id": generate_id(),
        "name": name.strip(),
        "script_path": script_path,
        "rule_type": rule_type,
        "rule": rule,
        "enabled": enabled,
        "created_at": now,
    }
    if rule_type == "interval":
        schedule["interval_base_at"] = now
    return schedule


def create_history_entry(
    schedule_id: str,
    schedule_name: str,
    script_path: str,
    triggered_at: str,
    started_at: str | None,
    status: str,
    error_message: str | None = None,
) -> dict:
    entry = {
        "id": generate_id(),
        "schedule_id": schedule_id,
        "schedule_name": schedule_name,
        "script_path": script_path,
        "triggered_at": triggered_at,
        "started_at": started_at,
        "finished_at": None,
        "status": status,
    }
    if error_message:
        entry["error_message"] = error_message
    return entry
