from __future__ import annotations

import json
from pathlib import Path

from light_polygon.config import get_config


def _session_file() -> Path:
    return get_config().data_dir / "session.json"


def save_session(username: str) -> None:
    path = _session_file()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"username": username}), encoding="utf-8")


def load_session() -> str | None:
    path = _session_file()
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data.get("username")
    except (json.JSONDecodeError, KeyError):
        return None


def clear_session() -> None:
    path = _session_file()
    if path.exists():
        path.unlink()
