"""
Unit tests for MigrationEngine.

One test per public method of the MigrationEngine class.
All tests use an in-process SQLite database for isolation.
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from engine import MigrationEngine


class TestMigrationEngine:
    """Tests for MigrationEngine — one test per public method."""

    def test_init_creates_history_table(self, engine, tmp_db):
        """__init__ creates the schema_migrations tracking table."""
        with tmp_db.connect() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='schema_migrations'"
            )
            result = cursor.fetchone()
        assert result is not None
        assert result[0] == "schema_migrations"

    def test_calculate_checksum_deterministic(self, engine):
        """_calculate_checksum() returns a consistent 16-char hex string."""
        content = "CREATE TABLE users (id INTEGER);"
        checksum1 = engine._calculate_checksum(content)
        checksum2 = engine._calculate_checksum(content)
        assert checksum1 == checksum2
        assert len(checksum1) == 16
        assert all(c in "0123456789abcdef" for c in checksum1)

    def test_get_applied_migrations_empty(self, engine):
        """get_applied_migrations() returns empty list when nothing is applied."""
        applied = engine.get_applied_migrations()
        assert applied == []

    def test_get_available_migrations(self, engine):
        """get_available_migrations() discovers .up.sql files with correct metadata."""
        available = engine.get_available_migrations()
        assert len(available) == 2
        assert available[0]["version"] == "001"
        assert available[0]["name"] == "create_users"
        assert available[1]["version"] == "002"

    def test_get_status(self, engine):
        """get_status() returns pending, applied, drift, and current_version."""
        status = engine.get_status()
        assert "pending" in status
        assert "applied" in status
        assert "drift_detected" in status
        assert "current_version" in status
        assert len(status["pending"]) == 2
        assert status["current_version"] is None

    def test_apply_migration(self, engine):
        """apply_migration() executes SQL and records in schema_migrations."""
        result = engine.apply_migration("001")
        assert result["success"] is True
        assert result["version"] == "001"
        assert "execution_time_ms" in result

        applied = engine.get_applied_migrations()
        assert len(applied) == 1
        assert applied[0]["version"] == "001"

    def test_apply_migration_dry_run(self, engine):
        """apply_migration(dry_run=True) previews SQL without modifying the database."""
        result = engine.apply_migration("001", dry_run=True)
        assert result["success"] is True
        assert result["dry_run"] is True
        assert "sql_preview" in result

        # Database should be untouched
        applied = engine.get_applied_migrations()
        assert len(applied) == 0

    def test_rollback_migration(self, engine):
        """rollback_migration() undoes an applied migration and removes tracking record."""
        engine.apply_migration("001")
        assert len(engine.get_applied_migrations()) == 1

        result = engine.rollback_migration("001")
        assert result["success"] is True
        assert len(engine.get_applied_migrations()) == 0

    def test_create_migration(self, engine, migrations_dir):
        """create_migration() generates versioned .up.sql and .down.sql files."""
        result = engine.create_migration(
            name="add_orders_table",
            up_sql="CREATE TABLE orders (id INTEGER PRIMARY KEY);",
            down_sql="DROP TABLE orders;",
        )
        assert result["success"] is True
        assert result["version"] == "003"  # auto-incremented from 002
        assert os.path.exists(result["up_file"])
        assert os.path.exists(result["down_file"])
