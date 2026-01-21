"""
Logging configuration for MCP Database Migration Server.
Configures logging to stderr as required by MCP protocol.
"""

import logging
import sys


def setup_logging(level: int = logging.INFO) -> logging.Logger:
    """
    Configure logging for the MCP server.

    Args:
        level: Logging level (default: logging.INFO)

    Returns:
        Configured logger instance
    """
    logging.basicConfig(
        level=level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[logging.StreamHandler(sys.stderr)],
    )
    return logging.getLogger("mcp-db-migrate")
