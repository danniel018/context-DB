"""
MCP Database Migration Server
A Model Context Protocol server for managing database migrations with raw SQL.
Supports SQLite and PostgreSQL databases.
"""

import os
import glob
import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional, Any
from abc import ABC, abstractmethod

from mcp.server.fastmcp import FastMCP

# --- CONFIGURATION ---
DB_TYPE = os.getenv("MCP_DB_TYPE", "sqlite")  # "sqlite" or "postgres"
DB_PATH = os.getenv("MCP_DB_PATH", "database.db")  # For SQLite
MIGRATIONS_DIR = os.getenv("MCP_MIGRATIONS_DIR", "./migrations")

# PostgreSQL Configuration
PG_HOST = os.getenv("MCP_PG_HOST", "localhost")
PG_PORT = os.getenv("MCP_PG_PORT", "5432")
PG_DATABASE = os.getenv("MCP_PG_DATABASE", "myapp")
PG_USER = os.getenv("MCP_PG_USER", "postgres")
PG_PASSWORD = os.getenv("MCP_PG_PASSWORD", "")


# --- DATABASE ADAPTERS ---
class DatabaseAdapter(ABC):
    """Abstract base class for database adapters."""
    
    @abstractmethod
    def connect(self):
        """Return a database connection."""
        pass
    
    @abstractmethod
    def get_schema(self) -> str:
        """Get the database schema as DDL."""
        pass
    
    @abstractmethod
    def inspect_table(self, table: str) -> Dict[str, Any]:
        """Get detailed information about a specific table."""
        pass
    
    @abstractmethod
    def list_tables(self) -> List[Dict[str, Any]]:
        """List all tables in the database."""
        pass


class SQLiteAdapter(DatabaseAdapter):
    """SQLite database adapter."""
    
    def __init__(self, db_path: str):
        self.db_path = db_path
    
    def connect(self):
        import sqlite3
        return sqlite3.connect(self.db_path)
    
    def get_schema(self) -> str:
        with self.connect() as conn:
            rows = conn.execute(
                "SELECT sql FROM sqlite_master WHERE type='table' AND sql IS NOT NULL"
            ).fetchall()
        return "\n\n".join([r[0] for r in rows])
    
    def inspect_table(self, table: str) -> Dict[str, Any]:
        with self.connect() as conn:
            # Get column info
            columns = conn.execute(f"PRAGMA table_info({table})").fetchall()
            col_info = [
                {
                    "name": c[1],
                    "type": c[2],
                    "nullable": not c[3],
                    "default": c[4],
                    "primary_key": bool(c[5])
                }
                for c in columns
            ]
            
            # Get row count
            row_count = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            
            # Get indexes
            indexes = conn.execute(
                f"SELECT name, sql FROM sqlite_master WHERE type='index' AND tbl_name='{table}'"
            ).fetchall()
            idx_info = [{"name": i[0], "definition": i[1]} for i in indexes if i[1]]
            
        return {
            "table": table,
            "row_count": row_count,
            "columns": col_info,
            "indexes": idx_info
        }
    
    def list_tables(self) -> List[Dict[str, Any]]:
        with self.connect() as conn:
            tables = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
            ).fetchall()
            
            result = []
            for (table_name,) in tables:
                col_count = len(conn.execute(f"PRAGMA table_info({table_name})").fetchall())
                result.append({
                    "table_name": table_name,
                    "column_count": col_count
                })
        return result


class PostgresAdapter(DatabaseAdapter):
    """PostgreSQL database adapter."""
    
    def __init__(self, host: str, port: str, database: str, user: str, password: str):
        self.config = {
            "host": host,
            "port": port,
            "database": database,
            "user": user,
            "password": password
        }
    
    def connect(self):
        import psycopg2
        return psycopg2.connect(**self.config)
    
    def get_schema(self) -> str:
        # For PostgreSQL, we generate DDL from information_schema
        with self.connect() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT table_name 
                    FROM information_schema.tables 
                    WHERE table_schema = 'public' AND table_type = 'BASE TABLE'
                """)
                tables = [r[0] for r in cur.fetchall()]
                
                ddl_statements = []
                for table in tables:
                    cur.execute("""
                        SELECT column_name, data_type, is_nullable, column_default
                        FROM information_schema.columns
                        WHERE table_name = %s
                        ORDER BY ordinal_position
                    """, (table,))
                    columns = cur.fetchall()
                    
                    col_defs = []
                    for col in columns:
                        col_def = f"  {col[0]} {col[1]}"
                        if col[2] == 'NO':
                            col_def += " NOT NULL"
                        if col[3]:
                            col_def += f" DEFAULT {col[3]}"
                        col_defs.append(col_def)
                    
                    ddl = f"CREATE TABLE {table} (\n" + ",\n".join(col_defs) + "\n);"
                    ddl_statements.append(ddl)
                
        return "\n\n".join(ddl_statements)
    
    def inspect_table(self, table: str) -> Dict[str, Any]:
        from psycopg2.extras import RealDictCursor
        
        with self.connect() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                # Get columns
                cur.execute("""
                    SELECT column_name, data_type, is_nullable, column_default
                    FROM information_schema.columns
                    WHERE table_name = %s
                    ORDER BY ordinal_position
                """, (table,))
                columns = [dict(row) for row in cur.fetchall()]
                
                # Get row count
                cur.execute(f"SELECT COUNT(*) as count FROM {table}")
                row_count = cur.fetchone()["count"]
                
                # Get indexes
                cur.execute("""
                    SELECT indexname as name, indexdef as definition
                    FROM pg_indexes
                    WHERE tablename = %s
                """, (table,))
                indexes = [dict(row) for row in cur.fetchall()]
                
        return {
            "table": table,
            "row_count": row_count,
            "columns": columns,
            "indexes": indexes
        }
    
    def list_tables(self) -> List[Dict[str, Any]]:
        from psycopg2.extras import RealDictCursor
        
        with self.connect() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT 
                        t.table_name,
                        (SELECT COUNT(*) FROM information_schema.columns c 
                         WHERE c.table_name = t.table_name) as column_count
                    FROM information_schema.tables t
                    WHERE t.table_schema = 'public' AND t.table_type = 'BASE TABLE'
                    ORDER BY t.table_name
                """)
                return [dict(row) for row in cur.fetchall()]


# --- MIGRATION ENGINE ---
class MigrationEngine:
    """
    Core migration engine supporting multiple database backends.
    Uses convention: {version}_{name}.up.sql and {version}_{name}.down.sql
    """
    
    def __init__(self, db_adapter: DatabaseAdapter, migrations_dir: str):
        self.db = db_adapter
        self.migrations_dir = Path(migrations_dir)
        self.migrations_dir.mkdir(parents=True, exist_ok=True)
        self._init_history_table()
    
    def _init_history_table(self):
        """Ensures the schema_migrations tracking table exists."""
        with self.db.connect() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS schema_migrations (
                    version TEXT PRIMARY KEY,
                    name TEXT,
                    checksum TEXT,
                    applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    execution_time_ms INTEGER
                )
            """)
            conn.commit()
    
    def _calculate_checksum(self, content: str) -> str:
        """Calculate SHA256 checksum of migration content."""
        return hashlib.sha256(content.encode()).hexdigest()[:16]
    
    def get_applied_migrations(self) -> List[Dict[str, Any]]:
        """Get list of applied migrations with metadata."""
        with self.db.connect() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT version, name, checksum, applied_at, execution_time_ms
                FROM schema_migrations
                ORDER BY version ASC
            """)
            rows = cursor.fetchall()
        
        return [
            {
                "version": r[0],
                "name": r[1],
                "checksum": r[2],
                "applied_at": str(r[3]),
                "execution_time_ms": r[4]
            }
            for r in rows
        ]
    
    def get_available_migrations(self) -> List[Dict[str, Any]]:
        """Scan the migrations folder for .up.sql files."""
        if not self.migrations_dir.exists():
            return []
        
        files = glob.glob(str(self.migrations_dir / "*.up.sql"))
        migrations = []
        
        for f in sorted(files):
            filename = os.path.basename(f)
            version_name = filename.replace(".up.sql", "")
            parts = version_name.split("_", 1)
            version = parts[0]
            name = parts[1] if len(parts) > 1 else ""
            
            with open(f, 'r') as file:
                content = file.read()
            
            migrations.append({
                "version": version,
                "name": name,
                "full_version": version_name,
                "filename": filename,
                "checksum": self._calculate_checksum(content),
                "path": f
            })
        
        return migrations
    
    def get_status(self) -> Dict[str, Any]:
        """Get comprehensive migration status."""
        applied_list = self.get_applied_migrations()
        applied_versions = {m["version"] for m in applied_list}
        available = self.get_available_migrations()
        available_versions = {m["version"] for m in available}
        
        pending = [m for m in available if m["version"] not in applied_versions]
        applied = [m for m in available if m["version"] in applied_versions]
        
        # Check for checksum mismatches (drift detection)
        applied_checksums = {m["version"]: m["checksum"] for m in applied_list}
        drift = []
        for m in applied:
            if m["version"] in applied_checksums:
                if m["checksum"] != applied_checksums[m["version"]]:
                    drift.append({
                        "version": m["version"],
                        "expected": applied_checksums[m["version"]],
                        "actual": m["checksum"]
                    })
        
        return {
            "pending": pending,
            "applied": applied,
            "drift_detected": drift,
            "current_version": applied_list[-1]["version"] if applied_list else None
        }
    
    def apply_migration(self, version: str, dry_run: bool = False) -> Dict[str, Any]:
        """Apply a specific migration."""
        available = {m["version"]: m for m in self.get_available_migrations()}
        
        if version not in available:
            return {"success": False, "error": f"Migration {version} not found"}
        
        migration = available[version]
        applied_versions = {m["version"] for m in self.get_applied_migrations()}
        
        if version in applied_versions:
            return {"success": False, "error": f"Migration {version} already applied"}
        
        # Read the SQL
        with open(migration["path"], 'r') as f:
            sql_script = f.read()
        
        if dry_run:
            return {
                "success": True,
                "dry_run": True,
                "version": version,
                "name": migration["name"],
                "sql_preview": sql_script[:500] + ("..." if len(sql_script) > 500 else "")
            }
        
        # Execute migration
        start_time = datetime.now()
        try:
            with self.db.connect() as conn:
                cursor = conn.cursor()
                cursor.executescript(sql_script) if hasattr(cursor, 'executescript') else cursor.execute(sql_script)
                
                execution_time = int((datetime.now() - start_time).total_seconds() * 1000)
                
                cursor.execute(
                    "INSERT INTO schema_migrations (version, name, checksum, execution_time_ms) VALUES (?, ?, ?, ?)"
                    if DB_TYPE == "sqlite" else
                    "INSERT INTO schema_migrations (version, name, checksum, execution_time_ms) VALUES (%s, %s, %s, %s)",
                    (version, migration["name"], migration["checksum"], execution_time)
                )
                conn.commit()
            
            return {
                "success": True,
                "version": version,
                "name": migration["name"],
                "execution_time_ms": execution_time
            }
        except Exception as e:
            return {"success": False, "version": version, "error": str(e)}
    
    def rollback_migration(self, version: str, dry_run: bool = False) -> Dict[str, Any]:
        """Rollback a specific migration using its .down.sql file."""
        available = {m["version"]: m for m in self.get_available_migrations()}
        
        if version not in available:
            return {"success": False, "error": f"Migration {version} not found"}
        
        migration = available[version]
        down_path = migration["path"].replace(".up.sql", ".down.sql")
        
        if not os.path.exists(down_path):
            return {"success": False, "error": f"Rollback file not found: {down_path}"}
        
        applied_versions = {m["version"] for m in self.get_applied_migrations()}
        if version not in applied_versions:
            return {"success": False, "error": f"Migration {version} is not applied"}
        
        with open(down_path, 'r') as f:
            sql_script = f.read()
        
        if dry_run:
            return {
                "success": True,
                "dry_run": True,
                "version": version,
                "sql_preview": sql_script[:500] + ("..." if len(sql_script) > 500 else "")
            }
        
        try:
            with self.db.connect() as conn:
                cursor = conn.cursor()
                cursor.executescript(sql_script) if hasattr(cursor, 'executescript') else cursor.execute(sql_script)
                
                cursor.execute(
                    "DELETE FROM schema_migrations WHERE version = ?"
                    if DB_TYPE == "sqlite" else
                    "DELETE FROM schema_migrations WHERE version = %s",
                    (version,)
                )
                conn.commit()
            
            return {"success": True, "version": version, "message": f"Rolled back {version}"}
        except Exception as e:
            return {"success": False, "version": version, "error": str(e)}
    
    def create_migration(self, name: str, up_sql: str, down_sql: Optional[str] = None) -> Dict[str, Any]:
        """Create a new migration file with auto-generated version number."""
        existing = self.get_available_migrations()
        
        if existing:
            last_version = max(int(m["version"]) for m in existing)
            version = f"{last_version + 1:03d}"
        else:
            version = "001"
        
        # Sanitize name
        safe_name = name.lower().replace(" ", "_").replace("-", "_")
        
        # Create UP migration
        up_filename = f"{version}_{safe_name}.up.sql"
        up_path = self.migrations_dir / up_filename
        
        with open(up_path, 'w') as f:
            f.write(f"-- Migration: {version}_{safe_name}\n")
            f.write(f"-- Created: {datetime.now().isoformat()}\n")
            f.write(f"-- Description: {name}\n\n")
            f.write(up_sql)
            f.write("\n")
        
        result = {
            "success": True,
            "version": version,
            "name": safe_name,
            "up_file": str(up_path),
            "down_file": None
        }
        
        # Create DOWN migration if provided
        if down_sql:
            down_filename = f"{version}_{safe_name}.down.sql"
            down_path = self.migrations_dir / down_filename
            
            with open(down_path, 'w') as f:
                f.write(f"-- Rollback: {version}_{safe_name}\n")
                f.write(f"-- Created: {datetime.now().isoformat()}\n\n")
                f.write(down_sql)
                f.write("\n")
            
            result["down_file"] = str(down_path)
        
        return result


# --- INITIALIZE ENGINE ---
def create_adapter() -> DatabaseAdapter:
    """Create the appropriate database adapter based on configuration."""
    if DB_TYPE == "postgres":
        return PostgresAdapter(PG_HOST, PG_PORT, PG_DATABASE, PG_USER, PG_PASSWORD)
    else:
        return SQLiteAdapter(DB_PATH)


db_adapter = create_adapter()
engine = MigrationEngine(db_adapter, MIGRATIONS_DIR)


# --- MCP SERVER ---
mcp = FastMCP(
    "db-migrate",
    description="MCP Server for database migrations and schema management"
)


# --- RESOURCES (Passive Context for AI) ---

@mcp.resource("migrations://status")
def resource_migration_status() -> str:
    """Returns a formatted summary of migration status."""
    status = engine.get_status()
    
    output = f"""DATABASE MIGRATION STATUS
========================
Database Type: {DB_TYPE}
Current Version: {status['current_version'] or '(none)'}
Applied: {len(status['applied'])}
Pending: {len(status['pending'])}
Drift Detected: {len(status['drift_detected'])}

PENDING MIGRATIONS:
{chr(10).join(['  - ' + m['full_version'] for m in status['pending']]) or '  (none)'}

APPLIED MIGRATIONS:
{chr(10).join(['  - ' + m['full_version'] for m in status['applied']]) or '  (none)'}
"""
    
    if status['drift_detected']:
        output += f"""
⚠️  DRIFT DETECTED:
{chr(10).join(['  - ' + d['version'] + ': checksum mismatch' for d in status['drift_detected']])}
"""
    
    return output


@mcp.resource("migrations://schema")
def resource_current_schema() -> str:
    """Returns the current database schema as DDL."""
    return db_adapter.get_schema() or "(No tables found)"


# --- TOOLS (Active Actions) ---

@mcp.tool()
def migration_status() -> str:
    """
    Get detailed migration status including pending, applied, and drift detection.
    Returns JSON with comprehensive status information.
    """
    status = engine.get_status()
    return json.dumps(status, indent=2, default=str)


@mcp.tool()
def list_pending_migrations() -> List[Dict[str, Any]]:
    """
    List all migrations that haven't been applied yet.
    Returns a list of pending migration objects with version, name, and checksum.
    """
    return engine.get_status()['pending']


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
        with open(path, 'r') as f:
            return f.read()
    return f"File not found: {path}"


@mcp.tool()
def apply_migration(version: str, dry_run: bool = False) -> str:
    """
    Apply a specific migration by version number.
    
    Args:
        version: The version number to apply (e.g., '001')
        dry_run: If True, shows what would happen without making changes
    
    Returns:
        JSON result with success status and details.
    """
    result = engine.apply_migration(version, dry_run)
    return json.dumps(result, indent=2)


@mcp.tool()
def apply_all_pending(dry_run: bool = False) -> str:
    """
    Apply all pending migrations in order.
    
    Args:
        dry_run: If True, shows what would happen without making changes
    
    Returns:
        JSON result with details of all applied migrations.
    """
    pending = engine.get_status()['pending']
    results = []
    
    for migration in pending:
        result = engine.apply_migration(migration["version"], dry_run)
        results.append(result)
        if not result["success"] and not dry_run:
            break
    
    return json.dumps({
        "total": len(pending),
        "applied": len([r for r in results if r["success"]]),
        "dry_run": dry_run,
        "results": results
    }, indent=2)


@mcp.tool()
def rollback_migration(version: str, dry_run: bool = False) -> str:
    """
    Rollback a specific migration using its .down.sql file.
    
    Args:
        version: The version number to rollback (e.g., '001')
        dry_run: If True, shows what would happen without making changes
    
    Returns:
        JSON result with success status and details.
    """
    result = engine.rollback_migration(version, dry_run)
    return json.dumps(result, indent=2)


@mcp.tool()
def rollback_last() -> str:
    """
    Rollback the most recently applied migration.
    
    Returns:
        JSON result with success status and details.
    """
    status = engine.get_status()
    if not status['applied']:
        return json.dumps({"success": False, "error": "No migrations to rollback"})
    
    last = status['applied'][-1]
    return json.dumps(engine.rollback_migration(last["version"]))


@mcp.tool()
def create_migration(name: str, up_sql: str, down_sql: str = "") -> str:
    """
    Create a new migration file with auto-generated version number.
    
    Args:
        name: Descriptive name for the migration (e.g., 'add_users_table')
        up_sql: SQL to execute when applying the migration
        down_sql: SQL to execute when rolling back (optional but recommended)
    
    Returns:
        JSON result with created file paths.
    """
    result = engine.create_migration(name, up_sql, down_sql if down_sql else None)
    return json.dumps(result, indent=2)


@mcp.tool()
def inspect_schema(table: str = "") -> str:
    """
    Inspect the database schema.
    
    Args:
        table: Specific table name to inspect. If empty, lists all tables.
    
    Returns:
        JSON with schema information.
    """
    if table:
        try:
            result = db_adapter.inspect_table(table)
        except Exception as e:
            result = {"error": str(e)}
    else:
        result = {
            "tables": db_adapter.list_tables(),
            "table_count": len(db_adapter.list_tables())
        }
    
    return json.dumps(result, indent=2, default=str)


@mcp.tool()
def run_query(query: str) -> str:
    """
    Execute a read-only SQL query for inspection purposes.
    WARNING: For safety, DROP, DELETE, UPDATE, INSERT, ALTER, TRUNCATE are blocked.
    
    Args:
        query: SQL SELECT query to execute
    
    Returns:
        Query results as JSON.
    """
    # Safety check
    dangerous = ["DROP", "DELETE", "UPDATE", "INSERT", "ALTER", "TRUNCATE", "CREATE"]
    query_upper = query.upper()
    for keyword in dangerous:
        if keyword in query_upper:
            return json.dumps({
                "error": f"Safety block: '{keyword}' statements not allowed. Use migrations for schema changes."
            })
    
    try:
        with db_adapter.connect() as conn:
            cursor = conn.cursor()
            cursor.execute(query)
            
            if cursor.description:
                columns = [desc[0] for desc in cursor.description]
                rows = cursor.fetchall()
                return json.dumps({
                    "columns": columns,
                    "rows": [list(row) for row in rows],
                    "row_count": len(rows)
                }, indent=2, default=str)
            else:
                return json.dumps({"message": "Query executed, no results returned"})
    except Exception as e:
        return json.dumps({"error": str(e)})


@mcp.tool()
def check_drift() -> str:
    """
    Check for schema drift by comparing migration checksums.
    Detects if migration files have been modified after being applied.
    
    Returns:
        JSON with drift detection results.
    """
    status = engine.get_status()
    
    if status['drift_detected']:
        return json.dumps({
            "drift_detected": True,
            "message": "WARNING: Migration files have been modified after being applied!",
            "details": status['drift_detected']
        }, indent=2)
    else:
        return json.dumps({
            "drift_detected": False,
            "message": "No drift detected. All migration checksums match."
        })


# --- MAIN ---
if __name__ == "__main__":
    mcp.run()
