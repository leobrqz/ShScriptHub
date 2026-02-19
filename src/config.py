import os
import json

CONFIG_FILENAME = "config.json"


def get_config_path() -> str:
    app_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(app_dir, CONFIG_FILENAME)


def _load_all() -> dict:
    path = get_config_path()
    if not os.path.isfile(path):
        return {}
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return {}


def _save_all(data: dict) -> None:
    config_path = get_config_path()
    config_dir = os.path.dirname(config_path)
    if config_dir:
        os.makedirs(config_dir, exist_ok=True)
    with open(config_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def load_project_path() -> str | None:
    raw = _load_all().get("project_path", "").strip()
    return raw if raw else None


def save_project_path(path: str) -> None:
    data = _load_all()
    data["project_path"] = path
    _save_all(data)


def load_terminal_path() -> str | None:
    raw = _load_all().get("terminal_path", "").strip()
    return raw if raw else None


def save_terminal_path(path: str) -> None:
    data = _load_all()
    data["terminal_path"] = path
    _save_all(data)


def load_venv_activate_path() -> str | None:
    raw = _load_all().get("venv_activate_path", "").strip()
    return raw if raw else None


def save_venv_activate_path(path: str) -> None:
    data = _load_all()
    data["venv_activate_path"] = path
    _save_all(data)


def load_script_categories() -> dict:
    """Returns dict script_path -> 'backend'|'frontend'|'none'."""
    raw = _load_all().get("script_categories")
    if isinstance(raw, dict):
        return {k: v for k, v in raw.items() if v in ("backend", "frontend", "none")}
    return {}


def save_script_category(script_path: str, category: str) -> None:
    data = _load_all()
    if "script_categories" not in data or not isinstance(data["script_categories"], dict):
        data["script_categories"] = {}
    data["script_categories"][script_path] = category
    _save_all(data)


def load_favorites() -> set:
    """Returns set of script paths that are favorited."""
    raw = _load_all().get("favorites")
    if isinstance(raw, list):
        return {str(p) for p in raw}
    return set()


def save_favorites(paths: set) -> None:
    data = _load_all()
    data["favorites"] = list(paths)
    _save_all(data)


def toggle_favorite(script_path: str) -> bool:
    """Toggles favorite state for script_path. Returns True if now favorited."""
    fav = load_favorites()
    if script_path in fav:
        fav.discard(script_path)
        save_favorites(fav)
        return False
    fav.add(script_path)
    save_favorites(fav)
    return True
