"""
Structured logging configuration.

Provides two formats:
  - **json**  (default in production): machine-readable structured logs.
  - **console** (default in development): human-friendly coloured output.

Usage:
    from app.core.logging import setup_logging, get_logger

    setup_logging()                   # call once at startup
    logger = get_logger(__name__)     # per-module logger
    logger.info("Processing", extra={"record_count": 42})
"""

import logging
import sys
from typing import Literal

from pythonjsonlogger import json as json_logger


LOG_FORMAT_CONSOLE = (
    "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
)

LOG_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


def setup_logging(
    level: str = "INFO",
    log_format: Literal["json", "console"] = "json",
) -> None:
    """
    Configure the root logger for the entire application.

    Args:
        level:      Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL).
        log_format: 'json' for structured JSON lines, 'console' for human-readable.
    """
    root_logger = logging.getLogger()
    root_logger.setLevel(level.upper())

    # Remove any pre-existing handlers to avoid duplicate log lines
    root_logger.handlers.clear()

    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(level.upper())

    if log_format == "json":
        formatter = _build_json_formatter()
    else:
        formatter = logging.Formatter(
            LOG_FORMAT_CONSOLE, datefmt=LOG_DATE_FORMAT)

    handler.setFormatter(formatter)
    root_logger.addHandler(handler)

    # Silence noisy third-party loggers
    for noisy in ("httpcore", "httpx", "uvicorn.access", "asyncio"):
        logging.getLogger(noisy).setLevel(logging.WARNING)

    root_logger.info(
        "Logging initialised",
        extra={"log_level": level.upper(), "log_format": log_format},
    )


def get_logger(name: str) -> logging.Logger:
    """
    Return a named logger.

    Convention: call with ``get_logger(__name__)`` in each module.
    """
    return logging.getLogger(name)


# ─── Internal ─────────────────────────────────────────────────────────


def _build_json_formatter() -> json_logger.JsonFormatter:
    """Build a JSON log formatter with standard fields."""
    return json_logger.JsonFormatter(
        fmt="%(asctime)s %(levelname)s %(name)s %(message)s",
        datefmt=LOG_DATE_FORMAT,
        rename_fields={
            "asctime": "timestamp",
            "levelname": "level",
            "name": "logger",
        },
    )
