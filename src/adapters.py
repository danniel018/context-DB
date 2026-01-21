"""
Database Adapters for MCP Database Migration Server.
Provides abstract base class and concrete implementations for SQLite, PostgreSQL, and MySQL.
"""

import sqlite3
from abc import ABC, abstractmethod
from typing import Any

import psycopg2


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
    def inspect_table(self, table: str) -> dict[str, Any]:
        """Get detailed information about a specific table."""
        pass

    @abstractmethod
    def list_tables(self) -> list[dict[str, Any]]:
        """List all tables in the database."""
        pass

    @abstractmethod
    def get_placeholder(self) -> str:
        """Return the parameter placeholder style for this database ('?' or '%s')."""
        pass

    @abstractmethod
    def execute_script(self, cursor, script: str) -> None:
        """Execute a SQL script (may contain multiple statements)."""
        pass


class SQLiteAdapter(DatabaseAdapter):
    """SQLite database adapter."""

    def __init__(self, db_path: str):
        self.db_path = db_path

    def connect(self):
        return sqlite3.connect(self.db_path)

    def get_schema(self) -> str:
        with self.connect() as conn:
            rows = conn.execute(
                "SELECT sql FROM sqlite_master WHERE type='table' AND sql IS NOT NULL"
            ).fetchall()
        return "\n\n".join([r[0] for r in rows])

    def inspect_table(self, table: str) -> dict[str, Any]:
        with self.connect() as conn:
            # Get column info
            columns = conn.execute(f"PRAGMA table_info({table})").fetchall()
            col_info = [
                {
                    "name": c[1],
                    "type": c[2],
                    "nullable": not c[3],
                    "default": c[4],
                    "primary_key": bool(c[5]),
                }
                for c in columns
            ]

            # Get row count
            row_count = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]

            # Get indexes
            indexes = conn.execute(
                "SELECT name, sql FROM sqlite_master WHERE type='index' AND tbl_name= ?", (table,)
            ).fetchall()
            idx_info = [{"name": i[0], "definition": i[1]} for i in indexes if i[1]]

        return {"table": table, "row_count": row_count, "columns": col_info, "indexes": idx_info}

    def list_tables(self) -> list[dict[str, Any]]:
        with self.connect() as conn:
            tables = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
            ).fetchall()

            result = []
            for (table_name,) in tables:
                col_count = len(conn.execute(f"PRAGMA table_info({table_name})").fetchall())
                result.append({"table_name": table_name, "column_count": col_count})
        return result

    def get_placeholder(self) -> str:
        return "?"

    def execute_script(self, cursor, script: str) -> None:
        cursor.executescript(script)


class PostgresAdapter(DatabaseAdapter):
    """PostgreSQL database adapter."""

    def __init__(self, host: str, port: str, database: str, user: str, password: str):
        self.config = {
            "host": host,
            "port": port,
            "database": database,
            "user": user,
            "password": password,
        }

    def connect(self):
        return psycopg2.connect(**self.config)

    def get_schema(self) -> str:
        # For PostgreSQL, we generate DDL from information_schema
        with self.connect() as conn, conn.cursor() as cur:
            cur.execute("""
                    SELECT table_name
                    FROM information_schema.tables
                    WHERE table_schema = 'public' AND table_type = 'BASE TABLE'
                """)
            tables = [r[0] for r in cur.fetchall()]

            ddl_statements = []
            for table in tables:
                cur.execute(
                    """
                        SELECT column_name, data_type, is_nullable, column_default
                        FROM information_schema.columns
                        WHERE table_name = %s
                        ORDER BY ordinal_position
                    """,
                    (table,),
                )
                columns = cur.fetchall()

                col_defs = []
                for col in columns:
                    col_def = f"  {col[0]} {col[1]}"
                    if col[2] == "NO":
                        col_def += " NOT NULL"
                    if col[3]:
                        col_def += f" DEFAULT {col[3]}"
                    col_defs.append(col_def)

                ddl = f"CREATE TABLE {table} (\n" + ",\n".join(col_defs) + "\n);"
                ddl_statements.append(ddl)

        return "\n\n".join(ddl_statements)

    def inspect_table(self, table: str) -> dict[str, Any]:
        from psycopg2.extras import RealDictCursor

        with self.connect() as conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
            # Get columns
            cur.execute(
                """
                    SELECT column_name, data_type, is_nullable, column_default
                    FROM information_schema.columns
                    WHERE table_name = %s
                    ORDER BY ordinal_position
                """,
                (table,),
            )
            columns = [dict(row) for row in cur.fetchall()]

            # Get row count
            cur.execute("SELECT COUNT(*) as count FROM %s", (table,))
            row_count = cur.fetchone()["count"]

            # Get indexes
            cur.execute(
                """
                    SELECT indexname as name, indexdef as definition
                    FROM pg_indexes
                    WHERE tablename = %s
                """,
                (table,),
            )
            indexes = [dict(row) for row in cur.fetchall()]

        return {"table": table, "row_count": row_count, "columns": columns, "indexes": indexes}

    def list_tables(self) -> list[dict[str, Any]]:
        from psycopg2.extras import RealDictCursor

        with self.connect() as conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
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

    def get_placeholder(self) -> str:
        return "%s"

    def execute_script(self, cursor, script: str) -> None:
        cursor.execute(script)


class MySQLAdapter(DatabaseAdapter):
    """MySQL database adapter."""

    def __init__(self, host: str, port: str, database: str, user: str, password: str):
        self.config = {
            "host": host,
            "port": int(port),
            "database": database,
            "user": user,
            "password": password,
        }

    def connect(self):
        import mysql.connector

        return mysql.connector.connect(**self.config)

    def get_schema(self) -> str:
        with self.connect() as conn:
            cursor = conn.cursor()
            cursor.execute("SHOW TABLES")
            tables = [r[0] for r in cursor.fetchall()]

            ddl_statements = []
            for table in tables:
                cursor.execute(f"SHOW CREATE TABLE `{table}`")
                result = cursor.fetchone()
                if result:
                    ddl_statements.append(result[1])

            cursor.close()
        return "\n\n".join(ddl_statements)

    def inspect_table(self, table: str) -> dict[str, Any]:
        with self.connect() as conn:
            cursor = conn.cursor(dictionary=True)

            # Get columns
            cursor.execute(
                """
                SELECT
                    COLUMN_NAME as column_name,
                    DATA_TYPE as data_type,
                    IS_NULLABLE as is_nullable,
                    COLUMN_DEFAULT as column_default,
                    COLUMN_KEY as column_key,
                    EXTRA as extra
                FROM information_schema.COLUMNS
                WHERE TABLE_SCHEMA = %s AND TABLE_NAME = %s
                ORDER BY ORDINAL_POSITION
            """,
                (self.config["database"], table),
            )
            columns = [dict(row) for row in cursor.fetchall()]

            # Get row count
            cursor.execute("SELECT COUNT(*) as count FROM %s" , (table,))
            row_count = cursor.fetchone()["count"]

            # Get indexes
            cursor.execute(
                """
                SELECT
                    INDEX_NAME as name,
                    GROUP_CONCAT(COLUMN_NAME ORDER BY SEQ_IN_INDEX) as columns,
                    NON_UNIQUE as non_unique,
                    INDEX_TYPE as index_type
                FROM information_schema.STATISTICS
                WHERE TABLE_SCHEMA = %s AND TABLE_NAME = %s
                GROUP BY INDEX_NAME, NON_UNIQUE, INDEX_TYPE
            """,
                (self.config["database"], table),
            )
            indexes = [dict(row) for row in cursor.fetchall()]

            cursor.close()

        return {"table": table, "row_count": row_count, "columns": columns, "indexes": indexes}

    def list_tables(self) -> list[dict[str, Any]]:
        with self.connect() as conn:
            cursor = conn.cursor(dictionary=True)
            cursor.execute(
                """
                SELECT
                    TABLE_NAME as table_name,
                    (SELECT COUNT(*)
                     FROM information_schema.COLUMNS c
                     WHERE c.TABLE_SCHEMA = t.TABLE_SCHEMA AND c.TABLE_NAME = t.TABLE_NAME) as column_count
                FROM information_schema.TABLES t
                WHERE t.TABLE_SCHEMA = %s AND t.TABLE_TYPE = 'BASE TABLE'
                ORDER BY t.TABLE_NAME
            """,
                (self.config["database"],),
            )
            result = [dict(row) for row in cursor.fetchall()]
            cursor.close()
        return result

    def get_placeholder(self) -> str:
        return "%s"

    def execute_script(self, cursor, script: str) -> None:
        # MySQL doesn't have executescript, so we split and execute each statement
        # Handle multi-statement scripts by splitting on semicolons
        statements = [s.strip() for s in script.split(";") if s.strip()]
        for statement in statements:
            cursor.execute(statement)
