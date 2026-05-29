from __future__ import annotations

import json
from pathlib import Path

from light_polygon.config import get_config

SESSION_FILE = Path.home() / ".light-polygon" / "session.json"


def save_session(username: str) -> None:
    SESSION_FILE.parent.mkdir(parents=True, exist_ok=True)
    SESSION_FILE.write_text(json.dumps({"username": username}), encoding="utf-8")


def load_session() -> str | None:
    if not SESSION_FILE.exists():
        return None
    try:
        data = json.loads(SESSION_FILE.read_text(encoding="utf-8"))
        return data.get("username")
    except (json.JSONDecodeError, KeyError):
        return None


def clear_session() -> None:
    if SESSION_FILE.exists():
        SESSION_FILE.unlink()
