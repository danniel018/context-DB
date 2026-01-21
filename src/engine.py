"""
Database Migration Engine.
Handles migration discovery, application, rollback, and tracking.
"""

import glob
import hashlib
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Any

from adapters import DatabaseAdapter

logger = logging.getLogger("mcp-db-migrate")


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
        logger.debug("Initializing schema_migrations table")
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
        logger.debug("schema_migrations table ready")

    def _calculate_checksum(self, content: str) -> str:
        """Calculate SHA256 checksum of migration content."""
        return hashlib.sha256(content.encode()).hexdigest()[:16]

    def get_applied_migrations(self) -> list[dict[str, Any]]:
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
                "execution_time_ms": r[4],
            }
            for r in rows
        ]

    def get_available_migrations(self) -> list[dict[str, Any]]:
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

            with open(f) as file:
                content = file.read()

            migrations.append(
                {
                    "version": version,
                    "name": name,
                    "full_version": version_name,
                    "filename": filename,
                    "checksum": self._calculate_checksum(content),
                    "path": f,
                }
            )

        return migrations

    def get_status(self) -> dict[str, Any]:
        """Get comprehensive migration status."""
        applied_list = self.get_applied_migrations()
        applied_versions = {m["version"] for m in applied_list}
        available = self.get_available_migrations()

        pending = [m for m in available if m["version"] not in applied_versions]
        applied = [m for m in available if m["version"] in applied_versions]

        # Check for checksum mismatches (drift detection)
        applied_checksums = {m["version"]: m["checksum"] for m in applied_list}
        drift = []
        for m in applied:
            if (
                m["version"] in applied_checksums
                and m["checksum"] != applied_checksums[m["version"]]
            ):
                drift.append(
                    {
                        "version": m["version"],
                        "expected": applied_checksums[m["version"]],
                        "actual": m["checksum"],
                    }
                )

        return {
            "pending": pending,
            "applied": applied,
            "drift_detected": drift,
            "current_version": applied_list[-1]["version"] if applied_list else None,
        }

    def apply_migration(self, version: str, dry_run: bool = False) -> dict[str, Any]:
        """Apply a specific migration."""
        available = {m["version"]: m for m in self.get_available_migrations()}

        if version not in available:
            return {"success": False, "error": f"Migration {version} not found"}

        migration = available[version]
        applied_versions = {m["version"] for m in self.get_applied_migrations()}

        if version in applied_versions:
            return {"success": False, "error": f"Migration {version} already applied"}

        # Read the SQL
        with open(migration["path"]) as f:
            sql_script = f.read()

        if dry_run:
            return {
                "success": True,
                "dry_run": True,
                "version": version,
                "name": migration["name"],
                "sql_preview": sql_script[:500] + ("..." if len(sql_script) > 500 else ""),
            }

        # Execute migration
        start_time = datetime.now()
        logger.info(f"Applying migration {version}: {migration['name']}")
        try:
            with self.db.connect() as conn:
                cursor = conn.cursor()
                self.db.execute_script(cursor, sql_script)

                execution_time = int((datetime.now() - start_time).total_seconds() * 1000)

                placeholder = self.db.get_placeholder()
                cursor.execute(
                    f"INSERT INTO schema_migrations (version, name, checksum, execution_time_ms) VALUES ({placeholder}, {placeholder}, {placeholder}, {placeholder})",
                    (version, migration["name"], migration["checksum"], execution_time),
                )
                conn.commit()

            logger.info(f"Migration {version} applied successfully in {execution_time}ms")
            return {
                "success": True,
                "version": version,
                "name": migration["name"],
                "execution_time_ms": execution_time,
            }
        except Exception as e:
            logger.error(f"Migration {version} failed: {e}")
            return {"success": False, "version": version, "error": str(e)}

    def rollback_migration(self, version: str, dry_run: bool = False) -> dict[str, Any]:
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

        with open(down_path) as f:
            sql_script = f.read()

        if dry_run:
            return {
                "success": True,
                "dry_run": True,
                "version": version,
                "sql_preview": sql_script[:500] + ("..." if len(sql_script) > 500 else ""),
            }

        logger.info(f"Rolling back migration {version}")
        try:
            with self.db.connect() as conn:
                cursor = conn.cursor()
                self.db.execute_script(cursor, sql_script)

                placeholder = self.db.get_placeholder()
                cursor.execute(
                    f"DELETE FROM schema_migrations WHERE version = {placeholder}",
                    (version,),
                )
                conn.commit()

            logger.info(f"Migration {version} rolled back successfully")
            return {
                "success": True,
                "version": version,
                "message": f"Rolled back {version}",
            }
        except Exception as e:
            logger.error(f"Rollback of {version} failed: {e}")
            return {"success": False, "version": version, "error": str(e)}

    def create_migration(
        self, name: str, up_sql: str, down_sql: str | None = None
    ) -> dict[str, Any]:
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

        with open(up_path, "w") as f:
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
            "down_file": None,
        }

        # Create DOWN migration if provided
        if down_sql:
            down_filename = f"{version}_{safe_name}.down.sql"
            down_path = self.migrations_dir / down_filename

            with open(down_path, "w") as f:
                f.write(f"-- Rollback: {version}_{safe_name}\n")
                f.write(f"-- Created: {datetime.now().isoformat()}\n\n")
                f.write(down_sql)
                f.write("\n")

            result["down_file"] = str(down_path)

        return result
