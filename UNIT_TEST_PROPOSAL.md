# Unit Test Proposal — Context-DB

## 1. Overview

This document proposes a unit test suite for the **Context-DB** MCP Database Migration Server. The project currently has **zero tests**. The goal is to establish a reliable test foundation with **one representative test per tool/module**, using SQLite as the test database backend to avoid external dependencies.

---

## 2. Tech Stack for Testing

| Dependency | Purpose |
|---|---|
| `pytest` | Test runner and assertion framework |
| `pytest-cov` | Code coverage reporting |
| `unittest.mock` | Mocking external dependencies (PostgreSQL, MySQL) |

### Install

```bash
pip install pytest pytest-cov
```

### Recommended `pyproject.toml` additions

```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
python_files = ["test_*.py"]
python_classes = ["Test*"]
python_functions = ["test_*"]
addopts = "-v --tb=short"
```

---

## 3. Test Directory Structure

```
tests/
├── conftest.py                  # Shared fixtures (tmp database, engine, adapters)
├── test_adapters.py             # Database adapter tests
├── test_engine.py               # MigrationEngine tests
├── test_factory.py              # Factory pattern tests
├── test_tools.py                # MCP tool handler tests (one per tool)
├── test_config.py               # Configuration loading tests
├── test_logging_config.py       # Logging setup tests
└── migrations/                  # Fixture migration files for tests
    ├── 001_create_users.up.sql
    ├── 001_create_users.down.sql
    ├── 002_add_email.up.sql
    └── 002_add_email.down.sql
```

---

## 4. Shared Fixtures (`conftest.py`)

All tests will share a set of `pytest` fixtures that create isolated, temporary SQLite databases and migration directories per test.

```python
import os
import pytest
from src.adapters import SQLiteAdapter
from src.engine import MigrationEngine


@pytest.fixture
def tmp_db(tmp_path):
    """Create a temporary SQLite database."""
    db_path = str(tmp_path / "test.db")
    return SQLiteAdapter(db_path)


@pytest.fixture
def migrations_dir(tmp_path):
    """Create a temporary migrations directory with sample migration files."""
    mig_dir = tmp_path / "migrations"
    mig_dir.mkdir()

    # 001_create_users
    (mig_dir / "001_create_users.up.sql").write_text(
        "CREATE TABLE users (id INTEGER PRIMARY KEY, name TEXT NOT NULL);"
    )
    (mig_dir / "001_create_users.down.sql").write_text(
        "DROP TABLE IF EXISTS users;"
    )

    # 002_add_email
    (mig_dir / "002_add_email.up.sql").write_text(
        "ALTER TABLE users ADD COLUMN email TEXT;"
    )
    (mig_dir / "002_add_email.down.sql").write_text(
        "ALTER TABLE users DROP COLUMN email;"
    )

    return str(mig_dir)


@pytest.fixture
def engine(tmp_db, migrations_dir):
    """Create a MigrationEngine with temporary database and migrations."""
    return MigrationEngine(tmp_db, migrations_dir)
```

---

## 5. Test Plan — One Test Per Tool/Component

### 5.1 Adapter Tests (`test_adapters.py`)

Each adapter has 6 abstract methods. We test SQLiteAdapter concretely; Postgres and MySQL are tested via mocking.

| # | Test | Method Under Test | What It Verifies |
|---|---|---|---|
| 1 | `test_sqlite_connect` | `SQLiteAdapter.connect()` | Returns a valid connection; `SELECT 1` succeeds |
| 2 | `test_sqlite_get_schema` | `SQLiteAdapter.get_schema()` | Returns DDL string containing `CREATE TABLE` after creating a table |
| 3 | `test_sqlite_inspect_table` | `SQLiteAdapter.inspect_table()` | Returns correct columns, types, row count, and indexes for a known table |
| 4 | `test_sqlite_list_tables` | `SQLiteAdapter.list_tables()` | Returns list of dicts with `table_name` and `column_count` |
| 5 | `test_sqlite_get_placeholder` | `SQLiteAdapter.get_placeholder()` | Returns `"?"` |
| 6 | `test_sqlite_execute_script` | `SQLiteAdapter.execute_script()` | Executes multi-statement SQL without error |

#### Example: `test_sqlite_connect`

```python
def test_sqlite_connect(tmp_db):
    """Verify that SQLiteAdapter.connect() returns a working connection."""
    with tmp_db.connect() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT 1")
        result = cursor.fetchone()
    assert result == (1,)
```

---

### 5.2 Engine Tests (`test_engine.py`)

The `MigrationEngine` class is the core of the project. Each public method gets one test.

| # | Test | Method Under Test | What It Verifies |
|---|---|---|---|
| 1 | `test_init_creates_history_table` | `__init__` / `_init_history_table()` | `schema_migrations` table exists after initialization |
| 2 | `test_calculate_checksum` | `_calculate_checksum()` | Returns deterministic 16-char hex string for given input |
| 3 | `test_get_applied_migrations_empty` | `get_applied_migrations()` | Returns empty list when no migrations are applied |
| 4 | `test_get_available_migrations` | `get_available_migrations()` | Finds both `.up.sql` files and parses version/name correctly |
| 5 | `test_get_status` | `get_status()` | Returns dict with `pending`, `applied`, `drift_detected`, and `current_version` keys |
| 6 | `test_apply_migration` | `apply_migration()` | Applies migration, records it in `schema_migrations`, and returns `success: True` |
| 7 | `test_apply_migration_dry_run` | `apply_migration(dry_run=True)` | Returns SQL preview without modifying the database |
| 8 | `test_rollback_migration` | `rollback_migration()` | Rolls back an applied migration and removes it from `schema_migrations` |
| 9 | `test_create_migration` | `create_migration()` | Creates `.up.sql` and `.down.sql` files with auto-versioned names |

#### Example: `test_apply_migration`

```python
def test_apply_migration(engine):
    """Verify that apply_migration executes SQL and records the migration."""
    result = engine.apply_migration("001")

    assert result["success"] is True
    assert result["version"] == "001"
    assert result["name"] == "create_users"
    assert "execution_time_ms" in result

    # Verify migration was recorded
    applied = engine.get_applied_migrations()
    assert len(applied) == 1
    assert applied[0]["version"] == "001"
```

---

### 5.3 Tool Tests (`test_tools.py`)

Each of the **12 MCP tools** from `server.py` gets one test. These tests call the tool handler functions directly (not through MCP protocol), using a real SQLite backend.

| # | Tool | Test Name | What It Verifies |
|---|---|---|---|
| 1 | `test_connection` | `test_tool_test_connection` | Returns `{"success": True}` with a valid database |
| 2 | `migration_status` | `test_tool_migration_status` | Returns dict with all required keys (`pending`, `applied`, `drift_detected`, `current_version`) |
| 3 | `list_pending_migrations` | `test_tool_list_pending_migrations` | Returns list of pending migrations; count matches available `.up.sql` files |
| 4 | `read_migration_sql` | `test_tool_read_migration_sql` | Returns the raw SQL content of a known migration file |
| 5 | `apply_migration` | `test_tool_apply_migration` | Applies a migration and returns `success: True` |
| 6 | `apply_all_pending` | `test_tool_apply_all_pending` | Applies all pending migrations; `applied` count matches `total` |
| 7 | `rollback_migration` | `test_tool_rollback_migration` | Rolls back a previously applied migration successfully |
| 8 | `rollback_last` | `test_tool_rollback_last` | Rolls back the most recently applied migration |
| 9 | `create_migration` | `test_tool_create_migration` | Creates migration files and returns file paths |
| 10 | `inspect_schema` | `test_tool_inspect_schema` | Returns table list or column details for a specific table |
| 11 | `run_query` | `test_tool_run_query` | Executes a SELECT query and returns columns + rows |
| 12 | `check_drift` | `test_tool_check_drift` | Returns `drift_detected: False` when no files have been modified |

#### Example: `test_tool_run_query`

```python
def test_tool_run_query(engine, tmp_db):
    """Verify run_query executes SELECT and blocks dangerous statements."""
    # Apply migration first to create tables
    engine.apply_migration("001")

    # Test successful SELECT
    with tmp_db.connect() as conn:
        conn.execute("INSERT INTO users (name) VALUES ('Alice')")
        conn.commit()

    result = run_query("SELECT * FROM users")
    assert "columns" in result
    assert result["row_count"] == 1
    assert result["rows"][0][1] == "Alice"

    # Test safety block
    result = run_query("DROP TABLE users")
    assert "error" in result
    assert "Safety block" in result["error"]
```

---

### 5.4 Factory Tests (`test_factory.py`)

| # | Test | What It Verifies |
|---|---|---|
| 1 | `test_create_sqlite_adapter` | `create_adapter()` returns `SQLiteAdapter` when `db_type == "sqlite"` |
| 2 | `test_create_postgres_adapter` | `create_adapter()` returns `PostgresAdapter` when `db_type == "postgres"` (mocked config) |
| 3 | `test_create_mysql_adapter` | `create_adapter()` returns `MySQLAdapter` when `db_type == "mysql"` (mocked config) |

#### Example: `test_create_sqlite_adapter`

```python
from unittest.mock import patch
from src.factory import create_adapter
from src.adapters import SQLiteAdapter

def test_create_sqlite_adapter():
    """Verify factory returns SQLiteAdapter for sqlite db_type."""
    mock_config = {
        "db_type": "sqlite",
        "db_path": ":memory:",
    }
    with patch("src.factory.CONFIG", mock_config):
        adapter = create_adapter()
    assert isinstance(adapter, SQLiteAdapter)
```

---

### 5.5 Config Tests (`test_config.py`)

| # | Test | What It Verifies |
|---|---|---|
| 1 | `test_settings_loads_from_env` | `Settings` class correctly reads environment variables and applies defaults |

#### Example: `test_settings_loads_from_env`

```python
import os
from unittest.mock import patch

def test_settings_loads_from_env():
    """Verify Settings reads DB_TYPE from environment."""
    env = {
        "DB_TYPE": "sqlite",
        "DB_PATH": "/tmp/test.db",
        "DB_PORT": "5432",
        "DB_DATABASE": "testdb",
        "DB_USER": "user",
        "DB_PASSWORD": "pass",
    }
    with patch.dict(os.environ, env, clear=False):
        from src.config import Settings
        settings = Settings()
    assert settings.db_type == "sqlite"
    assert settings.db_path == "/tmp/test.db"
```

---

### 5.6 Logging Tests (`test_logging_config.py`)

| # | Test | What It Verifies |
|---|---|---|
| 1 | `test_setup_logging_returns_logger` | `setup_logging()` returns a `logging.Logger` with name `"mcp-context-db"` |

#### Example: `test_setup_logging_returns_logger`

```python
import logging
from src.logging_config import setup_logging

def test_setup_logging_returns_logger():
    """Verify setup_logging returns a properly named logger."""
    logger = setup_logging()
    assert isinstance(logger, logging.Logger)
    assert logger.name == "mcp-context-db"
```

---

## 6. Summary Table

| Module | File | Tests | Coverage Target |
|---|---|---|---|
| Adapters | `test_adapters.py` | 6 | `SQLiteAdapter` — 100%, Postgres/MySQL placeholder + factory only |
| Engine | `test_engine.py` | 9 | All public methods of `MigrationEngine` |
| Tools | `test_tools.py` | 12 | All 12 MCP tool handlers |
| Factory | `test_factory.py` | 3 | All 3 adapter creation paths |
| Config | `test_config.py` | 1 | Environment-based settings loading |
| Logging | `test_logging_config.py` | 1 | Logger initialization |
| **Total** | | **32** | **Target: 85%+ line coverage** |

---

## 7. Testing Strategy Notes

### Isolation
- Every test uses `tmp_path` (pytest built-in) for file system isolation — no shared state between tests.
- SQLite `:memory:` or temp-file databases ensure no side effects.

### No External Dependencies
- PostgreSQL and MySQL adapters are tested through **mocking** (`unittest.mock.patch`) — no running database servers required.
- Only `SQLiteAdapter` tests hit a real database.

### Safety
- The `run_query` tool's safety block (dangerous keyword detection) is explicitly tested to prevent regressions.
- Migration checksums and drift detection are validated end-to-end.

### Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=src --cov-report=term-missing

# Run a specific test file
pytest tests/test_engine.py

# Run a specific test
pytest tests/test_tools.py::test_tool_run_query -v
```

---

## 8. Future Improvements (Out of Scope)

- Integration tests against real PostgreSQL/MySQL containers (using `testcontainers-python`)
- MCP protocol-level tests (calling tools through the MCP transport layer)
- CI/CD pipeline integration (GitHub Actions)
- Property-based testing for migration name sanitization (using `hypothesis`)
