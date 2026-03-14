"""
Persistence for schedules (schedules.json) and run history (scheduler_history.json).
Files live in the same directory as config.json.
"""
import json
import os

from config import get_config_path
from scheduler_data import HISTORY_RETENTION

SCHEDULES_FILENAME = "schedules.json"
HISTORY_FILENAME = "scheduler_history.json"


def _get_storage_dir() -> str:
    return os.path.dirname(get_config_path())


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
