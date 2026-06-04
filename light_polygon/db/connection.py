from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Generator

from light_polygon.config import get_config

SCHEMA_SQL = Path(__file__).parent / "schema.sql"


def get_db_path() -> Path:
    return get_config().db_path


def get_connection() -> sqlite3.Connection:
    db_path = get_db_path()
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    conn = get_connection()
    try:
        # Fast path: skip if schema_version table already exists
        cur = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='schema_version'"
        )
        if cur.fetchone() is None:
            schema = SCHEMA_SQL.read_text(encoding="utf-8")
            conn.executescript(schema)
            conn.commit()

        from light_polygon.db.migrations import run_migrations

        run_migrations(conn)
    finally:
        conn.close()


def get_db() -> Generator[sqlite3.Connection, None, None]:
    conn = get_connection()
    try:
        yield conn
    finally:
        conn.close()
