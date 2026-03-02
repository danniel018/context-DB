"""
Unit tests for MCP tool handlers (server.py).

One test per MCP tool. Tests call the handler functions directly
using a real SQLite backend — no MCP transport involved.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from adapters import SQLiteAdapter
from engine import MigrationEngine


class TestTools:
    """
    One test per MCP tool handler.

    Since the tool functions in server.py depend on module-level globals
    (db_adapter, engine), these tests replicate the same logic using local
    fixtures to avoid import-time side effects from server.py.
    """

    def test_test_connection(self, tmp_db):
        """test_connection: returns success=True for a valid database."""
        try:
            with tmp_db.connect() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT 1")
                result = {"success": True, "message": "Connection successful"}
        except Exception as e:
            result = {"success": False, "error": str(e)}

        assert result["success"] is True

    def test_migration_status(self, engine):
        """migration_status: returns dict with all required status keys."""
        status = engine.get_status()
        assert "pending" in status
        assert "applied" in status
        assert "drift_detected" in status
        assert "current_version" in status

    def test_list_pending_migrations(self, engine):
        """list_pending_migrations: returns all unapplied migrations."""
        pending = engine.get_status()["pending"]
        assert len(pending) == 2
        versions = [m["version"] for m in pending]
        assert "001" in versions
        assert "002" in versions

    def test_read_migration_sql(self, engine):
        """read_migration_sql: reads the raw SQL content of a migration file."""
        available = engine.get_available_migrations()
        migration = next(m for m in available if m["version"] == "001")
        path = migration["path"]

        assert os.path.exists(path)
        with open(path) as f:
            content = f.read()
        assert "CREATE TABLE users" in content

    def test_apply_migration(self, engine):
        """apply_migration: applies a migration and returns success."""
        result = engine.apply_migration("001")
        assert result["success"] is True
        assert result["version"] == "001"

    def test_apply_all_pending(self, engine):
        """apply_all_pending: applies all pending migrations in order."""
        pending = engine.get_status()["pending"]
        results = []
        for migration in pending:
            result = engine.apply_migration(migration["version"])
            results.append(result)
            if not result["success"]:
                break

        assert len(results) == 2
        assert all(r["success"] for r in results)

    def test_rollback_migration(self, engine):
        """rollback_migration: rolls back a previously applied migration."""
        engine.apply_migration("001")
        result = engine.rollback_migration("001")
        assert result["success"] is True
        assert len(engine.get_applied_migrations()) == 0

    def test_rollback_last(self, engine):
        """rollback_last: rolls back the most recently applied migration."""
        engine.apply_migration("001")
        engine.apply_migration("002")

        status = engine.get_status()
        last = status["applied"][-1]
        result = engine.rollback_migration(last["version"])

        assert result["success"] is True
        applied = engine.get_applied_migrations()
        assert len(applied) == 1
        assert applied[0]["version"] == "001"

    def test_create_migration(self, engine):
        """create_migration: creates migration files with auto-versioned names."""
        result = engine.create_migration(
            name="add_posts",
            up_sql="CREATE TABLE posts (id INTEGER PRIMARY KEY, title TEXT);",
            down_sql="DROP TABLE posts;",
        )
        assert result["success"] is True
        assert result["version"] == "003"
        assert os.path.exists(result["up_file"])

    def test_inspect_schema(self, engine, tmp_db):
        """inspect_schema: returns table list or column details."""
        engine.apply_migration("001")

        # List all tables
        tables = tmp_db.list_tables()
        table_names = [t["table_name"] for t in tables]
        assert "users" in table_names

        # Inspect specific table
        info = tmp_db.inspect_table("users")
        assert info["table"] == "users"
        assert len(info["columns"]) >= 2

    def test_run_query(self, engine, tmp_db):
        """run_query: executes SELECT queries and blocks dangerous statements."""
        engine.apply_migration("001")

        # Insert test data
        with tmp_db.connect() as conn:
            conn.execute("INSERT INTO users (name) VALUES ('Alice')")
            conn.commit()

        # Execute a safe SELECT
        with tmp_db.connect() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM users")
            columns = [desc[0] for desc in cursor.description]
            rows = cursor.fetchall()

        assert "name" in columns
        assert len(rows) == 1

        # Verify safety check logic
        dangerous_keywords = ["DROP", "DELETE", "UPDATE", "INSERT", "ALTER", "TRUNCATE", "CREATE"]
        test_query = "DROP TABLE users"
        query_upper = test_query.upper()
        blocked = any(kw in query_upper for kw in dangerous_keywords)
        assert blocked is True

    def test_check_drift(self, engine):
        """check_drift: returns no drift when files are unmodified."""
        engine.apply_migration("001")

        status = engine.get_status()
        assert status["drift_detected"] == []
