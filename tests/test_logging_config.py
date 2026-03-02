"""
Unit tests for logging configuration.
"""

import logging
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from logging_config import setup_logging


def test_setup_logging_returns_logger():
    """setup_logging() returns a Logger named 'mcp-context-db'."""
    logger = setup_logging()
    assert isinstance(logger, logging.Logger)
    assert logger.name == "mcp-context-db"
