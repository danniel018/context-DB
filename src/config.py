"""project configuration settings."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configuration settings for the MCP Database Migration Server."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")
    db_type: str  # "sqlite", "postgres", or "mysql"
    db_path: str = "database.db"  # For SQLite
    migrations_dir: str = "./migrations"
    # PostgreSQL/MySQL Configuration
    db_host: str = "localhost"
    db_port: str
    db_database: str
    db_user: str
    db_password: str


settings = Settings()
