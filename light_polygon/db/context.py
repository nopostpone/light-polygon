from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from typing import Generator

from light_polygon.db.connection import get_connection, init_db


@contextmanager
def db_transaction() -> Generator[sqlite3.Connection, None, None]:
    """Context manager for database transactions.

    Automatically initializes the DB schema on first use, commits on success,
    and rolls back on exception.
    """
    init_db()
    conn = get_connection()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
