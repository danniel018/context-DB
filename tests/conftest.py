"""
Shared test fixtures for Context-DB unit tests.

Provides isolated SQLite databases and temporary migration directories
so each test runs without side effects.
"""

import shutil

import pytest

import sys
import os

# Add src to path so imports work
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from adapters import SQLiteAdapter
from engine import MigrationEngine


FIXTURE_MIGRATIONS_DIR = os.path.join(os.path.dirname(__file__), "migrations")


@pytest.fixture
def tmp_db(tmp_path):
    """Create a temporary SQLite database adapter."""
    db_path = str(tmp_path / "test.db")
    return SQLiteAdapter(db_path)


@pytest.fixture
def migrations_dir(tmp_path):
    """
    Copy fixture migration files into a temporary directory.

    Returns the path to the temporary migrations directory.
    """
    mig_dir = tmp_path / "migrations"
    shutil.copytree(FIXTURE_MIGRATIONS_DIR, str(mig_dir))
    return str(mig_dir)


@pytest.fixture
def engine(tmp_db, migrations_dir):
    """Create a MigrationEngine backed by a temporary SQLite database."""
    return MigrationEngine(tmp_db, migrations_dir)
