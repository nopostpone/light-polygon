from __future__ import annotations


from light_polygon.db.models import Problem, User


class TestDbTransaction:
    """Tests for db_transaction() commit/rollback behaviour."""

    def test_commit_persists_changes(self, temp_data_dir):
        from light_polygon.db.connection import init_db
        from light_polygon.db.context import db_transaction

        init_db()
        import bcrypt

        with db_transaction() as conn:
            User.create(
                conn,
                "txuser",
                bcrypt.hashpw(b"pass", bcrypt.gensalt()).decode(),
                display_name="TX User",
            )

        # After transaction exits (commits), user should be visible
        from light_polygon.db.connection import get_connection

        conn2 = get_connection()
        try:
            found = User.find_by_username(conn2, "txuser")
            assert found is not None
            assert found.display_name == "TX User"
        finally:
            conn2.close()

    def test_rollback_on_exception(self, temp_data_dir):
        from light_polygon.db.connection import init_db
        from light_polygon.db.context import db_transaction

        init_db()
        import bcrypt

        try:
            with db_transaction() as conn:
                User.create(
                    conn,
                    "rollback_user",
                    bcrypt.hashpw(b"pass", bcrypt.gensalt()).decode(),
                    display_name="Should Rollback",
                )
                raise RuntimeError("simulated error")
        except RuntimeError:
            pass

        # After rollback, user should NOT exist
        from light_polygon.db.connection import get_connection

        conn2 = get_connection()
        try:
            found = User.find_by_username(conn2, "rollback_user")
            assert found is None, "User should not exist after rollback"
        finally:
            conn2.close()


class TestMigrations:
    """Tests for the incremental schema migration engine."""

    def test_empty_migrations_dir_does_not_crash(self, temp_data_dir):
        """run_migrations should handle an empty or missing directory."""
        from light_polygon.db.connection import init_db, get_connection
        from light_polygon.db.migrations import run_migrations

        init_db()
        conn = get_connection()
        try:
            # Should not raise
            run_migrations(conn)
        finally:
            conn.close()

    def test_schema_version_table_created(self, temp_data_dir):
        """After init_db, schema_version table should exist."""
        from light_polygon.db.connection import init_db, get_connection

        init_db()
        conn = get_connection()
        try:
            row = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='schema_version'"
            ).fetchone()
            assert row is not None
        finally:
            conn.close()

    def test_migration_applied_only_once(self, temp_data_dir):
        """Create a test migration file, verify it's applied exactly once."""
        import os

        from light_polygon.db.connection import init_db, get_connection
        from light_polygon.db.migrations import MIGRATIONS_DIR, run_migrations

        init_db()

        # Create a temporary migration file
        os.makedirs(MIGRATIONS_DIR, exist_ok=True)
        mig_path = MIGRATIONS_DIR / "001_test_migration.sql"
        mig_path.write_text(
            "CREATE TABLE IF NOT EXISTS _test_mig_table (x INTEGER);\n"
            "INSERT INTO _test_mig_table VALUES (1);\n",
            encoding="utf-8",
        )

        try:
            conn = get_connection()
            try:
                run_migrations(conn)

                # Verify table was created
                row = conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name='_test_mig_table'"
                ).fetchone()
                assert row is not None

                # Verify version was recorded
                ver = conn.execute(
                    "SELECT version FROM schema_version WHERE version = 1"
                ).fetchone()
                assert ver is not None

                # Run migrations again — should NOT fail on duplicate table
                run_migrations(conn)

                # Table should still have exactly 1 row
                count = conn.execute("SELECT COUNT(*) FROM _test_mig_table").fetchone()[
                    0
                ]
                assert count == 1, (
                    "Migration applied multiple times — should be idempotent"
                )
            finally:
                conn.close()
        finally:
            mig_path.unlink()

    def test_migrations_applied_in_version_order(self, temp_data_dir):
        """Multiple migration files should execute in numeric order."""
        import os

        from light_polygon.db.connection import init_db, get_connection
        from light_polygon.db.migrations import MIGRATIONS_DIR, run_migrations

        init_db()

        os.makedirs(MIGRATIONS_DIR, exist_ok=True)
        mig1 = MIGRATIONS_DIR / "002_first.sql"
        mig2 = MIGRATIONS_DIR / "003_second.sql"
        mig1.write_text(
            "CREATE TABLE IF NOT EXISTS _mig_order_test (step TEXT);\n"
            "INSERT INTO _mig_order_test VALUES ('first');\n",
            encoding="utf-8",
        )
        mig2.write_text(
            "INSERT INTO _mig_order_test VALUES ('second');\n",
            encoding="utf-8",
        )

        try:
            conn = get_connection()
            try:
                run_migrations(conn)

                rows = conn.execute(
                    "SELECT step FROM _mig_order_test ORDER BY rowid"
                ).fetchall()
                steps = [r[0] for r in rows]
                assert steps == ["first", "second"], (
                    f"Migrations applied in wrong order: {steps}"
                )

                # Verify both versions recorded
                v2 = conn.execute(
                    "SELECT version FROM schema_version WHERE version = 2"
                ).fetchone()
                v3 = conn.execute(
                    "SELECT version FROM schema_version WHERE version = 3"
                ).fetchone()
                assert v2 is not None
                assert v3 is not None
            finally:
                conn.close()
        finally:
            mig1.unlink()
            mig2.unlink()


class TestModelsNoAutoCommit:
    """Verify model methods delegate transaction control to the caller.

    Model methods MUST NOT call conn.commit() — that responsibility belongs
    to db_transaction() or manual connection management.

    These tests verify the convention by checking that an explicit BEGIN +
    rollback correctly undoes model operations. If a model called commit()
    internally, the transaction would be closed and rollback would be a no-op.
    """

    def test_user_create_rollback_loses_data(self, temp_data_dir):
        from light_polygon.db.connection import init_db, get_connection

        init_db()
        import bcrypt

        conn = get_connection()
        try:
            conn.execute("BEGIN")
            User.create(
                conn,
                "ghost_user",
                bcrypt.hashpw(b"pass", bcrypt.gensalt()).decode(),
            )
            # If User.create() called conn.commit() internally, the transaction
            # is already closed and the user is persisted. The rollback below
            # would be a no-op.
            conn.rollback()

            # Check from a fresh connection — user should NOT exist
            conn2 = get_connection()
            try:
                found = User.find_by_username(conn2, "ghost_user")
                assert found is None, (
                    "User persisted despite rollback — model may be calling commit()"
                )
            finally:
                conn2.close()
        finally:
            conn.close()

    def test_problem_save_rollback_loses_changes(self, temp_data_dir):
        from light_polygon.db.connection import init_db, get_connection

        init_db()
        import bcrypt

        # Create a user and problem first (outside transaction, persists)
        conn = get_connection()
        try:
            User.create(
                conn,
                "save_test_owner",
                bcrypt.hashpw(b"pass", bcrypt.gensalt()).decode(),
            )
            conn.commit()

            p = Problem.create(conn, slug="save-rollback", title="Original", owner_id=1)
            conn.commit()

            # Now test: save inside a transaction that gets rolled back
            conn.execute("BEGIN")
            p.title = "Changed"
            p.save(conn)
            conn.rollback()

            # Title should still be "Original"
            reloaded = Problem.find_by_id(conn, p.id)
            assert reloaded.title == "Original", (
                "Save persisted despite rollback — model may be calling commit()"
            )
        finally:
            conn.close()
