"""
Unit tests for configuration loading.
"""

import os
import sys
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))


def test_settings_loads_from_env():
    """Settings reads configuration from environment variables."""
    env = {
        "DB_TYPE": "sqlite",
        "DB_PATH": "/tmp/test.db",
        "DB_PORT": "5432",
        "DB_DATABASE": "testdb",
        "DB_USER": "user",
        "DB_PASSWORD": "pass",
    }
    with patch.dict(os.environ, env, clear=False):
        from config import Settings

        settings = Settings()

    assert settings.db_type == "sqlite"
    assert settings.db_path == "/tmp/test.db"
