# MCP Database Migration Server

[![MCP](https://img.shields.io/badge/MCP-Compatible-blue)](https://modelcontextprotocol.io)
[![Python](https://img.shields.io/badge/Python-3.10+-green)](https://python.org)
[![License](https://img.shields.io/badge/License-MIT-yellow)](LICENSE)

A **Model Context Protocol (MCP)** server that enables AI assistants to manage database migrations and schema operations using raw SQL. Designed for developers who want AI-powered database management directly in their workflow.

## 🎯 Features

- **Multi-Database Support**: SQLite (default), PostgreSQL, and MySQL
- **Raw SQL Migrations**: No ORM abstractions—write pure SQL
- **UP/DOWN Convention**: Standard migration pattern with rollback support
- **Drift Detection**: Checksum verification to detect modified migrations
- **Schema Inspection**: Explore tables, columns, indexes, and row counts
- **Safe Query Execution**: Read-only queries with safety guards
- **Dry Run Mode**: Preview changes before applying
- **Auto-Versioning**: Automatic version number generation for new migrations

## 📦 Installation

### Prerequisites

- Python 3.10+
- `mcp` package
- `psycopg2` (for PostgreSQL support)
- `mysql-connector-python` (for MySQL support)

### Install Dependencies

```bash
pip install mcp psycopg2-binary mysql-connector-python pydantic
```

### Clone and Setup

```bash
git clone https://github.com/danniel018/context-DB.git
cd context-DB
pip install -r requirements.txt
```

## 🚀 Quick Start

### 1. Configure Your Database

Set environment variables for your database:

**SQLite (Default):**
```bash
export MCP_DB_TYPE=sqlite
export MCP_DB_PATH=./my_database.db
export MCP_MIGRATIONS_DIR=./migrations
```

**PostgreSQL:**
```bash
export MCP_DB_TYPE=postgres
export MCP_PG_HOST=localhost
export MCP_PG_PORT=5432
export MCP_PG_DATABASE=myapp
export MCP_PG_USER=postgres
export MCP_PG_PASSWORD=yourpassword
export MCP_MIGRATIONS_DIR=./migrations
```

**MySQL:**
```bash
export MCP_DB_TYPE=mysql
export MCP_MYSQL_HOST=localhost
export MCP_MYSQL_PORT=3306
export MCP_MYSQL_DATABASE=myapp
export MCP_MYSQL_USER=root
export MCP_MYSQL_PASSWORD=yourpassword
export MCP_MIGRATIONS_DIR=./migrations
```

### 2. Run the Server

```bash
python src/mcp_db_migrate.py
```

### 3. Connect Your AI Assistant

Add to your MCP client configuration (e.g., Claude Desktop):

```json
{
  "mcpServers": {
    "db-migrate": {
      "command": "python",
      "args": ["path/to/src/mcp_db_migrate.py"],
      "env": {
        "MCP_DB_TYPE": "sqlite",
        "MCP_DB_PATH": "./database.db",
        "MCP_MIGRATIONS_DIR": "./migrations"
      }
    }
  }
}
```

## 📁 Migration File Structure

Migrations follow a simple naming convention:

```
migrations/
├── 001_initial_schema.up.sql      # Apply migration
├── 001_initial_schema.down.sql    # Rollback migration
├── 002_add_users_table.up.sql
├── 002_add_users_table.down.sql
├── 003_add_email_column.up.sql
└── 003_add_email_column.down.sql
```

### Example Migration Files

**`001_initial_schema.up.sql`:**
```sql
-- Migration: 001_initial_schema
-- Created: 2025-11-28T10:00:00

CREATE TABLE products (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    price DECIMAL(10, 2),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

**`001_initial_schema.down.sql`:**
```sql
-- Rollback: 001_initial_schema

DROP TABLE IF EXISTS products;
```

## 🛠️ Available Tools

| Tool | Description |
|------|-------------|
| `migration_status` | Get detailed status of all migrations |
| `list_pending_migrations` | List migrations not yet applied |
| `read_migration_sql` | Read the SQL content of a migration file |
| `apply_migration` | Apply a specific migration by version |
| `apply_all_pending` | Apply all pending migrations in order |
| `rollback_migration` | Rollback a specific migration |
| `rollback_last` | Rollback the most recently applied migration |
| `create_migration` | Create a new migration file with auto-version |
| `inspect_schema` | Inspect database tables and columns |
| `run_query` | Execute read-only SQL queries |
| `check_drift` | Detect if migration files were modified |

## 📚 Available Resources

Resources provide passive context for AI assistants:

| Resource URI | Description |
|--------------|-------------|
| `migrations://status` | Formatted migration status summary |
| `migrations://schema` | Current database schema as DDL |

## 💬 Example AI Conversations

### Check Migration Status
> "What's the current state of my database migrations?"

The AI will use `migration_status` to show pending and applied migrations.

### Create a New Migration
> "Create a migration to add an email column to the users table"

The AI will use `create_migration` with appropriate UP and DOWN SQL.

### Apply Migrations Safely
> "Apply all pending migrations but show me what will happen first"

The AI will use `apply_all_pending` with `dry_run=True`, then apply after confirmation.

### Inspect Schema
> "Show me the structure of the orders table"

The AI will use `inspect_schema` to display columns, types, and indexes.

### Detect Drift
> "Check if any migration files have been modified"

The AI will use `check_drift` to compare checksums.

## 🔒 Safety Features

- **Read-Only Queries**: The `run_query` tool blocks `DROP`, `DELETE`, `UPDATE`, `INSERT`, `ALTER`, `TRUNCATE`, and `CREATE` statements
- **Dry Run Mode**: Preview migrations before applying
- **Checksum Verification**: Detect when migration files are modified after being applied
- **Transaction Support**: Migrations are executed within transactions (database-dependent)

## 🗄️ Schema Tracking

The server automatically creates a `schema_migrations` table:

```sql
CREATE TABLE schema_migrations (
    version TEXT PRIMARY KEY,
    name TEXT,
    checksum TEXT,
    applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    execution_time_ms INTEGER
);
```

## ⚙️ Configuration Reference

| Environment Variable | Default | Description |
|---------------------|---------|-------------|
| `MCP_DB_TYPE` | `sqlite` | Database type: `sqlite`, `postgres`, or `mysql` |
| `MCP_DB_PATH` | `database.db` | SQLite database file path |
| `MCP_MIGRATIONS_DIR` | `./migrations` | Directory for migration files |
| `MCP_PG_HOST` | `localhost` | PostgreSQL host |
| `MCP_PG_PORT` | `5432` | PostgreSQL port |
| `MCP_PG_DATABASE` | `myapp` | PostgreSQL database name |
| `MCP_PG_USER` | `postgres` | PostgreSQL username |
| `MCP_PG_PASSWORD` | ` ` | PostgreSQL password |
| `MCP_MYSQL_HOST` | `localhost` | MySQL host |
| `MCP_MYSQL_PORT` | `3306` | MySQL port |
| `MCP_MYSQL_DATABASE` | `myapp` | MySQL database name |
| `MCP_MYSQL_USER` | `root` | MySQL username |
| `MCP_MYSQL_PASSWORD` | ` ` | MySQL password |

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin amazing-feature`)
5. Open a Pull Request

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🗺️ Roadmap

- [x] MySQL/MariaDB support
- [ ] Migration dependencies/ordering
- [ ] Seed data management
- [ ] Schema diff between environments
- [ ] Migration squashing
- [ ] CI/CD integration helpers
- [ ] Web UI for migration management

## 🙏 Acknowledgments

- [Model Context Protocol](https://modelcontextprotocol.io) - The protocol that makes this possible
- [FastMCP](https://github.com/jlowin/fastmcp) - Simplified MCP server creation

---

**Built with ❤️ for the AI-assisted development community**
