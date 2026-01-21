"""
MCP Database Migration Server.
Defines MCP resources, tools, and prompts for database migration management.
"""

import os
from typing import Any

from mcp.server.fastmcp import FastMCP

from config import CONFIG
from engine import MigrationEngine
from factory import create_adapter
from logging_config import setup_logging

# Initialize logging
logger = setup_logging()

# Initialize database adapter and migration engine
db_adapter = create_adapter()
engine = MigrationEngine(db_adapter, CONFIG["migrations_dir"])
logger.info(f"Migration engine initialized with migrations dir: {CONFIG['migrations_dir']}")

# Create MCP server
mcp = FastMCP("Context-DB")


# --- RESOURCES (Passive Context for AI) ---


@mcp.resource("migrations://status")
def resource_migration_status() -> str:
    """Returns a formatted summary of migration status."""
    status = engine.get_status()

    output = f"""DATABASE MIGRATION STATUS
========================
Database Type: {CONFIG["db_type"]}
Current Version: {status["current_version"] or "(none)"}
Applied: {len(status["applied"])}
Pending: {len(status["pending"])}
Drift Detected: {len(status["drift_detected"])}

PENDING MIGRATIONS:
{chr(10).join(["  - " + m["full_version"] for m in status["pending"]]) or "  (none)"}

APPLIED MIGRATIONS:
{chr(10).join(["  - " + m["full_version"] for m in status["applied"]]) or "  (none)"}
"""

    if status["drift_detected"]:
        output += f"""
⚠️  DRIFT DETECTED:
{chr(10).join(["  - " + d["version"] + ": checksum mismatch" for d in status["drift_detected"]])}
"""

    return output


@mcp.resource("migrations://schema")
def resource_current_schema() -> str:
    """Returns the current database schema as DDL."""
    return db_adapter.get_schema() or "(No tables found)"


# --- TOOLS (Active Actions) ---


@mcp.tool()
def test_connection() -> dict[str, Any]:
    """
    Test the database connection.
    Returns dict with success status or error message.
    """
    logger.debug("Testing database connection")
    try:
        with db_adapter.connect() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT 1")
            logger.info("Database connection test successful")
            return {"success": True, "message": "Connection successful"}
    except Exception as e:
        logger.error(f"Database connection test failed: {e}")
        return {"success": False, "error": str(e)}


@mcp.tool()
def migration_status() -> dict[str, Any]:
    """
    Get detailed migration status including pending, applied, and drift detection.
    Returns dict with comprehensive status information.
    """
    status = engine.get_status()
    return status


@mcp.tool()
def list_pending_migrations() -> list[dict[str, Any]]:
    """
    List all migrations that haven't been applied yet.
    Returns a list of pending migration objects with version, name, and checksum.
    """
    return engine.get_status()["pending"]


@mcp.tool()
def read_migration_sql(version: str, direction: str = "up") -> str:
    """
    Read the raw SQL content of a migration file.

    Args:
        version: The version number (e.g., '001') or full version (e.g., '001_initial')
        direction: 'up' for apply script, 'down' for rollback script

    Returns:
        The SQL content of the migration file.
    """
    available = engine.get_available_migrations()

    # Find matching migration
    migration = None
    for m in available:
        if m["version"] == version or m["full_version"] == version:
            migration = m
            break

    if not migration:
        return f"Migration {version} not found"

    suffix = ".up.sql" if direction == "up" else ".down.sql"
    path = migration["path"].replace(".up.sql", suffix)

    if os.path.exists(path):
        with open(path) as f:
            return f.read()
    return f"File not found: {path}"


@mcp.tool()
def apply_migration(version: str, dry_run: bool = False) -> dict[str, Any]:
    """
    Apply a specific migration by version number.

    Args:
        version: The version number to apply (e.g., '001')
        dry_run: If True, shows what would happen without making changes

    Returns:
        Dict with success status and details.
    """
    result = engine.apply_migration(version, dry_run)
    return result


@mcp.tool()
def apply_all_pending(dry_run: bool = False) -> dict[str, Any]:
    """
    Apply all pending migrations in order.

    Args:
        dry_run: If True, shows what would happen without making changes

    Returns:
        Dict with details of all applied migrations.
    """
    pending = engine.get_status()["pending"]
    results = []

    for migration in pending:
        result = engine.apply_migration(migration["version"], dry_run)
        results.append(result)
        if not result["success"] and not dry_run:
            break

    return {
        "total": len(pending),
        "applied": len([r for r in results if r["success"]]),
        "dry_run": dry_run,
        "results": results,
    }


@mcp.tool()
def rollback_migration(version: str, dry_run: bool = False) -> dict[str, Any]:
    """
    Rollback a specific migration using its .down.sql file.

    Args:
        version: The version number to rollback (e.g., '001')
        dry_run: If True, shows what would happen without making changes

    Returns:
        Dict with success status and details.
    """
    result = engine.rollback_migration(version, dry_run)
    return result


@mcp.tool()
def rollback_last() -> dict[str, Any]:
    """
    Rollback the most recently applied migration.

    Returns:
        Dict with success status and details.
    """
    status = engine.get_status()
    if not status["applied"]:
        return {"success": False, "error": "No migrations to rollback"}

    last = status["applied"][-1]
    return engine.rollback_migration(last["version"])


@mcp.tool()
def create_migration(name: str, up_sql: str, down_sql: str = "") -> dict[str, Any]:
    """
    Create a new migration file with auto-generated version number.

    Args:
        name: Descriptive name for the migration (e.g., 'add_users_table')
        up_sql: SQL to execute when applying the migration
        down_sql: SQL to execute when rolling back (optional but recommended)

    Returns:
        Dict with created file paths.
    """
    result = engine.create_migration(name, up_sql, down_sql if down_sql else None)
    return result


@mcp.tool()
def inspect_schema(table: str = "") -> dict[str, Any]:
    """
    Inspect the database schema.

    Args:
        table: Specific table name to inspect. If empty, lists all tables.

    Returns:
        Dict with schema information.
    """
    if table:
        try:
            result = db_adapter.inspect_table(table)
        except Exception as e:
            result = {"error": str(e)}
    else:
        result = {
            "tables": db_adapter.list_tables(),
            "table_count": len(db_adapter.list_tables()),
        }

    return result


@mcp.tool()
def run_query(query: str) -> dict[str, Any]:
    """
    Execute a read-only SQL query for inspection purposes.
    WARNING: For safety, DROP, DELETE, UPDATE, INSERT, ALTER, TRUNCATE are blocked.

    Args:
        query: SQL SELECT query to execute

    Returns:
        Query results as dict.
    """
    # Safety check
    dangerous = ["DROP", "DELETE", "UPDATE", "INSERT", "ALTER", "TRUNCATE", "CREATE"]
    query_upper = query.upper()
    for keyword in dangerous:
        if keyword in query_upper:
            logger.warning(f"Blocked dangerous query containing '{keyword}'")
            return {
                "error": f"Safety block: '{keyword}' statements not allowed. Use migrations for schema changes."
            }

    logger.debug(
        f"Executing query: {query[:100]}..." if len(query) > 100 else f"Executing query: {query}"
    )
    try:
        with db_adapter.connect() as conn:
            cursor = conn.cursor()
            cursor.execute(query)

            if cursor.description:
                columns = [desc[0] for desc in cursor.description]
                rows = cursor.fetchall()
                return {
                    "columns": columns,
                    "rows": [list(row) for row in rows],
                    "row_count": len(rows),
                }
            else:
                return {"message": "Query executed, no results returned"}
    except Exception as e:
        return {"error": str(e)}


@mcp.tool()
def check_drift() -> dict[str, Any]:
    """
    Check for schema drift by comparing migration checksums.
    Detects if migration files have been modified after being applied.

    Returns:
        Dict with drift detection results.
    """
    status = engine.get_status()

    if status["drift_detected"]:
        return {
            "drift_detected": True,
            "message": "WARNING: Migration files have been modified after being applied!",
            "details": status["drift_detected"],
        }
    else:
        return {
            "drift_detected": False,
            "message": "No drift detected. All migration checksums match.",
        }


# --- PROMPTS (Guided AI Interactions) ---


@mcp.prompt()
def explain_migration(version: str) -> list[dict[str, Any]]:
    """
    Generate a prompt to ask the LLM to explain a migration's purpose and changes.

    Args:
        version: The version number (e.g., '001') or full version (e.g., '001_initial')

    Returns:
        A list of message objects for the LLM conversation.
    """
    available = engine.get_available_migrations()

    # Find matching migration
    migration = None
    for m in available:
        if m["version"] == version or m["full_version"] == version:
            migration = m
            break

    if not migration:
        return [
            {
                "role": "user",
                "content": {
                    "type": "text",
                    "text": f"Migration {version} not found. Please check the version number.",
                },
            }
        ]

    # Read UP and DOWN migration SQL
    up_sql = ""
    down_sql = ""

    up_path = migration["path"]
    try:
        if os.path.exists(up_path):
            with open(up_path, encoding="utf-8") as f:
                up_sql = f.read()
    except OSError:
        up_sql = "(Error reading UP migration file)"

    down_path = migration["path"].replace(".up.sql", ".down.sql")
    try:
        if os.path.exists(down_path):
            with open(down_path, encoding="utf-8") as f:
                down_sql = f.read()
    except OSError:
        down_sql = "(Error reading DOWN migration file)"

    # Check if migration is applied
    applied_migrations = {m["version"]: m for m in engine.get_applied_migrations()}
    is_applied = migration["version"] in applied_migrations

    status_info = ""
    if is_applied:
        applied_info = applied_migrations[migration["version"]]
        status_info = f"""
Status: Applied
Applied At: {applied_info["applied_at"]}
Execution Time: {applied_info["execution_time_ms"]}ms
"""
    else:
        status_info = "Status: Pending (not yet applied)"

    # Create the prompt message
    prompt_text = f"""Please explain this database migration in detail:

Migration: {migration["full_version"]}
Version: {migration["version"]}
Name: {migration["name"]}
{status_info}

UP Migration SQL (applies the change):
```sql
{up_sql}
```

DOWN Migration SQL (rollback):
```sql
{down_sql if down_sql else "(No rollback script provided)"}
```

Please provide:
1. A clear explanation of what this migration does
2. The database schema changes being made
3. Any potential risks or considerations
4. The purpose of the rollback strategy (if provided)
"""

    return [
        {
            "role": "user",
            "content": {"type": "text", "text": prompt_text},
        }
    ]


def run():
    """Run the MCP server."""
    logger.info("Starting MCP Database Migration Server")
    mcp.run()


if __name__ == "__main__":
    run()
