"""
Unit tests for database adapters.

Tests SQLiteAdapter concretely. PostgresAdapter and MySQLAdapter
are covered via factory/mock tests since they require running servers.
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from adapters import SQLiteAdapter


class TestSQLiteAdapter:
    """Tests for SQLiteAdapter — one test per abstract method."""

    def test_connect(self, tmp_db):
        """connect() returns a working connection that can execute queries."""
        with tmp_db.connect() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT 1")
            result = cursor.fetchone()
        assert result == (1,)

    def test_get_schema(self, tmp_db):
        """get_schema() returns DDL strings for existing tables."""
        with tmp_db.connect() as conn:
            conn.execute("CREATE TABLE items (id INTEGER PRIMARY KEY, name TEXT)")
            conn.commit()

        schema = tmp_db.get_schema()
        assert "CREATE TABLE" in schema
        assert "items" in schema

    def test_inspect_table(self, tmp_db):
        """inspect_table() returns columns, row_count, and indexes for a table."""
        with tmp_db.connect() as conn:
            conn.execute("CREATE TABLE items (id INTEGER PRIMARY KEY, name TEXT NOT NULL)")
            conn.execute("INSERT INTO items (name) VALUES ('widget')")
            conn.commit()

        info = tmp_db.inspect_table("items")
        assert info["table"] == "items"
        assert info["row_count"] == 1
        assert len(info["columns"]) == 2
        assert info["columns"][0]["name"] == "id"

    def test_list_tables(self, tmp_db):
        """list_tables() returns all user tables with column counts."""
        with tmp_db.connect() as conn:
            conn.execute("CREATE TABLE a (id INTEGER)")
            conn.execute("CREATE TABLE b (id INTEGER, name TEXT)")
            conn.commit()

        tables = tmp_db.list_tables()
        names = {t["table_name"] for t in tables}
        assert "a" in names
        assert "b" in names

    def test_get_placeholder(self, tmp_db):
        """get_placeholder() returns '?' for SQLite."""
        assert tmp_db.get_placeholder() == "?"

    def test_execute_script(self, tmp_db):
        """execute_script() runs multi-statement SQL without errors."""
        script = """
        CREATE TABLE t1 (id INTEGER);
        CREATE TABLE t2 (id INTEGER);
        INSERT INTO t1 VALUES (1);
        """
        with tmp_db.connect() as conn:
            cursor = conn.cursor()
            tmp_db.execute_script(cursor, script)
            conn.commit()

            # Verify both tables were created
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name IN ('t1', 't2')")
            tables = {row[0] for row in cursor.fetchall()}
        assert tables == {"t1", "t2"}
