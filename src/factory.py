"""
Database Adapter Factory.
Creates the appropriate database adapter based on configuration.
"""

import logging

from adapters import DatabaseAdapter, MySQLAdapter, PostgresAdapter, SQLiteAdapter
from config import CONFIG

logger = logging.getLogger("mcp-db-migrate")


def create_adapter() -> DatabaseAdapter:
    """Create the appropriate database adapter based on configuration."""
    db_type = CONFIG["db_type"]
    logger.info(f"Initializing database adapter: {db_type}")

    if db_type == "postgres":
        logger.debug(f"Connecting to PostgreSQL at {CONFIG['db_host']}:{CONFIG['db_port']}")
        return PostgresAdapter(
            CONFIG["db_host"],
            CONFIG["db_port"],
            CONFIG["db_database"],
            CONFIG["db_user"],
            CONFIG["db_password"],
        )
    elif db_type == "mysql":
        logger.debug(f"Connecting to MySQL at {CONFIG['db_host']}:{CONFIG['db_port']}")
        return MySQLAdapter(
            CONFIG["db_host"],
            CONFIG["db_port"],
            CONFIG["db_database"],
            CONFIG["db_user"],
            CONFIG["db_password"],
        )
    else:
        logger.debug(f"Using SQLite database: {CONFIG['db_path']}")
        return SQLiteAdapter(CONFIG["db_path"])
