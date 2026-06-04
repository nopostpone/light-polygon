from __future__ import annotations

import tempfile
from pathlib import Path

import pytest


def _clear_config_cache() -> None:
    import light_polygon.config as cfg_mod

    cfg_mod._config = None


@pytest.fixture
def temp_data_dir(monkeypatch):
    """Create a temporary data directory for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        data_dir = Path(tmpdir) / "light-polygon"
        data_dir.mkdir()
        monkeypatch.setenv("LIGHT_POLYGON_DATA_DIR", str(data_dir))
        _clear_config_cache()
        yield data_dir
        _clear_config_cache()


@pytest.fixture
def db(temp_data_dir):
    """Initialize database and return connection."""
    from light_polygon.db.connection import init_db, get_connection

    init_db()
    conn = get_connection()
    yield conn
    conn.close()


@pytest.fixture
def logged_in_user(db):
    """Create and log in a test user."""
    from light_polygon.db.models import User
    import bcrypt

    user = User.create(
        db,
        "testuser",
        bcrypt.hashpw(b"testpass", bcrypt.gensalt()).decode(),
        display_name="Test User",
    )
    from light_polygon.auth.session import save_session

    save_session("testuser")
    return user


@pytest.fixture
def sample_problem(db, logged_in_user):
    """Create a sample problem for testing."""
    from light_polygon.problem.manager import ProblemManager

    mgr = ProblemManager(db)
    return mgr.create(
        slug="a-plus-b",
        title="A Plus B",
        owner_id=logged_in_user.id,
        time_limit_ms=1000,
        memory_limit_mb=256,
    )
