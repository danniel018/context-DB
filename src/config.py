import os

# --- CONFIGURATION ---
CONFIG = {
    "db_type": os.getenv("MCP_DB_TYPE", "sqlite"),  # "sqlite", "postgres", or "mysql"
    "db_path": os.getenv("MCP_DB_PATH", "database.db"),  # For SQLite
    "migrations_dir": os.getenv("MCP_MIGRATIONS_DIR", "./migrations"),
    # PostgreSQL/MySQL Configuration
    "db_host": os.getenv("MCP_DB_HOST", "localhost"),
    "db_port": os.getenv("MCP_DB_PORT", ""),
    "db_database": os.getenv("MCP_DB_DATABASE", ""),
    "db_user": os.getenv("MCP_DB_USER", ""),
    "db_password": os.getenv("MCP_DB_PASSWORD", ""),
}

