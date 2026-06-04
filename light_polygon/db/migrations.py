from __future__ import annotations

import sqlite3
from pathlib import Path

MIGRATIONS_DIR = Path(__file__).parent / "migrations"


def run_migrations(conn: sqlite3.Connection) -> None:
    """Apply pending schema migrations in order.

    Migration files live in ``db/migrations/`` and are named
    ``NNN_description.sql`` (e.g. ``001_add_indices.sql``).
    The numeric prefix determines execution order.
    """
    if not MIGRATIONS_DIR.exists():
        return

    # Ensure version tracking table exists
    conn.execute(
        "CREATE TABLE IF NOT EXISTS schema_version "
        "(version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL DEFAULT (datetime('now')))"
    )

    row = conn.execute("SELECT MAX(version) FROM schema_version").fetchone()
    current_version = row[0] or 0

    migration_files = sorted(MIGRATIONS_DIR.glob("*.sql"))
    for path in migration_files:
        try:
            version = int(path.stem.split("_")[0])
        except ValueError:
            continue
        if version > current_version:
            sql = path.read_text(encoding="utf-8")
            conn.executescript(sql)
            conn.execute(
                "INSERT INTO schema_version (version) VALUES (?)",
                (version,),
            )
            conn.commit()
