"""
ARIA ESI Structured Logging

Provides consistent logging across the aria_esi package with:
- Environment-based configuration via ARIA_LOG_LEVEL
- Backward compatibility with ARIA_DEBUG
- JSON-formatted output option for machine parsing
- Module-specific loggers

Usage:
    from aria_esi.core.logging import get_logger

    logger = get_logger(__name__)
    logger.debug("Processing request")
    logger.info("Query completed", extra={"endpoint": "/location"})
    logger.warning("Token expiring soon")
    logger.error("Request failed", exc_info=True)

Environment Variables:
    ARIA_LOG_LEVEL: Set log level (DEBUG, INFO, WARNING, ERROR)
    ARIA_DEBUG: Legacy - if set, enables DEBUG level
    ARIA_LOG_JSON: If set, output JSON-formatted logs
"""

import json
import logging
import sys
from datetime import datetime, timezone
from typing import Any, Optional

from .config import get_settings


# Log level from environment
def _get_log_level() -> int:
    """
    Determine log level from centralized config.

    Priority:
    1. ARIA_LOG_LEVEL (explicit level name)
    2. ARIA_DEBUG (legacy, enables DEBUG)
    3. Default: WARNING
    """
    return get_settings().log_level_int


def _is_json_output() -> bool:
    """Check if JSON output is requested."""
    return get_settings().log_json


class AriaFormatter(logging.Formatter):
    """
    Custom formatter for ARIA logs.

    Formats logs with timestamp, level, module, and message.
    Supports both human-readable and JSON output.
    """

    def __init__(self, json_output: bool = False) -> None:
        super().__init__()
        self.json_output = json_output

    def format(self, record: logging.LogRecord) -> str:
        # Get timestamp in ISO format
        timestamp = datetime.now(timezone.utc).isoformat(timespec="seconds")

        if self.json_output:
            return self._format_json(record, timestamp)
        return self._format_text(record, timestamp)

    def _format_text(self, record: logging.LogRecord, timestamp: str) -> str:
        """Format as human-readable text."""
        # Extract module name (last part of dotted name)
        module = record.name.split(".")[-1] if "." in record.name else record.name

        # Base message
        msg = f"[ARIA {record.levelname}] [{module}] {record.getMessage()}"

        # Add exception info if present
        if record.exc_info:
            import traceback

            exc_text = "".join(traceback.format_exception(*record.exc_info))
            msg += f"\n{exc_text}"

        return msg

    def _format_json(self, record: logging.LogRecord, timestamp: str) -> str:
        """Format as JSON for machine parsing."""
        log_data: dict[str, Any] = {
            "timestamp": timestamp,
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        # Add any extra fields
        for key, value in record.__dict__.items():
            if key not in (
                "name",
                "msg",
                "args",
                "levelname",
                "levelno",
                "pathname",
                "filename",
                "module",
                "lineno",
                "funcName",
                "created",
                "msecs",
                "relativeCreated",
                "thread",
                "threadName",
                "processName",
                "process",
                "exc_info",
                "exc_text",
                "stack_info",
                "message",
            ):
                log_data[key] = value

        # Add exception if present
        if record.exc_info:
            import traceback

            log_data["exception"] = "".join(traceback.format_exception(*record.exc_info))

        return json.dumps(log_data)


# Module-level logger cache
_loggers: dict[str, logging.Logger] = {}
_handler: Optional[logging.Handler] = None


def _get_handler() -> logging.Handler:
    """Get or create the shared stderr handler."""
    global _handler
    if _handler is None:
        _handler = logging.StreamHandler(sys.stderr)
        _handler.setFormatter(AriaFormatter(json_output=_is_json_output()))
    return _handler


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger for the given module name.

    Args:
        name: Module name (typically __name__)

    Returns:
        Configured logger instance
    """
    if name in _loggers:
        return _loggers[name]

    logger = logging.getLogger(name)
    logger.setLevel(_get_log_level())
    logger.addHandler(_get_handler())
    logger.propagate = False  # Don't bubble up to root logger

    _loggers[name] = logger
    return logger


def set_log_level(level: int) -> None:
    """
    Dynamically set log level for all ARIA loggers.

    Args:
        level: logging.DEBUG, logging.INFO, etc.
    """
    for logger in _loggers.values():
        logger.setLevel(level)


def debug_enabled() -> bool:
    """
    Check if debug logging is enabled.

    Useful for conditional expensive operations.
    """
    return _get_log_level() <= logging.DEBUG


def reset_logging() -> None:
    """
    Reset all ARIA loggers to default state.

    This function:
    1. Restores propagate=True on all aria_esi.* loggers in Python's manager
    2. Resets logger levels to NOTSET (so they inherit from root)
    3. Removes the shared handler from cached loggers
    4. Resets the handler cache (but NOT the logger cache)

    Used by test fixtures to prevent cross-test logging pollution.

    Note: We restore propagate and reset levels on ALL aria_esi.* loggers, not just
    cached ones, because application code may use standard logging.getLogger() which
    creates loggers outside our cache. Those loggers' parents (like aria_esi) might
    have propagate=False or high levels from our get_logger(), blocking caplog capture.
    """
    global _handler

    # Restore propagate=True and level=NOTSET on ALL aria_esi.* loggers in Python's
    # logging manager. This handles loggers created by both get_logger() and standard
    # logging.getLogger(). Resetting level to NOTSET ensures child loggers properly
    # inherit from root (where caplog sets the capture level).
    manager = logging.Logger.manager
    for name in list(manager.loggerDict.keys()):
        if name.startswith("aria_esi"):
            logger_or_placeholder = manager.loggerDict[name]
            # loggerDict can contain Logger objects or PlaceHolder objects
            if isinstance(logger_or_placeholder, logging.Logger):
                logger_or_placeholder.propagate = True
                logger_or_placeholder.setLevel(logging.NOTSET)

    # Also handle the "aria_esi" logger if it exists (may not be in loggerDict yet)
    if "aria_esi" in manager.loggerDict:
        logger_or_placeholder = manager.loggerDict["aria_esi"]
        if isinstance(logger_or_placeholder, logging.Logger):
            logger_or_placeholder.propagate = True
            logger_or_placeholder.setLevel(logging.NOTSET)

    # Remove handlers from our cached loggers
    for logger in _loggers.values():
        if _handler is not None:
            logger.removeHandler(_handler)

    # Reset handler cache only (loggers stay cached to preserve propagate=True)
    _handler = None


# Convenience function for backward compatibility
def debug_log(message: str) -> None:
    """
    Legacy debug logging function.

    Deprecated: Use get_logger(__name__).debug() instead.
    """
    logger = get_logger("aria_esi")
    logger.debug(message)
