import os

# --- CONFIGURATION ---
DB_TYPE = os.getenv("MCP_DB_TYPE", "sqlite")  # "sqlite", "postgres", or "mysql"
DB_PATH = os.getenv("MCP_DB_PATH", "database.db")  # For SQLite
MIGRATIONS_DIR = os.getenv("MCP_MIGRATIONS_DIR", "./migrations")

# PostgreSQL Configuration
PG_HOST = os.getenv("MCP_PG_HOST", "localhost")
PG_PORT = os.getenv("MCP_PG_PORT", "5432")
PG_DATABASE = os.getenv("MCP_PG_DATABASE", "myapp")
PG_USER = os.getenv("MCP_PG_USER", "postgres")
PG_PASSWORD = os.getenv("MCP_PG_PASSWORD", "")

# MySQL Configuration
MYSQL_HOST = os.getenv("MCP_MYSQL_HOST", "localhost")
MYSQL_PORT = os.getenv("MCP_MYSQL_PORT", "3306")
MYSQL_DATABASE = os.getenv("MCP_MYSQL_DATABASE", "myapp")
MYSQL_USER = os.getenv("MCP_MYSQL_USER", "root")
MYSQL_PASSWORD = os.getenv("MCP_MYSQL_PASSWORD", "")

