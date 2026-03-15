"""
Persistence for schedules, run history, and terminal logs.
All live under a "Scheduler" folder next to config.json (same dir as .exe or repo root).
JSON files: Scheduler/schedules.json, Scheduler/scheduler_history.json, Scheduler/history_logs.json.
Temporary .log files: Scheduler/logs/<run_id>.log
"""
import json
import os
import threading

from config import get_config_path
from scheduler_data import HISTORY_RETENTION

SCHEDULES_FILENAME = "schedules.json"
HISTORY_FILENAME = "scheduler_history.json"
HISTORY_LOGS_FILENAME = "history_logs.json"
SCHEDULER_FOLDER = "Scheduler"
LOGS_SUBFOLDER = "logs"

_history_logs_lock = threading.Lock()


def _get_storage_dir() -> str:
    base = os.path.dirname(get_config_path())
    return os.path.join(base, SCHEDULER_FOLDER)


def _get_logs_dir() -> str:
    return os.path.join(_get_storage_dir(), LOGS_SUBFOLDER)


def _storage_path(filename: str) -> str:
    return os.path.join(_get_storage_dir(), filename)


def load_schedules() -> list[dict]:
    path = _storage_path(SCHEDULES_FILENAME)
    if not os.path.isfile(path):
        return []
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict) and isinstance(data.get("schedules"), list):
            return data["schedules"]
    except (json.JSONDecodeError, OSError):
        pass
    return []


def save_schedules(schedules: list[dict]) -> None:
    path = _storage_path(SCHEDULES_FILENAME)
    storage_dir = os.path.dirname(path)
    if storage_dir:
        os.makedirs(storage_dir, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"schedules": schedules}, f, indent=2)


def load_history() -> list[dict]:
    path = _storage_path(HISTORY_FILENAME)
    if not os.path.isfile(path):
        return []
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict) and isinstance(data.get("runs"), list):
            return data["runs"]
    except (json.JSONDecodeError, OSError):
        pass
    return []


def _save_history(runs: list[dict]) -> None:
    path = _storage_path(HISTORY_FILENAME)
    storage_dir = os.path.dirname(path)
    if storage_dir:
        os.makedirs(storage_dir, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"runs": runs}, f, indent=2)


def append_history_entry(entry: dict) -> None:
    runs = load_history()
    runs.append(entry)
    if len(runs) > HISTORY_RETENTION:
        runs = runs[-HISTORY_RETENTION:]
    _save_history(runs)


def update_history_entry(entry_id: str, updates: dict) -> None:
    runs = load_history()
    for run in runs:
        if run.get("id") == entry_id:
            run.update(updates)
            break
    _save_history(runs)


def load_log(run_id: str) -> str:
    with _history_logs_lock:
        path = _storage_path(HISTORY_LOGS_FILENAME)
        if not os.path.isfile(path):
            return ""
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                return data.get(run_id, "") or ""
        except (json.JSONDecodeError, OSError):
            pass
        return ""


def append_log(run_id: str, text: str) -> None:
    with _history_logs_lock:
        path = _storage_path(HISTORY_LOGS_FILENAME)
        data = {}
        if os.path.isfile(path):
            try:
                with open(path, encoding="utf-8") as f:
                    data = json.load(f)
                if not isinstance(data, dict):
                    data = {}
            except (json.JSONDecodeError, OSError):
                data = {}
        data[run_id] = data.get(run_id, "") + text
        storage_dir = os.path.dirname(path)
        if storage_dir:
            os.makedirs(storage_dir, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)


def replace_log(run_id: str, content: str) -> None:
    """Replace the entire log for run_id with content. Used when reading from temp file."""
    with _history_logs_lock:
        path = _storage_path(HISTORY_LOGS_FILENAME)
        data = {}
        if os.path.isfile(path):
            try:
                with open(path, encoding="utf-8") as f:
                    data = json.load(f)
                if not isinstance(data, dict):
                    data = {}
            except (json.JSONDecodeError, OSError):
                data = {}
        data[run_id] = content
        storage_dir = os.path.dirname(path)
        if storage_dir:
            os.makedirs(storage_dir, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)


def get_run_log_file_path(run_id: str) -> str:
    """Path for a temporary log file used during capture. Lives in Scheduler/logs/."""
    logs_dir = _get_logs_dir()
    os.makedirs(logs_dir, exist_ok=True)
    return os.path.join(logs_dir, f"{run_id}.log")
