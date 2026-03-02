"""
Unit tests for the database adapter factory.

Tests that create_adapter() returns the correct adapter type
based on the db_type configuration value.
"""

import os
import sys
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from adapters import MySQLAdapter, PostgresAdapter, SQLiteAdapter
from factory import create_adapter


class TestFactory:
    """Tests for create_adapter() — one test per adapter type."""

    def test_create_sqlite_adapter(self):
        """create_adapter() returns SQLiteAdapter when db_type is 'sqlite'."""
        mock_config = {"db_type": "sqlite", "db_path": ":memory:"}
        with patch("factory.CONFIG", mock_config):
            adapter = create_adapter()
        assert isinstance(adapter, SQLiteAdapter)

    def test_create_postgres_adapter(self):
        """create_adapter() returns PostgresAdapter when db_type is 'postgres'."""
        mock_config = {
            "db_type": "postgres",
            "db_host": "localhost",
            "db_port": "5432",
            "db_database": "testdb",
            "db_user": "user",
            "db_password": "pass",
        }
        with patch("factory.CONFIG", mock_config):
            adapter = create_adapter()
        assert isinstance(adapter, PostgresAdapter)

    def test_create_mysql_adapter(self):
        """create_adapter() returns MySQLAdapter when db_type is 'mysql'."""
        mock_config = {
            "db_type": "mysql",
            "db_host": "localhost",
            "db_port": "3306",
            "db_database": "testdb",
            "db_user": "user",
            "db_password": "pass",
        }
        with patch("factory.CONFIG", mock_config):
            adapter = create_adapter()
        assert isinstance(adapter, MySQLAdapter)
