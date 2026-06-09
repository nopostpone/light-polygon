from __future__ import annotations


from light_polygon.auth.session import clear_session, load_session, save_session


class TestSessionPersist:
    def test_save_and_load_roundtrip(self, temp_data_dir):
        assert load_session() is None
        save_session("alice")
        assert load_session() == "alice"

    def test_overwrite_session(self, temp_data_dir):
        save_session("bob")
        save_session("carol")
        assert load_session() == "carol"

    def test_clear_session(self, temp_data_dir):
        save_session("dave")
        assert load_session() == "dave"
        clear_session()
        assert load_session() is None

    def test_clear_nonexistent_session_no_error(self, temp_data_dir):
        clear_session()
        clear_session()  # double-clear should not raise

    def test_load_nonexistent_returns_none(self, temp_data_dir):
        result = load_session()
        assert result is None

    def test_session_file_location_follows_data_dir(self, temp_data_dir):
        """P0#4: session file should be inside the configured data directory."""
        save_session("eve")
        from light_polygon.config import get_config

        cfg = get_config()
        expected_path = cfg.data_dir / "session.json"
        assert expected_path.exists(), f"Session file should be at {expected_path}"
        assert expected_path.parent == cfg.data_dir

    def test_load_with_corrupted_file(self, temp_data_dir):
        """Gracefully handle malformed session.json."""
        from light_polygon.config import get_config

        cfg = get_config()
        session_path = cfg.data_dir / "session.json"
        session_path.write_text("not valid json", encoding="utf-8")

        result = load_session()
        assert result is None
